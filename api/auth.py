"""Authentication module for the Financial Asset Relationship Database API."""

from __future__ import annotations

# pylint: disable=import-error
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext  # pyright: ignore[reportMissingModuleSource]
from pydantic import BaseModel
from typing_extensions import TypedDict

from api.models import User, UserInDB
from src.config.settings import Settings, get_settings, load_settings
from src.observability.context import get_request_context
from src.observability.facade import ObservabilityEvent, log_event

from .database import execute, fetch_one, fetch_value, initialize_schema

UTC = timezone.utc


logger = logging.getLogger(__name__)

# Security configuration
_AUTH_SETTINGS = load_settings()
SECRET_KEY = _AUTH_SETTINGS.required_secret_key

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REBUILD_OPERATOR_FORBIDDEN_DETAIL = "You do not have permission to perform destructive actions."
REBUILD_OPERATOR_NOT_CONFIGURED_DETAIL = "Rebuild operator authorization is not configured."
_SECURITY_AUDIT_LOGIN_SUCCESS = "auth_login_success"
_SECURITY_AUDIT_LOGIN_FAILURE = "auth_login_failure"
_SECURITY_AUDIT_TOKEN_EXPIRED = "auth_token_expired"  # noqa: S105
_SECURITY_AUDIT_TOKEN_INVALID = "auth_token_invalid"  # noqa: S105
_SECURITY_AUDIT_USER_DISABLED = "auth_user_disabled"
_SECURITY_AUDIT_ACCESS_DENIED = "auth_access_denied"
_SENSITIVE_METADATA_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "token",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "authorization",
        "secret",
        "secretkey",
        "apikey",
        "xapikey",
        "bearer",
    }
)
_SECURITY_AUDIT_IDENTITY_MAX_LENGTH = 128

__all__ = [
    "_SECURITY_AUDIT_ACCESS_DENIED",
    "_SECURITY_AUDIT_LOGIN_FAILURE",
    "_SECURITY_AUDIT_LOGIN_SUCCESS",
    "_SECURITY_AUDIT_TOKEN_EXPIRED",
    "_SECURITY_AUDIT_TOKEN_INVALID",
    "_SECURITY_AUDIT_USER_DISABLED",
    "_SecurityAuditEvent",
    "_log_security_event",
]

# Password hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@dataclass(frozen=True)
class _SecurityAuditEvent:
    """Bounded input payload for structured security audit logging."""

    event_slug: str
    username: str | None = None
    attempted_username: str | None = None
    request: Request | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    level: int = logging.INFO


def _request_security_metadata(request: Request | None = None) -> dict[str, str | None]:
    """Return bounded request metadata for security audit events."""
    context = get_request_context()
    metadata: dict[str, str | None] = {
        "request_id": context.get("request_id"),
        "correlation_id": context.get("correlation_id"),
        "trace_id": context.get("trace_id"),
        "span_id": context.get("span_id"),
        "endpoint": None,
        "ip_address": None,
    }

    if request is not None:
        metadata["endpoint"] = request.url.path
        metadata["ip_address"] = request.client.host if request.client else None

    return metadata


def _is_sensitive_metadata_key(key: str) -> bool:
    """Return whether a metadata key is a credential-bearing field name."""
    normalized = key.lower().replace("_", "").replace("-", "").replace(" ", "")
    if normalized == "tokentype":
        return False
    sensitive_substrings = ("password", "passwd", "pwd", "token", "authorization", "secret", "apikey")
    return normalized in _SENSITIVE_METADATA_KEYS or any(sub in normalized for sub in sensitive_substrings)


def _sanitize_metadata_value(value: Any) -> Any:
    """Recursively sanitize nested metadata values before logging."""
    if hasattr(value, "model_dump"):
        return _sanitize_metadata_value(value.model_dump())
    if hasattr(value, "dict"):
        return _sanitize_metadata_value(value.dict())
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_metadata_value(item)
            for key, item in value.items()
            if not _is_sensitive_metadata_key(str(key))
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_sanitize_metadata_value(item) for item in value]
    return value


