from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.platform import AuditEvent


class AuditService:
    @staticmethod
    def _normalize_json_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            return {str(key): AuditService._normalize_json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [AuditService._normalize_json_value(item) for item in value]
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, enum.Enum):
            return value.value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    @staticmethod
    def record_event(
        db: Session,
        action: str,
        entity_type: str,
        entity_id: int | str,
        actor: str = "demo_user",
        metadata_payload: dict[str, Any] | None = None,
        module: str | None = None,
        previous_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        reason: str | None = None,
        comment: str | None = None,
        user_id: int | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            metadata_payload=AuditService._normalize_json_value(metadata_payload),
        )
        db.add(audit_log)
        db.flush()

        audit_event = AuditEvent(
            user_id=user_id,
            actor=actor,
            action=action,
            module=module or entity_type,
            entity_type=entity_type,
            entity_id=str(entity_id),
            previous_value=AuditService._normalize_json_value(previous_value),
            new_value=AuditService._normalize_json_value(new_value if new_value is not None else metadata_payload),
            reason=reason,
            comment=comment,
        )
        db.add(audit_event)
        db.flush()
        return audit_log


def record_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: int | str,
    actor: str = "demo_user",
    metadata_payload: dict[str, Any] | None = None,
    module: str | None = None,
    previous_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str | None = None,
    comment: str | None = None,
    user_id: int | None = None,
) -> AuditLog:
    return AuditService.record_event(
        db=db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        metadata_payload=metadata_payload,
        module=module,
        previous_value=previous_value,
        new_value=new_value,
        reason=reason,
        comment=comment,
        user_id=user_id,
    )
