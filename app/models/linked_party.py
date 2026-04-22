from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.deal import Deal


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LinkedPartyType(str, enum.Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


class LinkedPartyRole(str, enum.Enum):
    BENEFICIAL_OWNER = "beneficial_owner"
    REPRESENTATIVE = "representative"
    CO_BUYER = "co_buyer"
    CO_SELLER = "co_seller"
    PAYER = "payer"
    INTERMEDIARY = "intermediary"
    OTHER = "other"


class LinkedParty(Base):
    __tablename__ = "linked_parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    party_type: Mapped[LinkedPartyType] = mapped_column(
        Enum(LinkedPartyType, name="linked_party_type"),
        nullable=False,
        index=True,
    )
    role: Mapped[LinkedPartyRole] = mapped_column(
        Enum(LinkedPartyRole, name="linked_party_role"),
        nullable=False,
        index=True,
    )
    relationship_to_client: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    primary_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    national_id_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    country_of_incorporation: Mapped[str | None] = mapped_column(String(100), nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    screening_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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
    deal: Mapped["Deal"] = relationship("Deal")