def _safe_security_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Drop sensitive metadata keys recursively before emitting audit logs."""
    return {
        str(key): _sanitize_metadata_value(value)
        for key, value in metadata.items()
        if not _is_sensitive_metadata_key(str(key))
    }


def _bounded_security_identity(value: str | None) -> str | None:
    """Normalize and bound user-controlled identity fields before audit logging."""
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized[:_SECURITY_AUDIT_IDENTITY_MAX_LENGTH]


def _log_security_event(event: _SecurityAuditEvent) -> None:
    """Emit a structured security audit event without credential-bearing values."""
    event_metadata: dict[str, Any] = _safe_security_metadata(event.metadata) if event.metadata else {}

    req_meta = _request_security_metadata(event.request)
    for k, v in req_meta.items():
        event_metadata[k] = v

    username = _bounded_security_identity(event.username)
    attempted_username = _bounded_security_identity(event.attempted_username)
    if username is not None:
        event_metadata["username"] = username
    if attempted_username is not None:
        event_metadata["attempted_username"] = attempted_username

    log_event(
        logger,
        event.level,
        ObservabilityEvent(
            event=event.event_slug,
            message=f"Security event: {event.event_slug}",
            metadata=event_metadata,
        ),
    )


# Models
class Token(BaseModel):
    """Represents an access token and its type returned to the client."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Carries optional token payload data, such as the extracted username."""

    username: str | None = None


