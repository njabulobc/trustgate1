from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.report import ReportType


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_type: ReportType
    title: str
    generated_by: str
    content: str
    created_at: datetime
