from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.edd import router as edd_router
from app.api.routes.intake import router as intake_router
from app.api.routes.monitoring import router as monitoring_router
from app.api.routes.relationships import router as relationships_router
from app.api.routes.reporting import router as reporting_router
from app.api.routes.risk import router as risk_router
from app.api.routes.screening import router as screening_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine

# Ensure all models are imported before metadata.create_all runs.
from app.models.alert import Alert  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.deal import Deal  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.edd_case import EDDCase  # noqa: F401
from app.models.linked_party import LinkedParty  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.risk_assessment import RiskAssessment  # noqa: F401
from app.models.screening import ScreeningCandidate, ScreeningResult  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.auth_service import AuthService


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        AuthService.ensure_seed_admin(db)
    yield


app = FastAPI(
    title="TrustGate",
    description=(
        "TrustGate compliance workflows covering intake, relationships, identity documents, "
        "screening, risk assessment, EDD management, monitoring alerts, reporting, and auditability."
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
app.include_router(intake_router)
app.include_router(relationships_router)
app.include_router(documents_router)
app.include_router(screening_router)
app.include_router(risk_router)
app.include_router(edd_router)
app.include_router(monitoring_router)
app.include_router(reporting_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
