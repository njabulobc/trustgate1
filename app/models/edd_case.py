from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EDDCaseStatus(str, enum.Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    CLOSED = "closed"


class EDDCase(Base):
    __tablename__ = "edd_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    risk_assessment_id: Mapped[int | None] = mapped_column(ForeignKey("risk_assessments.id", ondelete="SET NULL"), nullable=True, index=True)
    screening_result_id: Mapped[int | None] = mapped_column(ForeignKey("screening_results.id", ondelete="SET NULL"), nullable=True, index=True)

    status: Mapped[EDDCaseStatus] = mapped_column(
        Enum(EDDCaseStatus, name="edd_case_status"),
        nullable=False,
        default=EDDCaseStatus.OPEN,
        index=True,
    )
    trigger_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    analyst_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
