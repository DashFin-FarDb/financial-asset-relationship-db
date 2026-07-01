"""Pydantic models for the API authentication layer."""

from pydantic import BaseModel


class User(BaseModel):
    """User model for authentication."""

    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserPublic(User):
    """Public user model returned by authentication API endpoints."""


class UserInDB(User):
    """User model with hashed password for database storage."""

    hashed_password: str
