from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession
from app.schemas.platform import ReportExportResponse
from app.services.audit_service import record_audit_event
from app.services.platform_service import PlatformService, PlatformValidationError

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{report_name}", response_model=ReportExportResponse)
def generate_report(
    report_name: str,
    db: DBSession,
    user: CurrentUser,
    format: str = Query(default="json"),
) -> ReportExportResponse:
    try:
        rows = PlatformService.build_report_rows(db=db, report_name=report_name)
    except PlatformValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    csv_payload = PlatformService.build_csv(rows) if format == "csv" else None
    record_audit_event(
        db=db,
        actor=user.username,
        user_id=user.id,
        action="report.exported",
        module="reports",
        entity_type="report",
        entity_id=report_name,
        new_value={"format": format, "row_count": len(rows)},
    )
    db.commit()
    return ReportExportResponse(report_name=report_name, rows=rows, csv=csv_payload)
