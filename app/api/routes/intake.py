from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import UserRole
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

router = APIRouter(prefix="/intake", tags=["intake"])


def _build_intake_response(*, client, deal) -> IntakeRead:
    return IntakeRead(
        client=ClientRead.model_validate(client),
        deal=DealRead.model_validate(deal),
    )


@router.post(
    "",
    response_model=IntakeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST))],
)
def create_intake_case(
    payload: IntakeCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> IntakeRead:
    try:
        client, deal = create_intake(db=db, payload=payload, actor=current_user.email)
    except IntakeConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return _build_intake_response(client=client, deal=deal)


@router.get(
    "/clients/{client_id}",
    response_model=IntakeRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER, UserRole.VIEWER))],
)
def read_intake_by_client(
    client_id: int,
    db: DBSession,
    current_user: CurrentUser,
    deal_id: int | None = Query(default=None),
) -> IntakeRead:
    try:
        client, deal = get_intake_by_client_id(db=db, client_id=client_id, deal_id=deal_id)
    except IntakeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _build_intake_response(client=client, deal=deal)


@router.get(
    "/deals/{deal_id}",
    response_model=IntakeRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER, UserRole.VIEWER))],
)
def read_intake_by_deal(
    deal_id: int,
    db: DBSession,
    current_user: CurrentUser,
) -> IntakeRead:
    try:
        client, deal = get_intake_by_deal_id(db=db, deal_id=deal_id)
    except IntakeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _build_intake_response(client=client, deal=deal)


@router.patch(
    "/clients/{client_id}",
    response_model=IntakeRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST))],
)
def update_intake_case(
    client_id: int,
    payload: IntakeUpdate,
    db: DBSession,
    current_user: CurrentUser,
    deal_id: int | None = Query(default=None),
) -> IntakeRead:
    try:
        client, deal = update_intake(
            db=db,
            client_id=client_id,
            payload=payload,
            actor=current_user.email,
            deal_id=deal_id,
        )
    except IntakeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntakeConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return _build_intake_response(client=client, deal=deal)
