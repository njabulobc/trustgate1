from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ComplianceVerdict(str, Enum):
    CLEAR = "clear"
    REVIEW_REQUIRED = "review_required"
    EDD_REQUIRED = "edd_required"


class ComplianceDecisionReasonRead(BaseModel):
    code: str
    summary: str
    severity: str
    rationale: str


class ComplianceDecisionActionRead(BaseModel):
    action: str
    status: str
    pep_case_id: int | None = None


class ComplianceDecisionEvidenceRead(BaseModel):
    screening_result_ids: list[int] = Field(default_factory=list)
    candidate_ids: list[int] = Field(default_factory=list)
    pep_case_ids: list[int] = Field(default_factory=list)
    risk_assessment_id: int


class ComplianceDecisionResponse(BaseModel):
    verdict: ComplianceVerdict
    top_reasons: list[str] = Field(default_factory=list)
    required_actions: list[ComplianceDecisionActionRead] = Field(default_factory=list)
    evidence: ComplianceDecisionEvidenceRead
    why: dict[str, Any] = Field(default_factory=dict)
