from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DBSession
from app.schemas.compliance import ComplianceDecisionResponse
from app.services.risk_service import RiskPersistenceError, RiskValidationError
from app.services.screening_service import (
    ScreeningExecutionError,
    ScreeningPersistenceError,
    ScreeningValidationError,
)
from app.services.compliance_decision_service import generate_client_compliance_decision

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post(
    "/clients/{client_id}/decision",
    response_model=ComplianceDecisionResponse,
    status_code=status.HTTP_200_OK,
)
async def create_compliance_decision(
    client_id: int,
    db: DBSession,
    deal_id: int | None = Query(default=None),
) -> ComplianceDecisionResponse:
    try:
        return await generate_client_compliance_decision(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )
    except ScreeningValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RiskValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ScreeningExecutionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except (ScreeningPersistenceError, RiskPersistenceError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
