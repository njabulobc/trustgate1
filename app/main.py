from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.intake import router as intake_router
from app.api.routes.relationships import router as relationships_router
from app.api.routes.risk import router as risk_router
from app.api.routes.screening import router as screening_router
from app.core.database import Base, engine

# Ensure all MVP models are imported before metadata.create_all runs.
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.deal import Deal  # noqa: F401
from app.models.linked_party import LinkedParty  # noqa: F401
from app.models.risk_assessment import RiskAssessment  # noqa: F401
from app.models.screening import ScreeningCandidate, ScreeningResult  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="TrustGate MVP",
    description=(
        "TrustGate MVP for real-estate compliance workflows covering intake, "
        "linked parties, screening, risk assessment, and auditability."
    ),
    lifespan=lifespan,
)

app.include_router(intake_router)
app.include_router(relationships_router)
app.include_router(screening_router)
app.include_router(risk_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}