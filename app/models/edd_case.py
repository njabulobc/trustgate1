from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.deal import Deal
    from app.models.linked_party import LinkedParty
    from app.models.risk_assessment import RiskAssessment
    from app.models.screening import PepCase, ScreeningCandidate


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EddTriggerType(str, enum.Enum):
    SCREENING = "screening"
    RISK = "risk"
    PEP = "pep"
    MANUAL = "manual"


class EddPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EddStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class EddCase(Base):
    __tablename__ = "edd_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trigger_type: Mapped[EddTriggerType] = mapped_column(Enum(EddTriggerType, name="edd_trigger_type"), nullable=False, index=True)
    trigger_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    priority: Mapped[EddPriority] = mapped_column(Enum(EddPriority, name="edd_priority"), nullable=False, default=EddPriority.MEDIUM, index=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[EddStatus] = mapped_column(Enum(EddStatus, name="edd_status"), nullable=False, default=EddStatus.OPEN, index=True)
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    closure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closure_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_party_id: Mapped[int | None] = mapped_column(ForeignKey("linked_parties.id", ondelete="SET NULL"), nullable=True, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    screening_candidate_id: Mapped[int | None] = mapped_column(ForeignKey("screening_candidates.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    risk_assessment_id: Mapped[int | None] = mapped_column(ForeignKey("risk_assessments.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    client: Mapped["Client | None"] = relationship("Client")
    linked_party: Mapped["LinkedParty | None"] = relationship("LinkedParty")
    deal: Mapped["Deal | None"] = relationship("Deal")
    screening_candidate: Mapped["ScreeningCandidate | None"] = relationship("ScreeningCandidate")
    risk_assessment: Mapped["RiskAssessment | None"] = relationship("RiskAssessment")
    pep_case: Mapped["PepCase | None"] = relationship("PepCase", back_populates="edd_case", uselist=False)
