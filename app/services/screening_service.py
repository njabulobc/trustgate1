from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.client import Client, ClientType
from app.models.deal import Deal
from app.models.linked_party import LinkedParty, LinkedPartyType
from app.models.screening import (
    CandidateDisposition,
    MatchCategory,
    PepCase,
    PepCaseStatus,
    ScreeningCandidate,
    ScreeningResult,
    ScreeningStatus,
    ScreeningSubjectType,
    VerificationStatus,
)
from app.schemas.screening import CandidateDispositionUpdate
from app.services.audit_service import record_audit_event
from app.services.provider_adapter_service import (
    OpenSanctionsAdapter,
    ProviderAdapterError,
    ProviderBatchScreeningResponse,
    ScreeningSubjectInput,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class _ScreeningSubjectContext:
    subject_type: ScreeningSubjectType
    client_id: int | None
    linked_party_id: int | None
    subject_name_snapshot: str
    query_text: str
    provider_input: ScreeningSubjectInput


class ScreeningServiceError(Exception):
    """Base exception for screening service failures."""


class ScreeningNotFoundError(ScreeningServiceError):
    """Raised when a screening record cannot be found."""


class ScreeningValidationError(ScreeningServiceError):
    """Raised when screening input or entity relationships are invalid."""


class PepCaseTransitionValidationError(ScreeningValidationError):
    """Raised when a PEP case update violates transition control policies."""

    def __init__(
        self,
        *,
        message: str,
        error_code: str,
        audit_metadata: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.audit_metadata = audit_metadata


class ScreeningPersistenceError(ScreeningServiceError):
    """Raised when screening data cannot be persisted."""


class ScreeningExecutionError(ScreeningServiceError):
    """Raised when provider execution fails."""


class ScreeningService:
    _PEP_CASE_STATUS_TRANSITIONS: dict[PepCaseStatus, set[PepCaseStatus]] = {
        PepCaseStatus.OPEN: {PepCaseStatus.IN_REVIEW, PepCaseStatus.REJECTED},
        PepCaseStatus.IN_REVIEW: {
            PepCaseStatus.SENIOR_APPROVED,
            PepCaseStatus.REJECTED,
            PepCaseStatus.CLOSED,
        },
        PepCaseStatus.SENIOR_APPROVED: {PepCaseStatus.CLOSED},
        PepCaseStatus.REJECTED: {PepCaseStatus.IN_REVIEW},
        PepCaseStatus.CLOSED: set(),
    }
    _PEP_CASE_CLOSURE_STATES: set[PepCaseStatus] = {
        PepCaseStatus.REJECTED,
        PepCaseStatus.CLOSED,
    }
    _PEP_CASE_VERIFICATION_GATED_STATES: set[PepCaseStatus] = {
        PepCaseStatus.SENIOR_APPROVED,
        PepCaseStatus.CLOSED,
    }

    @staticmethod
    def classify_candidate(
        candidate_payload: dict[str, Any] | None,
    ) -> tuple[MatchCategory, dict[str, Any]]:
        topics: list[str] = []
        if isinstance(candidate_payload, dict):
            raw_topics = candidate_payload.get("topics")
            if isinstance(raw_topics, list):
                topics = [str(topic).lower() for topic in raw_topics]

        if "role.pep" in topics:
            return (
                MatchCategory.PEP,
                {
                    "alerts": [
                        {
                            "policy": "pep_detection",
                            "severity": "high",
                            "rationale": "Candidate tagged as role.pep; EDD and senior approval controls are required.",
                        }
                    ]
                },
            )
        if "role.rca" in topics:
            return (
                MatchCategory.RCA,
                {
                    "alerts": [
                        {
                            "policy": "rca_detection",
                            "severity": "medium",
                            "rationale": "Candidate tagged as role.rca; apply RCA-specific review workflow.",
                        }
                    ]
                },
            )
        return MatchCategory.STANDARD, {"alerts": []}

    @staticmethod
    async def run_screening_for_client(
        db: Session,
        client_id: int,
        *,
        deal_id: int | None = None,
        actor: str = "demo_user",
        adapter: OpenSanctionsAdapter | None = None,
    ) -> list[ScreeningResult]:
        client = ScreeningService._get_client_or_raise(db=db, client_id=client_id)
        linked_parties = ScreeningService._get_screenable_linked_parties(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )
        subjects = ScreeningService._build_subject_contexts(
            client=client,
            linked_parties=linked_parties,
        )

        provider = adapter or OpenSanctionsAdapter()

        try:
            provider_response = await provider.screen_subjects(
                subjects=[subject.provider_input for subject in subjects],
            )
        except ProviderAdapterError as exc:
            failed_results = ScreeningService._persist_failed_screening_results(
                db=db,
                subjects=subjects,
                provider_name=provider.provider_name,
                error_message=str(exc),
                provider_response=exc.provider_response,
                actor=actor,
            )
            raise ScreeningExecutionError(str(exc)) from exc

        return ScreeningService._persist_successful_screening_results(
            db=db,
            subjects=subjects,
            provider_response=provider_response,
            actor=actor,
        )

    @staticmethod
    def list_screening_results_for_client(
        db: Session,
        client_id: int,
    ) -> list[ScreeningResult]:
        ScreeningService._get_client_or_raise(db=db, client_id=client_id)

        stmt = (
            select(ScreeningResult)
            .options(selectinload(ScreeningResult.candidates))
            .outerjoin(
                LinkedParty,
                ScreeningResult.linked_party_id == LinkedParty.id,
            )
            .where(
                or_(
                    ScreeningResult.client_id == client_id,
                    LinkedParty.client_id == client_id,
                )
            )
            .order_by(ScreeningResult.screened_at.desc(), ScreeningResult.id.desc())
        )

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_screening_result(
        db: Session,
        screening_result_id: int,
    ) -> ScreeningResult:
        stmt = (
            select(ScreeningResult)
            .options(selectinload(ScreeningResult.candidates))
            .where(ScreeningResult.id == screening_result_id)
        )
        screening_result = db.execute(stmt).scalar_one_or_none()

        if screening_result is None:
            raise ScreeningNotFoundError(
                f"Screening result with id={screening_result_id} was not found."
            )

        return screening_result

    @staticmethod
    def update_candidate_disposition(
        db: Session,
        candidate_id: int,
        payload: CandidateDispositionUpdate,
        *,
        actor: str = "demo_user",
    ) -> ScreeningCandidate:
        candidate = ScreeningService._get_candidate_or_raise(
            db=db,
            candidate_id=candidate_id,
        )
        screening_result = ScreeningService.get_screening_result(
            db=db,
            screening_result_id=candidate.screening_result_id,
        )

        changed_fields: list[str] = []

        if candidate.disposition != payload.disposition:
            candidate.disposition = payload.disposition
            changed_fields.append("disposition")

        if candidate.disposition_reason != payload.disposition_reason:
            candidate.disposition_reason = payload.disposition_reason
            changed_fields.append("disposition_reason")

        review_timestamp = utcnow()

        if candidate.reviewed_at != review_timestamp:
            candidate.reviewed_at = review_timestamp
            changed_fields.append("reviewed_at")

        if screening_result.status != ScreeningStatus.REVIEWED:
            screening_result.status = ScreeningStatus.REVIEWED
            changed_fields.append("screening_result.status")

        screening_result.reviewed_at = review_timestamp

        if not changed_fields:
            return candidate

        try:
            record_audit_event(
                db=db,
                actor=actor,
                action="screening_candidate.disposition_updated",
                entity_type="screening_candidate",
                entity_id=candidate.id,
                metadata_payload={
                    "screening_result_id": candidate.screening_result_id,
                    "disposition": candidate.disposition.value,
                    "subject_type": screening_result.subject_type.value,
                    "client_id": screening_result.client_id,
                    "linked_party_id": screening_result.linked_party_id,
                },
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ScreeningPersistenceError(
                "Unable to update candidate disposition because the data violates a persistence constraint."
            ) from exc
        except Exception:
            db.rollback()
            raise

        db.refresh(candidate)
        if candidate.match_category in (MatchCategory.PEP, MatchCategory.RCA) and payload.disposition in (
            CandidateDisposition.CONFIRMED_MATCH,
            CandidateDisposition.NEEDS_EDD,
        ):
            ScreeningService.ensure_pep_case(
                db=db,
                screening_candidate_id=candidate.id,
                actor=actor,
            )
        return candidate

    @staticmethod
    def ensure_pep_case(
        db: Session,
        screening_candidate_id: int,
        *,
        actor: str = "demo_user",
    ) -> PepCase:
        candidate = ScreeningService._get_candidate_or_raise(
            db=db,
            candidate_id=screening_candidate_id,
        )
        if candidate.match_category not in (MatchCategory.PEP, MatchCategory.RCA):
            raise ScreeningValidationError(
                "PEP case management is only available for PEP/RCA candidates."
            )

        stmt = select(PepCase).where(PepCase.screening_candidate_id == screening_candidate_id)
        pep_case = db.execute(stmt).scalar_one_or_none()
        if pep_case is not None:
            return pep_case

        pep_case = PepCase(
            screening_candidate_id=screening_candidate_id,
            status=PepCaseStatus.IN_REVIEW,
            senior_approval_status=VerificationStatus.PENDING,
            source_of_wealth_status=VerificationStatus.PENDING,
            source_of_funds_status=VerificationStatus.PENDING,
            enhanced_monitoring=True,
        )
        db.add(pep_case)
        try:
            db.flush()
            record_audit_event(
                db=db,
                actor=actor,
                action="pep_case.created",
                entity_type="pep_case",
                entity_id=pep_case.id,
                metadata_payload={
                    "screening_candidate_id": screening_candidate_id,
                    "match_category": candidate.match_category.value,
                },
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ScreeningPersistenceError("Unable to persist pep case.") from exc
        except Exception:
            db.rollback()
            raise
        db.refresh(pep_case)
        return pep_case

    @staticmethod
    def update_pep_case(
        db: Session,
        pep_case_id: int,
        *,
        status: PepCaseStatus | None = None,
        senior_approval_status: VerificationStatus | None = None,
        source_of_wealth_status: VerificationStatus | None = None,
        source_of_funds_status: VerificationStatus | None = None,
        enhanced_monitoring: bool | None = None,
        monitoring_notes: str | None = None,
        closure_evidence: dict[str, Any] | None = None,
        actor: str = "demo_user",
    ) -> PepCase:
        stmt = select(PepCase).where(PepCase.id == pep_case_id)
        pep_case = db.execute(stmt).scalar_one_or_none()
        if pep_case is None:
            raise ScreeningNotFoundError(f"PEP case with id={pep_case_id} was not found.")

        current_status = pep_case.status
        proposed_status = status if status is not None else pep_case.status
        proposed_senior_approval_status = (
            senior_approval_status
            if senior_approval_status is not None
            else pep_case.senior_approval_status
        )
        proposed_source_of_wealth_status = (
            source_of_wealth_status
            if source_of_wealth_status is not None
            else pep_case.source_of_wealth_status
        )
        proposed_source_of_funds_status = (
            source_of_funds_status
            if source_of_funds_status is not None
            else pep_case.source_of_funds_status
        )
        proposed_closure_evidence = (
            closure_evidence if closure_evidence is not None else pep_case.closure_evidence
        )

        transition_audit_context = {
            "previous_status": current_status.value,
            "requested_status": proposed_status.value,
            "proposed_senior_approval_status": proposed_senior_approval_status.value,
            "proposed_source_of_wealth_status": proposed_source_of_wealth_status.value,
            "proposed_source_of_funds_status": proposed_source_of_funds_status.value,
            "closure_evidence_present": bool(proposed_closure_evidence),
        }

        if proposed_status != current_status:
            allowed_statuses = ScreeningService._PEP_CASE_STATUS_TRANSITIONS.get(
                current_status,
                set(),
            )
            if proposed_status not in allowed_statuses:
                failure_metadata = {
                    **transition_audit_context,
                    "allowed_next_statuses": sorted(
                        allowed_status.value for allowed_status in allowed_statuses
                    ),
                    "validation_error_code": "invalid_status_transition",
                }
                record_audit_event(
                    db=db,
                    actor=actor,
                    action="pep_case.update_rejected",
                    entity_type="pep_case",
                    entity_id=pep_case.id,
                    metadata_payload=failure_metadata,
                )
                db.commit()
                raise PepCaseTransitionValidationError(
                    message=(
                        f"Cannot transition PEP case from '{current_status.value}' "
                        f"to '{proposed_status.value}'."
                    ),
                    error_code="invalid_status_transition",
                    audit_metadata=failure_metadata,
                )

        if proposed_status in ScreeningService._PEP_CASE_VERIFICATION_GATED_STATES and (
            proposed_senior_approval_status != VerificationStatus.VERIFIED
            or proposed_source_of_wealth_status != VerificationStatus.VERIFIED
            or proposed_source_of_funds_status != VerificationStatus.VERIFIED
        ):
            failure_metadata = {
                **transition_audit_context,
                "validation_error_code": "verification_controls_not_satisfied",
            }
            record_audit_event(
                db=db,
                actor=actor,
                action="pep_case.update_rejected",
                entity_type="pep_case",
                entity_id=pep_case.id,
                metadata_payload=failure_metadata,
            )
            db.commit()
            raise PepCaseTransitionValidationError(
                message=(
                    "Cannot move a PEP case to 'senior_approved' or 'closed' until senior "
                    "approval, source of wealth, and source of funds are verified."
                ),
                error_code="verification_controls_not_satisfied",
                audit_metadata=failure_metadata,
            )

        if (
            proposed_status in ScreeningService._PEP_CASE_CLOSURE_STATES
            and not proposed_closure_evidence
        ):
            failure_metadata = {
                **transition_audit_context,
                "validation_error_code": "closure_evidence_required",
            }
            record_audit_event(
                db=db,
                actor=actor,
                action="pep_case.update_rejected",
                entity_type="pep_case",
                entity_id=pep_case.id,
                metadata_payload=failure_metadata,
            )
            db.commit()
            raise PepCaseTransitionValidationError(
                message=(
                    "Cannot move a PEP case into a closure state without closure evidence."
                ),
                error_code="closure_evidence_required",
                audit_metadata=failure_metadata,
            )

        if status is not None:
            pep_case.status = status
        if senior_approval_status is not None:
            pep_case.senior_approval_status = senior_approval_status
        if source_of_wealth_status is not None:
            pep_case.source_of_wealth_status = source_of_wealth_status
        if source_of_funds_status is not None:
            pep_case.source_of_funds_status = source_of_funds_status
        if enhanced_monitoring is not None:
            pep_case.enhanced_monitoring = enhanced_monitoring
        if monitoring_notes is not None:
            pep_case.monitoring_notes = monitoring_notes
        if closure_evidence is not None:
            pep_case.closure_evidence = closure_evidence
        pep_case.reviewed_at = utcnow()

        try:
            record_audit_event(
                db=db,
                actor=actor,
                action="pep_case.updated",
                entity_type="pep_case",
                entity_id=pep_case.id,
                metadata_payload={"status": pep_case.status.value},
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ScreeningPersistenceError("Unable to update pep case.") from exc
        except Exception:
            db.rollback()
            raise
        db.refresh(pep_case)
        return pep_case

    @staticmethod
    def list_pep_cases_for_client(db: Session, client_id: int) -> list[PepCase]:
        ScreeningService._get_client_or_raise(db=db, client_id=client_id)
        stmt = (
            select(PepCase)
            .join(ScreeningCandidate, PepCase.screening_candidate_id == ScreeningCandidate.id)
            .join(ScreeningResult, ScreeningCandidate.screening_result_id == ScreeningResult.id)
            .outerjoin(LinkedParty, ScreeningResult.linked_party_id == LinkedParty.id)
            .where(or_(ScreeningResult.client_id == client_id, LinkedParty.client_id == client_id))
            .order_by(PepCase.updated_at.desc(), PepCase.id.desc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def _persist_successful_screening_results(
        db: Session,
        *,
        subjects: list[_ScreeningSubjectContext],
        provider_response: ProviderBatchScreeningResponse,
        actor: str,
    ) -> list[ScreeningResult]:
        results_by_query_id = {
            result.query_id: result for result in provider_response.results
        }
        request_queries = provider_response.request_payload.get("queries", {})
        response_queries = provider_response.response_payload.get("responses", {})

        persisted_results: list[ScreeningResult] = []

        try:
            for subject in subjects:
                normalized_result = results_by_query_id.get(subject.provider_input.query_id)
                if normalized_result is None:
                    raise ScreeningExecutionError(
                        f"Provider response is missing query_id '{subject.provider_input.query_id}'."
                    )

                screening_result = ScreeningResult(
                    subject_type=subject.subject_type,
                    client_id=subject.client_id,
                    linked_party_id=subject.linked_party_id,
                    provider_name=provider_response.provider_name,
                    status=ScreeningStatus.COMPLETED,
                    subject_name_snapshot=subject.subject_name_snapshot,
                    query_text=subject.query_text,
                    request_payload={
                        "query_id": subject.provider_input.query_id,
                        "query": request_queries.get(subject.provider_input.query_id),
                    },
                    response_payload={
                        "query_id": subject.provider_input.query_id,
                        "response": response_queries.get(subject.provider_input.query_id),
                    },
                    error_message=None,
                )
                db.add(screening_result)
                db.flush()

                for candidate in normalized_result.candidates:
                    match_category, policy_flags = ScreeningService.classify_candidate(
                        candidate.candidate_payload
                    )
                    screening_candidate = ScreeningCandidate(
                        screening_result_id=screening_result.id,
                        provider_candidate_id=candidate.provider_candidate_id,
                        provider_entity_id=candidate.provider_entity_id,
                        matched_name=candidate.matched_name,
                        match_score=(
                            Decimal(str(candidate.match_score))
                            if candidate.match_score is not None
                            else None
                        ),
                        dataset=candidate.dataset,
                        country=candidate.country,
                        notes=candidate.notes,
                        match_category=match_category,
                        policy_flags=policy_flags,
                        candidate_payload=candidate.candidate_payload,
                    )
                    db.add(screening_candidate)

                record_audit_event(
                    db=db,
                    actor=actor,
                    action="screening.run.completed",
                    entity_type="screening_result",
                    entity_id=screening_result.id,
                    metadata_payload={
                        "subject_type": screening_result.subject_type.value,
                        "client_id": screening_result.client_id,
                        "linked_party_id": screening_result.linked_party_id,
                        "provider_name": screening_result.provider_name,
                        "candidate_count": len(normalized_result.candidates),
                    },
                )

                persisted_results.append(screening_result)

            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ScreeningPersistenceError(
                "Unable to persist screening results because the data violates a persistence constraint."
            ) from exc
        except Exception:
            db.rollback()
            raise

        for screening_result in persisted_results:
            db.refresh(screening_result)

        return persisted_results

    @staticmethod
    def _persist_failed_screening_results(
        db: Session,
        *,
        subjects: list[_ScreeningSubjectContext],
        provider_name: str,
        error_message: str,
        provider_response: Any,
        actor: str,
    ) -> list[ScreeningResult]:
        failed_results: list[ScreeningResult] = []

        try:
            for subject in subjects:
                screening_result = ScreeningResult(
                    subject_type=subject.subject_type,
                    client_id=subject.client_id,
                    linked_party_id=subject.linked_party_id,
                    provider_name=provider_name,
                    status=ScreeningStatus.FAILED,
                    subject_name_snapshot=subject.subject_name_snapshot,
                    query_text=subject.query_text,
                    request_payload=None,
                    response_payload={"provider_response": provider_response}
                    if provider_response is not None
                    else None,
                    error_message=error_message,
                )
                db.add(screening_result)
                db.flush()

                record_audit_event(
                    db=db,
                    actor=actor,
                    action="screening.run.failed",
                    entity_type="screening_result",
                    entity_id=screening_result.id,
                    metadata_payload={
                        "subject_type": screening_result.subject_type.value,
                        "client_id": screening_result.client_id,
                        "linked_party_id": screening_result.linked_party_id,
                        "provider_name": screening_result.provider_name,
                        "error_message": error_message,
                    },
                )

                failed_results.append(screening_result)

            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ScreeningPersistenceError(
                "Unable to persist failed screening results because the data violates a persistence constraint."
            ) from exc
        except Exception:
            db.rollback()
            raise

        for screening_result in failed_results:
            db.refresh(screening_result)

        return failed_results

    @staticmethod
    def _build_subject_contexts(
        *,
        client: Client,
        linked_parties: list[LinkedParty],
    ) -> list[_ScreeningSubjectContext]:
        subjects: list[_ScreeningSubjectContext] = [
            _ScreeningSubjectContext(
                subject_type=ScreeningSubjectType.CLIENT,
                client_id=client.id,
                linked_party_id=None,
                subject_name_snapshot=client.primary_name,
                query_text=client.primary_name,
                provider_input=ScreeningService._build_client_subject_input(client),
            )
        ]

        for linked_party in linked_parties:
            subjects.append(
                _ScreeningSubjectContext(
                    subject_type=ScreeningSubjectType.LINKED_PARTY,
                    client_id=None,
                    linked_party_id=linked_party.id,
                    subject_name_snapshot=linked_party.primary_name,
                    query_text=linked_party.primary_name,
                    provider_input=ScreeningService._build_linked_party_subject_input(
                        linked_party
                    ),
                )
            )

        return subjects

    @staticmethod
    def _build_client_subject_input(client: Client) -> ScreeningSubjectInput:
        subject_kind = (
            "individual"
            if client.client_type == ClientType.INDIVIDUAL
            else "company"
        )

        return ScreeningSubjectInput(
            query_id=f"client_{client.id}",
            subject_kind=subject_kind,
            primary_name=client.primary_name,
            date_of_birth=ScreeningService._to_iso_date(client.date_of_birth),
            nationality=client.nationality,
            country=client.country_of_incorporation,
            national_id_number=client.national_id_number,
            registration_number=client.registration_number,
            address=client.address,
        )

    @staticmethod
    def _build_linked_party_subject_input(
        linked_party: LinkedParty,
    ) -> ScreeningSubjectInput:
        subject_kind = (
            "individual"
            if linked_party.party_type == LinkedPartyType.INDIVIDUAL
            else "company"
        )

        return ScreeningSubjectInput(
            query_id=f"linked_party_{linked_party.id}",
            subject_kind=subject_kind,
            primary_name=linked_party.primary_name,
            date_of_birth=ScreeningService._to_iso_date(linked_party.date_of_birth),
            nationality=linked_party.nationality,
            country=linked_party.country_of_incorporation,
            national_id_number=linked_party.national_id_number,
            registration_number=linked_party.registration_number,
            address=linked_party.address,
        )

    @staticmethod
    def _get_screenable_linked_parties(
        db: Session,
        *,
        client_id: int,
        deal_id: int | None = None,
    ) -> list[LinkedParty]:
        if deal_id is not None:
            deal = ScreeningService._get_deal_or_raise(db=db, deal_id=deal_id)
            if deal.client_id != client_id:
                raise ScreeningValidationError(
                    f"Deal with id={deal_id} does not belong to client id={client_id}."
                )

        stmt = select(LinkedParty).where(
            LinkedParty.client_id == client_id,
            LinkedParty.screening_required.is_(True),
        )

        if deal_id is not None:
            stmt = stmt.where(LinkedParty.deal_id == deal_id)

        stmt = stmt.order_by(LinkedParty.created_at.asc(), LinkedParty.id.asc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def _get_client_or_raise(db: Session, client_id: int) -> Client:
        stmt = select(Client).where(Client.id == client_id)
        client = db.execute(stmt).scalar_one_or_none()

        if client is None:
            raise ScreeningValidationError(
                f"Client with id={client_id} was not found."
            )

        return client

    @staticmethod
    def _get_deal_or_raise(db: Session, deal_id: int) -> Deal:
        stmt = select(Deal).where(Deal.id == deal_id)
        deal = db.execute(stmt).scalar_one_or_none()

        if deal is None:
            raise ScreeningValidationError(f"Deal with id={deal_id} was not found.")

        return deal

    @staticmethod
    def _get_candidate_or_raise(db: Session, candidate_id: int) -> ScreeningCandidate:
        stmt = select(ScreeningCandidate).where(ScreeningCandidate.id == candidate_id)
        candidate = db.execute(stmt).scalar_one_or_none()

        if candidate is None:
            raise ScreeningNotFoundError(
                f"Screening candidate with id={candidate_id} was not found."
            )

        return candidate

    @staticmethod
    def _to_iso_date(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.date().isoformat()


async def run_screening_for_client(
    db: Session,
    client_id: int,
    *,
    deal_id: int | None = None,
    actor: str = "demo_user",
    adapter: OpenSanctionsAdapter | None = None,
) -> list[ScreeningResult]:
    return await ScreeningService.run_screening_for_client(
        db=db,
        client_id=client_id,
        deal_id=deal_id,
        actor=actor,
        adapter=adapter,
    )


def list_screening_results_for_client(
    db: Session,
    client_id: int,
) -> list[ScreeningResult]:
    return ScreeningService.list_screening_results_for_client(
        db=db,
        client_id=client_id,
    )


def get_screening_result(
    db: Session,
    screening_result_id: int,
) -> ScreeningResult:
    return ScreeningService.get_screening_result(
        db=db,
        screening_result_id=screening_result_id,
    )


def update_candidate_disposition(
    db: Session,
    candidate_id: int,
    payload: CandidateDispositionUpdate,
    *,
    actor: str = "demo_user",
) -> ScreeningCandidate:
    return ScreeningService.update_candidate_disposition(
        db=db,
        candidate_id=candidate_id,
        payload=payload,
        actor=actor,
    )


def ensure_pep_case(
    db: Session,
    screening_candidate_id: int,
    *,
    actor: str = "demo_user",
) -> PepCase:
    return ScreeningService.ensure_pep_case(
        db=db,
        screening_candidate_id=screening_candidate_id,
        actor=actor,
    )


def update_pep_case(
    db: Session,
    pep_case_id: int,
    *,
    status: PepCaseStatus | None = None,
    senior_approval_status: VerificationStatus | None = None,
    source_of_wealth_status: VerificationStatus | None = None,
    source_of_funds_status: VerificationStatus | None = None,
    enhanced_monitoring: bool | None = None,
    monitoring_notes: str | None = None,
    closure_evidence: dict[str, Any] | None = None,
    actor: str = "demo_user",
) -> PepCase:
    return ScreeningService.update_pep_case(
        db=db,
        pep_case_id=pep_case_id,
        status=status,
        senior_approval_status=senior_approval_status,
        source_of_wealth_status=source_of_wealth_status,
        source_of_funds_status=source_of_funds_status,
        enhanced_monitoring=enhanced_monitoring,
        monitoring_notes=monitoring_notes,
        closure_evidence=closure_evidence,
        actor=actor,
    )


def list_pep_cases_for_client(
    db: Session,
    client_id: int,
) -> list[PepCase]:
    return ScreeningService.list_pep_cases_for_client(
        db=db,
        client_id=client_id,
    )
