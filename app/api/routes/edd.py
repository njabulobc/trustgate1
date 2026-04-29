from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import UserRole
from app.schemas.edd import EDDCaseCreate, EDDCaseRead, EDDCaseUpdate
from app.services.edd_service import (
    EDDNotFoundError,
    EDDPersistenceError,
    EDDValidationError,
    create_edd_case,
    list_edd_cases,
    update_edd_case,
)

router = APIRouter(prefix="/edd", tags=["edd"])


@router.post(
    "/cases",
    response_model=EDDCaseRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER))],
)
def create_case(payload: EDDCaseCreate, db: DBSession, current_user: CurrentUser) -> EDDCaseRead:
    try:
        case = create_edd_case(db=db, payload=payload, actor=current_user.email)
    except EDDValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except EDDPersistenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return EDDCaseRead.model_validate(case)


@router.get(
    "/cases",
    response_model=list[EDDCaseRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER, UserRole.VIEWER))],
)
def list_cases(db: DBSession, current_user: CurrentUser, client_id: int | None = Query(default=None)) -> list[EDDCaseRead]:
    cases = list_edd_cases(db=db, client_id=client_id)
    return [EDDCaseRead.model_validate(item) for item in cases]


@router.patch(
    "/cases/{case_id}",
    response_model=EDDCaseRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER))],
)
def update_case(case_id: int, payload: EDDCaseUpdate, db: DBSession, current_user: CurrentUser) -> EDDCaseRead:
    try:
        case = update_edd_case(db=db, case_id=case_id, payload=payload, actor=current_user.email)
    except EDDNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EDDPersistenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return EDDCaseRead.model_validate(case)
