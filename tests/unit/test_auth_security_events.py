"""Unit tests for authentication security audit events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException, status

from api.auth import (
    _SECURITY_AUDIT_ACCESS_DENIED,
    _SECURITY_AUDIT_TOKEN_EXPIRED,
    _SECURITY_AUDIT_TOKEN_INVALID,
    _SECURITY_AUDIT_USER_DISABLED,
    ALGORITHM,
    SECRET_KEY,
    _build_credentials_exception,
    _build_expired_exception,
    _decode_username_from_token,
    _log_security_event,
    get_current_active_user,
    get_current_rebuild_operator_user,
)
from api.models import User

pytestmark = pytest.mark.unit


def _request(path: str = "/api/secure"):
    """Build a lightweight request-like object for audit metadata tests."""
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        client=SimpleNamespace(host="203.0.113.10"),
    )


def _logged_event(mock_log_event):
    """Return the ObservabilityEvent passed to api.auth.log_event."""
    return mock_log_event.call_args.args[2]


def test_decode_username_logs_expired_token_before_raising() -> None:
    """Expired JWTs should emit a structured security event before raising 401."""
    token = jwt.encode(
        {"sub": "alice", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with patch("api.auth.log_event") as mock_log_event, pytest.raises(HTTPException) as exc_info:
        _decode_username_from_token(
            token=token,
            credentials_exception=_build_credentials_exception(),
            expired_exception=_build_expired_exception(),
            request=_request(),
        )

    assert exc_info.value.detail == "Token has expired"
    event = _logged_event(mock_log_event)
    assert event.event == _SECURITY_AUDIT_TOKEN_EXPIRED
    assert event.metadata["reason"] == "expired_signature"
    assert event.metadata["endpoint"] == "/api/secure"


def test_decode_username_logs_invalid_token_before_raising() -> None:
    """Malformed JWTs should emit auth_token_invalid before raising credentials failure."""
    with patch("api.auth.log_event") as mock_log_event, pytest.raises(HTTPException) as exc_info:
        _decode_username_from_token(
            token="not.a.valid.jwt",
            credentials_exception=_build_credentials_exception(),
            expired_exception=_build_expired_exception(),
            request=_request(),
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    event = _logged_event(mock_log_event)
    assert event.event == _SECURITY_AUDIT_TOKEN_INVALID
    assert event.metadata["reason"] == "invalid_token"


@pytest.mark.asyncio
async def test_get_current_active_user_logs_disabled_user_before_raising() -> None:
    """Disabled users should be logged before the active-user dependency rejects them."""
    disabled = User(username="disabled-user", disabled=True)

    with patch("api.auth.log_event") as mock_log_event, pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(_request(), disabled)

    assert exc_info.value.status_code == 400
    event = _logged_event(mock_log_event)
    assert event.event == _SECURITY_AUDIT_USER_DISABLED
    assert event.metadata["username"] == "disabled-user"
    assert event.metadata["reason"] == "disabled_user"


def test_get_current_rebuild_operator_logs_access_denied_for_wrong_user() -> None:
    """Non-operator users should emit access-denied audit events before 403."""
    user = User(username="analyst", disabled=False)
    settings = SimpleNamespace(admin_username="operator")

    with patch("api.auth.log_event") as mock_log_event, pytest.raises(HTTPException) as exc_info:
        get_current_rebuild_operator_user(_request("/api/graph/rebuild"), user, settings)  # type: ignore[arg-type]

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    event = _logged_event(mock_log_event)
    assert event.event == _SECURITY_AUDIT_ACCESS_DENIED
    assert event.metadata["username"] == "analyst"
    assert event.metadata["reason"] == "operator_required"
    assert event.metadata["required_role"] == "operator"


def test_get_current_rebuild_operator_logs_access_denied_when_operator_not_configured() -> None:
    """Missing operator configuration should emit access-denied audit events before 503."""
    user = User(username="analyst", disabled=False)
    settings = SimpleNamespace(admin_username="")

    with patch("api.auth.log_event") as mock_log_event, pytest.raises(HTTPException) as exc_info:
        get_current_rebuild_operator_user(_request("/api/graph/rebuild"), user, settings)  # type: ignore[arg-type]

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    event = _logged_event(mock_log_event)
    assert event.event == _SECURITY_AUDIT_ACCESS_DENIED
    assert event.metadata["reason"] == "operator_not_configured"


def test_security_event_metadata_excludes_tokens_and_passwords() -> None:
    """Security audit helper must not emit token, password, secret, or authorization metadata keys."""
    with patch("api.auth.log_event") as mock_log_event:
        _log_security_event(
            _SECURITY_AUDIT_ACCESS_DENIED,
            username="alice",
            request=_request(),
            metadata={
                "password": "super-secret",
                "access_token": "token-value",
                "authorization": "Bearer token-value",
                "secret_key": "secret-value",
                "reason": "operator_required",
            },
        )

    metadata = _logged_event(mock_log_event).metadata
    joined_values = " ".join(str(value) for value in metadata.values())
    assert "password" not in metadata
    assert "access_token" not in metadata
    assert "authorization" not in metadata
    assert "secret_key" not in metadata
    assert "super-secret" not in joined_values
    assert "token-value" not in joined_values
    assert metadata["reason"] == "operator_required"
