from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User, UserRole
from app.services.audit_service import record_audit_event


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthServiceError(Exception):
    """Base exception for authentication failures."""


class AuthenticationFailedError(AuthServiceError):
    """Raised when credentials are invalid."""


class AuthorizationError(AuthServiceError):
    """Raised when the user cannot perform the requested action."""


class UserConflictError(AuthServiceError):
    """Raised when a user mutation conflicts with persistence constraints."""


@dataclass(slots=True)
class AuthenticatedPrincipal:
    user: User
    token: str


class PasswordHasher:
    ITERATIONS = 240_000

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PasswordHasher.ITERATIONS)
        return "$".join(
            [
                "pbkdf2_sha256",
                str(PasswordHasher.ITERATIONS),
                base64.urlsafe_b64encode(salt).decode("ascii"),
                base64.urlsafe_b64encode(derived).decode("ascii"),
            ]
        )

    @staticmethod
    def verify_password(password: str, encoded_hash: str) -> bool:
        try:
            algorithm, iterations_text, salt_b64, hash_b64 = encoded_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            iterations = int(iterations_text)
            salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
            expected = base64.urlsafe_b64decode(hash_b64.encode("ascii"))
        except (ValueError, TypeError, base64.binascii.Error):
            return False

        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)


class JwtService:
    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    @staticmethod
    def _b64url_decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))

    @staticmethod
    def create_access_token(user: User) -> str:
        expires_at = utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "iss": settings.JWT_ISSUER,
            "exp": int(expires_at.timestamp()),
        }
        signing_input = ".".join(
            [
                JwtService._b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
                JwtService._b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
            ]
        )
        signature = hmac.new(
            settings.JWT_SECRET_KEY.get_secret_value().encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return f"{signing_input}.{JwtService._b64url_encode(signature)}"

    @staticmethod
    def decode_access_token(token: str) -> dict[str, Any]:
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError as exc:
            raise AuthenticationFailedError("Malformed access token.") from exc

        signing_input = f"{header_b64}.{payload_b64}"
        expected_signature = hmac.new(
            settings.JWT_SECRET_KEY.get_secret_value().encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        actual_signature = JwtService._b64url_decode(signature_b64)
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise AuthenticationFailedError("Invalid access token signature.")

        payload = json.loads(JwtService._b64url_decode(payload_b64))
        if payload.get("iss") != settings.JWT_ISSUER:
            raise AuthenticationFailedError("Invalid access token issuer.")
        if int(payload.get("exp", 0)) < int(utcnow().timestamp()):
            raise AuthenticationFailedError("Access token has expired.")
        return payload


class AuthService:
    @staticmethod
    def seed_bootstrap_admin(db: Session) -> None:
        stmt = select(User).where(User.username == settings.BOOTSTRAP_ADMIN_USERNAME)
        existing = db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return

        user = User(
            username=settings.BOOTSTRAP_ADMIN_USERNAME,
            email=settings.BOOTSTRAP_ADMIN_EMAIL,
            full_name=settings.BOOTSTRAP_ADMIN_FULL_NAME,
            role=UserRole.ADMINISTRATOR,
            password_hash=PasswordHasher.hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD.get_secret_value()),
            is_active=True,
        )
        db.add(user)
        db.commit()

    @staticmethod
    def authenticate(db: Session, username: str, password: str) -> AuthenticatedPrincipal:
        stmt = select(User).where(User.username == username)
        user = db.execute(stmt).scalar_one_or_none()
        if user is None or not user.is_active or not PasswordHasher.verify_password(password, user.password_hash):
            raise AuthenticationFailedError("Invalid username or password.")

        user.last_login_at = utcnow()
        token = JwtService.create_access_token(user)
        record_audit_event(
            db=db,
            actor=user.username,
            user_id=user.id,
            action="auth.login",
            module="auth",
            entity_type="user",
            entity_id=user.id,
            metadata_payload={"role": user.role.value},
        )
        db.commit()
        db.refresh(user)
        return AuthenticatedPrincipal(user=user, token=token)

    @staticmethod
    def get_user_from_token(db: Session, token: str) -> User:
        payload = JwtService.decode_access_token(token)
        user_id = int(payload["sub"])
        stmt = select(User).where(User.id == user_id)
        user = db.execute(stmt).scalar_one_or_none()
        if user is None or not user.is_active:
            raise AuthenticationFailedError("Authenticated user is not available.")
        return user

    @staticmethod
    def list_users(db: Session) -> list[User]:
        stmt = select(User).order_by(User.created_at.asc(), User.id.asc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_user(
        db: Session,
        *,
        username: str,
        email: str,
        full_name: str,
        role: UserRole,
        password: str,
        actor: User,
    ) -> User:
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            password_hash=PasswordHasher.hash_password(password),
            is_active=True,
        )
        try:
            db.add(user)
            db.flush()
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="user.created",
                module="administration",
                entity_type="user",
                entity_id=user.id,
                metadata_payload={"role": role.value, "email": email},
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise UserConflictError("Unable to create user because the username or email already exists.") from exc
        db.refresh(user)
        return user

    @staticmethod
    def update_user(
        db: Session,
        *,
        user_id: int,
        update_data: dict[str, Any],
        actor: User,
    ) -> User:
        stmt = select(User).where(User.id == user_id)
        user = db.execute(stmt).scalar_one_or_none()
        if user is None:
            raise AuthenticationFailedError(f"User with id={user_id} was not found.")

        previous_value = {
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
        }

        if "password" in update_data and update_data["password"]:
            user.password_hash = PasswordHasher.hash_password(str(update_data.pop("password")))

        for field_name, field_value in update_data.items():
            if field_value is not None and hasattr(user, field_name):
                setattr(user, field_name, field_value)

        try:
            record_audit_event(
                db=db,
                actor=actor.username,
                user_id=actor.id,
                action="user.updated",
                module="administration",
                entity_type="user",
                entity_id=user.id,
                previous_value=previous_value,
                new_value={
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "is_active": user.is_active,
                },
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise UserConflictError("Unable to update user because the username or email already exists.") from exc
        db.refresh(user)
        return user
