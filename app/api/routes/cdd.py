from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.platform import CddWorkflowRead, CddWorkflowWrite
from app.services.platform_service import PlatformConflictError, PlatformNotFoundError, PlatformService

router = APIRouter(prefix="/cdd", tags=["cdd"])


@router.get("/clients/{client_id}", response_model=CddWorkflowRead)
def read_cdd_workflow(
    client_id: int,
    db: DBSession,
    user: CurrentUser,
    deal_id: int | None = Query(default=None),
) -> CddWorkflowRead:
    try:
        workflow = PlatformService.get_or_create_cdd(db=db, client_id=client_id, deal_id=deal_id)
    except PlatformNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CddWorkflowRead.model_validate(workflow)


@router.put("/clients/{client_id}", response_model=CddWorkflowRead)
def upsert_cdd_workflow(
    client_id: int,
    payload: CddWorkflowWrite,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> CddWorkflowRead:
    try:
        workflow = PlatformService.upsert_cdd(
            db=db,
            client_id=client_id,
            payload=payload.model_dump(),
            actor=user,
        )
    except (PlatformNotFoundError, PlatformConflictError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, PlatformNotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return CddWorkflowRead.model_validate(workflow)
