from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.auth import UserRead
from app.schemas.platform import AdminOverview, AppSettingRead, AppSettingWrite, AuditEventRead
from app.services.auth_service import AuthService
from app.services.platform_service import PlatformService

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/overview", response_model=AdminOverview)
def read_admin_overview(
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR)),
) -> AdminOverview:
    users = [
        {
            "id": item.id,
            "username": item.username,
            "full_name": item.full_name,
            "email": item.email,
            "role": item.role.value,
            "is_active": item.is_active,
        }
        for item in AuthService.list_users(db=db)
    ]
    settings = [AppSettingRead.model_validate(item) for item in PlatformService.list_settings(db=db)]
    audit_events = [AuditEventRead.model_validate(item) for item in PlatformService.list_audit_events(db=db)]
    return AdminOverview(users=users, settings=settings, audit_events=audit_events)


@router.get("/settings", response_model=list[AppSettingRead])
def list_settings(
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR)),
) -> list[AppSettingRead]:
    return [AppSettingRead.model_validate(item) for item in PlatformService.list_settings(db=db)]


@router.put("/settings/{key}", response_model=AppSettingRead)
def upsert_setting(
    key: str,
    payload: AppSettingWrite,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR)),
) -> AppSettingRead:
    if payload.key != key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Setting key in path and body must match.")
    setting = PlatformService.upsert_setting(db=db, payload=payload.model_dump(), actor=user)
    return AppSettingRead.model_validate(setting)
