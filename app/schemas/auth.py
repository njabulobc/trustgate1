from pydantic import BaseModel

from app.core.auth import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionUserRead(BaseModel):
    username: str
    role: UserRole
    display_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: SessionUserRead
