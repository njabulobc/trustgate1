from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.platform import EddCaseRead, EddCaseWrite
from app.services.platform_service import PlatformConflictError, PlatformNotFoundError, PlatformService

router = APIRouter(prefix="/edd", tags=["edd"])


@router.get("/cases", response_model=list[EddCaseRead])
def list_edd_cases(
    db: DBSession,
    user: CurrentUser,
    client_id: int | None = Query(default=None),
) -> list[EddCaseRead]:
    return [EddCaseRead.model_validate(item) for item in PlatformService.list_edd_cases(db=db, client_id=client_id)]


@router.post("/clients/{client_id}/cases", response_model=EddCaseRead, status_code=status.HTTP_201_CREATED)
def create_edd_case(
    client_id: int,
    payload: EddCaseWrite,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> EddCaseRead:
    try:
        case = PlatformService.create_edd_case(db=db, client_id=client_id, payload=payload.model_dump(), actor=user)
    except (PlatformNotFoundError, PlatformConflictError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, PlatformNotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return EddCaseRead.model_validate(case)


@router.patch("/cases/{case_id}", response_model=EddCaseRead)
def update_edd_case(
    case_id: int,
    payload: EddCaseWrite,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> EddCaseRead:
    try:
        case = PlatformService.update_edd_case(db=db, case_id=case_id, payload=payload.model_dump(), actor=user)
    except (PlatformNotFoundError, PlatformConflictError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, PlatformNotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return EddCaseRead.model_validate(case)
