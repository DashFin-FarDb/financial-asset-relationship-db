"""Authentication module for the Financial Asset Relationship Database API"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext  # pyright: ignore[reportMissingModuleSource]
from pydantic import BaseModel

from .database import execute, fetch_one, fetch_value, initialize_schema
from .models import UserInDB

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set before importing api.auth")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Models
class Token(BaseModel):
    """Represents an access token and its type returned to the client."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Carries optional token payload data, such as the extracted username."""

    username: Optional[str] = None


class User(BaseModel):
    """Schema for user details including authentication credentials and profile information."""

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    hashed_password: str


def _is_truthy(value: str | None) -> bool:
    """
    Determine whether a string value represents a truthy boolean.

    Parameters:
        value (str | None): Input string to evaluate; recognised truthy forms are
            "true", "1", "yes" and "on" (case-insensitive).

    Returns:
        bool: True if `value` matches a recognised truthy form,
            False otherwise.
    """
    return False if not value else value.lower() in ("true", "1", "yes", "on")


class UserRepository:
    """Repository for accessing user credential records."""

    @staticmethod
    def get_user(username: str) -> Optional[UserInDB]:
        """
        Retrieve a user record by username from the repository.

        Returns:
            `UserInDB` for the matching username, `None` if no such user exists.
        """
        row = fetch_one(
            """
            SELECT username, email, full_name, hashed_password, disabled
            FROM user_credentials
            WHERE username = ?
            """,
            (username,),
        )
        if row is None:
            return None
        return UserInDB(
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            disabled=bool(row["disabled"]),
            hashed_password=row["hashed_password"],
        )

    @staticmethod
    def has_users() -> bool:
        """
        Determine whether any user credential records exist.

        Returns:
            `True` if at least one user credential exists, `False` otherwise.
        """
        return fetch_value("SELECT 1 FROM user_credentials LIMIT 1") is not None

    class UserProfile(TypedDict, total=False):
        """Optional user profile fields for user upsert operations."""

        user_email: str | None
        user_full_name: str | None
        is_disabled: bool

    @staticmethod
    def create_or_update_user(
        *,
        username: str,
        hashed_password: str,
        user_profile: Optional["UserRepository.UserProfile"] = None,
        **legacy_profile_fields: object,
    ) -> None:
        """
        Create or update a user credential record in the repository.

        Performs an upsert into the user_credentials table for the given username using the provided hashed password and optional profile data. Supports a dictionary-style `user_profile` with optional keys `user_email`, `user_full_name`, and `is_disabled`; legacy keyword fields (`user_email`, `user_full_name`, `is_disabled`) passed via `**legacy_profile_fields` are also accepted and take precedence when provided.

        Parameters:
            username (str): Unique identifier for the user.
            hashed_password (str): Password hash (must already be hashed).
            user_profile (Optional[UserRepository.UserProfile]): Optional profile mapping containing any of `user_email`, `user_full_name`, `is_disabled`.
            **legacy_profile_fields (object): Backward-compatible keyword fields (`user_email`, `user_full_name`, `is_disabled`) accepted for existing call sites.
        """
        profile = user_profile.copy() if user_profile is not None else {}

        # Backward-compatible mapping for existing call sites using keyword fields.
        if "user_email" in legacy_profile_fields:
            profile["user_email"] = (
                str(legacy_profile_fields["user_email"]) if legacy_profile_fields["user_email"] is not None else None
            )
        if "user_full_name" in legacy_profile_fields:
            profile["user_full_name"] = (
                str(legacy_profile_fields["user_full_name"])
                if legacy_profile_fields["user_full_name"] is not None
                else None
            )
        if "is_disabled" in legacy_profile_fields:
            profile["is_disabled"] = bool(legacy_profile_fields["is_disabled"])

        # Remove recognized legacy keys and error on any unexpected ones to avoid silent typos.
        for _key in ("user_email", "user_full_name", "is_disabled"):
            legacy_profile_fields.pop(_key, None)

        if legacy_profile_fields:
            unexpected_keys = ", ".join(sorted(legacy_profile_fields.keys()))
            raise TypeError(f"Unexpected legacy profile field(s): {unexpected_keys}")

        user_email = profile.get("user_email")
        user_full_name = profile.get("user_full_name")
        is_disabled = profile.get("is_disabled", False)

        execute(
            """
            INSERT INTO user_credentials (
                username,
                email,
                full_name,
                hashed_password,
                disabled
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                email=excluded.email,
                full_name=excluded.full_name,
                hashed_password=excluded.hashed_password,
                disabled=excluded.disabled
            """,
            (
                username,
                user_email,
                user_full_name,
                hashed_password,
                1 if is_disabled else 0,
            ),
        )


initialize_schema()
user_repository = UserRepository()


