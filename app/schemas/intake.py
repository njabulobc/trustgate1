from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.client import ClientStatus, ClientType
from app.models.deal import DealStatus, DealTransactionType


class ClientBase(BaseModel):
    client_type: ClientType
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


class ClientCreate(ClientBase):
    status: ClientStatus = ClientStatus.DRAFT


class ClientUpdate(BaseModel):
    client_type: ClientType | None = None
    status: ClientStatus | None = None
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


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ClientStatus
    created_at: datetime
    updated_at: datetime


class DealBase(BaseModel):
    transaction_reference: str = Field(..., min_length=1, max_length=100)
    transaction_type: DealTransactionType
    property_reference: str | None = Field(default=None, max_length=150)
    property_location: str = Field(..., min_length=1)
    transaction_value: Decimal = Field(..., ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    is_cross_border: bool = False
    source_of_funds_summary: str | None = None


class DealCreate(DealBase):
    status: DealStatus = DealStatus.DRAFT


class DealUpdate(BaseModel):
    transaction_reference: str | None = Field(default=None, min_length=1, max_length=100)
    transaction_type: DealTransactionType | None = None
    status: DealStatus | None = None
    property_reference: str | None = Field(default=None, max_length=150)
    property_location: str | None = Field(default=None, min_length=1)
    transaction_value: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_cross_border: bool | None = None
    source_of_funds_summary: str | None = None


class DealRead(DealBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    status: DealStatus
    created_at: datetime
    updated_at: datetime


class IntakeCreate(BaseModel):
    client: ClientCreate
    deal: DealCreate


class IntakeUpdate(BaseModel):
    client: ClientUpdate | None = None
    deal: DealUpdate | None = None


class IntakeRead(BaseModel):
    client: ClientRead
    deal: DealRead