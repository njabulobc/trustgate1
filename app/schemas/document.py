from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentEntityType, DocumentType


class DocumentCreate(BaseModel):
    entity_type: DocumentEntityType
    client_id: int | None = None
    linked_party_id: int | None = None
    deal_id: int | None = None
    document_type: DocumentType
    document_name: str = Field(..., min_length=1, max_length=255)
    storage_uri: str = Field(..., min_length=1, max_length=500)
    notes: str | None = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: DocumentEntityType
    client_id: int | None
    linked_party_id: int | None
    deal_id: int | None
    document_type: DocumentType
    document_name: str
    storage_uri: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
