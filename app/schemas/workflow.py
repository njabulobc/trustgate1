from datetime import datetime

from pydantic import BaseModel, Field

from app.models.workflow import QueueStatus


class WorkflowQueueRequest(BaseModel):
    notes: str | None = None


class WorkflowAssignmentRequest(BaseModel):
    assigned_reviewer: str = Field(min_length=2, max_length=100)


class WorkflowStatusRequest(BaseModel):
    status: QueueStatus


class WorkflowCaseRead(BaseModel):
    id: int
    deal_id: int
    client_id: int
    status: QueueStatus
    assigned_reviewer: str | None
    queue_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowCaseListResponse(BaseModel):
    items: list[WorkflowCaseRead]
    page: int
    page_size: int
    total: int
