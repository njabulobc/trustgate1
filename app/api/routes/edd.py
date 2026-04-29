from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DBSession
from app.models.edd_case import EddStatus
from app.schemas.edd import EddCaseAssign, EddCaseClose, EddCaseCreate, EddCaseRead, EddCaseStatusUpdate
from app.services.edd_service import EddNotFoundError, EddService, EddValidationError

router = APIRouter(prefix="/edd", tags=["edd"])


@router.post("", response_model=EddCaseRead, status_code=status.HTTP_201_CREATED)
def create_edd_case(payload: EddCaseCreate, db: DBSession) -> EddCaseRead:
    try:
        return EddCaseRead.model_validate(EddService.create_case(db, payload))
    except EddValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[EddCaseRead])
def list_edd_cases(db: DBSession, status_filter: EddStatus | None = Query(default=None, alias="status"), assignee: str | None = None) -> list[EddCaseRead]:
    return [EddCaseRead.model_validate(c) for c in EddService.list_cases(db, status=status_filter, assignee=assignee)]


@router.patch("/{case_id}/assign", response_model=EddCaseRead)
def assign_edd_case(case_id: int, payload: EddCaseAssign, db: DBSession) -> EddCaseRead:
    try:
        return EddCaseRead.model_validate(EddService.assign_case(db, case_id, payload.assignee))
    except EddNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{case_id}/status", response_model=EddCaseRead)
def update_edd_case_status(case_id: int, payload: EddCaseStatusUpdate, db: DBSession) -> EddCaseRead:
    try:
        return EddCaseRead.model_validate(EddService.transition_case(db, case_id, payload.status))
    except EddNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EddValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{case_id}/close", response_model=EddCaseRead)
def close_edd_case(case_id: int, payload: EddCaseClose, db: DBSession) -> EddCaseRead:
    try:
        return EddCaseRead.model_validate(EddService.close_case(db, case_id, payload.reason, payload.evidence))
    except EddNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
