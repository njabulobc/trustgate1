from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.screening import (
    CandidateDisposition,
    MatchCategory,
    PepCaseStatus,
    ScreeningStatus,
    ScreeningSubjectType,
    VerificationStatus,
)


class ScreeningRunRequest(BaseModel):
    subject_type: ScreeningSubjectType
    client_id: int | None = None
    linked_party_id: int | None = None
    query_text: str | None = Field(default=None, min_length=1, max_length=255)


class ScreeningCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    screening_result_id: int
    provider_candidate_id: str | None
    provider_entity_id: str | None
    matched_name: str
    match_score: Decimal | None
    list_name: str | None
    dataset: str | None
    country: str | None
    notes: str | None
    match_category: MatchCategory
    policy_flags: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Deterministic multi-factor policy metadata used to explain PEP/RCA classification, "
            "including weighted signals, thresholds, false-positive reduction decisions, and alerts."
        ),
    )
    disposition: CandidateDisposition
    disposition_reason: str | None
    reviewed_at: datetime | None
    candidate_payload: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ScreeningResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_type: ScreeningSubjectType
    client_id: int | None
    linked_party_id: int | None
    provider_name: str
    status: ScreeningStatus
    subject_name_snapshot: str
    query_text: str | None
    request_payload: dict[str, Any] | None
    response_payload: dict[str, Any] | None
    error_message: str | None
    screened_at: datetime
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    candidates: list[ScreeningCandidateRead] = []


class ScreeningRunResponse(BaseModel):
    screening_result: ScreeningResultRead


class CandidateDispositionUpdate(BaseModel):
    disposition: CandidateDisposition
    disposition_reason: str | None = None


class PepCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    screening_candidate_id: int
    status: PepCaseStatus
    senior_approval_status: VerificationStatus
    source_of_wealth_status: VerificationStatus
    source_of_funds_status: VerificationStatus
    enhanced_monitoring: bool
    monitoring_notes: str | None
    closure_evidence: dict[str, Any] | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PepCaseUpdate(BaseModel):
    status: PepCaseStatus | None = None
    senior_approval_status: VerificationStatus | None = None
    source_of_wealth_status: VerificationStatus | None = None
    source_of_funds_status: VerificationStatus | None = None
    enhanced_monitoring: bool | None = None
    monitoring_notes: str | None = None
    closure_evidence: dict[str, Any] | None = None
