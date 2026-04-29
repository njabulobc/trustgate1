from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.edd_case import EddCase, EddStatus
from app.schemas.edd import EddCaseCreate
from app.services.audit_service import record_audit_event


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_ALLOWED = {
    EddStatus.OPEN: {EddStatus.ASSIGNED, EddStatus.IN_REVIEW, EddStatus.CLOSED},
    EddStatus.ASSIGNED: {EddStatus.IN_REVIEW, EddStatus.ESCALATED, EddStatus.CLOSED},
    EddStatus.IN_REVIEW: {EddStatus.ESCALATED, EddStatus.APPROVED, EddStatus.REJECTED, EddStatus.CLOSED},
    EddStatus.ESCALATED: {EddStatus.IN_REVIEW, EddStatus.APPROVED, EddStatus.REJECTED, EddStatus.CLOSED},
    EddStatus.APPROVED: {EddStatus.CLOSED},
    EddStatus.REJECTED: {EddStatus.CLOSED},
    EddStatus.CLOSED: set(),
}


class EddServiceError(Exception): ...
class EddValidationError(EddServiceError): ...
class EddNotFoundError(EddServiceError): ...


class EddService:
    @staticmethod
    def create_case(db: Session, payload: EddCaseCreate, *, actor: str = "demo_user") -> EddCase:
        if payload.screening_candidate_id:
            existing = db.execute(select(EddCase).where(EddCase.screening_candidate_id == payload.screening_candidate_id)).scalar_one_or_none()
            if existing:
                return existing
        if payload.risk_assessment_id:
            existing = db.execute(select(EddCase).where(EddCase.risk_assessment_id == payload.risk_assessment_id)).scalar_one_or_none()
            if existing:
                return existing
        case = EddCase(**payload.model_dump())
        db.add(case)
        try:
            db.flush()
            record_audit_event(db=db, actor=actor, action="edd_case.created", entity_type="edd_case", entity_id=case.id, metadata_payload={"status": case.status.value, "trigger": case.trigger_type.value})
            db.commit()
        except IntegrityError as exc:
            db.rollback(); raise EddValidationError("Unable to create EDD case due to integrity constraints.") from exc
        db.refresh(case)
        return case

    @staticmethod
    def list_cases(db: Session, *, status: EddStatus | None = None, assignee: str | None = None) -> list[EddCase]:
        stmt = select(EddCase)
        if status:
            stmt = stmt.where(EddCase.status == status)
        if assignee:
            stmt = stmt.where(EddCase.assignee == assignee)
        return list(db.execute(stmt.order_by(EddCase.updated_at.desc(), EddCase.id.desc())).scalars().all())

    @staticmethod
    def get_case(db: Session, case_id: int) -> EddCase:
        case = db.execute(select(EddCase).where(EddCase.id == case_id)).scalar_one_or_none()
        if not case:
            raise EddNotFoundError(f"EDD case with id={case_id} not found.")
        return case

    @staticmethod
    def assign_case(db: Session, case_id: int, assignee: str, *, actor: str = "demo_user") -> EddCase:
        case = EddService.get_case(db, case_id)
        case.assignee = assignee
        if case.status == EddStatus.OPEN:
            case.status = EddStatus.ASSIGNED
            case.acknowledged_at = utcnow()
        record_audit_event(db=db, actor=actor, action="edd_case.assigned", entity_type="edd_case", entity_id=case.id, metadata_payload={"assignee": assignee, "status": case.status.value})
        db.commit(); db.refresh(case); return case

    @staticmethod
    def transition_case(db: Session, case_id: int, new_status: EddStatus, *, actor: str = "demo_user") -> EddCase:
        case = EddService.get_case(db, case_id)
        if new_status == case.status:
            return case
        if new_status not in _ALLOWED[case.status]:
            raise EddValidationError(f"Invalid transition from {case.status.value} to {new_status.value}.")
        case.status = new_status
        now = utcnow()
        if new_status == EddStatus.IN_REVIEW and case.started_at is None:
            case.started_at = now
        if new_status == EddStatus.ESCALATED:
            case.escalated_at = now
        record_audit_event(db=db, actor=actor, action="edd_case.transitioned", entity_type="edd_case", entity_id=case.id, metadata_payload={"status": case.status.value})
        db.commit(); db.refresh(case); return case

    @staticmethod
    def close_case(db: Session, case_id: int, reason: str, evidence: dict | None, *, actor: str = "demo_user") -> EddCase:
        case = EddService.get_case(db, case_id)
        case.status = EddStatus.CLOSED
        case.closed_at = utcnow()
        case.closure_reason = reason
        case.closure_evidence = evidence
        record_audit_event(db=db, actor=actor, action="edd_case.closed", entity_type="edd_case", entity_id=case.id, metadata_payload={"reason": reason})
        db.commit(); db.refresh(case); return case
