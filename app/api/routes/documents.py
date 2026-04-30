from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.platform import DocumentChecklistSummary, DocumentRead, DocumentReviewUpdate
from app.services.platform_service import PlatformConflictError, PlatformNotFoundError, PlatformService, PlatformValidationError

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/clients/{client_id}", response_model=list[DocumentRead])
def list_client_documents(client_id: int, db: DBSession, user: CurrentUser) -> list[DocumentRead]:
    try:
        documents = PlatformService.list_documents(db=db, client_id=client_id)
    except PlatformNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [DocumentRead.model_validate(item) for item in documents]


@router.get("/clients/{client_id}/checklist", response_model=DocumentChecklistSummary)
def read_document_checklist(client_id: int, db: DBSession, user: CurrentUser) -> DocumentChecklistSummary:
    try:
        checklist = PlatformService.summarize_document_checklist(db=db, client_id=client_id)
    except PlatformNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentChecklistSummary.model_validate(checklist)


@router.post("/clients/{client_id}", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(
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
    document_type: str = Form(...),
    deal_id: int | None = Form(default=None),
    linked_party_id: int | None = Form(default=None),
    expiry_date: date | None = Form(default=None),
    file: UploadFile = File(...),
) -> DocumentRead:
    try:
        document = PlatformService.save_document_upload(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
            linked_party_id=linked_party_id,
            document_type=document_type,
            expiry_date=expiry_date,
            file=file,
            actor=user,
        )
    except (PlatformNotFoundError, PlatformConflictError, PlatformValidationError) as exc:
        if isinstance(exc, PlatformConflictError):
            code = status.HTTP_409_CONFLICT
        elif isinstance(exc, PlatformValidationError):
            code = status.HTTP_400_BAD_REQUEST
        else:
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return DocumentRead.model_validate(document)


@router.patch("/{document_id}", response_model=DocumentRead)
def review_document(
    document_id: int,
    payload: DocumentReviewUpdate,
    db: DBSession,
    user: User = Depends(
        require_roles(
            UserRole.ADMINISTRATOR,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.REVIEWER,
        )
    ),
) -> DocumentRead:
    try:
        document = PlatformService.review_document(
            db=db,
            document_id=document_id,
            payload=payload.model_dump(),
            actor=user,
        )
    except (PlatformNotFoundError, PlatformConflictError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, PlatformNotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return DocumentRead.model_validate(document)
