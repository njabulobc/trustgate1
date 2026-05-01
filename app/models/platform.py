from __future__ import annotations

import enum
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KycOnboardingStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class TaxClearanceStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    PENDING = "pending"
    VERIFIED = "verified"
    EXEMPT = "exempt"
    REJECTED = "rejected"


class DocumentLifecycleStatus(str, enum.Enum):
    REQUIRED = "required"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    RESUBMISSION_REQUIRED = "resubmission_required"


class ReviewDecision(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class WorkflowStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class OwnershipOwnerType(str, enum.Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"
    TRUST = "trust"
    NOMINEE = "nominee"


class EddCaseStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_review"
    AWAITING_INFORMATION = "awaiting_information"
    ESCALATED = "escalated"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class EddCasePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    CLOSED = "closed"


class KycProfile(Base):
    __tablename__ = "kyc_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    onboarding_status: Mapped[KycOnboardingStatus] = mapped_column(
        Enum(KycOnboardingStatus, name="kyc_onboarding_status"),
        nullable=False,
        default=KycOnboardingStatus.DRAFT,
        index=True,
    )
    full_legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    national_id_or_passport_number: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(150), nullable=True)
    employer: Mapped[str | None] = mapped_column(String(150), nullable=True)
    business_activity: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_registration_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tax_identification_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tax_clearance_status: Mapped[TaxClearanceStatus] = mapped_column(
        Enum(TaxClearanceStatus, name="tax_clearance_status"),
        nullable=False,
        default=TaxClearanceStatus.UNKNOWN,
    )
    residency_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cross_border_indicator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pep_declaration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    related_party_declaration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class KycDocument(Base):
    __tablename__ = "kyc_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_party_id: Mapped[int | None] = mapped_column(ForeignKey("linked_parties.id", ondelete="SET NULL"), nullable=True, index=True)
    document_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    lifecycle_status: Mapped[DocumentLifecycleStatus] = mapped_column(
        Enum(DocumentLifecycleStatus, name="document_lifecycle_status"),
        nullable=False,
        default=DocumentLifecycleStatus.SUBMITTED,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reviewer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class CddWorkflow(Base):
    __tablename__ = "cdd_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_analyst_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    completion_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="cdd_workflow_status"),
        nullable=False,
        default=WorkflowStatus.OPEN,
        index=True,
    )
    source_of_funds_status: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, name="cdd_source_of_funds_status"),
        nullable=False,
        default=ReviewDecision.PENDING,
    )
    source_of_wealth_status: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, name="cdd_source_of_wealth_status"),
        nullable=False,
        default=ReviewDecision.PENDING,
    )
    payment_method_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_purpose_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_activity_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    adverse_transaction_indicators: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_evidence_checklist: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    analyst_decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, name="cdd_analyst_decision"),
        nullable=False,
        default=ReviewDecision.PENDING,
    )
    reviewer_decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, name="cdd_reviewer_decision"),
        nullable=False,
        default=ReviewDecision.PENDING,
    )
    analyst_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class BeneficialOwnershipRecord(Base):
    __tablename__ = "beneficial_ownership_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_party_id: Mapped[int | None] = mapped_column(ForeignKey("linked_parties.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_record_id: Mapped[int | None] = mapped_column(ForeignKey("beneficial_ownership_records.id", ondelete="SET NULL"), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_type: Mapped[OwnershipOwnerType] = mapped_column(
        Enum(OwnershipOwnerType, name="ownership_owner_type"),
        nullable=False,
        default=OwnershipOwnerType.INDIVIDUAL,
        index=True,
    )
    classification: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ownership_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    control_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    direct_ownership: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    indirect_ownership: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nominee_indicator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trust_indicator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    representative_relationship: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    control_without_ownership: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    corporate_parent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ownership_chain_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    complexity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class EddCase(Base):
    __tablename__ = "edd_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    source_module: Mapped[str] = mapped_column(String(120), nullable=False, default="manual")
    case_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_analyst_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    priority: Mapped[EddCasePriority] = mapped_column(
        Enum(EddCasePriority, name="edd_case_priority"),
        nullable=False,
        default=EddCasePriority.MEDIUM,
        index=True,
    )
    status: Mapped[EddCaseStatus] = mapped_column(
        Enum(EddCaseStatus, name="edd_case_status"),
        nullable=False,
        default=EddCaseStatus.OPEN,
        index=True,
    )
    required_actions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evidence_checklist: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    analyst_findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_outcome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    closure_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class MonitoringEvent(Base):
    __tablename__ = "monitoring_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_source: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    triggered_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class MonitoringAlert(Base):
    __tablename__ = "monitoring_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_party_id: Mapped[int | None] = mapped_column(ForeignKey("linked_parties.id", ondelete="SET NULL"), nullable=True, index=True)
    edd_case_id: Mapped[int | None] = mapped_column(ForeignKey("edd_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(120), nullable=False, default="monitoring")
    alert_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"),
        nullable=False,
        default=AlertSeverity.MEDIUM,
        index=True,
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"),
        nullable=False,
        default=AlertStatus.OPEN,
        index=True,
    )
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    disposition: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class RiskOverride(Base):
    __tablename__ = "risk_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    risk_assessment_id: Mapped[int] = mapped_column(ForeignKey("risk_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    overridden_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    override_level: Mapped[str] = mapped_column(String(50), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    previous_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
