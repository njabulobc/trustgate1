from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DBSession
from app.schemas.risk import RiskAssessmentRead, RiskAssessmentResponse
from app.services.risk_service import (
    RiskAssessmentNotFoundError,
    RiskPersistenceError,
    RiskValidationError,
    assess_risk,
    get_latest_risk_assessment,
)

router = APIRouter(prefix="/risk", tags=["risk"])


def _build_risk_response(risk_assessment) -> RiskAssessmentResponse:
    return RiskAssessmentResponse(
        risk_assessment=RiskAssessmentRead.model_validate(risk_assessment)
    )


@router.post(
    "/clients/{client_id}",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
)
def create_risk_assessment(
    client_id: int,
    db: DBSession,
    deal_id: int | None = Query(default=None),
) -> RiskAssessmentResponse:
    try:
        risk_assessment = assess_risk(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )
    except RiskValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RiskPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _build_risk_response(risk_assessment)


@router.get(
    "/clients/{client_id}",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
)
def read_latest_risk_assessment(
    client_id: int,
    db: DBSession,
    deal_id: int | None = Query(default=None),
) -> RiskAssessmentResponse:
    try:
        risk_assessment = get_latest_risk_assessment(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )
    except RiskValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RiskAssessmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return _build_risk_response(risk_assessment)