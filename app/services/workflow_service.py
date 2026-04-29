from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.workflow import QueueStatus, WorkflowCase


class WorkflowError(Exception):
    pass


class WorkflowNotFoundError(WorkflowError):
    pass


class WorkflowValidationError(WorkflowError):
    pass


def ensure_workflow_case(db: Session, deal_id: int) -> WorkflowCase:
    case = db.scalar(select(WorkflowCase).where(WorkflowCase.deal_id == deal_id))
    if case:
        return case

    deal = db.scalar(select(Deal).where(Deal.id == deal_id))
    if not deal:
        raise WorkflowNotFoundError(f"Deal {deal_id} not found")

    case = WorkflowCase(deal_id=deal.id, client_id=deal.client_id, status=QueueStatus.NEW)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def queue_case(db: Session, deal_id: int, notes: str | None = None) -> WorkflowCase:
    case = ensure_workflow_case(db, deal_id)
    case.status = QueueStatus.QUEUED
    case.queue_notes = notes
    db.commit()
    db.refresh(case)
    return case


def assign_case(db: Session, deal_id: int, assigned_reviewer: str) -> WorkflowCase:
    case = ensure_workflow_case(db, deal_id)
    case.assigned_reviewer = assigned_reviewer
    if case.status == QueueStatus.NEW:
        case.status = QueueStatus.QUEUED
    db.commit()
    db.refresh(case)
    return case


def transition_case_status(db: Session, deal_id: int, status: QueueStatus) -> WorkflowCase:
    case = ensure_workflow_case(db, deal_id)
    if status == QueueStatus.IN_REVIEW and not case.assigned_reviewer:
        raise WorkflowValidationError("Assign reviewer before moving to in_review")
    case.status = status
    db.commit()
    db.refresh(case)
    return case


def list_workflow_cases(
    db: Session,
    *,
    page: int,
    page_size: int,
    status: QueueStatus | None,
    assigned_reviewer: str | None,
    search: str | None,
) -> tuple[list[WorkflowCase], int]:
    stmt = select(WorkflowCase)
    if status:
        stmt = stmt.where(WorkflowCase.status == status)
    if assigned_reviewer:
        stmt = stmt.where(WorkflowCase.assigned_reviewer == assigned_reviewer)
    if search:
        stmt = stmt.where(WorkflowCase.queue_notes.ilike(f"%{search}%"))

    all_rows = db.scalars(stmt.order_by(WorkflowCase.updated_at.desc())).all()
    total = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    return all_rows[start:end], total
