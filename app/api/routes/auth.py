from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, require_roles
from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead
from app.services.auth_service import AuthService, AuthenticationError
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, db: DBSession) -> TokenResponse:
    try:
        user = AuthService.authenticate_user(db=db, email=payload.email, password=payload.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    token = AuthService.issue_token(user, settings.JWT_SECRET_KEY.get_secret_value())
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
def who_am_i(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def create_user(payload: UserCreate, db: DBSession, current_user: CurrentUser) -> UserRead:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=AuthService.hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    record_audit_event(
        db=db,
        actor=current_user.email,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        metadata_payload={"email": user.email, "role": user.role.value},
    )
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)
