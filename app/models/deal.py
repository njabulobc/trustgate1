from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.client import Client


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DealTransactionType(str, enum.Enum):
    PURCHASE = "purchase"
    SALE = "sale"
    LEASE = "lease"
    RENTAL = "rental"
    TRANSFER = "transfer"
    OTHER = "other"


class DealStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    SCREENING_PENDING = "screening_pending"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    transaction_reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    transaction_type: Mapped[DealTransactionType] = mapped_column(
        Enum(DealTransactionType, name="deal_transaction_type"),
        nullable=False,
        index=True,
    )
    status: Mapped[DealStatus] = mapped_column(
        Enum(DealStatus, name="deal_status"),
        nullable=False,
        default=DealStatus.DRAFT,
        index=True,
    )

    property_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )
    property_location: Mapped[str] = mapped_column(Text, nullable=False)

    transaction_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    is_cross_border: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    source_of_funds_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

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