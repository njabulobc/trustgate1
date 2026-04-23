from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.deal import Deal
from app.models.document import Document
from app.models.linked_party import LinkedParty
from app.schemas.document import DocumentCreate
from app.services.audit_service import record_audit_event


class DocumentServiceError(Exception):
    pass


class DocumentValidationError(DocumentServiceError):
    pass


class DocumentConflictError(DocumentServiceError):
    pass


class DocumentService:
    @staticmethod
    def create_document(db: Session, payload: DocumentCreate, actor: str = "demo_user") -> Document:
        if payload.entity_type.value == "client" and payload.client_id is None:
            raise DocumentValidationError("client_id is required for client documents.")
        if payload.entity_type.value == "linked_party" and payload.linked_party_id is None:
            raise DocumentValidationError("linked_party_id is required for linked-party documents.")
        if payload.entity_type.value == "deal" and payload.deal_id is None:
            raise DocumentValidationError("deal_id is required for deal documents.")

        if payload.client_id is not None and db.execute(select(Client).where(Client.id == payload.client_id)).scalar_one_or_none() is None:
            raise DocumentValidationError(f"Client with id={payload.client_id} was not found.")
        if payload.linked_party_id is not None and db.execute(select(LinkedParty).where(LinkedParty.id == payload.linked_party_id)).scalar_one_or_none() is None:
            raise DocumentValidationError(f"Linked party with id={payload.linked_party_id} was not found.")
        if payload.deal_id is not None and db.execute(select(Deal).where(Deal.id == payload.deal_id)).scalar_one_or_none() is None:
            raise DocumentValidationError(f"Deal with id={payload.deal_id} was not found.")

        doc = Document(**payload.model_dump())
        try:
            db.add(doc)
            db.flush()
            record_audit_event(
                db=db,
                actor=actor,
                action="document.created",
                entity_type="document",
                entity_id=doc.id,
                metadata_payload={"entity_type": doc.entity_type.value, "document_type": doc.document_type.value},
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise DocumentConflictError("Unable to save document because of persistence constraints.") from exc

        db.refresh(doc)
        return doc

    @staticmethod
    def list_documents(db: Session, client_id: int | None = None, linked_party_id: int | None = None, deal_id: int | None = None) -> list[Document]:
        stmt = select(Document)
        if client_id is not None:
            stmt = stmt.where(Document.client_id == client_id)
        if linked_party_id is not None:
            stmt = stmt.where(Document.linked_party_id == linked_party_id)
        if deal_id is not None:
            stmt = stmt.where(Document.deal_id == deal_id)
        stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc())
        return list(db.execute(stmt).scalars().all())


def create_document(db: Session, payload: DocumentCreate, actor: str = "demo_user") -> Document:
    return DocumentService.create_document(db, payload, actor)


def list_documents(db: Session, client_id: int | None = None, linked_party_id: int | None = None, deal_id: int | None = None) -> list[Document]:
    return DocumentService.list_documents(db, client_id, linked_party_id, deal_id)
