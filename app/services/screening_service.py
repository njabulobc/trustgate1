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


@dataclass(frozen=True, slots=True)
class _ClassificationPolicyPack:
    name: str
    provider_score_weight: float
    list_quality_weight: float
    concordance_weight: float
    pep_threshold: float
    rca_threshold: float
    false_positive_score_cap: float
    minimum_topic_signal: float


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
    _CLASSIFICATION_POLICY_PACKS: dict[str, _ClassificationPolicyPack] = {
        "default": _ClassificationPolicyPack(
            name="default",
            provider_score_weight=0.45,
            list_quality_weight=0.20,
            concordance_weight=0.35,
            pep_threshold=0.67,
            rca_threshold=0.56,
            false_positive_score_cap=0.52,
            minimum_topic_signal=0.5,
        ),
        "enhanced_due_diligence": _ClassificationPolicyPack(
            name="enhanced_due_diligence",
            provider_score_weight=0.40,
            list_quality_weight=0.20,
            concordance_weight=0.40,
            pep_threshold=0.62,
            rca_threshold=0.52,
            false_positive_score_cap=0.50,
            minimum_topic_signal=0.45,
        ),
    }

    @staticmethod
    def classify_candidate(
        subject: _ScreeningSubjectContext,
        *,
        match_score: float | None,
        matched_name: str,
        list_name: str | None,
        dataset: str | None,
        country: str | None,
        candidate_payload: dict[str, Any] | None,
    ) -> tuple[MatchCategory, dict[str, Any]]:
        topics = ScreeningService._extract_topics(candidate_payload)
        policy_pack = ScreeningService._resolve_policy_pack(candidate_payload=candidate_payload, dataset=dataset)
        provider_score_signal = ScreeningService._normalize_match_score(match_score)
        list_quality_signal = ScreeningService._score_list_quality(
            topics=topics,
            dataset=dataset,
            list_name=list_name,
        )
        concordance_breakdown = ScreeningService._score_concordance(
            subject=subject,
            candidate_payload=candidate_payload,
            matched_name=matched_name,
            country=country,
        )
        concordance_signal = concordance_breakdown["score"]

        weighted_score = (
            provider_score_signal * policy_pack.provider_score_weight
            + list_quality_signal * policy_pack.list_quality_weight
            + concordance_signal * policy_pack.concordance_weight
        )

        has_pep_topic = "role.pep" in topics
        has_rca_topic = "role.rca" in topics
        candidate_type = "pep" if has_pep_topic else "rca" if has_rca_topic else "standard"

        false_positive_reduction = ScreeningService._apply_false_positive_reduction(
            policy_pack=policy_pack,
            weighted_score=weighted_score,
            provider_score_signal=provider_score_signal,
            concordance_breakdown=concordance_breakdown,
            has_policy_topic=has_pep_topic or has_rca_topic,
        )

        match_category = MatchCategory.STANDARD
        if not false_positive_reduction["applied"]:
            if has_pep_topic and list_quality_signal >= policy_pack.minimum_topic_signal and weighted_score >= policy_pack.pep_threshold:
                match_category = MatchCategory.PEP
            elif has_rca_topic and list_quality_signal >= policy_pack.minimum_topic_signal and weighted_score >= policy_pack.rca_threshold:
                match_category = MatchCategory.RCA

        explainability = [
            {
                "factor": "provider_score",
                "weight": policy_pack.provider_score_weight,
                "signal": provider_score_signal,
                "contribution": provider_score_signal * policy_pack.provider_score_weight,
            },
            {
                "factor": "list_quality",
                "weight": policy_pack.list_quality_weight,
                "signal": list_quality_signal,
                "contribution": list_quality_signal * policy_pack.list_quality_weight,
            },
            {
                "factor": "name_dob_country_concordance",
                "weight": policy_pack.concordance_weight,
                "signal": concordance_signal,
                "contribution": concordance_signal * policy_pack.concordance_weight,
                "details": concordance_breakdown,
            },
        ]

        alerts: list[dict[str, str]] = []
        if match_category == MatchCategory.PEP:
            alerts.append(
                {
                    "policy": "pep_detection",
                    "severity": "high",
                    "rationale": "Multi-factor scoring indicates a high-confidence PEP match requiring EDD and senior approval.",
                }
            )
        elif match_category == MatchCategory.RCA:
            alerts.append(
                {
                    "policy": "rca_detection",
                    "severity": "medium",
                    "rationale": "Multi-factor scoring indicates an RCA match requiring RCA-specific review controls.",
                }
            )
        elif candidate_type in {"pep", "rca"} and false_positive_reduction["applied"]:
            alerts.append(
                {
                    "policy": "false_positive_reduction",
                    "severity": "low",
                    "rationale": "Candidate contains a policy topic but was downgraded due to low-confidence identity concordance.",
                }
            )

        policy_flags = {
            "version": "candidate_policy_flags.v2",
            "policy_pack": policy_pack.name,
            "candidate_type_signal": candidate_type,
            "topics": topics,
            "signals": {
                "provider_score": provider_score_signal,
                "list_quality": list_quality_signal,
                "name_dob_country_concordance": concordance_signal,
            },
            "weights": {
                "provider_score": policy_pack.provider_score_weight,
                "list_quality": policy_pack.list_quality_weight,
                "name_dob_country_concordance": policy_pack.concordance_weight,
            },
            "thresholds": {
                "pep_threshold": policy_pack.pep_threshold,
                "rca_threshold": policy_pack.rca_threshold,
                "false_positive_score_cap": policy_pack.false_positive_score_cap,
                "minimum_topic_signal": policy_pack.minimum_topic_signal,
            },
            "weighted_score": weighted_score,
            "false_positive_reduction": false_positive_reduction,
            "classification": {
                "category": match_category.value,
                "decision_basis": "multi_factor_policy_pack",
            },
            "explainability": explainability,
            "alerts": alerts,
        }

        return match_category, policy_flags

    @staticmethod
    def _extract_topics(candidate_payload: dict[str, Any] | None) -> list[str]:
        if not isinstance(candidate_payload, dict):
            return []
        raw_topics = candidate_payload.get("topics")
        if not isinstance(raw_topics, list):
            return []
        return sorted({str(topic).lower() for topic in raw_topics if topic is not None})

    @staticmethod
    def _resolve_policy_pack(
        *,
        candidate_payload: dict[str, Any] | None,
        dataset: str | None,
    ) -> _ClassificationPolicyPack:
        policy_pack_name: str | None = None
        if isinstance(candidate_payload, dict):
            metadata = candidate_payload.get("metadata")
            if isinstance(metadata, dict):
                explicit_pack = metadata.get("policy_pack")
                if isinstance(explicit_pack, str):
                    policy_pack_name = explicit_pack.strip().lower()
        if not policy_pack_name and dataset and "pep" in dataset.lower():
            policy_pack_name = "enhanced_due_diligence"
        return ScreeningService._CLASSIFICATION_POLICY_PACKS.get(
            policy_pack_name or "default",
            ScreeningService._CLASSIFICATION_POLICY_PACKS["default"],
        )

    @staticmethod
    def _normalize_match_score(match_score: float | None) -> float:
        if match_score is None:
            return 0.0
        return max(0.0, min(float(match_score), 1.0))

    @staticmethod
    def _score_list_quality(
        *,
        topics: list[str],
        dataset: str | None,
        list_name: str | None,
    ) -> float:
        score = 0.0
        if "role.pep" in topics:
            score = max(score, 1.0)
        elif "role.rca" in topics:
            score = max(score, 0.8)

        provenance_text = " ".join(filter(None, [dataset, list_name])).lower()
        if any(keyword in provenance_text for keyword in ("pep", "sanctions", "watchlist", "public_office")):
            score = max(score, 0.75)
        return score

    @staticmethod
    def _score_concordance(
        *,
        subject: _ScreeningSubjectContext,
        candidate_payload: dict[str, Any] | None,
        matched_name: str,
        country: str | None,
    ) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        if isinstance(candidate_payload, dict):
            raw_properties = candidate_payload.get("properties")
            if isinstance(raw_properties, dict):
                properties = raw_properties

        subject_name = subject.provider_input.primary_name.strip().lower()
        matched_name_tokens = set((matched_name or "").strip().lower().split())
        subject_name_tokens = set(subject_name.split())

        name_exact = bool(subject_name and matched_name and subject_name == matched_name.strip().lower())
        shared_tokens = len(matched_name_tokens & subject_name_tokens)
        name_signal = 1.0 if name_exact else min(1.0, shared_tokens / 2) if shared_tokens else 0.0

        candidate_birth_dates = ScreeningService._extract_property_values(properties, "birthDate")
        dob_input = (subject.provider_input.date_of_birth or "").strip()
        dob_signal = 1.0 if dob_input and dob_input in candidate_birth_dates else 0.0

        candidate_countries = set(
            value.lower()
            for key in ("country", "nationality", "jurisdiction")
            for value in ScreeningService._extract_property_values(properties, key)
        )
        if country:
            candidate_countries.add(country.lower())
        subject_country = (subject.provider_input.country or subject.provider_input.nationality or "").strip().lower()
        country_signal = 1.0 if subject_country and subject_country in candidate_countries else 0.0

        score = name_signal * 0.6 + dob_signal * 0.25 + country_signal * 0.15

        return {
            "score": score,
            "name_signal": name_signal,
            "name_exact": name_exact,
            "dob_signal": dob_signal,
            "country_signal": country_signal,
            "candidate_birth_dates": candidate_birth_dates,
            "candidate_countries": sorted(candidate_countries),
        }

    @staticmethod
    def _extract_property_values(properties: dict[str, Any], key: str) -> list[str]:
        value = properties.get(key)
        if isinstance(value, list):
            return [str(entry).strip() for entry in value if entry]
        if isinstance(value, str) and value:
            return [value.strip()]
        return []

    @staticmethod
    def _apply_false_positive_reduction(
        *,
        policy_pack: _ClassificationPolicyPack,
        weighted_score: float,
        provider_score_signal: float,
        concordance_breakdown: dict[str, Any],
        has_policy_topic: bool,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        if has_policy_topic and weighted_score <= policy_pack.false_positive_score_cap:
            reasons.append("low_weighted_score_for_policy_topic")
        if provider_score_signal < 0.45:
            reasons.append("provider_score_below_floor")
        if concordance_breakdown["name_signal"] < 0.5 and concordance_breakdown["dob_signal"] == 0:
            reasons.append("weak_name_and_dob_concordance")
        if (
            has_policy_topic
            and concordance_breakdown["name_signal"] < 0.5
            and concordance_breakdown["country_signal"] == 0
        ):
            reasons.append("topic_without_identity_concordance")

        high_confidence_override = provider_score_signal >= 0.9 and (
            concordance_breakdown["name_exact"] or concordance_breakdown["dob_signal"] == 1.0
        )
        applied = bool(reasons) and not high_confidence_override
        return {
            "applied": applied,
            "rules_triggered": reasons,
            "high_confidence_override": high_confidence_override,
        }

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
                        subject,
                        match_score=candidate.match_score,
                        matched_name=candidate.matched_name,
                        list_name=candidate.list_name,
                        dataset=candidate.dataset,
                        country=candidate.country,
                        candidate_payload=candidate.candidate_payload,
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
