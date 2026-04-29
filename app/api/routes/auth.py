from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.core.auth import authenticate, create_session
from app.schemas.auth import LoginRequest, LoginResponse, SessionUserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(payload: LoginRequest) -> LoginResponse:
    user = authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username/password")
    token = create_session(user)
    return LoginResponse(access_token=token, user=SessionUserRead(username=user.username, role=user.role, display_name=user.display_name))


@router.get("/session", response_model=SessionUserRead, status_code=status.HTTP_200_OK)
def get_session(user: CurrentUser) -> SessionUserRead:
    return SessionUserRead(username=user.username, role=user.role, display_name=user.display_name)
