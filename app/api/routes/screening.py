from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DBSession
from app.models.screening import ScreeningSubjectType
from app.schemas.screening import (
    CandidateDispositionUpdate,
    ScreeningCandidateRead,
    ScreeningResultRead,
    ScreeningRunRequest,
)
from app.services.screening_service import (  # type: ignore[import-not-found]
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
)
async def run_screening(
    payload: ScreeningRunRequest,
    db: DBSession,
) -> list[ScreeningResultRead]:
    if payload.subject_type != ScreeningSubjectType.CLIENT or payload.client_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screening runs must be initiated for a primary client in the current MVP.",
        )

    try:
        screening_results = await run_screening_for_client(
            db=db,
            client_id=payload.client_id,
        )
    except ScreeningValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ScreeningExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except ScreeningPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return [ScreeningResultRead.model_validate(item) for item in screening_results]


@router.get(
    "/clients/{client_id}",
    response_model=list[ScreeningResultRead],
    status_code=status.HTTP_200_OK,
)
def list_client_screening_results(
    client_id: int,
    db: DBSession,
) -> list[ScreeningResultRead]:
    try:
        screening_results = list_screening_results_for_client(
            db=db,
            client_id=client_id,
        )
    except ScreeningValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return [ScreeningResultRead.model_validate(item) for item in screening_results]


@router.patch(
    "/candidates/{candidate_id}/disposition",
    response_model=ScreeningCandidateRead,
    status_code=status.HTTP_200_OK,
)
def review_screening_candidate(
    candidate_id: int,
    payload: CandidateDispositionUpdate,
    db: DBSession,
) -> ScreeningCandidateRead:
    try:
        candidate = update_candidate_disposition(
            db=db,
            candidate_id=candidate_id,
            payload=payload,
        )
    except ScreeningNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ScreeningPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ScreeningCandidateRead.model_validate(candidate)