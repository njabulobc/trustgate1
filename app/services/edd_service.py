from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.deal import Deal
from app.models.edd_case import EDDCase, EDDCaseStatus
from app.schemas.edd import EDDCaseCreate, EDDCaseUpdate
from app.services.audit_service import record_audit_event


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EDDServiceError(Exception):
    pass


class EDDValidationError(EDDServiceError):
    pass


class EDDNotFoundError(EDDServiceError):
    pass


class EDDPersistenceError(EDDServiceError):
    pass


class EDDService:
    @staticmethod
    def create_case(db: Session, payload: EDDCaseCreate, actor: str = "demo_user") -> EDDCase:
        client = db.execute(select(Client).where(Client.id == payload.client_id)).scalar_one_or_none()
        if client is None:
            raise EDDValidationError(f"Client with id={payload.client_id} was not found.")

        if payload.deal_id is not None:
            deal = db.execute(select(Deal).where(Deal.id == payload.deal_id)).scalar_one_or_none()
            if deal is None or deal.client_id != client.id:
                raise EDDValidationError("deal_id is invalid for the specified client.")

        case = EDDCase(**payload.model_dump())

        try:
            db.add(case)
            db.flush()
            record_audit_event(
                db=db,
                actor=actor,
                action="edd_case.created",
                entity_type="edd_case",
                entity_id=case.id,
                metadata_payload={"client_id": case.client_id, "deal_id": case.deal_id, "status": case.status.value},
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise EDDPersistenceError("Unable to create EDD case due to persistence constraints.") from exc

        db.refresh(case)
        return case

    @staticmethod
    def list_cases(db: Session, client_id: int | None = None) -> list[EDDCase]:
        stmt = select(EDDCase)
        if client_id is not None:
            stmt = stmt.where(EDDCase.client_id == client_id)
        stmt = stmt.order_by(EDDCase.created_at.desc(), EDDCase.id.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_case(db: Session, case_id: int, payload: EDDCaseUpdate, actor: str = "demo_user") -> EDDCase:
        case = db.execute(select(EDDCase).where(EDDCase.id == case_id)).scalar_one_or_none()
        if case is None:
            raise EDDNotFoundError(f"EDD case with id={case_id} was not found.")

        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(case, key, value)

        if case.status == EDDCaseStatus.CLOSED:
            case.closed_at = utcnow()

        try:
            record_audit_event(
                db=db,
                actor=actor,
                action="edd_case.updated",
                entity_type="edd_case",
                entity_id=case.id,
                metadata_payload={"status": case.status.value, "assigned_to": case.assigned_to},
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise EDDPersistenceError("Unable to update EDD case due to persistence constraints.") from exc

        db.refresh(case)
        return case


def create_edd_case(db: Session, payload: EDDCaseCreate, actor: str = "demo_user") -> EDDCase:
    return EDDService.create_case(db, payload, actor)


def list_edd_cases(db: Session, client_id: int | None = None) -> list[EDDCase]:
    return EDDService.list_cases(db, client_id)


def update_edd_case(db: Session, case_id: int, payload: EDDCaseUpdate, actor: str = "demo_user") -> EDDCase:
    return EDDService.update_case(db, case_id, payload, actor)
