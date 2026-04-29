from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.alert import AlertStatus, AlertType


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int | None
    linked_party_id: int | None
    deal_id: int | None
    alert_type: AlertType
    status: AlertStatus
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class AlertUpdate(BaseModel):
    status: AlertStatus
