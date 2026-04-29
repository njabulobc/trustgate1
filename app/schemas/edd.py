from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.edd_case import EddPriority, EddStatus, EddTriggerType


class EddCaseCreate(BaseModel):
    trigger_type: EddTriggerType
    trigger_reference: str | None = None
    priority: EddPriority = EddPriority.MEDIUM
    risk_level: str | None = None
    assignee: str | None = None
    due_date: datetime | None = None
    client_id: int | None = None
    linked_party_id: int | None = None
    deal_id: int | None = None
    screening_candidate_id: int | None = None
    risk_assessment_id: int | None = None


class EddCaseAssign(BaseModel):
    assignee: str


class EddCaseStatusUpdate(BaseModel):
    status: EddStatus


class EddCaseClose(BaseModel):
    reason: str
    evidence: dict[str, Any] | None = None


class EddCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    trigger_type: EddTriggerType
    trigger_reference: str | None
    priority: EddPriority
    risk_level: str | None
    status: EddStatus
    assignee: str | None
    due_date: datetime | None
    acknowledged_at: datetime | None
    started_at: datetime | None
    escalated_at: datetime | None
    closed_at: datetime | None
    closure_reason: str | None
    closure_evidence: dict[str, Any] | None
    client_id: int | None
    linked_party_id: int | None
    deal_id: int | None
    screening_candidate_id: int | None
    risk_assessment_id: int | None
    created_at: datetime
    updated_at: datetime
