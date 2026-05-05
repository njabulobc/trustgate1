from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.user import User, UserRole
from app.schemas.auth import AuthTokenResponse, LoginRequest, UserCreate, UserRead, UserUpdate
from app.services.auth_service import AuthenticationFailedError, AuthService, UserConflictError
from app.services.permissions import get_role_capabilities

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthTokenResponse, status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, db: DBSession) -> AuthTokenResponse:
    try:
        principal = AuthService.authenticate(db=db, username=payload.username, password=payload.password)
    except AuthenticationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return AuthTokenResponse(access_token=principal.token, user=UserRead.model_validate(principal.user, update={"capabilities": get_role_capabilities(principal.user.role)}))


@router.get("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
def read_current_user(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user, update={"capabilities": get_role_capabilities(user.role)})


@router.get(
    "/users",
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
)
def list_users(
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR)),
) -> list[UserRead]:
    return [UserRead.model_validate(item, update={"capabilities": get_role_capabilities(item.role)}) for item in AuthService.list_users(db=db)]


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR)),
) -> UserRead:
    try:
        created = AuthService.create_user(
            db=db,
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role,
            password=payload.password,
            actor=user,
        )
    except UserConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserRead.model_validate(created, update={"capabilities": get_role_capabilities(created.role)})


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMINISTRATOR)),
) -> UserRead:
    try:
        updated = AuthService.update_user(
            db=db,
            user_id=user_id,
            update_data=payload.model_dump(exclude_unset=True),
            actor=user,
        )
    except (UserConflictError, AuthenticationFailedError) as exc:
        status_code = status.HTTP_409_CONFLICT if isinstance(exc, UserConflictError) else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return UserRead.model_validate(updated, update={"capabilities": get_role_capabilities(updated.role)})
