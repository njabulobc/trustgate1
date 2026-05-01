from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client, ClientType
from app.models.deal import Deal
from app.models.linked_party import LinkedParty, LinkedPartyRole
from app.models.platform import (
    AlertSeverity,
    AlertStatus,
    BeneficialOwnershipRecord,
    CddWorkflow,
    DocumentLifecycleStatus,
    KycDocument,
    KycProfile,
    MonitoringAlert,
    ReviewDecision,
)
from app.models.risk_assessment import RiskAssessment, RiskLevel
from app.models.screening import (
    CandidateDisposition,
    MatchCategory,
    ScreeningCandidate,
    ScreeningResult,
    ScreeningSubjectType,
)
from app.services.audit_service import record_audit_event


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class RiskScoringRules:
    confirmed_primary_client_match_score: Decimal = Decimal("50.00")
    confirmed_linked_party_match_score: Decimal = Decimal("25.00")
    high_value_transaction_score: Decimal = Decimal("15.00")
    cross_border_transaction_score: Decimal = Decimal("10.00")
    unknown_beneficial_ownership_score: Decimal = Decimal("20.00")
    pep_or_rca_exposure_score: Decimal = Decimal("15.00")
    sanctions_exposure_score: Decimal = Decimal("20.00")
    cash_transaction_score: Decimal = Decimal("10.00")
    weak_source_of_funds_score: Decimal = Decimal("12.00")
    weak_source_of_wealth_score: Decimal = Decimal("10.00")
    incomplete_documents_score: Decimal = Decimal("10.00")
    expired_documents_score: Decimal = Decimal("10.00")
    ownership_complexity_score: Decimal = Decimal("15.00")
    repeated_alert_score: Decimal = Decimal("10.00")
    jurisdictional_risk_score: Decimal = Decimal("8.00")

    high_value_transaction_threshold: Decimal = Decimal("500000.00")
    repeated_alert_threshold: int = 2
    ownership_complexity_threshold: Decimal = Decimal("70.00")

    medium_risk_threshold: Decimal = Decimal("20.00")
    high_risk_threshold: Decimal = Decimal("55.00")


class RiskServiceError(Exception):
    """Base exception for risk service failures."""


class RiskAssessmentNotFoundError(RiskServiceError):
    """Raised when a risk assessment cannot be found."""


class RiskValidationError(RiskServiceError):
    """Raised when risk input or entity relationships are invalid."""


class RiskPersistenceError(RiskServiceError):
    """Raised when a risk assessment cannot be persisted."""


