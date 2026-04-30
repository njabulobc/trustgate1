from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.schemas.platform import AnalystQueueResponse, WorkbenchFilter
from app.services.platform_service import PlatformService

router = APIRouter(prefix="/workbench", tags=["workbench"])


@router.get("/queue", response_model=AnalystQueueResponse)
def read_workbench_queue(
    db: DBSession,
    user: CurrentUser,
    status_value: str | None = Query(default=None, alias="status"),
    assignee_id: int | None = Query(default=None),
    client_id: int | None = Query(default=None),
    module: str | None = Query(default=None),
) -> AnalystQueueResponse:
    filters = {
        "status": status_value,
        "assignee_id": assignee_id,
        "client_id": client_id,
        "module": module,
    }
    items = PlatformService.build_workbench_queue(db=db, filters=filters)
    return AnalystQueueResponse(items=items)
