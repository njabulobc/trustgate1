from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.api.routes.administration import router as administration_router
from app.api.routes.auth import router as auth_router
from app.api.routes.cdd import router as cdd_router
from app.api.routes.compliance import router as compliance_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.documents import router as documents_router
from app.api.routes.edd import router as edd_router
from app.api.routes.intake import router as intake_router
from app.api.routes.kyc import router as kyc_router
from app.api.routes.monitoring import router as monitoring_router
from app.api.routes.ownership import router as ownership_router
from app.api.routes.reports import router as reports_router
from app.api.routes.relationships import router as relationships_router
from app.api.routes.risk import router as risk_router
from app.api.routes.screening import router as screening_router
from app.api.routes.workbench import router as workbench_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine

# Ensure all MVP models are imported before metadata.create_all runs.
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.deal import Deal  # noqa: F401
from app.models.linked_party import LinkedParty  # noqa: F401
from app.models.platform import (  # noqa: F401
    AlertSeverity,
    AppSetting,
    AuditEvent,
    BeneficialOwnershipRecord,
    CddWorkflow,
    EddCase,
    KycDocument,
    KycProfile,
    MonitoringAlert,
    MonitoringEvent,
    RiskOverride,
)
from app.models.risk_assessment import RiskAssessment  # noqa: F401
from app.models.screening import PepCase, ScreeningCandidate, ScreeningResult  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.auth_service import AuthService
from app.services.platform_service import PlatformService


def _run_safe_schema_updates() -> None:
    if not engine.url.drivername.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "screening_candidates" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("screening_candidates")}
    statements: list[str] = []
    if "match_category" not in existing_columns:
        statements.append(
            "ALTER TABLE screening_candidates "
            "ADD COLUMN match_category VARCHAR(8) NOT NULL DEFAULT 'STANDARD'"
        )
    if "policy_flags" not in existing_columns:
        statements.append("ALTER TABLE screening_candidates ADD COLUMN policy_flags JSON")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _run_safe_schema_updates()
    Path(settings.DOCUMENT_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        AuthService.seed_bootstrap_admin(db=db)
        PlatformService.ensure_default_settings(db=db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="TrustGate MVP",
    description=(
        "TrustGate MVP for real-estate compliance workflows covering intake, "
        "linked parties, screening, risk assessment, and auditability."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(intake_router)
app.include_router(kyc_router)
app.include_router(documents_router)
app.include_router(cdd_router)
app.include_router(ownership_router)
app.include_router(relationships_router)
app.include_router(screening_router)
app.include_router(risk_router)
app.include_router(edd_router)
app.include_router(monitoring_router)
app.include_router(workbench_router)
app.include_router(reports_router)
app.include_router(administration_router)
app.include_router(compliance_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
