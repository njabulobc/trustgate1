from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.edd_case import EDDCaseStatus


class EDDCaseCreate(BaseModel):
    client_id: int
    deal_id: int | None = None
    risk_assessment_id: int | None = None
    screening_result_id: int | None = None
    trigger_reason: str
    analyst_notes: str | None = None
    assigned_to: str | None = None


class EDDCaseUpdate(BaseModel):
    status: EDDCaseStatus | None = None
    analyst_notes: str | None = None
    assigned_to: str | None = None


class EDDCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    deal_id: int | None
    risk_assessment_id: int | None
    screening_result_id: int | None
    status: EDDCaseStatus
    trigger_reason: str
    analyst_notes: str | None
    assigned_to: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