class RiskService:
    RULES = RiskScoringRules()

    @classmethod
    def assess_risk(
        cls,
        db: Session,
        client_id: int,
        *,
        deal_id: int | None = None,
        actor: str = "demo_user",
    ) -> RiskAssessment:
        client = cls._get_client_or_raise(db=db, client_id=client_id)
        deal = cls._resolve_deal_context(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )

        primary_client_confirmed_count = cls._count_confirmed_primary_client_matches(
            db=db,
            client_id=client.id,
        )
        linked_party_confirmed_count = cls._count_confirmed_linked_party_matches(
            db=db,
            client_id=client.id,
            deal_id=deal.id if deal is not None else None,
        )
        unknown_beneficial_ownership = cls._has_unknown_beneficial_ownership(
            db=db,
            client=client,
            deal_id=deal.id if deal is not None else None,
        )
        profile = cls._get_kyc_profile(db=db, client_id=client.id)
        cdd_workflow = cls._get_cdd_workflow(
            db=db,
            client_id=client.id,
            deal_id=deal.id if deal is not None else None,
        )
        document_snapshot = cls._get_document_snapshot(db=db, client_id=client.id)
        ownership_snapshot = cls._get_ownership_snapshot(
            db=db,
            client_id=client.id,
            deal_id=deal.id if deal is not None else None,
        )
        alert_snapshot = cls._get_alert_snapshot(db=db, client_id=client.id)
        screening_snapshot = cls._get_screening_snapshot(db=db, client_id=client.id)

        factor_breakdown, total_score = cls._build_factor_breakdown(
            client=client,
            deal=deal,
            primary_client_confirmed_count=primary_client_confirmed_count,
            linked_party_confirmed_count=linked_party_confirmed_count,
            unknown_beneficial_ownership=unknown_beneficial_ownership,
            profile=profile,
            cdd_workflow=cdd_workflow,
            document_snapshot=document_snapshot,
            ownership_snapshot=ownership_snapshot,
            alert_snapshot=alert_snapshot,
            screening_snapshot=screening_snapshot,
        )
        factor_breakdown = cls._normalize_json_value(factor_breakdown)
        risk_level = cls._determine_risk_level(total_score)
        summary = cls._build_summary(
            client=client,
            deal=deal,
            risk_level=risk_level,
            total_score=total_score,
            factor_breakdown=factor_breakdown,
        )

        assessment = cls._get_latest_assessment_for_context(
            db=db,
            client_id=client.id,
            deal_id=deal.id if deal is not None else None,
        )
        is_created = assessment is None

        if assessment is None:
            assessment = RiskAssessment(
                client_id=client.id,
                deal_id=deal.id if deal is not None else None,
                total_score=total_score,
                risk_level=risk_level,
                factor_breakdown=factor_breakdown,
                summary=summary,
                assessed_at=utcnow(),
                is_system_generated=True,
            )
            db.add(assessment)
        else:
            assessment.total_score = total_score
            assessment.risk_level = risk_level
            assessment.factor_breakdown = factor_breakdown
            assessment.summary = summary
            assessment.assessed_at = utcnow()
            assessment.is_system_generated = True

        try:
            db.flush()

            record_audit_event(
                db=db,
                actor=actor,
                action="risk_assessment.created" if is_created else "risk_assessment.updated",
                entity_type="risk_assessment",
                entity_id=assessment.id,
                metadata_payload={
                    "client_id": assessment.client_id,
                    "deal_id": assessment.deal_id,
                    "total_score": float(total_score),
                    "risk_level": risk_level.value,
                    "triggered_factors": factor_breakdown["triggered_factors"],
                },
            )

            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise RiskPersistenceError(
                "Unable to persist risk assessment because the data violates a persistence constraint."
            ) from exc
        except Exception:
            db.rollback()
            raise

        db.refresh(assessment)
        return assessment

    @staticmethod
    def get_risk_assessment(
        db: Session,
        risk_assessment_id: int,
    ) -> RiskAssessment:
        stmt = select(RiskAssessment).where(RiskAssessment.id == risk_assessment_id)
        assessment = db.execute(stmt).scalar_one_or_none()

        if assessment is None:
            raise RiskAssessmentNotFoundError(
                f"Risk assessment with id={risk_assessment_id} was not found."
            )

        return assessment

    @classmethod
    def get_latest_risk_assessment(
        cls,
        db: Session,
        client_id: int,
        *,
        deal_id: int | None = None,
    ) -> RiskAssessment:
        cls._get_client_or_raise(db=db, client_id=client_id)
        if deal_id is not None:
            cls._resolve_deal_context(db=db, client_id=client_id, deal_id=deal_id)

        assessment = cls._get_latest_assessment_for_context(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )
        if assessment is None:
            raise RiskAssessmentNotFoundError(
                f"No risk assessment was found for client id={client_id} and deal id={deal_id}."
            )

        return assessment

    @classmethod
    def _build_factor_breakdown(
        cls,
        *,
        client: Client,
        deal: Deal | None,
        primary_client_confirmed_count: int,
        linked_party_confirmed_count: int,
        unknown_beneficial_ownership: bool,
        profile: KycProfile | None,
        cdd_workflow: CddWorkflow | None,
        document_snapshot: dict[str, Any],
        ownership_snapshot: dict[str, Any],
        alert_snapshot: dict[str, Any],
        screening_snapshot: dict[str, Any],
    ) -> tuple[dict[str, Any], Decimal]:
        total_score = Decimal("0.00")
        triggered_factors: list[str] = []

        confirmed_primary_client_match_triggered = primary_client_confirmed_count > 0
        confirmed_linked_party_match_triggered = linked_party_confirmed_count > 0
        high_value_transaction_triggered = (
            deal is not None
            and deal.transaction_value >= cls.RULES.high_value_transaction_threshold
        )
        cross_border_transaction_triggered = (
            (deal is not None and deal.is_cross_border is True)
            or (profile is not None and profile.cross_border_indicator is True)
        )
        pep_or_rca_exposure_triggered = screening_snapshot["pep_or_rca_count"] > 0 or (profile.pep_declaration if profile is not None else False)
        sanctions_exposure_triggered = screening_snapshot["sanctions_count"] > 0
        cash_transaction_triggered = bool(cdd_workflow and cdd_workflow.payment_method_review and "cash" in cdd_workflow.payment_method_review.lower())
        weak_source_of_funds_triggered = bool(cdd_workflow and cdd_workflow.source_of_funds_status in {ReviewDecision.REJECTED, ReviewDecision.ESCALATED, ReviewDecision.PENDING})
        weak_source_of_wealth_triggered = bool(cdd_workflow and cdd_workflow.source_of_wealth_status in {ReviewDecision.REJECTED, ReviewDecision.ESCALATED, ReviewDecision.PENDING})
        incomplete_documents_triggered = document_snapshot["missing_count"] > 0
        expired_documents_triggered = document_snapshot["expired_count"] > 0
        ownership_complexity_triggered = ownership_snapshot["max_complexity_score"] >= cls.RULES.ownership_complexity_threshold
        repeated_alert_triggered = alert_snapshot["open_count"] >= cls.RULES.repeated_alert_threshold
        jurisdictional_risk_triggered = bool(
            (client.nationality and client.nationality.lower() not in {"zimbabwe", "botswana", "zambia", "namibia", "south africa"})
            or (profile is not None and profile.residency_status and "non" in profile.residency_status.lower())
        )

        if confirmed_primary_client_match_triggered:
            total_score += cls.RULES.confirmed_primary_client_match_score
            triggered_factors.append("confirmed_primary_client_match")

        if confirmed_linked_party_match_triggered:
            total_score += cls.RULES.confirmed_linked_party_match_score
            triggered_factors.append("confirmed_linked_party_match")

        if high_value_transaction_triggered:
            total_score += cls.RULES.high_value_transaction_score
            triggered_factors.append("high_value_transaction")

        if cross_border_transaction_triggered:
            total_score += cls.RULES.cross_border_transaction_score
            triggered_factors.append("cross_border_transaction")

        if unknown_beneficial_ownership:
            total_score += cls.RULES.unknown_beneficial_ownership_score
            triggered_factors.append("unknown_beneficial_ownership")

        if pep_or_rca_exposure_triggered:
            total_score += cls.RULES.pep_or_rca_exposure_score
            triggered_factors.append("pep_or_rca_exposure")

        if sanctions_exposure_triggered:
            total_score += cls.RULES.sanctions_exposure_score
            triggered_factors.append("sanctions_exposure")

        if cash_transaction_triggered:
            total_score += cls.RULES.cash_transaction_score
            triggered_factors.append("cash_transaction")

        if weak_source_of_funds_triggered:
            total_score += cls.RULES.weak_source_of_funds_score
            triggered_factors.append("weak_source_of_funds")

        if weak_source_of_wealth_triggered:
            total_score += cls.RULES.weak_source_of_wealth_score
            triggered_factors.append("weak_source_of_wealth")

        if incomplete_documents_triggered:
            total_score += cls.RULES.incomplete_documents_score
            triggered_factors.append("incomplete_documents")

        if expired_documents_triggered:
            total_score += cls.RULES.expired_documents_score
            triggered_factors.append("expired_documents")

        if ownership_complexity_triggered:
            total_score += cls.RULES.ownership_complexity_score
            triggered_factors.append("ownership_complexity")

        if repeated_alert_triggered:
            total_score += cls.RULES.repeated_alert_score
            triggered_factors.append("repeated_alerts")

        if jurisdictional_risk_triggered:
            total_score += cls.RULES.jurisdictional_risk_score
            triggered_factors.append("jurisdictional_risk")

        total_score = cls._normalize_decimal(total_score)

        factor_breakdown: dict[str, Any] = {
            "rules_version": "mvp_v1",
            "thresholds": {
                "high_value_transaction_threshold": float(
                    cls.RULES.high_value_transaction_threshold
                ),
                "medium_risk_threshold": float(cls.RULES.medium_risk_threshold),
                "high_risk_threshold": float(cls.RULES.high_risk_threshold),
            },
            "context": {
                "client_id": client.id,
                "deal_id": deal.id if deal is not None else None,
                "client_type": client.client_type.value,
            },
            "factors": {
                "confirmed_primary_client_match": {
                    "triggered": confirmed_primary_client_match_triggered,
                    "score": float(
                        cls.RULES.confirmed_primary_client_match_score
                        if confirmed_primary_client_match_triggered
                        else Decimal("0.00")
                    ),
                    "details": {
                        "confirmed_candidate_count": primary_client_confirmed_count,
                    },
                },
                "confirmed_linked_party_match": {
                    "triggered": confirmed_linked_party_match_triggered,
                    "score": float(
                        cls.RULES.confirmed_linked_party_match_score
                        if confirmed_linked_party_match_triggered
                        else Decimal("0.00")
                    ),
                    "details": {
                        "confirmed_candidate_count": linked_party_confirmed_count,
                    },
                },
                "high_value_transaction": {
                    "triggered": high_value_transaction_triggered,
                    "score": float(
                        cls.RULES.high_value_transaction_score
                        if high_value_transaction_triggered
                        else Decimal("0.00")
                    ),
                    "details": {
                        "transaction_value": float(deal.transaction_value)
                        if deal is not None
                        else None,
                        "currency": deal.currency if deal is not None else None,
                    },
                },
                "cross_border_transaction": {
                    "triggered": cross_border_transaction_triggered,
                    "score": float(
                        cls.RULES.cross_border_transaction_score
                        if cross_border_transaction_triggered
                        else Decimal("0.00")
                    ),
                    "details": {
                        "is_cross_border": deal.is_cross_border if deal is not None else None,
                    },
                },
                "unknown_beneficial_ownership": {
                    "triggered": unknown_beneficial_ownership,
                    "score": float(
                        cls.RULES.unknown_beneficial_ownership_score
                        if unknown_beneficial_ownership
                        else Decimal("0.00")
                    ),
                    "details": {
                        "applicable": client.client_type == ClientType.COMPANY,
                    },
                },
                "pep_or_rca_exposure": {
                    "triggered": pep_or_rca_exposure_triggered,
                    "score": float(cls.RULES.pep_or_rca_exposure_score if pep_or_rca_exposure_triggered else Decimal("0.00")),
                    "details": {"pep_or_rca_count": screening_snapshot["pep_or_rca_count"], "pep_declaration": profile.pep_declaration if profile is not None else False},
                },
                "sanctions_exposure": {
                    "triggered": sanctions_exposure_triggered,
                    "score": float(cls.RULES.sanctions_exposure_score if sanctions_exposure_triggered else Decimal("0.00")),
                    "details": {"sanctions_count": screening_snapshot["sanctions_count"]},
                },
                "cash_transaction": {
                    "triggered": cash_transaction_triggered,
                    "score": float(cls.RULES.cash_transaction_score if cash_transaction_triggered else Decimal("0.00")),
                    "details": {"payment_method_review": cdd_workflow.payment_method_review if cdd_workflow is not None else None},
                },
                "weak_source_of_funds": {
                    "triggered": weak_source_of_funds_triggered,
                    "score": float(cls.RULES.weak_source_of_funds_score if weak_source_of_funds_triggered else Decimal("0.00")),
                    "details": {"source_of_funds_status": cdd_workflow.source_of_funds_status.value if cdd_workflow is not None else None},
                },
                "weak_source_of_wealth": {
                    "triggered": weak_source_of_wealth_triggered,
                    "score": float(cls.RULES.weak_source_of_wealth_score if weak_source_of_wealth_triggered else Decimal("0.00")),
                    "details": {"source_of_wealth_status": cdd_workflow.source_of_wealth_status.value if cdd_workflow is not None else None},
                },
                "incomplete_documents": {
                    "triggered": incomplete_documents_triggered,
                    "score": float(cls.RULES.incomplete_documents_score if incomplete_documents_triggered else Decimal("0.00")),
                    "details": document_snapshot,
                },
                "expired_documents": {
                    "triggered": expired_documents_triggered,
                    "score": float(cls.RULES.expired_documents_score if expired_documents_triggered else Decimal("0.00")),
                    "details": document_snapshot,
                },
                "ownership_complexity": {
                    "triggered": ownership_complexity_triggered,
                    "score": float(cls.RULES.ownership_complexity_score if ownership_complexity_triggered else Decimal("0.00")),
                    "details": ownership_snapshot,
                },
                "repeated_alerts": {
                    "triggered": repeated_alert_triggered,
                    "score": float(cls.RULES.repeated_alert_score if repeated_alert_triggered else Decimal("0.00")),
                    "details": alert_snapshot,
                },
                "jurisdictional_risk": {
                    "triggered": jurisdictional_risk_triggered,
                    "score": float(cls.RULES.jurisdictional_risk_score if jurisdictional_risk_triggered else Decimal("0.00")),
                    "details": {"nationality": client.nationality, "residency_status": profile.residency_status if profile is not None else None},
                },
            },
            "triggered_factors": triggered_factors,
            "total_score": float(total_score),
        }

        return factor_breakdown, total_score

    @classmethod
    def _build_summary(
        cls,
        *,
        client: Client,
        deal: Deal | None,
        risk_level: RiskLevel,
        total_score: Decimal,
        factor_breakdown: dict[str, Any],
    ) -> str:
        triggered_factors: list[str] = factor_breakdown["triggered_factors"]

        readable_labels = {
            "confirmed_primary_client_match": "confirmed primary client screening match",
            "confirmed_linked_party_match": "confirmed linked-party screening match",
            "high_value_transaction": "high-value transaction context",
            "cross_border_transaction": "cross-border transaction context",
            "unknown_beneficial_ownership": "unknown beneficial ownership",
            "pep_or_rca_exposure": "PEP/RCA exposure",
            "sanctions_exposure": "sanctions exposure",
            "cash_transaction": "cash transaction indicator",
            "weak_source_of_funds": "weak source-of-funds verification",
            "weak_source_of_wealth": "weak source-of-wealth verification",
            "incomplete_documents": "incomplete KYC documents",
            "expired_documents": "expired KYC documents",
            "ownership_complexity": "ownership complexity",
            "repeated_alerts": "repeated monitoring alerts",
            "jurisdictional_risk": "jurisdictional risk",
        }

        if triggered_factors:
            triggered_text = ", ".join(readable_labels[factor] for factor in triggered_factors)
        else:
            triggered_text = "no material risk factors were triggered"

        scope = (
            f"client {client.id} and deal {deal.id}"
            if deal is not None
            else f"client {client.id}"
        )

        return (
            f"Risk assessment for {scope}: {risk_level.value} risk with a total score of "
            f"{cls._format_decimal(total_score)}. Triggered factors: {triggered_text}."
        )

    @classmethod
    def _determine_risk_level(cls, total_score: Decimal) -> RiskLevel:
        if total_score >= cls.RULES.high_risk_threshold:
            return RiskLevel.HIGH
        if total_score >= cls.RULES.medium_risk_threshold:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _get_client_or_raise(db: Session, client_id: int) -> Client:
        stmt = select(Client).where(Client.id == client_id)
        client = db.execute(stmt).scalar_one_or_none()

        if client is None:
            raise RiskValidationError(f"Client with id={client_id} was not found.")

        return client

    @classmethod
    def _resolve_deal_context(
        cls,
        db: Session,
        *,
        client_id: int,
        deal_id: int | None,
    ) -> Deal | None:
        if deal_id is not None:
            stmt = select(Deal).where(Deal.id == deal_id)
            deal = db.execute(stmt).scalar_one_or_none()

            if deal is None:
                raise RiskValidationError(f"Deal with id={deal_id} was not found.")
            if deal.client_id != client_id:
                raise RiskValidationError(
                    f"Deal with id={deal_id} does not belong to client id={client_id}."
                )

            return deal

        stmt = (
            select(Deal)
            .where(Deal.client_id == client_id)
            .order_by(Deal.created_at.desc(), Deal.id.desc())
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def _count_confirmed_primary_client_matches(
        db: Session,
        *,
        client_id: int,
    ) -> int:
        stmt = (
            select(func.count(ScreeningCandidate.id))
            .select_from(ScreeningCandidate)
            .join(
                ScreeningResult,
                ScreeningCandidate.screening_result_id == ScreeningResult.id,
            )
            .where(
                ScreeningResult.subject_type == ScreeningSubjectType.CLIENT,
                ScreeningResult.client_id == client_id,
                ScreeningCandidate.disposition == CandidateDisposition.CONFIRMED_MATCH,
            )
        )
        return int(db.execute(stmt).scalar_one())

    @staticmethod
    def _count_confirmed_linked_party_matches(
        db: Session,
        *,
        client_id: int,
        deal_id: int | None,
    ) -> int:
        stmt = (
            select(func.count(ScreeningCandidate.id))
            .select_from(ScreeningCandidate)
            .join(
                ScreeningResult,
                ScreeningCandidate.screening_result_id == ScreeningResult.id,
            )
            .join(
                LinkedParty,
                ScreeningResult.linked_party_id == LinkedParty.id,
            )
            .where(
                ScreeningResult.subject_type == ScreeningSubjectType.LINKED_PARTY,
                LinkedParty.client_id == client_id,
                ScreeningCandidate.disposition == CandidateDisposition.CONFIRMED_MATCH,
            )
        )

        if deal_id is not None:
            stmt = stmt.where(LinkedParty.deal_id == deal_id)

        return int(db.execute(stmt).scalar_one())

    @staticmethod
    def _has_unknown_beneficial_ownership(
        db: Session,
        *,
        client: Client,
        deal_id: int | None,
    ) -> bool:
        if client.client_type != ClientType.COMPANY:
            return False

        stmt = (
            select(func.count(LinkedParty.id))
            .where(
                LinkedParty.client_id == client.id,
                LinkedParty.role == LinkedPartyRole.BENEFICIAL_OWNER,
            )
        )

        if deal_id is not None:
            stmt = stmt.where(LinkedParty.deal_id == deal_id)

        beneficial_owner_count = int(db.execute(stmt).scalar_one())
        return beneficial_owner_count == 0

    @staticmethod
    def _get_kyc_profile(db: Session, *, client_id: int) -> KycProfile | None:
        stmt = select(KycProfile).where(KycProfile.client_id == client_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _get_cdd_workflow(
        db: Session,
        *,
        client_id: int,
        deal_id: int | None,
    ) -> CddWorkflow | None:
        stmt = select(CddWorkflow).where(CddWorkflow.client_id == client_id)
        if deal_id is None:
            stmt = stmt.order_by(CddWorkflow.updated_at.desc(), CddWorkflow.id.desc())
        else:
            stmt = stmt.where(or_(CddWorkflow.deal_id == deal_id, CddWorkflow.deal_id.is_(None))).order_by(
                CddWorkflow.updated_at.desc(),
                CddWorkflow.id.desc(),
            )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def _get_document_snapshot(db: Session, *, client_id: int) -> dict[str, Any]:
        documents = db.execute(select(KycDocument).where(KycDocument.client_id == client_id)).scalars().all()
        return {
            "total_count": len(documents),
            "verified_count": sum(1 for doc in documents if doc.lifecycle_status == DocumentLifecycleStatus.VERIFIED),
            "expired_count": sum(1 for doc in documents if doc.lifecycle_status == DocumentLifecycleStatus.EXPIRED),
            "missing_count": sum(
                1
                for doc in documents
                if doc.lifecycle_status
                in {
                    DocumentLifecycleStatus.REJECTED,
                    DocumentLifecycleStatus.RESUBMISSION_REQUIRED,
                }
            ),
        }

    @staticmethod
    def _get_ownership_snapshot(
        db: Session,
        *,
        client_id: int,
        deal_id: int | None,
    ) -> dict[str, Any]:
        stmt = select(BeneficialOwnershipRecord).where(BeneficialOwnershipRecord.client_id == client_id)
        if deal_id is not None:
            stmt = stmt.where(or_(BeneficialOwnershipRecord.deal_id == deal_id, BeneficialOwnershipRecord.deal_id.is_(None)))
        records = db.execute(stmt).scalars().all()
        max_complexity = max((record.complexity_score or Decimal("0.00") for record in records), default=Decimal("0.00"))
        return {
            "count": len(records),
            "max_complexity_score": max_complexity,
            "control_without_ownership_count": sum(1 for record in records if record.control_without_ownership),
        }

    @staticmethod
    def _get_alert_snapshot(db: Session, *, client_id: int) -> dict[str, Any]:
        alerts = db.execute(
            select(MonitoringAlert).where(
                MonitoringAlert.client_id == client_id,
                MonitoringAlert.status != AlertStatus.CLOSED,
            )
        ).scalars().all()
        return {
            "open_count": len(alerts),
            "critical_count": sum(1 for alert in alerts if alert.severity == AlertSeverity.CRITICAL),
        }

    @staticmethod
    def _get_screening_snapshot(db: Session, *, client_id: int) -> dict[str, Any]:
        candidates = db.execute(
            select(ScreeningCandidate)
            .join(ScreeningResult, ScreeningCandidate.screening_result_id == ScreeningResult.id)
            .outerjoin(LinkedParty, ScreeningResult.linked_party_id == LinkedParty.id)
            .where(
                or_(ScreeningResult.client_id == client_id, LinkedParty.client_id == client_id),
                ScreeningCandidate.disposition.in_(
                    [CandidateDisposition.CONFIRMED_MATCH, CandidateDisposition.NEEDS_EDD]
                ),
            )
        ).scalars().all()
        return {
            "pep_or_rca_count": sum(1 for candidate in candidates if candidate.match_category in {MatchCategory.PEP, MatchCategory.RCA}),
            "sanctions_count": sum(1 for candidate in candidates if (candidate.dataset or "").lower().find("sanction") >= 0),
        }

    @staticmethod
    def _get_latest_assessment_for_context(
        db: Session,
        *,
        client_id: int,
        deal_id: int | None,
    ) -> RiskAssessment | None:
        stmt = select(RiskAssessment).where(RiskAssessment.client_id == client_id)

        if deal_id is None:
            stmt = stmt.where(RiskAssessment.deal_id.is_(None))
        else:
            stmt = stmt.where(RiskAssessment.deal_id == deal_id)

        stmt = stmt.order_by(
            RiskAssessment.assessed_at.desc(),
            RiskAssessment.id.desc(),
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def _normalize_decimal(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        return f"{RiskService._normalize_decimal(value):.2f}"

    @staticmethod
    def _normalize_json_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            return {str(key): RiskService._normalize_json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [RiskService._normalize_json_value(item) for item in value]
        if isinstance(value, Decimal):
            return float(RiskService._normalize_decimal(value))
        if isinstance(value, enum.Enum):
            return value.value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value


def assess_risk(
    db: Session,
    client_id: int,
    *,
    deal_id: int | None = None,
    actor: str = "demo_user",
) -> RiskAssessment:
    return RiskService.assess_risk(
        db=db,
        client_id=client_id,
        deal_id=deal_id,
        actor=actor,
    )


def get_risk_assessment(
    db: Session,
    risk_assessment_id: int,
) -> RiskAssessment:
    return RiskService.get_risk_assessment(
        db=db,
        risk_assessment_id=risk_assessment_id,
    )


def get_latest_risk_assessment(
    db: Session,
    client_id: int,
    *,
    deal_id: int | None = None,
) -> RiskAssessment:
    return RiskService.get_latest_risk_assessment(
        db=db,
        client_id=client_id,
        deal_id=deal_id,
    )
