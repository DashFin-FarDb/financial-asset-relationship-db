"""Pydantic models for the API authentication layer."""

from typing import Optional

from pydantic import BaseModel


class UserInDB(BaseModel):
    """User record as stored in the database, including hashed password."""

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    hashed_password: str
