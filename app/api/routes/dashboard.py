from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.platform import DashboardSummary
from app.services.platform_service import PlatformService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def read_dashboard_summary(db: DBSession, user: CurrentUser) -> DashboardSummary:
    return PlatformService.get_dashboard_summary(db=db)
