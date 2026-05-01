from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.platform import OwnershipGraphNode, OwnershipRecordRead, OwnershipRecordWrite
from app.services.platform_service import PlatformConflictError, PlatformNotFoundError, PlatformService, PlatformValidationError

router = APIRouter(prefix="/ownership", tags=["beneficial_ownership"])


@router.get("/clients/{client_id}", response_model=list[OwnershipRecordRead])
def list_ownership_records(client_id: int, db: DBSession, user: CurrentUser) -> list[OwnershipRecordRead]:
    try:
        records = PlatformService.list_ownership_records(db=db, client_id=client_id)
    except PlatformNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [OwnershipRecordRead.model_validate(item) for item in records]


@router.get("/clients/{client_id}/graph", response_model=list[OwnershipGraphNode])
def read_ownership_graph(client_id: int, db: DBSession, user: CurrentUser) -> list[OwnershipGraphNode]:
    try:
        return [OwnershipGraphNode.model_validate(item) for item in PlatformService.build_ownership_graph(db=db, client_id=client_id)]
    except PlatformNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/clients/{client_id}", response_model=OwnershipRecordRead, status_code=status.HTTP_201_CREATED)
def create_ownership_record(
    client_id: int,
    payload: OwnershipRecordWrite,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> OwnershipRecordRead:
    try:
        record = PlatformService.create_ownership_record(db=db, client_id=client_id, payload=payload.model_dump(), actor=user)
    except (PlatformNotFoundError, PlatformConflictError, PlatformValidationError) as exc:
        if isinstance(exc, PlatformConflictError):
            code = status.HTTP_409_CONFLICT
        elif isinstance(exc, PlatformValidationError):
            code = status.HTTP_400_BAD_REQUEST
        else:
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return OwnershipRecordRead.model_validate(record)


@router.patch("/{record_id}", response_model=OwnershipRecordRead)
def update_ownership_record(
    record_id: int,
    payload: OwnershipRecordWrite,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> OwnershipRecordRead:
    try:
        record = PlatformService.update_ownership_record(db=db, record_id=record_id, payload=payload.model_dump(), actor=user)
    except (PlatformNotFoundError, PlatformConflictError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, PlatformNotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return OwnershipRecordRead.model_validate(record)
