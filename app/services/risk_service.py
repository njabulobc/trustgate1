from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client, ClientType
from app.models.deal import Deal
from app.models.linked_party import LinkedParty, LinkedPartyRole
from app.models.risk_assessment import RiskAssessment, RiskLevel
from app.models.screening import (
    CandidateDisposition,
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

    high_value_transaction_threshold: Decimal = Decimal("500000.00")

    medium_risk_threshold: Decimal = Decimal("20.00")
    high_risk_threshold: Decimal = Decimal("50.00")


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

        factor_breakdown, total_score = cls._build_factor_breakdown(
            client=client,
            deal=deal,
            primary_client_confirmed_count=primary_client_confirmed_count,
            linked_party_confirmed_count=linked_party_confirmed_count,
            unknown_beneficial_ownership=unknown_beneficial_ownership,
        )
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
            deal is not None and deal.is_cross_border is True
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