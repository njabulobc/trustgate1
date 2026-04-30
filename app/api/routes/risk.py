from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.platform import RiskOverrideRead, RiskOverrideWrite
from app.schemas.risk import RiskAssessmentRead, RiskAssessmentResponse
from app.services.platform_service import PlatformConflictError, PlatformService, PlatformValidationError
from app.services.risk_service import (
    RiskAssessmentNotFoundError,
    RiskPersistenceError,
    RiskValidationError,
    assess_risk,
    get_latest_risk_assessment,
)

router = APIRouter(prefix="/risk", tags=["risk"])


def _build_risk_response(db: DBSession, risk_assessment) -> RiskAssessmentResponse:
    overrides = PlatformService.list_risk_overrides(
        db=db,
        client_id=risk_assessment.client_id,
        deal_id=risk_assessment.deal_id,
    )
    latest_override = overrides[0] if overrides else None
    effective_level = latest_override.override_level if latest_override is not None else risk_assessment.risk_level.value
    edd_required = effective_level in {"high", "critical"}
    return RiskAssessmentResponse(
        risk_assessment=RiskAssessmentRead.model_validate(risk_assessment),
        recommended_action="Open or maintain EDD case." if edd_required else "Proceed with standard monitoring.",
        edd_required=edd_required,
        overrides=[RiskOverrideRead.model_validate(item) for item in overrides],
    )


@router.post(
    "/clients/{client_id}",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
)
def create_risk_assessment(
    client_id: int,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
    deal_id: int | None = Query(default=None),
) -> RiskAssessmentResponse:
    try:
        risk_assessment = assess_risk(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
            actor=user.username,
        )
    except RiskValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RiskPersistenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return _build_risk_response(db, risk_assessment)


@router.get(
    "/clients/{client_id}",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
)
def read_latest_risk_assessment(
    client_id: int,
    db: DBSession,
    user: CurrentUser,
    deal_id: int | None = Query(default=None),
) -> RiskAssessmentResponse:
    try:
        risk_assessment = get_latest_risk_assessment(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )
    except RiskValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RiskAssessmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _build_risk_response(db, risk_assessment)


@router.post(
    "/clients/{client_id}/override",
    response_model=RiskOverrideRead,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_override(
    client_id: int,
    payload: RiskOverrideWrite,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.COMPLIANCE_OFFICER, UserRole.REVIEWER)),
    deal_id: int | None = Query(default=None),
) -> RiskOverrideRead:
    try:
        override = PlatformService.create_risk_override(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
            payload=payload.model_dump(),
            actor=user,
        )
    except (PlatformValidationError, PlatformConflictError) as exc:
        code = status.HTTP_400_BAD_REQUEST if isinstance(exc, PlatformValidationError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return RiskOverrideRead.model_validate(override)
