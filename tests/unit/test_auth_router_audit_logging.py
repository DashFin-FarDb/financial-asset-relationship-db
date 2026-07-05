"""Unit tests for authentication router audit logging."""

from __future__ import annotations

# pylint: disable=import-error
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status
from starlette.requests import Request

from api.models import UserInDB
from api.routers.auth import login_for_access_token

pytestmark = pytest.mark.unit
_PASSWORD_FIELD = "password"  # nosec  # DevSkim: ignore all
VALID_LOGIN_CREDENTIAL = "valid-login-credential"
INVALID_LOGIN_CREDENTIAL = "invalid-login-credential"


def _request():
    """Build a lightweight request-like object for direct route calls."""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/token",
            "headers": [],
            "client": ("198.51.100.20", 12345),
        }
    )


def _form(username: str = "alice", credential: str = VALID_LOGIN_CREDENTIAL):
    """Build a lightweight OAuth form object for direct route calls."""
    return SimpleNamespace(username=username, **{_PASSWORD_FIELD: credential})


def _security_payload(mock_security_event):
    """Return the _SecurityAuditEvent payload passed to the router helper."""
    return mock_security_event.call_args.args[0]


@pytest.mark.asyncio
async def test_login_success_emits_auth_login_success() -> None:
    """Successful login should emit auth_login_success before returning the bearer token."""
    user = UserInDB(username="alice", hashed_password="hashed", disabled=False)

    with (
        patch("api.routers.auth.authenticate_user", return_value=user),
        patch("api.routers.auth.create_access_token", return_value="issued-token"),
        patch("api.routers.auth._log_security_event") as mock_security_event,
    ):
        response = await login_for_access_token(_request(), _form())

    assert response.access_token == "issued-token"
    mock_security_event.assert_called_once()
    payload = _security_payload(mock_security_event)
    assert payload.event_slug == "auth_login_success"
    assert payload.username == "alice"
    assert payload.metadata == {"rate_limit_policy": "5/minute"}


@pytest.mark.asyncio
async def test_login_failure_emits_auth_login_failure_before_401() -> None:
    """Failed login should emit auth_login_failure before raising 401."""
    with (
        patch("api.routers.auth.authenticate_user", return_value=False),
        patch("api.routers.auth._log_security_event") as mock_security_event,
        pytest.raises(HTTPException) as exc_info,
    ):
        await login_for_access_token(_request(), _form(username="alice", credential=INVALID_LOGIN_CREDENTIAL))

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    mock_security_event.assert_called_once()
    payload = _security_payload(mock_security_event)
    assert payload.event_slug == "auth_login_failure"
    assert payload.attempted_username == "alice"
    assert payload.metadata == {"rate_limit_policy": "5/minute"}


@pytest.mark.asyncio
async def test_login_failure_logs_attempted_username_not_password() -> None:
    """Failed login audit metadata should include username context but not the submitted credential."""
    submitted_secret = "do-not-log"
    with (
        patch("api.routers.auth.authenticate_user", return_value=False),
        patch("api.routers.auth._log_security_event") as mock_security_event,
        pytest.raises(HTTPException),
    ):
        await login_for_access_token(_request(), _form(username="alice", credential=submitted_secret))

    payload = _security_payload(mock_security_event)
    assert payload.attempted_username == "alice"
    assert submitted_secret not in str(payload)
