from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.deal import Deal
from app.models.linked_party import LinkedParty
from app.schemas.relationship import LinkedPartyCreate, LinkedPartyUpdate
from app.services.audit_service import record_audit_event


class RelationshipServiceError(Exception):
    """Base exception for linked-party service failures."""


class LinkedPartyNotFoundError(RelationshipServiceError):
    """Raised when a linked party cannot be found."""


class LinkedPartyConflictError(RelationshipServiceError):
    """Raised when a write operation violates a persistence constraint."""


class RelationshipValidationError(RelationshipServiceError):
    """Raised when linked-party input fails service-level validation."""


class RelationshipService:
    @staticmethod
    def create_linked_party(
        db: Session,
        payload: LinkedPartyCreate,
        actor: str = "demo_user",
    ) -> LinkedParty:
        RelationshipService._validate_client_and_deal(
            db=db,
            client_id=payload.client_id,
            deal_id=payload.deal_id,
        )

        linked_party = LinkedParty(**payload.model_dump())

        try:
            db.add(linked_party)
            db.flush()

            record_audit_event(
                db=db,
                actor=actor,
                action="linked_party.created",
                entity_type="linked_party",
                entity_id=linked_party.id,
                metadata_payload={
                    "client_id": linked_party.client_id,
                    "deal_id": linked_party.deal_id,
                    "party_type": linked_party.party_type.value,
                    "role": linked_party.role.value,
                    "screening_required": linked_party.screening_required,
                },
            )

            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise LinkedPartyConflictError(
                "Unable to create linked party because the data violates a persistence constraint."
            ) from exc
        except Exception:
            db.rollback()
            raise

        db.refresh(linked_party)
        return linked_party

    @staticmethod
    def list_linked_parties(
        db: Session,
        *,
        client_id: int | None = None,
        deal_id: int | None = None,
    ) -> list[LinkedParty]:
        if client_id is not None and deal_id is not None:
            RelationshipService._validate_client_and_deal(
                db=db,
                client_id=client_id,
                deal_id=deal_id,
            )
        elif client_id is not None:
            RelationshipService._get_client_or_raise(db=db, client_id=client_id)
        elif deal_id is not None:
            RelationshipService._get_deal_or_raise(db=db, deal_id=deal_id)

        stmt = select(LinkedParty)

        if client_id is not None:
            stmt = stmt.where(LinkedParty.client_id == client_id)
        if deal_id is not None:
            stmt = stmt.where(LinkedParty.deal_id == deal_id)

        stmt = stmt.order_by(LinkedParty.created_at.desc(), LinkedParty.id.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_linked_party(
        db: Session,
        linked_party_id: int,
    ) -> LinkedParty:
        return RelationshipService._get_linked_party_or_raise(
            db=db,
            linked_party_id=linked_party_id,
        )

    @staticmethod
    def update_linked_party(
        db: Session,
        linked_party_id: int,
        payload: LinkedPartyUpdate,
        actor: str = "demo_user",
    ) -> LinkedParty:
        linked_party = RelationshipService._get_linked_party_or_raise(
            db=db,
            linked_party_id=linked_party_id,
        )

        changed_fields = RelationshipService._apply_updates(
            instance=linked_party,
            update_data=payload.model_dump(exclude_unset=True),
        )

        if not changed_fields:
            return linked_party

        try:
            record_audit_event(
                db=db,
                actor=actor,
                action="linked_party.updated",
                entity_type="linked_party",
                entity_id=linked_party.id,
                metadata_payload={
                    "client_id": linked_party.client_id,
                    "deal_id": linked_party.deal_id,
                    "changed_fields": changed_fields,
                },
            )

            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise LinkedPartyConflictError(
                "Unable to update linked party because the data violates a persistence constraint."
            ) from exc
        except Exception:
            db.rollback()
            raise

        db.refresh(linked_party)
        return linked_party

    @staticmethod
    def delete_linked_party(
        db: Session,
        linked_party_id: int,
        actor: str = "demo_user",
    ) -> None:
        linked_party = RelationshipService._get_linked_party_or_raise(
            db=db,
            linked_party_id=linked_party_id,
        )

        try:
            record_audit_event(
                db=db,
                actor=actor,
                action="linked_party.deleted",
                entity_type="linked_party",
                entity_id=linked_party.id,
                metadata_payload={
                    "client_id": linked_party.client_id,
                    "deal_id": linked_party.deal_id,
                    "role": linked_party.role.value,
                    "primary_name": linked_party.primary_name,
                },
            )

            db.delete(linked_party)
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _get_linked_party_or_raise(
        db: Session,
        linked_party_id: int,
    ) -> LinkedParty:
        stmt = select(LinkedParty).where(LinkedParty.id == linked_party_id)
        linked_party = db.execute(stmt).scalar_one_or_none()

        if linked_party is None:
            raise LinkedPartyNotFoundError(
                f"Linked party with id={linked_party_id} was not found."
            )

        return linked_party

    @staticmethod
    def _get_client_or_raise(db: Session, client_id: int) -> Client:
        stmt = select(Client).where(Client.id == client_id)
        client = db.execute(stmt).scalar_one_or_none()

        if client is None:
            raise RelationshipValidationError(
                f"Client with id={client_id} was not found."
            )

        return client

    @staticmethod
    def _get_deal_or_raise(db: Session, deal_id: int) -> Deal:
        stmt = select(Deal).where(Deal.id == deal_id)
        deal = db.execute(stmt).scalar_one_or_none()

        if deal is None:
            raise RelationshipValidationError(
                f"Deal with id={deal_id} was not found."
            )

        return deal

    @staticmethod
    def _validate_client_and_deal(
        db: Session,
        *,
        client_id: int,
        deal_id: int,
    ) -> tuple[Client, Deal]:
        client = RelationshipService._get_client_or_raise(db=db, client_id=client_id)
        deal = RelationshipService._get_deal_or_raise(db=db, deal_id=deal_id)

        if deal.client_id != client.id:
            raise RelationshipValidationError(
                f"Deal with id={deal_id} does not belong to client id={client_id}."
            )

        return client, deal

    @staticmethod
    def _apply_updates(instance: Any, update_data: dict[str, Any]) -> list[str]:
        changed_fields: list[str] = []

        for field_name, new_value in update_data.items():
            current_value = getattr(instance, field_name)
            if current_value != new_value:
                setattr(instance, field_name, new_value)
                changed_fields.append(field_name)

        return changed_fields


def create_linked_party(
    db: Session,
    payload: LinkedPartyCreate,
    actor: str = "demo_user",
) -> LinkedParty:
    return RelationshipService.create_linked_party(db=db, payload=payload, actor=actor)


def list_linked_parties(
    db: Session,
    *,
    client_id: int | None = None,
    deal_id: int | None = None,
) -> list[LinkedParty]:
    return RelationshipService.list_linked_parties(
        db=db,
        client_id=client_id,
        deal_id=deal_id,
    )


def get_linked_party(
    db: Session,
    linked_party_id: int,
) -> LinkedParty:
    return RelationshipService.get_linked_party(db=db, linked_party_id=linked_party_id)


def update_linked_party(
    db: Session,
    linked_party_id: int,
    payload: LinkedPartyUpdate,
    actor: str = "demo_user",
) -> LinkedParty:
    return RelationshipService.update_linked_party(
        db=db,
        linked_party_id=linked_party_id,
        payload=payload,
        actor=actor,
    )


def delete_linked_party(
    db: Session,
    linked_party_id: int,
    actor: str = "demo_user",
) -> None:
    RelationshipService.delete_linked_party(
        db=db,
        linked_party_id=linked_party_id,
        actor=actor,
    )