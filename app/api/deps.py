from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import UserRecord, UserRole, get_session
from app.core.database import get_db


DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(authorization: str | None = Header(default=None)) -> UserRecord:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.replace("Bearer ", "", 1).strip()
    user = get_session(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return user


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    def role_checker(user: CurrentUser) -> UserRecord:
        if user.role not in roles and user.role != UserRole.SUPERUSER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return role_checker


__all__ = ["get_db", "DBSession", "CurrentUser", "require_roles"]
