from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.linked_party import LinkedPartyRole, LinkedPartyType


class LinkedPartyBase(BaseModel):
    party_type: LinkedPartyType
    role: LinkedPartyRole
    relationship_to_client: str = Field(..., min_length=1, max_length=100)
    primary_name: str = Field(..., min_length=1, max_length=255)

    first_name: str | None = Field(default=None, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    date_of_birth: datetime | None = None
    nationality: str | None = Field(default=None, max_length=100)
    national_id_number: str | None = Field(default=None, max_length=100)

    registration_number: str | None = Field(default=None, max_length=100)
    country_of_incorporation: str | None = Field(default=None, max_length=100)

    email: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=50)
    address: str | None = None

    screening_required: bool = True


class LinkedPartyCreate(LinkedPartyBase):
    client_id: int
    deal_id: int


class LinkedPartyUpdate(BaseModel):
    party_type: LinkedPartyType | None = None
    role: LinkedPartyRole | None = None
    relationship_to_client: str | None = Field(default=None, min_length=1, max_length=100)
    primary_name: str | None = Field(default=None, min_length=1, max_length=255)

    first_name: str | None = Field(default=None, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    date_of_birth: datetime | None = None
    nationality: str | None = Field(default=None, max_length=100)
    national_id_number: str | None = Field(default=None, max_length=100)

    registration_number: str | None = Field(default=None, max_length=100)
    country_of_incorporation: str | None = Field(default=None, max_length=100)

    email: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=50)
    address: str | None = None

    screening_required: bool | None = None


class LinkedPartyRead(LinkedPartyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    deal_id: int
    created_at: datetime
    updated_at: datetime