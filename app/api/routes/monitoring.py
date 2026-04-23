from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.alert import AlertStatus
from app.models.user import UserRole
from app.schemas.monitoring import AlertRead, AlertUpdate
from app.services.monitoring_service import (
    MonitoringNotFoundError,
    MonitoringPersistenceError,
    list_alerts,
    run_periodic_rescreening_checks,
    update_alert_status,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.post(
    "/rescreen",
    response_model=list[AlertRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER))],
)
def run_rescreening_job(
    db: DBSession,
    current_user: CurrentUser,
    days_since_last_screening: int = Query(default=30, ge=1),
) -> list[AlertRead]:
    alerts = run_periodic_rescreening_checks(
        db=db,
        days_since_last_screening=days_since_last_screening,
        actor=current_user.email,
    )
    return [AlertRead.model_validate(alert) for alert in alerts]


@router.get(
    "/alerts",
    response_model=list[AlertRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER, UserRole.VIEWER))],
)
def list_monitoring_alerts(
    db: DBSession,
    current_user: CurrentUser,
    client_id: int | None = Query(default=None),
    status_filter: AlertStatus | None = Query(default=None, alias="status"),
) -> list[AlertRead]:
    alerts = list_alerts(db=db, client_id=client_id, status_filter=status_filter)
    return [AlertRead.model_validate(alert) for alert in alerts]


@router.patch(
    "/alerts/{alert_id}",
    response_model=AlertRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER))],
)
def update_monitoring_alert(
    alert_id: int,
    payload: AlertUpdate,
    db: DBSession,
    current_user: CurrentUser,
) -> AlertRead:
    try:
        alert = update_alert_status(
            db=db,
            alert_id=alert_id,
            new_status=payload.status,
            actor=current_user.email,
        )
    except MonitoringNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MonitoringPersistenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return AlertRead.model_validate(alert)
