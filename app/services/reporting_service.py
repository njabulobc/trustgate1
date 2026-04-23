from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertStatus
from app.models.client import Client
from app.models.edd_case import EDDCase
from app.models.report import Report, ReportType
from app.models.risk_assessment import RiskAssessment, RiskLevel
from app.models.screening import ScreeningResult
from app.services.audit_service import record_audit_event


class ReportingService:
    @staticmethod
    def generate_report(db: Session, report_type: ReportType, generated_by: str) -> Report:
        if report_type == ReportType.COMPLIANCE_SUMMARY:
            content = ReportingService._build_compliance_summary(db)
            title = "Compliance Summary"
        elif report_type == ReportType.CLIENT_RISK_REGISTER:
            content = ReportingService._build_client_risk_register(db)
            title = "Client Risk Register"
        else:
            content = ReportingService._build_screening_activity(db)
            title = "Screening Activity"

        report = Report(
            report_type=report_type,
            title=title,
            generated_by=generated_by,
            content=content,
        )
        db.add(report)
        db.flush()

        record_audit_event(
            db=db,
            actor=generated_by,
            action="report.generated",
            entity_type="report",
            entity_id=report.id,
            metadata_payload={"report_type": report.report_type.value},
        )
        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def _build_compliance_summary(db: Session) -> str:
        total_clients = db.execute(select(func.count(Client.id))).scalar_one()
        total_screenings = db.execute(select(func.count(ScreeningResult.id))).scalar_one()
        open_alerts = db.execute(select(func.count(Alert.id)).where(Alert.status == AlertStatus.OPEN)).scalar_one()
        open_edd = db.execute(select(func.count(EDDCase.id))).scalar_one()
        return (
            f"Total clients: {total_clients}\n"
            f"Total screenings: {total_screenings}\n"
            f"Open alerts: {open_alerts}\n"
            f"EDD cases: {open_edd}"
        )

    @staticmethod
    def _build_client_risk_register(db: Session) -> str:
        rows = db.execute(
            select(RiskAssessment.client_id, RiskAssessment.risk_level, RiskAssessment.total_score)
            .order_by(RiskAssessment.assessed_at.desc())
        ).all()
        if not rows:
            return "No risk assessments available."
        lines = ["client_id,risk_level,total_score"]
        for client_id, risk_level, total_score in rows:
            level_value = risk_level.value if isinstance(risk_level, RiskLevel) else str(risk_level)
            lines.append(f"{client_id},{level_value},{total_score}")
        return "\n".join(lines)

    @staticmethod
    def _build_screening_activity(db: Session) -> str:
        rows = db.execute(
            select(ScreeningResult.id, ScreeningResult.subject_type, ScreeningResult.status, ScreeningResult.screened_at)
            .order_by(ScreeningResult.screened_at.desc())
            .limit(100)
        ).all()
        if not rows:
            return "No screening activity found."
        lines = ["screening_result_id,subject_type,status,screened_at"]
        for result_id, subject_type, status, screened_at in rows:
            lines.append(f"{result_id},{subject_type.value},{status.value},{screened_at.isoformat()}")
        return "\n".join(lines)


def generate_report(db: Session, report_type: ReportType, generated_by: str) -> Report:
    return ReportingService.generate_report(db, report_type, generated_by)
