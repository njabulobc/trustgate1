from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.platform import (
    AlertSeverity,
    AlertStatus,
    CddWorkflow,
    DocumentLifecycleStatus,
    EddCasePriority,
    EddCaseStatus,
    KycOnboardingStatus,
    MonitoringAlert,
    OwnershipOwnerType,
    ReviewDecision,
    TaxClearanceStatus,
    WorkflowStatus,
)
from app.models.user import UserRole


class DashboardSummary(BaseModel):
    total_clients: int
    pending_kyc_reviews: int
    incomplete_document_files: int
    open_cdd_tasks: int
    open_edd_cases: int
    screening_hits_requiring_review: int
    open_alerts: int
    high_risk_clients_or_deals: int
    reports_shortcut_count: int


class IntakeListItem(BaseModel):
    client_id: int
    deal_id: int | None
    primary_name: str
    client_type: str
    client_status: str
    transaction_reference: str | None
    transaction_type: str | None
    deal_status: str | None
    risk_level: str | None
    updated_at: datetime


class KycProfileWrite(BaseModel):
    deal_id: int | None = None
    onboarding_status: KycOnboardingStatus = KycOnboardingStatus.DRAFT
    full_legal_name: str = Field(..., min_length=1, max_length=255)
    date_of_birth: datetime | None = None
    national_id_or_passport_number: str | None = Field(default=None, max_length=120)
    nationality: str | None = Field(default=None, max_length=100)
    address: str | None = None
    contact_details: str | None = None
    occupation: str | None = Field(default=None, max_length=150)
    employer: str | None = Field(default=None, max_length=150)
    business_activity: str | None = None
    company_registration_number: str | None = Field(default=None, max_length=120)
    tax_identification_number: str | None = Field(default=None, max_length=120)
    tax_clearance_status: TaxClearanceStatus = TaxClearanceStatus.UNKNOWN
    residency_status: str | None = Field(default=None, max_length=100)
    cross_border_indicator: bool = False
    pep_declaration: bool = False
    related_party_declaration: bool = False
    notes: str | None = None


