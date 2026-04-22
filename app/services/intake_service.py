from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.deal import Deal
from app.schemas.intake import IntakeCreate, IntakeUpdate
from app.services.audit_service import record_audit_event


class IntakeServiceError(Exception):
    """Base exception for intake service failures."""


class IntakeNotFoundError(IntakeServiceError):
    """Raised when the requested intake record cannot be found."""


class IntakeConflictError(IntakeServiceError):
    """Raised when a write operation violates a persistence constraint."""


class IntakeService:
    @staticmethod
    def create_intake(
        db: Session,
        payload: IntakeCreate,
        actor: str = "demo_user",
    ) -> tuple[Client, Deal]:
        client = Client(**payload.client.model_dump())

        try:
            db.add(client)
            db.flush()

            deal = Deal(
                client_id=client.id,
                **payload.deal.model_dump(),
            )
            db.add(deal)
            db.flush()

            record_audit_event(
                db=db,
                actor=actor,
                action="client.created",
                entity_type="client",
                entity_id=client.id,
                metadata_payload={
                    "client_type": client.client_type.value,
                    "status": client.status.value,
                },
            )
            record_audit_event(
                db=db,
                actor=actor,
                action="deal.created",
                entity_type="deal",
                entity_id=deal.id,
                metadata_payload={
                    "client_id": client.id,
                    "transaction_reference": deal.transaction_reference,
                    "transaction_type": deal.transaction_type.value,
                    "status": deal.status.value,
                },
            )

            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise IntakeConflictError(
                "Unable to create intake because the data violates a persistence constraint."
            ) from exc
        except Exception:
            db.rollback()
            raise

        db.refresh(client)
        db.refresh(deal)
        return client, deal

    @staticmethod
    def get_intake_by_client_id(
        db: Session,
        client_id: int,
        deal_id: int | None = None,
    ) -> tuple[Client, Deal]:
        client = IntakeService._get_client_or_raise(db=db, client_id=client_id)
        deal = IntakeService._get_deal_for_client_or_raise(
            db=db,
            client_id=client.id,
            deal_id=deal_id,
        )
        return client, deal

    @staticmethod
    def get_intake_by_deal_id(
        db: Session,
        deal_id: int,
    ) -> tuple[Client, Deal]:
        deal = IntakeService._get_deal_or_raise(db=db, deal_id=deal_id)
        client = IntakeService._get_client_or_raise(db=db, client_id=deal.client_id)
        return client, deal

    @staticmethod
    def update_intake(
        db: Session,
        client_id: int,
        payload: IntakeUpdate,
        actor: str = "demo_user",
        deal_id: int | None = None,
    ) -> tuple[Client, Deal]:
        client, deal = IntakeService.get_intake_by_client_id(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
        )

        client_changed_fields: list[str] = []
        deal_changed_fields: list[str] = []

        if payload.client is not None:
            client_changed_fields = IntakeService._apply_updates(
                instance=client,
                update_data=payload.client.model_dump(exclude_unset=True),
            )

        if payload.deal is not None:
            deal_changed_fields = IntakeService._apply_updates(
                instance=deal,
                update_data=payload.deal.model_dump(exclude_unset=True),
            )

        if not client_changed_fields and not deal_changed_fields:
            return client, deal

        try:
            if client_changed_fields:
                record_audit_event(
                    db=db,
                    actor=actor,
                    action="client.updated",
                    entity_type="client",
                    entity_id=client.id,
                    metadata_payload={
                        "changed_fields": client_changed_fields,
                    },
                )

            if deal_changed_fields:
                record_audit_event(
                    db=db,
                    actor=actor,
                    action="deal.updated",
                    entity_type="deal",
                    entity_id=deal.id,
                    metadata_payload={
                        "client_id": client.id,
                        "changed_fields": deal_changed_fields,
                    },
                )

            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise IntakeConflictError(
                "Unable to update intake because the data violates a persistence constraint."
            ) from exc
        except Exception:
            db.rollback()
            raise

        db.refresh(client)
        db.refresh(deal)
        return client, deal

    @staticmethod
    def _get_client_or_raise(db: Session, client_id: int) -> Client:
        stmt = select(Client).where(Client.id == client_id)
        client = db.execute(stmt).scalar_one_or_none()
        if client is None:
            raise IntakeNotFoundError(f"Client with id={client_id} was not found.")
        return client

    @staticmethod
    def _get_deal_or_raise(db: Session, deal_id: int) -> Deal:
        stmt = select(Deal).where(Deal.id == deal_id)
        deal = db.execute(stmt).scalar_one_or_none()
        if deal is None:
            raise IntakeNotFoundError(f"Deal with id={deal_id} was not found.")
        return deal

    @staticmethod
    def _get_deal_for_client_or_raise(
        db: Session,
        client_id: int,
        deal_id: int | None = None,
    ) -> Deal:
        stmt = select(Deal).where(Deal.client_id == client_id)

        if deal_id is not None:
            stmt = stmt.where(Deal.id == deal_id)
        else:
            stmt = stmt.order_by(Deal.created_at.desc(), Deal.id.desc())

        deal = db.execute(stmt).scalars().first()
        if deal is None:
            if deal_id is not None:
                raise IntakeNotFoundError(
                    f"Deal with id={deal_id} for client id={client_id} was not found."
                )
            raise IntakeNotFoundError(
                f"No associated deal was found for client id={client_id}."
            )
        return deal

    @staticmethod
    def _apply_updates(instance: Any, update_data: dict[str, Any]) -> list[str]:
        changed_fields: list[str] = []

        for field_name, new_value in update_data.items():
            current_value = getattr(instance, field_name)
            if current_value != new_value:
                setattr(instance, field_name, new_value)
                changed_fields.append(field_name)

        return changed_fields


def create_intake(
    db: Session,
    payload: IntakeCreate,
    actor: str = "demo_user",
) -> tuple[Client, Deal]:
    return IntakeService.create_intake(db=db, payload=payload, actor=actor)


def get_intake_by_client_id(
    db: Session,
    client_id: int,
    deal_id: int | None = None,
) -> tuple[Client, Deal]:
    return IntakeService.get_intake_by_client_id(
        db=db,
        client_id=client_id,
        deal_id=deal_id,
    )


def get_intake_by_deal_id(
    db: Session,
    deal_id: int,
) -> tuple[Client, Deal]:
    return IntakeService.get_intake_by_deal_id(db=db, deal_id=deal_id)


def update_intake(
    db: Session,
    client_id: int,
    payload: IntakeUpdate,
    actor: str = "demo_user",
    deal_id: int | None = None,
) -> tuple[Client, Deal]:
    return IntakeService.update_intake(
        db=db,
        client_id=client_id,
        payload=payload,
        actor=actor,
        deal_id=deal_id,
    )