def verify_password(plain_password, hashed_password):
    """
    Verify whether a plaintext password matches a stored hashed password.

    Returns:
        `True` if the plaintext password matches the hashed password, `False` otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """
    Hash a plaintext password using the configured password-hashing context.

    Parameters:
        password (str): Plaintext password to hash.

    Returns:
        str: The hashed password.
    """
    return pwd_context.hash(password)


def _seed_credentials_from_env(repository: UserRepository) -> None:
    """
    Seed an administrative user from environment variables into the given repository.

    If both ADMIN_USERNAME and ADMIN_PASSWORD are set, create or update that user
    in the repository using optional ADMIN_EMAIL, ADMIN_FULL_NAME, and
    ADMIN_DISABLED (interpreted as a truthy flag). The provided password is stored
    hashed. If either ADMIN_USERNAME or ADMIN_PASSWORD is missing, the repository is
    not modified.
    """
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        return

    hashed_password = get_password_hash(password)
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_full_name = os.getenv("ADMIN_FULL_NAME")
    admin_disabled = _is_truthy(os.getenv("ADMIN_DISABLED", "false"))

    repository.create_or_update_user(
        username=username,
        hashed_password=hashed_password,
        user_profile={
            "user_email": admin_email,
            "user_full_name": admin_full_name,
            "is_disabled": admin_disabled,
        },
    )


_seed_credentials_from_env(user_repository)

if not user_repository.has_users():
    raise ValueError(
        "No user credentials available. Provide ADMIN_USERNAME and ADMIN_PASSWORD or pre-populate the database."
    )


def get_user(
    username: str,
    repository: Optional[UserRepository] = None,
) -> Optional[UserInDB]:
    """
    Retrieve a user by username.

    Parameters:
        repository (Optional[UserRepository]): Repository to query;
            if omitted the module-level `user_repository` is used.

    Returns:
        Optional[UserInDB]: The matching UserInDB instance, or `None` if no
            user exists with that username.
    """
    repo = repository or user_repository
    return repo.get_user(username)


def authenticate_user(
    username: str,
    password: str,
    repository: Optional[UserRepository] = None,
) -> UserInDB | bool:
    """
    Authenticate a username and password and return the corresponding stored user.

    Parameters:
        username (str): Username to authenticate.
        password (str): Plaintext password to verify.
        repository (Optional[UserRepository]): Repository to query for the user; if
            omitted the module-level repository is used.

    Returns:
        UserInDB when authentication succeeds, `False` otherwise.
    """
    user = get_user(username, repository=repository)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create a JWT access token that includes an expiry (`exp`) claim.

    Parameters:
        data (dict):
            Claims to include in the token payload.
            The function will add or overwrite the `exp` claim.
        expires_delta (Optional[timedelta]):
            Time span after which the token expires; if omitted the token
            expires in 15 minutes.

    Returns:
        str: Encoded JWT as a compact string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Retrieve the User corresponding to the provided JWT.

    Returns:
        User: The User model for the token's subject.

    Raises:
        HTTPException: 401 with detail "Token has expired" if the token is expired.
        HTTPException: 401 with detail "Could not validate credentials" if the token is invalid,
            missing the subject, or no matching user is found.
    """
    credentials_exception = _build_credentials_exception()
    expired_exception = _build_expired_exception()
    username = _decode_username_from_token(
        token=token,
        credentials_exception=credentials_exception,
        expired_exception=expired_exception,
    )
    user = get_user(username)
    if user is None:
        raise credentials_exception
    return user


def _build_credentials_exception() -> HTTPException:
    """
    Build the HTTPException used when authentication credentials are invalid.

    Returns:
        HTTPException: 401 Unauthorized with detail "Could not validate credentials" and header "WWW-Authenticate: Bearer".
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _build_expired_exception() -> HTTPException:
    """
    Return an HTTP 401 Unauthorized exception representing an expired bearer token.

    Returns:
        HTTPException: An exception with status 401, detail "Token has expired", and a
        `WWW-Authenticate: Bearer` header.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token has expired",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_username_from_token(
    *,
    token: str,
    credentials_exception: HTTPException,
    expired_exception: HTTPException,
) -> str:
    """
    Extracts the subject username from a JWT and validates it.

    Parameters:
        token (str): JWT access token containing a `sub` claim.
        credentials_exception (HTTPException): Exception to raise when the token is invalid or missing the subject.
        expired_exception (HTTPException): Exception to raise when the token has expired.

    Returns:
        username (str): The `sub` claim value (username) from the token.

    Raises:
        HTTPException: `expired_exception` if the token has expired.
        HTTPException: `credentials_exception` if the token is invalid or the `sub` claim is missing.
    """
    try:
        # Explicitly specify algorithms parameter to prevent algorithm confusion attacks
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        return str(TokenData(username=username).username)
    except ExpiredSignatureError as e:
        raise expired_exception from e
    except InvalidTokenError as e:
        raise credentials_exception from e


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """
    Ensure the authenticated user is active.

    Raises:
        HTTPException: 400 with detail "Inactive user" if the user's account is disabled.

    Returns:
        current_user (User): The authenticated user's public profile.
    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