class KycProfileRead(KycProfileWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    created_by_user_id: int | None
    updated_by_user_id: int | None
    created_at: datetime
    updated_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    deal_id: int | None
    linked_party_id: int | None
    document_type: str
    lifecycle_status: DocumentLifecycleStatus
    file_name: str
    content_type: str | None
    storage_path: str
    storage_reference: str | None
    checksum_sha256: str
    file_size_bytes: int
    expiry_date: date | None
    reviewer_user_id: int | None
    review_timestamp: datetime | None
    rejection_reason: str | None
    reviewer_comments: str | None
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime


class DocumentReviewUpdate(BaseModel):
    lifecycle_status: DocumentLifecycleStatus
    expiry_date: date | None = None
    rejection_reason: str | None = None
    reviewer_comments: str | None = None


class DocumentChecklistSummary(BaseModel):
    client_id: int
    total_documents: int
    verified_documents: int
    missing_document_types: list[str]
    expired_documents: int
    requires_resubmission: int


class CddWorkflowWrite(BaseModel):
    deal_id: int | None = None
    assigned_analyst_id: int | None = None
    completion_status: WorkflowStatus = WorkflowStatus.OPEN
    source_of_funds_status: ReviewDecision = ReviewDecision.PENDING
    source_of_wealth_status: ReviewDecision = ReviewDecision.PENDING
    payment_method_review: str | None = None
    transaction_purpose_review: str | None = None
    expected_activity_profile: str | None = None
    adverse_transaction_indicators: str | None = None
    supporting_evidence_checklist: dict[str, Any] | None = None
    analyst_decision: ReviewDecision = ReviewDecision.PENDING
    reviewer_decision: ReviewDecision = ReviewDecision.PENDING
    analyst_notes: str | None = None
    reviewer_notes: str | None = None


class CddWorkflowRead(CddWorkflowWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime


class OwnershipRecordWrite(BaseModel):
    deal_id: int | None = None
    linked_party_id: int | None = None
    parent_record_id: int | None = None
    owner_name: str = Field(..., min_length=1, max_length=255)
    owner_type: OwnershipOwnerType = OwnershipOwnerType.INDIVIDUAL
    classification: str | None = Field(default=None, max_length=120)
    ownership_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    control_type: str | None = Field(default=None, max_length=120)
    direct_ownership: bool = True
    indirect_ownership: bool = False
    nominee_indicator: bool = False
    trust_indicator: bool = False
    representative_relationship: bool = False
    control_without_ownership: bool = False
    corporate_parent_name: str | None = Field(default=None, max_length=255)
    ownership_chain_notes: str | None = None
    complexity_score: Decimal | None = Field(default=None, ge=0, le=100)


class OwnershipRecordRead(OwnershipRecordWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime


class OwnershipGraphNode(BaseModel):
    id: int
    owner_name: str
    parent_record_id: int | None
    ownership_percentage: Decimal | None
    control_type: str | None
    complexity_score: Decimal | None


class RiskOverrideWrite(BaseModel):
    override_level: str = Field(..., min_length=1, max_length=50)
    justification: str = Field(..., min_length=5)
    notes: str | None = None


class RiskOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    risk_assessment_id: int
    overridden_by_user_id: int | None
    override_level: str
    justification: str
    notes: str | None
    created_at: datetime


class EddCaseWrite(BaseModel):
    deal_id: int | None = None
    source_module: str = Field(default="manual", min_length=1, max_length=120)
    case_type: str = Field(..., min_length=1, max_length=120)
    trigger_reason: str = Field(..., min_length=5)
    assigned_analyst_id: int | None = None
    priority: EddCasePriority = EddCasePriority.MEDIUM
    status: EddCaseStatus = EddCaseStatus.OPEN
    required_actions: dict[str, Any] | None = None
    evidence_checklist: dict[str, Any] | None = None
    analyst_findings: str | None = None
    reviewer_comments: str | None = None
    approval_outcome: str | None = Field(default=None, max_length=120)
    closure_decision: str | None = None
    due_at: datetime | None = None


class EddCaseRead(EddCaseWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime


class AlertWrite(BaseModel):
    deal_id: int | None = None
    linked_party_id: int | None = None
    edd_case_id: int | None = None
    module: str = Field(default="monitoring", min_length=1, max_length=120)
    alert_type: str = Field(..., min_length=1, max_length=120)
    severity: AlertSeverity = AlertSeverity.MEDIUM
    status: AlertStatus = AlertStatus.OPEN
    assigned_user_id: int | None = None
    disposition: str | None = None
    escalation_reason: str | None = None
    closure_reason: str | None = None
    due_at: datetime | None = None


class AlertRead(AlertWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MonitoringRunRequest(BaseModel):
    client_id: int
    deal_id: int | None = None
    reason: str | None = None


class MonitoringEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    deal_id: int | None
    event_type: str
    event_source: str
    summary: str
    details: dict[str, Any] | None
    triggered_by_user_id: int | None
    created_at: datetime


class ReportFilter(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    client_type: str | None = None
    risk_level: str | None = None
    status: str | None = None
    analyst_id: int | None = None
    module: str | None = None


class ReportDataset(BaseModel):
    name: str
    rows: list[dict[str, Any]]


class WorkbenchItem(BaseModel):
    module: str
    item_type: str
    item_id: int
    client_id: int | None
    deal_id: int | None
    title: str
    status: str
    severity_or_priority: str | None
    assigned_user_id: int | None
    updated_at: datetime


class WorkbenchFilter(BaseModel):
    status: str | None = None
    risk_level: str | None = None
    assignee_id: int | None = None
    client_id: int | None = None
    module: str | None = None


class AppSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value_json: dict[str, Any] | None
    description: str | None
    updated_by_user_id: int | None
    updated_at: datetime


class AppSettingWrite(BaseModel):
    key: str = Field(..., min_length=1, max_length=120)
    value_json: dict[str, Any] | None = None
    description: str | None = None


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    actor: str
    action: str
    module: str
    entity_type: str
    entity_id: str
    previous_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    reason: str | None
    comment: str | None
    timestamp: datetime


class AnalystQueueResponse(BaseModel):
    items: list[WorkbenchItem]


class ReportExportResponse(BaseModel):
    report_name: str
    rows: list[dict[str, Any]]
    csv: str | None = None


class AdminOverview(BaseModel):
    users: list[dict[str, Any]]
    settings: list[AppSettingRead]
    audit_events: list[AuditEventRead]
