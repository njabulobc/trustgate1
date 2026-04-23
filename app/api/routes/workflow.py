from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DBSession, require_roles
from app.core.auth import UserRole
from app.models.workflow import QueueStatus
from app.schemas.workflow import (
    WorkflowAssignmentRequest,
    WorkflowCaseListResponse,
    WorkflowCaseRead,
    WorkflowQueueRequest,
    WorkflowStatusRequest,
)
from app.services.workflow_service import (
    WorkflowNotFoundError,
    WorkflowValidationError,
    assign_case,
    list_workflow_cases,
    queue_case,
    transition_case_status,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.get("/cases", response_model=WorkflowCaseListResponse, dependencies=[Depends(require_roles(UserRole.ANALYST, UserRole.REVIEWER))])
def get_cases(
    db: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    status_filter: QueueStatus | None = Query(default=None, alias="status"),
    assigned_reviewer: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> WorkflowCaseListResponse:
    items, total = list_workflow_cases(
        db,
        page=page,
        page_size=page_size,
        status=status_filter,
        assigned_reviewer=assigned_reviewer,
        search=search,
    )
    return WorkflowCaseListResponse(items=[WorkflowCaseRead.model_validate(item) for item in items], page=page, page_size=page_size, total=total)


@router.post("/deals/{deal_id}/queue", response_model=WorkflowCaseRead, dependencies=[Depends(require_roles(UserRole.ANALYST, UserRole.REVIEWER))])
def queue_workflow_case(deal_id: int, payload: WorkflowQueueRequest, db: DBSession) -> WorkflowCaseRead:
    try:
        case = queue_case(db, deal_id, payload.notes)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return WorkflowCaseRead.model_validate(case)


@router.patch("/deals/{deal_id}/assign", response_model=WorkflowCaseRead, dependencies=[Depends(require_roles(UserRole.REVIEWER))])
def assign_workflow_case(deal_id: int, payload: WorkflowAssignmentRequest, db: DBSession) -> WorkflowCaseRead:
    try:
        case = assign_case(db, deal_id, payload.assigned_reviewer)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return WorkflowCaseRead.model_validate(case)


@router.patch("/deals/{deal_id}/status", response_model=WorkflowCaseRead, dependencies=[Depends(require_roles(UserRole.REVIEWER))])
def update_case_status(deal_id: int, payload: WorkflowStatusRequest, db: DBSession) -> WorkflowCaseRead:
    try:
        case = transition_case_status(db, deal_id, payload.status)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkflowCaseRead.model_validate(case)
