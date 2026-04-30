from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.platform import KycProfileRead, KycProfileWrite
from app.services.platform_service import PlatformConflictError, PlatformNotFoundError, PlatformService

router = APIRouter(prefix="/kyc", tags=["kyc"])


@router.get("/clients/{client_id}", response_model=KycProfileRead | None)
def read_kyc_profile(client_id: int, db: DBSession, user: CurrentUser) -> KycProfileRead | None:
    try:
        profile = PlatformService.get_kyc_profile(db=db, client_id=client_id)
    except PlatformNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KycProfileRead.model_validate(profile) if profile is not None else None


@router.put("/clients/{client_id}", response_model=KycProfileRead)
def upsert_kyc_profile(
    client_id: int,
    payload: KycProfileWrite,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> KycProfileRead:
    try:
        profile = PlatformService.upsert_kyc_profile(
            db=db,
            client_id=client_id,
            payload=payload.model_dump(),
            actor=user,
        )
    except (PlatformNotFoundError, PlatformConflictError) as exc:
        status_code = status.HTTP_404_NOT_FOUND if isinstance(exc, PlatformNotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return KycProfileRead.model_validate(profile)
