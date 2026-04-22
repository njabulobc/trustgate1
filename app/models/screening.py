from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.linked_party import LinkedParty


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScreeningSubjectType(str, enum.Enum):
    CLIENT = "client"
    LINKED_PARTY = "linked_party"


class ScreeningStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEWED = "reviewed"


class CandidateDisposition(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED_MATCH = "confirmed_match"
    FALSE_POSITIVE = "false_positive"
    NEEDS_EDD = "needs_edd"


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    subject_type: Mapped[ScreeningSubjectType] = mapped_column(
        Enum(ScreeningSubjectType, name="screening_subject_type"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    linked_party_id: Mapped[int | None] = mapped_column(
        ForeignKey("linked_parties.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    provider_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[ScreeningStatus] = mapped_column(
        Enum(ScreeningStatus, name="screening_status"),
        nullable=False,
        default=ScreeningStatus.PENDING,
        index=True,
    )

    subject_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    query_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    screened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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

    client: Mapped["Client | None"] = relationship("Client")
    linked_party: Mapped["LinkedParty | None"] = relationship("LinkedParty")
    candidates: Mapped[list["ScreeningCandidate"]] = relationship(
        "ScreeningCandidate",
        back_populates="screening_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ScreeningCandidate(Base):
    __tablename__ = "screening_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    screening_result_id: Mapped[int] = mapped_column(
        ForeignKey("screening_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider_candidate_id: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    provider_entity_id: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)

    matched_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    match_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)

    list_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    dataset: Mapped[str | None] = mapped_column(String(150), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    disposition: Mapped[CandidateDisposition] = mapped_column(
        Enum(CandidateDisposition, name="candidate_disposition"),
        nullable=False,
        default=CandidateDisposition.PENDING,
        index=True,
    )
    disposition_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

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

    screening_result: Mapped["ScreeningResult"] = relationship(
        "ScreeningResult",
        back_populates="candidates",
    )