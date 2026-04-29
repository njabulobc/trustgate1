from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.risk_assessment import RiskLevel


class RiskAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    deal_id: int | None
    total_score: Decimal
    risk_level: RiskLevel
    factor_breakdown: dict[str, Any] | None
    summary: str | None
    assessed_at: datetime
    is_system_generated: bool
    created_at: datetime
    updated_at: datetime


class RiskAssessmentResponse(BaseModel):
    risk_assessment: RiskAssessmentRead

class RiskAssessmentHistoryResponse(BaseModel):
    items: list[RiskAssessmentRead]
