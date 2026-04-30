from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client import Client, ClientType
from app.models.deal import Deal
from app.models.linked_party import LinkedParty
from app.models.platform import (
    AlertSeverity,
    AlertStatus,
    AppSetting,
    AuditEvent,
    BeneficialOwnershipRecord,
    CddWorkflow,
    DocumentLifecycleStatus,
    EddCase,
    EddCasePriority,
    EddCaseStatus,
    KycDocument,
    KycOnboardingStatus,
    KycProfile,
    MonitoringAlert,
    MonitoringEvent,
    RiskOverride,
    ReviewDecision,
    TaxClearanceStatus,
    WorkflowStatus,
)
from app.models.risk_assessment import RiskAssessment, RiskLevel
from app.models.screening import CandidateDisposition, MatchCategory, ScreeningCandidate, ScreeningResult
from app.models.user import User, UserRole
from app.schemas.platform import DashboardSummary, IntakeListItem, WorkbenchItem
from app.services.audit_service import record_audit_event


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PlatformServiceError(Exception):
    """Base exception for platform workflow failures."""


class PlatformNotFoundError(PlatformServiceError):
    """Raised when a platform record cannot be found."""


class PlatformValidationError(PlatformServiceError):
    """Raised when a platform request is invalid."""


class PlatformConflictError(PlatformServiceError):
    """Raised when a platform write collides with persistence constraints."""


DEFAULT_DOCUMENT_TYPES = {
    ClientType.INDIVIDUAL: [
        "national_id",
        "passport",
        "proof_of_residence",
        "bank_statement",
        "tax_clearance_certificate",
        "source_of_funds_support",
    ],
    ClientType.COMPANY: [
        "company_registration_documents",
        "beneficial_ownership_evidence",
        "authorization_or_mandate",
        "tax_clearance_certificate",
        "bank_statement",
        "source_of_funds_support",
    ],
}


DEFAULT_APP_SETTINGS: list[tuple[str, dict[str, Any], str]] = [
    ("risk_factors", {"high_value_threshold": 500000, "cross_border_score": 10}, "Risk factor configuration"),
    ("document_checklists", {"individual": DEFAULT_DOCUMENT_TYPES[ClientType.INDIVIDUAL], "company": DEFAULT_DOCUMENT_TYPES[ClientType.COMPANY]}, "Document checklist configuration"),
    ("cdd_checklist", {"required_items": ["source_of_funds", "source_of_wealth", "payment_method", "transaction_purpose"]}, "CDD checklist configuration"),
    ("edd_triggers", {"triggers": ["pep_or_rca", "cross_border", "complex_ownership", "high_risk"]}, "EDD trigger configuration"),
    ("monitoring", {"interval_days": settings.DEFAULT_MONITORING_INTERVAL_DAYS}, "Monitoring interval configuration"),
]


