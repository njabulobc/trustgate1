from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.routes.compliance import router as compliance_router
from app.api.routes.edd import router as edd_router
from app.api.routes.intake import router as intake_router
from app.api.routes.relationships import router as relationships_router
from app.api.routes.risk import router as risk_router
from app.api.routes.screening import router as screening_router
from app.core.config import settings
from app.core.database import Base, engine

# Ensure all MVP models are imported before metadata.create_all runs.
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.deal import Deal  # noqa: F401
from app.models.edd_case import EddCase  # noqa: F401
from app.models.linked_party import LinkedParty  # noqa: F401
from app.models.risk_assessment import RiskAssessment  # noqa: F401
from app.models.screening import PepCase, ScreeningCandidate, ScreeningResult  # noqa: F401


def _repair_legacy_schema() -> None:
    """Apply additive schema repairs for legacy SQLite databases.

    SQLite `create_all` does not alter existing tables, so older local DB files
    can miss newly-added columns and fail at runtime.
    """

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "screening_candidates" not in tables:
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("screening_candidates")
    }

    with engine.begin() as connection:
        if "match_category" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE screening_candidates "
                    "ADD COLUMN match_category VARCHAR(20) NOT NULL DEFAULT 'standard'"
                )
            )
        if "policy_flags" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE screening_candidates "
                    "ADD COLUMN policy_flags JSON"
                )
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _repair_legacy_schema()
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

app.include_router(intake_router)
app.include_router(relationships_router)
app.include_router(screening_router)
app.include_router(risk_router)
app.include_router(compliance_router)
app.include_router(edd_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
