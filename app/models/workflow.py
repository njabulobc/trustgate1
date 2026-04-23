from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QueueStatus(str, enum.Enum):
    NEW = "new"
    QUEUED = "queued"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    COMPLETED = "completed"


class WorkflowCase(Base):
    __tablename__ = "workflow_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[QueueStatus] = mapped_column(Enum(QueueStatus, name="queue_status"), nullable=False, default=QueueStatus.NEW, index=True)
    assigned_reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    queue_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