class PlatformService:
    @staticmethod
    def ensure_default_settings(db: Session, actor: User | None = None) -> None:
        for key, value_json, description in DEFAULT_APP_SETTINGS:
            stmt = select(AppSetting).where(AppSetting.key == key)
            existing = db.execute(stmt).scalar_one_or_none()
            if existing is not None:
                continue
            db.add(
                AppSetting(
                    key=key,
                    value_json=value_json,
                    description=description,
                    updated_by_user_id=actor.id if actor is not None else None,
                )
            )
        db.commit()

    @staticmethod
    def list_intake_records(db: Session) -> list[IntakeListItem]:
        clients = list(db.execute(select(Client).order_by(Client.updated_at.desc(), Client.id.desc())).scalars().all())
        items: list[IntakeListItem] = []
        for client in clients:
            deal = db.execute(
                select(Deal).where(Deal.client_id == client.id).order_by(Deal.updated_at.desc(), Deal.id.desc())
            ).scalars().first()
            risk = db.execute(
                select(RiskAssessment)
                .where(RiskAssessment.client_id == client.id)
                .order_by(RiskAssessment.assessed_at.desc(), RiskAssessment.id.desc())
            ).scalars().first()
            items.append(
                IntakeListItem(
                    client_id=client.id,
                    deal_id=deal.id if deal is not None else None,
                    primary_name=client.primary_name,
                    client_type=client.client_type.value,
                    client_status=client.status.value,
                    transaction_reference=deal.transaction_reference if deal is not None else None,
                    transaction_type=deal.transaction_type.value if deal is not None else None,
                    deal_status=deal.status.value if deal is not None else None,
                    risk_level=risk.risk_level.value if risk is not None else None,
                    updated_at=max(client.updated_at, deal.updated_at if deal is not None else client.updated_at),
                )
            )
        return items

    @staticmethod
    def get_dashboard_summary(db: Session) -> DashboardSummary:
        total_clients = int(db.execute(select(func.count(Client.id))).scalar_one())
        pending_kyc_reviews = int(
            db.execute(
                select(func.count(KycProfile.id)).where(KycProfile.onboarding_status == KycOnboardingStatus.READY_FOR_REVIEW)
            ).scalar_one()
        )
        incomplete_document_files = int(
            db.execute(
                select(func.count(KycDocument.id)).where(
                    KycDocument.lifecycle_status.in_(
                        [
                            DocumentLifecycleStatus.SUBMITTED,
                            DocumentLifecycleStatus.UNDER_REVIEW,
                            DocumentLifecycleStatus.REJECTED,
                            DocumentLifecycleStatus.RESUBMISSION_REQUIRED,
                            DocumentLifecycleStatus.EXPIRED,
                        ]
                    )
                )
            ).scalar_one()
        )
        open_cdd_tasks = int(
            db.execute(
                select(func.count(CddWorkflow.id)).where(
                    CddWorkflow.completion_status.in_([WorkflowStatus.OPEN, WorkflowStatus.IN_PROGRESS, WorkflowStatus.UNDER_REVIEW])
                )
            ).scalar_one()
        )
        open_edd_cases = int(
            db.execute(
                select(func.count(EddCase.id)).where(
                    EddCase.status.in_(
                        [
                            EddCaseStatus.OPEN,
                            EddCaseStatus.ASSIGNED,
                            EddCaseStatus.IN_REVIEW,
                            EddCaseStatus.AWAITING_INFORMATION,
                            EddCaseStatus.ESCALATED,
                        ]
                    )
                )
            ).scalar_one()
        )
        screening_hits_requiring_review = int(
            db.execute(
                select(func.count(ScreeningCandidate.id)).where(
                    ScreeningCandidate.disposition == CandidateDisposition.PENDING
                )
            ).scalar_one()
        )
        open_alerts = int(
            db.execute(
                select(func.count(MonitoringAlert.id)).where(MonitoringAlert.status != AlertStatus.CLOSED)
            ).scalar_one()
        )
        high_risk_clients_or_deals = int(
            db.execute(
                select(func.count(RiskAssessment.id)).where(RiskAssessment.risk_level == RiskLevel.HIGH)
            ).scalar_one()
        )
        return DashboardSummary(
            total_clients=total_clients,
            pending_kyc_reviews=pending_kyc_reviews,
            incomplete_document_files=incomplete_document_files,
            open_cdd_tasks=open_cdd_tasks,
            open_edd_cases=open_edd_cases,
            screening_hits_requiring_review=screening_hits_requiring_review,
            open_alerts=open_alerts,
            high_risk_clients_or_deals=high_risk_clients_or_deals,
            reports_shortcut_count=5,
        )

    @staticmethod
    def get_kyc_profile(db: Session, client_id: int) -> KycProfile | None:
        PlatformService._get_client_or_raise(db, client_id)
        return db.execute(select(KycProfile).where(KycProfile.client_id == client_id)).scalar_one_or_none()

    @staticmethod
    def upsert_kyc_profile(
        db: Session,
        client_id: int,
        payload: dict[str, Any],
        actor: User,
    ) -> KycProfile:
        client = PlatformService._get_client_or_raise(db, client_id)
        profile = db.execute(select(KycProfile).where(KycProfile.client_id == client_id)).scalar_one_or_none()
        is_created = profile is None
        if profile is None:
            profile = KycProfile(client_id=client_id, created_by_user_id=actor.id, **payload)
            db.add(profile)
        else:
            previous_value = {
                "onboarding_status": profile.onboarding_status.value,
                "cross_border_indicator": profile.cross_border_indicator,
                "pep_declaration": profile.pep_declaration,
            }
            for field_name, field_value in payload.items():
                setattr(profile, field_name, field_value)
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="kyc.updated",
                module="kyc",
                entity_type="kyc_profile",
                entity_id=profile.id,
                previous_value=previous_value,
                new_value=payload,
            )
        profile.updated_by_user_id = actor.id

        client.primary_name = payload["full_legal_name"]
        client.date_of_birth = payload.get("date_of_birth")
        client.nationality = payload.get("nationality")
        client.address = payload.get("address")
        client.email = PlatformService._extract_email(payload.get("contact_details"))
        client.phone_number = PlatformService._extract_phone(payload.get("contact_details"))
        if payload.get("company_registration_number"):
            client.registration_number = payload.get("company_registration_number")
        if payload.get("national_id_or_passport_number"):
            client.national_id_number = payload.get("national_id_or_passport_number")

        if payload.get("deal_id"):
            deal = PlatformService._get_deal_or_raise(db, payload["deal_id"])
            if deal.client_id != client_id:
                raise PlatformValidationError(f"Deal with id={deal.id} does not belong to client id={client_id}.")
            deal.is_cross_border = bool(payload.get("cross_border_indicator"))

        try:
            db.flush()
            if is_created:
                record_audit_event(
                    db=db,
                    actor=actor.username,
                    user_id=actor.id,
                    action="kyc.created",
                    module="kyc",
                    entity_type="kyc_profile",
                    entity_id=profile.id,
                    new_value=payload,
                )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to persist KYC profile.") from exc
        db.refresh(profile)
        return profile

    @staticmethod
    def list_documents(db: Session, client_id: int) -> list[KycDocument]:
        PlatformService._get_client_or_raise(db, client_id)
        stmt = select(KycDocument).where(KycDocument.client_id == client_id).order_by(KycDocument.updated_at.desc(), KycDocument.id.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def save_document_upload(
        db: Session,
        *,
        client_id: int,
        deal_id: int | None,
        linked_party_id: int | None,
        document_type: str,
        expiry_date: date | None,
        file: UploadFile,
        actor: User,
    ) -> KycDocument:
        PlatformService._get_client_or_raise(db, client_id)
        if deal_id is not None:
            deal = PlatformService._get_deal_or_raise(db, deal_id)
            if deal.client_id != client_id:
                raise PlatformValidationError(f"Deal with id={deal_id} does not belong to client id={client_id}.")

        file_bytes = file.file.read()
        checksum = hashlib.sha256(file_bytes).hexdigest()
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "document")
        upload_dir = Path(settings.DOCUMENT_UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        target_path = upload_dir / f"{client_id}_{utcnow().strftime('%Y%m%d%H%M%S')}_{safe_name}"
        target_path.write_bytes(file_bytes)

        document = KycDocument(
            client_id=client_id,
            deal_id=deal_id,
            linked_party_id=linked_party_id,
            document_type=document_type,
            lifecycle_status=DocumentLifecycleStatus.SUBMITTED,
            file_name=file.filename or safe_name,
            content_type=file.content_type,
            storage_path=str(target_path.resolve()),
            storage_reference=target_path.name,
            checksum_sha256=checksum,
            file_size_bytes=len(file_bytes),
            expiry_date=expiry_date,
            created_by_user_id=actor.id,
        )
        try:
            db.add(document)
            db.flush()
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="document.uploaded",
                module="documents",
                entity_type="kyc_document",
                entity_id=document.id,
                new_value={"document_type": document_type, "status": document.lifecycle_status.value, "file_name": document.file_name},
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to store document metadata.") from exc
        db.refresh(document)
        return document

    @staticmethod
    def review_document(db: Session, document_id: int, payload: dict[str, Any], actor: User) -> KycDocument:
        document = db.execute(select(KycDocument).where(KycDocument.id == document_id)).scalar_one_or_none()
        if document is None:
            raise PlatformNotFoundError(f"Document with id={document_id} was not found.")
        previous_value = {"status": document.lifecycle_status.value, "expiry_date": document.expiry_date.isoformat() if document.expiry_date else None}
        document.lifecycle_status = payload["lifecycle_status"]
        document.expiry_date = payload.get("expiry_date")
        document.rejection_reason = payload.get("rejection_reason")
        document.reviewer_comments = payload.get("reviewer_comments")
        document.reviewer_user_id = actor.id
        document.review_timestamp = utcnow()
        try:
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="document.reviewed",
                module="documents",
                entity_type="kyc_document",
                entity_id=document.id,
                previous_value=previous_value,
                new_value={"status": document.lifecycle_status.value, "expiry_date": document.expiry_date.isoformat() if document.expiry_date else None},
                reason=document.rejection_reason,
                comment=document.reviewer_comments,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to update document review status.") from exc
        db.refresh(document)
        return document

    @staticmethod
    def summarize_document_checklist(db: Session, client_id: int) -> dict[str, Any]:
        client = PlatformService._get_client_or_raise(db, client_id)
        documents = PlatformService.list_documents(db, client_id)
        required = DEFAULT_DOCUMENT_TYPES[client.client_type]
        uploaded_types = {doc.document_type for doc in documents}
        verified_count = sum(1 for doc in documents if doc.lifecycle_status == DocumentLifecycleStatus.VERIFIED)
        expired_count = sum(1 for doc in documents if doc.lifecycle_status == DocumentLifecycleStatus.EXPIRED)
        resubmission_count = sum(1 for doc in documents if doc.lifecycle_status == DocumentLifecycleStatus.RESUBMISSION_REQUIRED)
        return {
            "client_id": client_id,
            "total_documents": len(documents),
            "verified_documents": verified_count,
            "missing_document_types": sorted(set(required) - uploaded_types),
            "expired_documents": expired_count,
            "requires_resubmission": resubmission_count,
        }

    @staticmethod
    def get_or_create_cdd(db: Session, client_id: int, deal_id: int | None = None) -> CddWorkflow:
        PlatformService._get_client_or_raise(db, client_id)
        stmt = select(CddWorkflow).where(CddWorkflow.client_id == client_id)
        if deal_id is None:
            stmt = stmt.where(CddWorkflow.deal_id.is_(None))
        else:
            stmt = stmt.where(CddWorkflow.deal_id == deal_id)
        workflow = db.execute(stmt.order_by(CddWorkflow.updated_at.desc(), CddWorkflow.id.desc())).scalars().first()
        if workflow is not None:
            return workflow
        workflow = CddWorkflow(client_id=client_id, deal_id=deal_id)
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        return workflow

    @staticmethod
    def upsert_cdd(db: Session, client_id: int, payload: dict[str, Any], actor: User) -> CddWorkflow:
        workflow = PlatformService.get_or_create_cdd(db, client_id, payload.get("deal_id"))
        previous_value = {
            "completion_status": workflow.completion_status.value,
            "analyst_decision": workflow.analyst_decision.value,
            "reviewer_decision": workflow.reviewer_decision.value,
        }
        for field_name, field_value in payload.items():
            setattr(workflow, field_name, field_value)
        try:
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="cdd.updated",
                module="cdd",
                entity_type="cdd_workflow",
                entity_id=workflow.id,
                previous_value=previous_value,
                new_value=payload,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to persist CDD workflow.") from exc
        db.refresh(workflow)
        return workflow

    @staticmethod
    def list_ownership_records(db: Session, client_id: int) -> list[BeneficialOwnershipRecord]:
        PlatformService._get_client_or_raise(db, client_id)
        stmt = select(BeneficialOwnershipRecord).where(BeneficialOwnershipRecord.client_id == client_id).order_by(BeneficialOwnershipRecord.id.asc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_ownership_record(db: Session, client_id: int, payload: dict[str, Any], actor: User) -> BeneficialOwnershipRecord:
        PlatformService._get_client_or_raise(db, client_id)
        if payload.get("deal_id") is not None:
            deal = PlatformService._get_deal_or_raise(db, payload["deal_id"])
            if deal.client_id != client_id:
                raise PlatformValidationError(f"Deal with id={deal.id} does not belong to client id={client_id}.")
        record = BeneficialOwnershipRecord(client_id=client_id, **payload)
        try:
            db.add(record)
            db.flush()
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="ownership.created",
                module="beneficial_ownership",
                entity_type="ownership_record",
                entity_id=record.id,
                new_value=payload,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to persist ownership record.") from exc
        db.refresh(record)
        return record

    @staticmethod
    def update_ownership_record(db: Session, record_id: int, payload: dict[str, Any], actor: User) -> BeneficialOwnershipRecord:
        record = db.execute(select(BeneficialOwnershipRecord).where(BeneficialOwnershipRecord.id == record_id)).scalar_one_or_none()
        if record is None:
            raise PlatformNotFoundError(f"Ownership record with id={record_id} was not found.")
        previous_value = {"ownership_percentage": float(record.ownership_percentage or 0), "control_type": record.control_type}
        for field_name, field_value in payload.items():
            setattr(record, field_name, field_value)
        try:
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="ownership.updated",
                module="beneficial_ownership",
                entity_type="ownership_record",
                entity_id=record.id,
                previous_value=previous_value,
                new_value=payload,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to update ownership record.") from exc
        db.refresh(record)
        return record

    @staticmethod
    def build_ownership_graph(db: Session, client_id: int) -> list[dict[str, Any]]:
        records = PlatformService.list_ownership_records(db, client_id)
        return [
            {
                "id": record.id,
                "owner_name": record.owner_name,
                "parent_record_id": record.parent_record_id,
                "ownership_percentage": record.ownership_percentage,
                "control_type": record.control_type,
                "complexity_score": record.complexity_score,
            }
            for record in records
        ]

    @staticmethod
    def list_risk_overrides(db: Session, client_id: int, deal_id: int | None = None) -> list[RiskOverride]:
        assessment = PlatformService._get_latest_risk_assessment(db, client_id, deal_id)
        if assessment is None:
            return []
        stmt = select(RiskOverride).where(RiskOverride.risk_assessment_id == assessment.id).order_by(RiskOverride.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_risk_override(db: Session, client_id: int, deal_id: int | None, payload: dict[str, Any], actor: User) -> RiskOverride:
        assessment = PlatformService._get_latest_risk_assessment(db, client_id, deal_id)
        if assessment is None:
            raise PlatformValidationError("A risk assessment must exist before a manual override can be recorded.")
        override = RiskOverride(
            risk_assessment_id=assessment.id,
            overridden_by_user_id=actor.id,
            override_level=payload["override_level"],
            justification=payload["justification"],
            notes=payload.get("notes"),
        )
        try:
            db.add(override)
            db.flush()
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="risk.override_created",
                module="risk",
                entity_type="risk_override",
                entity_id=override.id,
                new_value=payload,
                reason=payload["justification"],
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to persist risk override.") from exc
        db.refresh(override)
        return override

    @staticmethod
    def list_edd_cases(db: Session, client_id: int | None = None) -> list[EddCase]:
        stmt = select(EddCase)
        if client_id is not None:
            stmt = stmt.where(EddCase.client_id == client_id)
        stmt = stmt.order_by(EddCase.updated_at.desc(), EddCase.id.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_edd_case(db: Session, client_id: int, payload: dict[str, Any], actor: User) -> EddCase:
        PlatformService._get_client_or_raise(db, client_id)
        edd_case = EddCase(client_id=client_id, **payload)
        try:
            db.add(edd_case)
            db.flush()
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="edd.created",
                module="edd",
                entity_type="edd_case",
                entity_id=edd_case.id,
                new_value=payload,
                reason=payload["trigger_reason"],
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to persist EDD case.") from exc
        db.refresh(edd_case)
        return edd_case

    @staticmethod
    def update_edd_case(db: Session, case_id: int, payload: dict[str, Any], actor: User) -> EddCase:
        edd_case = db.execute(select(EddCase).where(EddCase.id == case_id)).scalar_one_or_none()
        if edd_case is None:
            raise PlatformNotFoundError(f"EDD case with id={case_id} was not found.")
        previous_value = {"status": edd_case.status.value, "priority": edd_case.priority.value}
        for field_name, field_value in payload.items():
            setattr(edd_case, field_name, field_value)
        try:
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="edd.updated",
                module="edd",
                entity_type="edd_case",
                entity_id=edd_case.id,
                previous_value=previous_value,
                new_value=payload,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to update EDD case.") from exc
        db.refresh(edd_case)
        return edd_case

    @staticmethod
    def list_alerts(db: Session, client_id: int | None = None) -> list[MonitoringAlert]:
        stmt = select(MonitoringAlert)
        if client_id is not None:
            stmt = stmt.where(MonitoringAlert.client_id == client_id)
        stmt = stmt.order_by(MonitoringAlert.updated_at.desc(), MonitoringAlert.id.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_alert(db: Session, client_id: int, payload: dict[str, Any], actor: User) -> MonitoringAlert:
        PlatformService._get_client_or_raise(db, client_id)
        alert = MonitoringAlert(client_id=client_id, **payload)
        try:
            db.add(alert)
            db.flush()
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="alert.created",
                module="monitoring",
                entity_type="monitoring_alert",
                entity_id=alert.id,
                new_value=payload,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to persist alert.") from exc
        db.refresh(alert)
        return alert

    @staticmethod
    def update_alert(db: Session, alert_id: int, payload: dict[str, Any], actor: User) -> MonitoringAlert:
        alert = db.execute(select(MonitoringAlert).where(MonitoringAlert.id == alert_id)).scalar_one_or_none()
        if alert is None:
            raise PlatformNotFoundError(f"Alert with id={alert_id} was not found.")
        previous_value = {"status": alert.status.value, "severity": alert.severity.value}
        for field_name, field_value in payload.items():
            setattr(alert, field_name, field_value)
        if alert.status == AlertStatus.CLOSED:
            alert.resolved_at = utcnow()
        try:
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="alert.updated",
                module="monitoring",
                entity_type="monitoring_alert",
                entity_id=alert.id,
                previous_value=previous_value,
                new_value=payload,
                reason=payload.get("closure_reason"),
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to update alert.") from exc
        db.refresh(alert)
        return alert

    @staticmethod
    def list_monitoring_events(db: Session, client_id: int | None = None) -> list[MonitoringEvent]:
        stmt = select(MonitoringEvent)
        if client_id is not None:
            stmt = stmt.where(MonitoringEvent.client_id == client_id)
        stmt = stmt.order_by(MonitoringEvent.created_at.desc(), MonitoringEvent.id.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def run_monitoring(db: Session, client_id: int, deal_id: int | None, actor: User, reason: str | None = None) -> list[MonitoringAlert]:
        client = PlatformService._get_client_or_raise(db, client_id)
        alerts: list[MonitoringAlert] = []
        checklist = PlatformService.summarize_document_checklist(db, client_id)
        high_risk = PlatformService._get_latest_risk_assessment(db, client_id, deal_id)
        ownership_records = PlatformService.list_ownership_records(db, client_id)
        open_edd_cases = PlatformService.list_edd_cases(db, client_id)

        generated_payloads: list[dict[str, Any]] = []
        if checklist["missing_document_types"]:
            generated_payloads.append(
                {
                    "module": "documents",
                    "alert_type": "missing_required_document",
                    "severity": AlertSeverity.HIGH,
                    "status": AlertStatus.OPEN,
                    "disposition": ", ".join(checklist["missing_document_types"]),
                    "due_at": utcnow() + timedelta(days=2),
                }
            )
        if checklist["expired_documents"] > 0:
            generated_payloads.append(
                {
                    "module": "documents",
                    "alert_type": "expired_document",
                    "severity": AlertSeverity.HIGH,
                    "status": AlertStatus.OPEN,
                    "disposition": f"{checklist['expired_documents']} expired document(s)",
                    "due_at": utcnow() + timedelta(days=1),
                }
            )
        if high_risk is not None and high_risk.risk_level == RiskLevel.HIGH:
            generated_payloads.append(
                {
                    "module": "risk",
                    "alert_type": "high_risk_client",
                    "severity": AlertSeverity.CRITICAL,
                    "status": AlertStatus.OPEN,
                    "disposition": high_risk.summary,
                    "due_at": utcnow() + timedelta(days=1),
                }
            )
        if any((record.complexity_score or Decimal("0")) >= Decimal("70") for record in ownership_records):
            generated_payloads.append(
                {
                    "module": "beneficial_ownership",
                    "alert_type": "beneficial_ownership_change",
                    "severity": AlertSeverity.HIGH,
                    "status": AlertStatus.OPEN,
                    "disposition": "Complex ownership score above threshold.",
                    "due_at": utcnow() + timedelta(days=3),
                }
            )
        if any(
            case.status not in {EddCaseStatus.CLOSED, EddCaseStatus.APPROVED, EddCaseStatus.REJECTED}
            and coerce_utc(case.created_at) < utcnow() - timedelta(days=7)
            for case in open_edd_cases
        ):
            generated_payloads.append(
                {
                    "module": "edd",
                    "alert_type": "unresolved_edd_aging",
                    "severity": AlertSeverity.MEDIUM,
                    "status": AlertStatus.OPEN,
                    "disposition": "EDD case aging beyond 7 days.",
                    "due_at": utcnow() + timedelta(days=1),
                }
            )

        try:
            event = MonitoringEvent(
                client_id=client_id,
                deal_id=deal_id,
                event_type="monitoring_run",
                event_source="manual",
                summary=reason or f"Monitoring run executed for client {client.primary_name}.",
                details={"generated_alert_count": len(generated_payloads)},
                triggered_by_user_id=actor.id,
            )
            db.add(event)
            db.flush()
            for payload in generated_payloads:
                existing = db.execute(
                    select(MonitoringAlert).where(
                        MonitoringAlert.client_id == client_id,
                        MonitoringAlert.alert_type == payload["alert_type"],
                        MonitoringAlert.status != AlertStatus.CLOSED,
                    )
                ).scalars().first()
                if existing is not None:
                    alerts.append(existing)
                    continue
                alert = MonitoringAlert(client_id=client_id, deal_id=deal_id, **payload)
                db.add(alert)
                db.flush()
                alerts.append(alert)
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="monitoring.run",
                module="monitoring",
                entity_type="client",
                entity_id=client_id,
                new_value={"deal_id": deal_id, "generated_alerts": len(alerts)},
                reason=reason,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise PlatformConflictError("Unable to complete monitoring run.") from exc
        for alert in alerts:
            db.refresh(alert)
        return alerts

    @staticmethod
    def build_workbench_queue(db: Session, filters: dict[str, Any] | None = None) -> list[WorkbenchItem]:
        filters = filters or {}
        items: list[WorkbenchItem] = []

        documents = db.execute(
            select(KycDocument).where(
                KycDocument.lifecycle_status.in_(
                    [
                        DocumentLifecycleStatus.SUBMITTED,
                        DocumentLifecycleStatus.UNDER_REVIEW,
                        DocumentLifecycleStatus.RESUBMISSION_REQUIRED,
                    ]
                )
            )
        ).scalars().all()
        items.extend(
            WorkbenchItem(
                module="documents",
                item_type="document_review",
                item_id=document.id,
                client_id=document.client_id,
                deal_id=document.deal_id,
                title=f"{document.document_type} review",
                status=document.lifecycle_status.value,
                severity_or_priority="medium",
                assigned_user_id=document.reviewer_user_id,
                updated_at=document.updated_at,
            )
            for document in documents
        )

        cdds = db.execute(
            select(CddWorkflow).where(CddWorkflow.completion_status != WorkflowStatus.COMPLETED)
        ).scalars().all()
        items.extend(
            WorkbenchItem(
                module="cdd",
                item_type="cdd_task",
                item_id=workflow.id,
                client_id=workflow.client_id,
                deal_id=workflow.deal_id,
                title="CDD workflow pending",
                status=workflow.completion_status.value,
                severity_or_priority=workflow.analyst_decision.value,
                assigned_user_id=workflow.assigned_analyst_id,
                updated_at=workflow.updated_at,
            )
            for workflow in cdds
        )

        cases = db.execute(
            select(EddCase).where(EddCase.status != EddCaseStatus.CLOSED)
        ).scalars().all()
        items.extend(
            WorkbenchItem(
                module="edd",
                item_type="edd_case",
                item_id=case.id,
                client_id=case.client_id,
                deal_id=case.deal_id,
                title=case.case_type,
                status=case.status.value,
                severity_or_priority=case.priority.value,
                assigned_user_id=case.assigned_analyst_id,
                updated_at=case.updated_at,
            )
            for case in cases
        )

        alerts = db.execute(select(MonitoringAlert).where(MonitoringAlert.status != AlertStatus.CLOSED)).scalars().all()
        items.extend(
            WorkbenchItem(
                module="monitoring",
                item_type="alert",
                item_id=alert.id,
                client_id=alert.client_id,
                deal_id=alert.deal_id,
                title=alert.alert_type,
                status=alert.status.value,
                severity_or_priority=alert.severity.value,
                assigned_user_id=alert.assigned_user_id,
                updated_at=alert.updated_at,
            )
            for alert in alerts
        )

        candidates = db.execute(select(ScreeningCandidate).where(ScreeningCandidate.disposition == CandidateDisposition.PENDING)).scalars().all()
        items.extend(
            WorkbenchItem(
                module="screening",
                item_type="screening_hit",
                item_id=candidate.id,
                client_id=None,
                deal_id=None,
                title=candidate.matched_name,
                status=candidate.disposition.value,
                severity_or_priority=candidate.match_category.value,
                assigned_user_id=None,
                updated_at=candidate.updated_at,
            )
            for candidate in candidates
        )

        filtered_items = [
            item
            for item in items
            if (filters.get("status") is None or item.status == filters["status"])
            and (filters.get("assignee_id") is None or item.assigned_user_id == filters["assignee_id"])
            and (filters.get("client_id") is None or item.client_id == filters["client_id"])
            and (filters.get("module") is None or item.module == filters["module"])
        ]
        return sorted(filtered_items, key=lambda item: item.updated_at, reverse=True)

    @staticmethod
    def list_settings(db: Session) -> list[AppSetting]:
        stmt = select(AppSetting).order_by(AppSetting.key.asc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def upsert_setting(db: Session, payload: dict[str, Any], actor: User) -> AppSetting:
        stmt = select(AppSetting).where(AppSetting.key == payload["key"])
        setting = db.execute(stmt).scalar_one_or_none()
        if setting is None:
            setting = AppSetting(
                key=payload["key"],
                value_json=payload.get("value_json"),
                description=payload.get("description"),
                updated_by_user_id=actor.id,
            )
            db.add(setting)
            db.flush()
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="setting.created",
                module="administration",
                entity_type="app_setting",
                entity_id=setting.id,
                new_value=payload.get("value_json"),
                comment=payload.get("description"),
            )
        else:
            previous_value = setting.value_json
            setting.value_json = payload.get("value_json")
            setting.description = payload.get("description")
            setting.updated_by_user_id = actor.id
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="setting.updated",
                module="administration",
                entity_type="app_setting",
                entity_id=setting.id,
                previous_value=previous_value,
                new_value=setting.value_json,
            )
        db.commit()
        db.refresh(setting)
        return setting

    @staticmethod
    def list_audit_events(db: Session, limit: int = 200) -> list[AuditEvent]:
        stmt = select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(limit)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def build_report_rows(db: Session, report_name: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        if report_name == "kyc_completeness":
            rows = []
            for intake in PlatformService.list_intake_records(db):
                checklist = PlatformService.summarize_document_checklist(db, intake.client_id)
                profile = PlatformService.get_kyc_profile(db, intake.client_id)
                rows.append(
                    {
                        "client_id": intake.client_id,
                        "client_name": intake.primary_name,
                        "kyc_status": profile.onboarding_status.value if profile is not None else "missing",
                        "missing_documents": ", ".join(checklist["missing_document_types"]),
                        "verified_documents": checklist["verified_documents"],
                    }
                )
            return rows
        if report_name == "document_expiry":
            documents = db.execute(select(KycDocument).where(KycDocument.expiry_date.is_not(None))).scalars().all()
            return [
                {
                    "client_id": document.client_id,
                    "document_type": document.document_type,
                    "file_name": document.file_name,
                    "expiry_date": document.expiry_date.isoformat() if document.expiry_date else None,
                    "status": document.lifecycle_status.value,
                }
                for document in documents
            ]
        if report_name == "screening_history":
            results = db.execute(select(ScreeningResult).order_by(ScreeningResult.screened_at.desc())).scalars().all()
            return [
                {
                    "screening_result_id": result.id,
                    "client_id": result.client_id,
                    "linked_party_id": result.linked_party_id,
                    "provider": result.provider_name,
                    "status": result.status.value,
                    "screened_at": result.screened_at.isoformat(),
                }
                for result in results
            ]
        if report_name == "open_edd_aging":
            cases = db.execute(select(EddCase).where(EddCase.status != EddCaseStatus.CLOSED)).scalars().all()
            return [
                {
                    "edd_case_id": case.id,
                    "client_id": case.client_id,
                    "case_type": case.case_type,
                    "priority": case.priority.value,
                    "status": case.status.value,
                    "age_days": max(0, (utcnow() - coerce_utc(case.created_at)).days),
                }
                for case in cases
            ]
        if report_name == "alert_summary":
            alerts = PlatformService.list_alerts(db)
            return [
                {
                    "alert_id": alert.id,
                    "client_id": alert.client_id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "module": alert.module,
                }
                for alert in alerts
            ]
        if report_name == "high_risk_clients":
            risks = db.execute(select(RiskAssessment).where(RiskAssessment.risk_level == RiskLevel.HIGH)).scalars().all()
            return [
                {
                    "risk_assessment_id": risk.id,
                    "client_id": risk.client_id,
                    "deal_id": risk.deal_id,
                    "risk_level": risk.risk_level.value,
                    "total_score": float(risk.total_score),
                    "summary": risk.summary,
                }
                for risk in risks
            ]
        if report_name == "audit_export":
            events = PlatformService.list_audit_events(db, limit=500)
            return [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "actor": event.actor,
                    "module": event.module,
                    "action": event.action,
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                }
                for event in events
            ]
        raise PlatformValidationError(f"Unsupported report name '{report_name}'.")

    @staticmethod
    def build_csv(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return ""
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()

    @staticmethod
    def maybe_create_edd_from_screening(db: Session, client_id: int, actor: User, candidate_id: int, reason: str) -> None:
        candidate = db.execute(select(ScreeningCandidate).where(ScreeningCandidate.id == candidate_id)).scalar_one_or_none()
        if candidate is None:
            return
        existing = db.execute(
            select(EddCase).where(
                EddCase.client_id == client_id,
                EddCase.case_type == "screening_escalation",
                EddCase.trigger_reason == reason,
                EddCase.status != EddCaseStatus.CLOSED,
            )
        ).scalars().first()
        if existing is not None:
            return
        PlatformService.create_edd_case(
            db,
            client_id,
            {
                "case_type": "screening_escalation",
                "source_module": "screening",
                "trigger_reason": reason,
                "priority": EddCasePriority.HIGH if candidate.match_category in {MatchCategory.PEP, MatchCategory.RCA} else EddCasePriority.MEDIUM,
                "status": EddCaseStatus.OPEN,
                "required_actions": {"candidate_id": candidate_id, "action": "Review confirmed screening escalation"},
            },
            actor,
        )

    @staticmethod
    def _get_client_or_raise(db: Session, client_id: int) -> Client:
        client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
        if client is None:
            raise PlatformNotFoundError(f"Client with id={client_id} was not found.")
        return client

    @staticmethod
    def _get_deal_or_raise(db: Session, deal_id: int) -> Deal:
        deal = db.execute(select(Deal).where(Deal.id == deal_id)).scalar_one_or_none()
        if deal is None:
            raise PlatformNotFoundError(f"Deal with id={deal_id} was not found.")
        return deal

    @staticmethod
    def _get_latest_risk_assessment(db: Session, client_id: int, deal_id: int | None) -> RiskAssessment | None:
        stmt = select(RiskAssessment).where(RiskAssessment.client_id == client_id)
        if deal_id is None:
            stmt = stmt.order_by(RiskAssessment.assessed_at.desc(), RiskAssessment.id.desc())
        else:
            stmt = stmt.where(or_(RiskAssessment.deal_id == deal_id, RiskAssessment.deal_id.is_(None))).order_by(
                RiskAssessment.assessed_at.desc(),
                RiskAssessment.id.desc(),
            )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def _extract_email(contact_details: str | None) -> str | None:
        if not contact_details:
            return None
        match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", contact_details)
        return match.group(0) if match else None

    @staticmethod
    def _extract_phone(contact_details: str | None) -> str | None:
        if not contact_details:
            return None
        match = re.search(r"\+?[0-9][0-9()\-\s]{6,}", contact_details)
        return match.group(0).strip() if match else None