class UserRepository:
    """Repository for accessing user credential records."""

    @staticmethod
    def get_user(username: str) -> UserInDB | None:
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
        Check whether any user credential records exist.

        Returns:
            `true` if at least one user credential exists, `false` otherwise.
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
        user_profile: UserRepository.UserProfile | None = None,
        **legacy_profile_fields: object,
    ) -> None:
        """
        Insert or update a user credential record in the user_credentials table.

        Performs an upsert for the given username using the provided hashed_password and optional profile data.
        Accepts a modern mapping via `user_profile` containing any of `user_email`, `user_full_name`, and `is_disabled`.
        Legacy keyword fields (`user_email`, `user_full_name`, `is_disabled`) passed via `**legacy_profile_fields`,
        are accepted and override values from `user_profile` when provided.
        A `TypeError` is raised if any unexpected legacy keys are supplied.
        The `disabled` column is stored as `1` when `is_disabled` is truthy, otherwise `0`.

        Parameters:
            user_profile (Optional[UserRepository.UserProfile]): Optional mapping with any of `user_email`,
                `user_full_name`, `is_disabled`.
            **legacy_profile_fields (object): Backward-compatible keyword fields (`user_email`, `user_full_name`,
                `is_disabled`) which override values in `user_profile` when present;
                unexpected keys cause a `TypeError`.
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


def _seed_credentials_from_settings(
    repository: UserRepository,
    settings: Settings,
) -> None:
    """
    Seed an administrative user into the repository from centralized settings.

    If both admin username and password are configured, hash the password and
    upsert a user using optional admin email, full name, and disabled flag. If
    either username or password is missing, leave the repository unchanged.

    Parameters:
        repository (UserRepository): Repository to seed.
        settings (Settings): Settings instance containing admin credentials.
    """
    username = settings.admin_username
    password = settings.admin_password
    if not username or not password:
        return

    hashed_password = get_password_hash(password)
    admin_disabled = settings.admin_disabled

    repository.create_or_update_user(
        username=username,
        hashed_password=hashed_password,
        user_profile={
            "user_email": settings.admin_email,
            "user_full_name": settings.admin_full_name,
            "is_disabled": admin_disabled,
        },
    )


def _seed_credentials_from_env(repository: UserRepository) -> None:
    """
    Seed an administrative user through the backward-compatible env wrapper.

    Resolve environment values through load_settings() rather than reading
    os.environ directly. Keep the function name for compatibility.

    Parameters:
        repository (UserRepository): Repository to seed.
    """
    _seed_credentials_from_settings(repository, load_settings())


_seed_credentials_from_settings(user_repository, _AUTH_SETTINGS)

if not user_repository.has_users():
    raise ValueError(
        "No user credentials available. Provide ADMIN_USERNAME and ADMIN_PASSWORD or pre-populate the database."
    )


def get_user(
    username: str,
    repository: UserRepository | None = None,
) -> UserInDB | None:
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
    repository: UserRepository | None = None,
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


def create_access_token(data: dict, expires_delta: timedelta | None = None):
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
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(  # noqa: RUF029  # NOSONAR
    token: str = Depends(oauth2_scheme),  # noqa: B008
    request: Request = None,  # type: ignore[assignment]
) -> UserInDB:
    """
    Retrieve the UserInDB identified by the JWT's subject.

    Returns:
        UserInDB: The UserInDB object for the token's subject (includes hashed_password).

    Raises:
        HTTPException: 401 with detail "Token has expired" when the token has expired.
        HTTPException: 401 with detail "Could not validate credentials" when the token is invalid, missing a subject,
            or no matching user is found.
    """
    credentials_exception = _build_credentials_exception()
    expired_exception = _build_expired_exception()
    username = _decode_username_from_token(
        token=token,
        credentials_exception=credentials_exception,
        expired_exception=expired_exception,
        request=request,
    )
    user = get_user(username)
    if user is None:
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_TOKEN_INVALID,
                username=username,
                request=request,
                metadata={"reason": "user_not_found"},
                level=logging.WARNING,
            )
        )
        raise credentials_exception
    return user


def _build_credentials_exception() -> HTTPException:
    """
    Build the HTTPException used when authentication credentials are invalid.

    Returns:
        HTTPException: 401 Unauthorized with detail "Could not validate credentials" and header
            "WWW-Authenticate: Bearer".
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _build_expired_exception() -> HTTPException:
    """
    Create an HTTP 401 Unauthorized exception for an expired bearer token.

    Returns:
        HTTPException: An exception with status code 401, detail "Token has expired", and header
        `WWW-Authenticate: Bearer`.
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
    request: Request | None = None,
) -> str:
    """
    Extract the username stored in the token's `sub` claim and validate the token.

    Parameters:
        token (str): JWT access token expected to contain a `sub` claim.
        credentials_exception (HTTPException): Exception to raise when the token is invalid or missing `sub`.
        expired_exception (HTTPException): Exception to raise when the token has expired.

    Returns:
        username (str): The `sub` claim value from the token.

    Raises:
        HTTPException: `expired_exception` if the token has expired.
        HTTPException: `credentials_exception` if the token is invalid or the `sub` claim is missing.
    """
    try:
        # Explicitly specify algorithms parameter to prevent algorithm confusion attacks
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            _log_security_event(
                _SecurityAuditEvent(
                    event_slug=_SECURITY_AUDIT_TOKEN_INVALID,
                    request=request,
                    metadata={"reason": "missing_subject"},
                    level=logging.WARNING,
                )
            )
            raise credentials_exception
        return str(TokenData(username=username).username)
    except ExpiredSignatureError as e:
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_TOKEN_EXPIRED,
                request=request,
                metadata={"reason": "expired_signature"},
                level=logging.WARNING,
            )
        )
        raise expired_exception from e
    except InvalidTokenError as e:
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_TOKEN_INVALID,
                request=request,
                metadata={"reason": "invalid_token"},
                level=logging.WARNING,
            )
        )
        raise credentials_exception from e


async def get_current_active_user(  # noqa: RUF029  # NOSONAR
    current_user: User = Depends(get_current_user),  # noqa: B008
    request: Request = None,  # type: ignore[assignment]
) -> User:
    """
    Verify that the authenticated user's account is active.

    Note: Although get_current_user returns UserInDB, this function accepts and returns
    the base User type since it doesn't need access to hashed_password. This provides
    better separation of concerns - only authentication code should see hashed passwords.

    Raises:
        HTTPException: 400 with detail "Inactive user" if the user's account is disabled.

    Returns:
        User: The authenticated user's public profile (without hashed_password).
    """
    if current_user.disabled:
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_USER_DISABLED,
                username=current_user.username,
                request=request,
                metadata={"reason": "disabled_user"},
                level=logging.WARNING,
            )
        )
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_rebuild_operator_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request = None,  # type: ignore[assignment]
) -> User:
    """
    Enforce operator authorization for destructive graph rebuild actions.

    Allows only the configured admin username from settings; denies other active
    users with a bounded forbidden response.
    """
    configured_admin = (settings.admin_username or "").strip()

    if not configured_admin:
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_ACCESS_DENIED,
                username=current_user.username,
                request=request,
                metadata={
                    "reason": "operator_not_configured",
                    "required_role": "operator",
                },
                level=logging.WARNING,
            )
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=REBUILD_OPERATOR_NOT_CONFIGURED_DETAIL,
        )

    if current_user.username.strip() != configured_admin:
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_ACCESS_DENIED,
                username=current_user.username,
                request=request,
                metadata={
                    "reason": "operator_required",
                    "required_role": "operator",
                },
                level=logging.WARNING,
            )
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=REBUILD_OPERATOR_FORBIDDEN_DETAIL,
        )
    return current_user
