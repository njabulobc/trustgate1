from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditService:
    @staticmethod
    def record_event(
        db: Session,
        action: str,
        entity_type: str,
        entity_id: int | str,
        actor: str = "demo_user",
        metadata_payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            metadata_payload=metadata_payload,
        )
        db.add(audit_log)
        db.flush()
        db.refresh(audit_log)
        return audit_log


def record_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: int | str,
    actor: str = "demo_user",
    metadata_payload: dict[str, Any] | None = None,
) -> AuditLog:
    return AuditService.record_event(
        db=db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        metadata_payload=metadata_payload,
    )