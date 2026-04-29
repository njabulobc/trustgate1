from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DBSession, require_roles
from app.core.auth import UserRole
from app.schemas.intake import (
    ClientRead,
    DealRead,
    IntakeCreate,
    IntakeRead,
    IntakeUpdate,
)
from app.services.intake_service import (
    IntakeConflictError,
    IntakeNotFoundError,
    create_intake,
    get_intake_by_client_id,
    get_intake_by_deal_id,
    update_intake,
)

router = APIRouter(prefix="/intake", tags=["intake"], dependencies=[Depends(require_roles(UserRole.ANALYST, UserRole.REVIEWER))])


def _build_intake_response(*, client, deal) -> IntakeRead:
    return IntakeRead(
        client=ClientRead.model_validate(client),
        deal=DealRead.model_validate(deal),
    )


@router.post(
    "",
    response_model=IntakeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_intake_case(
    payload: IntakeCreate,
    db: DBSession,
) -> IntakeRead:
    try:
        client, deal = create_intake(db=db, payload=payload)
    except IntakeConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _build_intake_response(client=client, deal=deal)


@router.get(
    "/clients/{client_id}",
    response_model=IntakeRead,
    status_code=status.HTTP_200_OK,
)
def read_intake_by_client(
    client_id: int,
    db: DBSession,
    deal_id: int | None = Query(default=None),
) -> IntakeRead:
    try:
        client, deal = get_intake_by_client_id(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )
    except IntakeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return _build_intake_response(client=client, deal=deal)


@router.get(
    "/deals/{deal_id}",
    response_model=IntakeRead,
    status_code=status.HTTP_200_OK,
)
def read_intake_by_deal(
    deal_id: int,
    db: DBSession,
) -> IntakeRead:
    try:
        client, deal = get_intake_by_deal_id(db=db, deal_id=deal_id)
    except IntakeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return _build_intake_response(client=client, deal=deal)


@router.patch(
    "/clients/{client_id}",
    response_model=IntakeRead,
    status_code=status.HTTP_200_OK,
)
def update_intake_case(
    client_id: int,
    payload: IntakeUpdate,
    db: DBSession,
    deal_id: int | None = Query(default=None),
) -> IntakeRead:
    try:
        client, deal = update_intake(
            db=db,
            client_id=client_id,
            payload=payload,
            deal_id=deal_id,
        )
    except IntakeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except IntakeConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _build_intake_response(client=client, deal=deal)