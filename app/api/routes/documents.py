from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import UserRole
from app.schemas.document import DocumentCreate, DocumentRead
from app.services.document_service import (
    DocumentConflictError,
    DocumentValidationError,
    create_document,
    list_documents,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER))],
)
def create_document_record(payload: DocumentCreate, db: DBSession, current_user: CurrentUser) -> DocumentRead:
    try:
        doc = create_document(db=db, payload=payload, actor=current_user.email)
    except DocumentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DocumentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return DocumentRead.model_validate(doc)


@router.get(
    "",
    response_model=list[DocumentRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.REVIEWER, UserRole.VIEWER))],
)
def list_document_records(
    db: DBSession,
    current_user: CurrentUser,
    client_id: int | None = Query(default=None),
    linked_party_id: int | None = Query(default=None),
    deal_id: int | None = Query(default=None),
) -> list[DocumentRead]:
    docs = list_documents(db=db, client_id=client_id, linked_party_id=linked_party_id, deal_id=deal_id)
    return [DocumentRead.model_validate(doc) for doc in docs]
