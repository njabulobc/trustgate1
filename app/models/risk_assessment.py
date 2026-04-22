from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.deal import Deal


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deal_id: Mapped[int | None] = mapped_column(
        ForeignKey("deals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    total_score: Mapped[float] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level"),
        nullable=False,
        index=True,
    )

    factor_breakdown: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        index=True,
    )
    is_system_generated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    client: Mapped["Client"] = relationship("Client")
    deal: Mapped["Deal | None"] = relationship("Deal")