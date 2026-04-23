from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import StrEnum


class UserRole(StrEnum):
    SUPERUSER = "superuser"
    REVIEWER = "reviewer"
    ANALYST = "analyst"


@dataclass(frozen=True)
class UserRecord:
    username: str
    password: str
    role: UserRole
    display_name: str


TEST_USERS: dict[str, UserRecord] = {
    "superuser": UserRecord(
        username="superuser",
        password="superuser-pass",
        role=UserRole.SUPERUSER,
        display_name="Super User",
    ),
    "reviewer": UserRecord(
        username="reviewer",
        password="reviewer-pass",
        role=UserRole.REVIEWER,
        display_name="Review Analyst",
    ),
    "analyst": UserRecord(
        username="analyst",
        password="analyst-pass",
        role=UserRole.ANALYST,
        display_name="Intake Analyst",
    ),
}

SESSIONS: dict[str, UserRecord] = {}


def authenticate(username: str, password: str) -> UserRecord | None:
    user = TEST_USERS.get(username)
    if not user or user.password != password:
        return None
    return user


def create_session(user: UserRecord) -> str:
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = user
    return token


def get_session(token: str) -> UserRecord | None:
    return SESSIONS.get(token)
