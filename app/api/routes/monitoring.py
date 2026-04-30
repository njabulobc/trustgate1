from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.platform import AlertRead, AlertWrite, MonitoringEventRead, MonitoringRunRequest
from app.services.platform_service import PlatformConflictError, PlatformNotFoundError, PlatformService

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(
    db: DBSession,
    user: CurrentUser,
    client_id: int | None = Query(default=None),
) -> list[AlertRead]:
    return [AlertRead.model_validate(item) for item in PlatformService.list_alerts(db=db, client_id=client_id)]


@router.get("/events", response_model=list[MonitoringEventRead])
def list_events(
    db: DBSession,
    user: CurrentUser,
    client_id: int | None = Query(default=None),
) -> list[MonitoringEventRead]:
    return [MonitoringEventRead.model_validate(item) for item in PlatformService.list_monitoring_events(db=db, client_id=client_id)]


@router.post("/run", response_model=list[AlertRead])
def run_monitoring(
    payload: MonitoringRunRequest,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> list[AlertRead]:
    try:
        alerts = PlatformService.run_monitoring(
            db=db,
            client_id=payload.client_id,
            deal_id=payload.deal_id,
            actor=user,
            reason=payload.reason,
        )
    except (PlatformNotFoundError, PlatformConflictError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, PlatformNotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return [AlertRead.model_validate(item) for item in alerts]


@router.post("/clients/{client_id}/alerts", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
def create_alert(
    client_id: int,
    payload: AlertWrite,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST)),
) -> AlertRead:
    try:
        alert = PlatformService.create_alert(db=db, client_id=client_id, payload=payload.model_dump(), actor=user)
    except (PlatformNotFoundError, PlatformConflictError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, PlatformNotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return AlertRead.model_validate(alert)


@router.patch("/alerts/{alert_id}", response_model=AlertRead)
def update_alert(
    alert_id: int,
    payload: AlertWrite,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST, UserRole.REVIEWER)),
) -> AlertRead:
    try:
        alert = PlatformService.update_alert(db=db, alert_id=alert_id, payload=payload.model_dump(), actor=user)
    except (PlatformNotFoundError, PlatformConflictError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, PlatformNotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return AlertRead.model_validate(alert)
