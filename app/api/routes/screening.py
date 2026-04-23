from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.screening import ScreeningSubjectType
from app.models.user import UserRole
from app.schemas.screening import CandidateDispositionUpdate, ScreeningCandidateRead, ScreeningResultRead, ScreeningRunRequest
from app.services.screening_service import (
    ScreeningExecutionError,
    ScreeningNotFoundError,
    ScreeningPersistenceError,
    ScreeningValidationError,
    list_screening_results_for_client,
    run_screening_for_client,
    update_candidate_disposition,
)

router = APIRouter(prefix="/screening", tags=["screening"])


@router.post(
    "/run",
    response_model=list[ScreeningResultRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER))],
)
async def run_screening(payload: ScreeningRunRequest, db: DBSession, current_user: CurrentUser) -> list[ScreeningResultRead]:
    if payload.subject_type != ScreeningSubjectType.CLIENT or payload.client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Screening runs must be initiated for a primary client in the current MVP.")

    try:
        screening_results = await run_screening_for_client(db=db, client_id=payload.client_id, actor=current_user.email)
    except ScreeningValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ScreeningExecutionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ScreeningPersistenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return [ScreeningResultRead.model_validate(item) for item in screening_results]


@router.get(
    "/clients/{client_id}",
    response_model=list[ScreeningResultRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER, UserRole.VIEWER))],
)
def list_client_screening_results(client_id: int, db: DBSession, current_user: CurrentUser) -> list[ScreeningResultRead]:
    try:
        screening_results = list_screening_results_for_client(db=db, client_id=client_id)
    except ScreeningValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return [ScreeningResultRead.model_validate(item) for item in screening_results]


@router.patch(
    "/candidates/{candidate_id}/disposition",
    response_model=ScreeningCandidateRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER))],
)
def review_screening_candidate(
    candidate_id: int,
    payload: CandidateDispositionUpdate,
    db: DBSession,
    current_user: CurrentUser,
) -> ScreeningCandidateRead:
    try:
        candidate = update_candidate_disposition(db=db, candidate_id=candidate_id, payload=payload, actor=current_user.email)
    except ScreeningNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScreeningPersistenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ScreeningCandidateRead.model_validate(candidate)
