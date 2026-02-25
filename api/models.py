"""Pydantic models for the API package."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class UserInDB(BaseModel):
    """Database-backed user record for authentication flows."""

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    hashed_password: str
