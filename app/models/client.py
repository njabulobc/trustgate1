from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClientType(str, enum.Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


class ClientStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    REJECTED = "rejected"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    client_type: Mapped[ClientType] = mapped_column(
        Enum(ClientType, name="client_type"),
        nullable=False,
        index=True,
    )
    status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus, name="client_status"),
        nullable=False,
        default=ClientStatus.DRAFT,
        index=True,
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