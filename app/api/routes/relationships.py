from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.relationship import (
    LinkedPartyCreate,
    LinkedPartyRead,
    LinkedPartyUpdate,
)
from app.services.relationship_service import (
    LinkedPartyConflictError,
    LinkedPartyNotFoundError,
    RelationshipValidationError,
    create_linked_party,
    delete_linked_party,
    list_linked_parties,
    update_linked_party,
)

router = APIRouter(prefix="/relationships", tags=["relationships"])


@router.post(
    "",
    response_model=LinkedPartyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    payload: LinkedPartyCreate,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> LinkedPartyRead:
    try:
        linked_party = create_linked_party(db=db, payload=payload, actor=user.username)
    except RelationshipValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LinkedPartyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return LinkedPartyRead.model_validate(linked_party)


@router.get(
    "",
    response_model=list[LinkedPartyRead],
    status_code=status.HTTP_200_OK,
)
def list_relationships(
    db: DBSession,
    user: CurrentUser,
    client_id: int | None = Query(default=None),
    deal_id: int | None = Query(default=None),
) -> list[LinkedPartyRead]:
    try:
        linked_parties = list_linked_parties(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )
    except RelationshipValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return [LinkedPartyRead.model_validate(item) for item in linked_parties]


@router.patch(
    "/{linked_party_id}",
    response_model=LinkedPartyRead,
    status_code=status.HTTP_200_OK,
)
def update_relationship(
    linked_party_id: int,
    payload: LinkedPartyUpdate,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
            UserRole.REVIEWER,
        )
    ),
) -> LinkedPartyRead:
    try:
        linked_party = update_linked_party(
            db=db,
            linked_party_id=linked_party_id,
            payload=payload,
            actor=user.username,
        )
    except LinkedPartyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LinkedPartyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return LinkedPartyRead.model_validate(linked_party)


@router.delete(
    "/{linked_party_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_relationship(
    linked_party_id: int,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
        )
    ),
) -> Response:
    try:
        delete_linked_party(db=db, linked_party_id=linked_party_id, actor=user.username)
    except LinkedPartyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
