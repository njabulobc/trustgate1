from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import AuthService, AuthenticationError


DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DBSession,
    authorization: str | None = Header(default=None),
) -> User:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = AuthService.decode_token(token, settings.JWT_SECRET_KEY.get_secret_value())
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
        )

    user = AuthService.get_user_by_id(db=db, user_id=int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active or no longer exists.",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole) -> Callable[[CurrentUser], User]:
    def _role_guard(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this action.",
            )
        return user

    return _role_guard


__all__ = ["get_db", "DBSession", "CurrentUser", "require_roles"]
