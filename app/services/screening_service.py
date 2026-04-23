from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.client import Client, ClientType
from app.models.deal import Deal
from app.models.edd_case import EDDCase
from app.models.linked_party import LinkedParty, LinkedPartyType
from app.models.screening import (
    ScreeningCandidate,
    ScreeningResult,
    ScreeningStatus,
    ScreeningSubjectType,
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


class ScreeningPersistenceError(ScreeningServiceError):
    """Raised when screening data cannot be persisted."""


class ScreeningExecutionError(ScreeningServiceError):
    """Raised when provider execution fails."""


class ScreeningService:
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
        return candidate

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

                has_high_confidence_match = False
                for candidate in normalized_result.candidates:
                    candidate_score = (
                        Decimal(str(candidate.match_score))
                        if candidate.match_score is not None
                        else None
                    )
                    if (
                        candidate_score is not None
                        and float(candidate_score) >= settings.SCREENING_HIGH_CONFIDENCE_SCORE
                    ):
                        has_high_confidence_match = True

                    screening_candidate = ScreeningCandidate(
                        screening_result_id=screening_result.id,
                        provider_candidate_id=candidate.provider_candidate_id,
                        provider_entity_id=candidate.provider_entity_id,
                        matched_name=candidate.matched_name,
                        match_score=candidate_score,
                        list_name=candidate.list_name,
                        dataset=candidate.dataset,
                        country=candidate.country,
                        notes=candidate.notes,
                        candidate_payload=candidate.candidate_payload,
                    )
                    db.add(screening_candidate)

                if has_high_confidence_match and subject.client_id is not None:
                    edd_case = EDDCase(
                        client_id=subject.client_id,
                        screening_result_id=screening_result.id,
                        trigger_reason="High-confidence screening match detected.",
                    )
                    db.add(edd_case)
                    db.flush()
                    record_audit_event(
                        db=db,
                        actor=actor,
                        action="edd_case.created",
                        entity_type="edd_case",
                        entity_id=edd_case.id,
                        metadata_payload={
                            "trigger_type": "high_confidence_screening_match",
                            "screening_result_id": screening_result.id,
                            "client_id": subject.client_id,
                        },
                    )

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
                    client_id=client.id,
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
