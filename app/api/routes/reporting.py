from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.report import Report, ReportType
from app.models.user import UserRole
from app.schemas.reporting import ReportRead
from app.services.reporting_service import generate_report

router = APIRouter(prefix="/reporting", tags=["reporting"])


@router.post(
    "/reports/{report_type}",
    response_model=ReportRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER))],
)
def generate_reporting_output(report_type: ReportType, db: DBSession, current_user: CurrentUser) -> ReportRead:
    report = generate_report(db=db, report_type=report_type, generated_by=current_user.email)
    return ReportRead.model_validate(report)


@router.get(
    "/reports",
    response_model=list[ReportRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER, UserRole.VIEWER))],
)
def list_reports(db: DBSession, current_user: CurrentUser) -> list[ReportRead]:
    reports = db.execute(select(Report).order_by(Report.created_at.desc(), Report.id.desc())).scalars().all()
    return [ReportRead.model_validate(report) for report in reports]
