from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


class AuthServiceError(Exception):
    pass


class AuthenticationError(AuthServiceError):
    pass


class AuthorizationError(AuthServiceError):
    pass


class AuthService:
    TOKEN_TTL_MINUTES = 60

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390000)
        return f"pbkdf2_sha256${_b64url_encode(salt)}${_b64url_encode(derived)}"

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            algorithm, salt_b64, hash_b64 = password_hash.split("$")
        except ValueError:
            return False
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(hash_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390000)
        return hmac.compare_digest(expected, candidate)

    @classmethod
    def issue_token(cls, user: User, secret_key: str) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        expires_at = _utcnow() + timedelta(minutes=cls.TOKEN_TTL_MINUTES)
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "exp": int(expires_at.timestamp()),
            "iat": int(_utcnow().timestamp()),
        }
        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"

    @staticmethod
    def decode_token(token: str, secret_key: str) -> dict:
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError as exc:
            raise AuthenticationError("Invalid token format.") from exc

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            raise AuthenticationError("Invalid token signature.")

        payload = json.loads(_b64url_decode(payload_b64))
        exp = payload.get("exp")
        if exp is None or int(exp) < int(_utcnow().timestamp()):
            raise AuthenticationError("Token has expired.")
        return payload

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        stmt = select(User).where(User.email == email)
        user = db.execute(stmt).scalar_one_or_none()
        if user is None or not user.is_active or not AuthService.verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        return user

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return db.execute(stmt).scalar_one_or_none()

    @classmethod
    def ensure_seed_admin(cls, db: Session) -> None:
        stmt = select(User).where(User.email == "admin@trustgate.local")
        existing = db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return
        user = User(
            email="admin@trustgate.local",
            full_name="System Admin",
            password_hash=cls.hash_password("trustgate-admin"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()
