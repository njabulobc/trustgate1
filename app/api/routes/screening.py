from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.screening import ScreeningSubjectType
from app.models.user import User, UserRole
from app.schemas.screening import (
    CandidateDispositionUpdate,
    PepCaseRead,
    PepCaseUpdate,
    ScreeningCandidateRead,
    ScreeningResultRead,
    ScreeningRunRequest,
)
from app.services.screening_service import (  # type: ignore[import-not-found]
    ensure_pep_case,
    list_pep_cases_for_client,
    get_screening_result,
    ScreeningExecutionError,
    ScreeningNotFoundError,
    ScreeningPersistenceError,
    ScreeningValidationError,
    list_screening_results_for_client,
    run_screening_for_client,
    update_pep_case,
    update_candidate_disposition,
)
from app.services.platform_service import PlatformService

router = APIRouter(prefix="/screening", tags=["screening"])


@router.post(
    "/run",
    response_model=list[ScreeningResultRead],
    status_code=status.HTTP_200_OK,
)
async def run_screening(
    payload: ScreeningRunRequest,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
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
            actor=user.username,
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
    user: CurrentUser,
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
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> ScreeningCandidateRead:
    try:
        candidate = update_candidate_disposition(
            db=db,
            candidate_id=candidate_id,
            payload=payload,
            actor=user.username,
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

    if payload.disposition in {candidate.disposition.CONFIRMED_MATCH, candidate.disposition.NEEDS_EDD}:
        screening_result = get_screening_result(
            db=db,
            screening_result_id=candidate.screening_result_id,
        )
        client_id = screening_result.client_id
        if client_id is not None:
            PlatformService.maybe_create_edd_from_screening(
                db=db,
                client_id=client_id,
                actor=user,
                candidate_id=candidate.id,
                reason=f"Screening candidate {candidate.id} dispositioned as {candidate.disposition.value}.",
            )

    return ScreeningCandidateRead.model_validate(candidate)


@router.post(
    "/candidates/{candidate_id}/pep-case",
    response_model=PepCaseRead,
    status_code=status.HTTP_200_OK,
)
def open_pep_case(
    candidate_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.COMPLIANCE_OFFICER, UserRole.REVIEWER)),
) -> PepCaseRead:
    try:
        pep_case = ensure_pep_case(
            db=db,
            screening_candidate_id=candidate_id,
            actor=user.username,
        )
    except ScreeningNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScreeningValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ScreeningPersistenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return PepCaseRead.model_validate(pep_case)


@router.patch(
    "/pep-cases/{pep_case_id}",
    response_model=PepCaseRead,
    status_code=status.HTTP_200_OK,
)
def patch_pep_case(
    pep_case_id: int,
    payload: PepCaseUpdate,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.REVIEWER,
        )
    ),
) -> PepCaseRead:
    try:
        pep_case = update_pep_case(
            db=db,
            pep_case_id=pep_case_id,
            status=payload.status,
            senior_approval_status=payload.senior_approval_status,
            source_of_wealth_status=payload.source_of_wealth_status,
            source_of_funds_status=payload.source_of_funds_status,
            enhanced_monitoring=payload.enhanced_monitoring,
            monitoring_notes=payload.monitoring_notes,
            closure_evidence=payload.closure_evidence,
            actor=user.username,
        )
    except ScreeningNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScreeningPersistenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return PepCaseRead.model_validate(pep_case)


@router.get(
    "/clients/{client_id}/pep-cases",
    response_model=list[PepCaseRead],
    status_code=status.HTTP_200_OK,
)
def list_client_pep_cases(client_id: int, db: DBSession, user: CurrentUser) -> list[PepCaseRead]:
    try:
        pep_cases = list_pep_cases_for_client(db=db, client_id=client_id)
    except ScreeningValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return [PepCaseRead.model_validate(item) for item in pep_cases]
