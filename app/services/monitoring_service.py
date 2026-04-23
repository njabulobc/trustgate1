from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertStatus, AlertType
from app.models.screening import ScreeningResult, ScreeningSubjectType
from app.services.audit_service import record_audit_event


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MonitoringServiceError(Exception):
    pass


class MonitoringPersistenceError(MonitoringServiceError):
    pass


class MonitoringNotFoundError(MonitoringServiceError):
    pass


class MonitoringService:
    @staticmethod
    def run_periodic_rescreening_checks(db: Session, days_since_last_screening: int = 30, actor: str = "system") -> list[Alert]:
        cutoff = utcnow() - timedelta(days=days_since_last_screening)
        stmt = select(ScreeningResult).where(
            ScreeningResult.subject_type == ScreeningSubjectType.CLIENT,
            ScreeningResult.screened_at < cutoff,
        )
        old_results = list(db.execute(stmt).scalars().all())

        created_alerts: list[Alert] = []
        try:
            for screening in old_results:
                alert = Alert(
                    client_id=screening.client_id,
                    linked_party_id=screening.linked_party_id,
                    alert_type=AlertType.MONITORING,
                    status=AlertStatus.OPEN,
                    title="Periodic re-screening due",
                    description=f"Subject from screening result {screening.id} is due for re-screening.",
                )
                db.add(alert)
                db.flush()
                created_alerts.append(alert)
                record_audit_event(
                    db=db,
                    actor=actor,
                    action="alert.created",
                    entity_type="alert",
                    entity_id=alert.id,
                    metadata_payload={"alert_type": alert.alert_type.value, "client_id": alert.client_id},
                )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise MonitoringPersistenceError("Unable to generate monitoring alerts due to persistence constraints.") from exc

        for alert in created_alerts:
            db.refresh(alert)
        return created_alerts

    @staticmethod
    def list_alerts(db: Session, client_id: int | None = None, status_filter: AlertStatus | None = None) -> list[Alert]:
        stmt = select(Alert)
        if client_id is not None:
            stmt = stmt.where(Alert.client_id == client_id)
        if status_filter is not None:
            stmt = stmt.where(Alert.status == status_filter)
        stmt = stmt.order_by(Alert.created_at.desc(), Alert.id.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_alert_status(db: Session, alert_id: int, new_status: AlertStatus, actor: str = "demo_user") -> Alert:
        alert = db.execute(select(Alert).where(Alert.id == alert_id)).scalar_one_or_none()
        if alert is None:
            raise MonitoringNotFoundError(f"Alert with id={alert_id} was not found.")

        alert.status = new_status
        if new_status == AlertStatus.RESOLVED:
            alert.resolved_at = utcnow()

        try:
            record_audit_event(
                db=db,
                actor=actor,
                action="alert.updated",
                entity_type="alert",
                entity_id=alert.id,
                metadata_payload={"status": alert.status.value},
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise MonitoringPersistenceError("Unable to update alert due to persistence constraints.") from exc

        db.refresh(alert)
        return alert


def run_periodic_rescreening_checks(db: Session, days_since_last_screening: int = 30, actor: str = "system") -> list[Alert]:
    return MonitoringService.run_periodic_rescreening_checks(db, days_since_last_screening, actor)


def list_alerts(db: Session, client_id: int | None = None, status_filter: AlertStatus | None = None) -> list[Alert]:
    return MonitoringService.list_alerts(db, client_id, status_filter)


def update_alert_status(db: Session, alert_id: int, new_status: AlertStatus, actor: str = "demo_user") -> Alert:
    return MonitoringService.update_alert_status(db, alert_id, new_status, actor)
