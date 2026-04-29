from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReportType(str, enum.Enum):
    COMPLIANCE_SUMMARY = "compliance_summary"
    CLIENT_RISK_REGISTER = "client_risk_register"
    SCREENING_ACTIVITY = "screening_activity"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType, name="report_type"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
