"""Unit tests for authentication router audit logging."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status
from starlette.requests import Request

from api.models import UserInDB
from api.routers.auth import login_for_access_token

pytestmark = pytest.mark.unit


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


def _form(username: str = "alice", password: str = "correct-password"):
    """Build a lightweight OAuth form object for direct route calls."""
    return SimpleNamespace(username=username, password=password)


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
    assert mock_security_event.call_args.args[0] == "auth_login_success"
    assert mock_security_event.call_args.kwargs["username"] == "alice"
    assert mock_security_event.call_args.kwargs["metadata"] == {"rate_limit_policy": "5/minute"}


@pytest.mark.asyncio
async def test_login_failure_emits_auth_login_failure_before_401() -> None:
    """Failed login should emit auth_login_failure before raising 401."""
    with (
        patch("api.routers.auth.authenticate_user", return_value=False),
        patch("api.routers.auth._log_security_event") as mock_security_event,
        pytest.raises(HTTPException) as exc_info,
    ):
        await login_for_access_token(_request(), _form(username="alice", password="wrong-password"))

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    mock_security_event.assert_called_once()
    assert mock_security_event.call_args.args[0] == "auth_login_failure"
    assert mock_security_event.call_args.kwargs["attempted_username"] == "alice"
    assert mock_security_event.call_args.kwargs["metadata"] == {"rate_limit_policy": "5/minute"}


@pytest.mark.asyncio
async def test_login_failure_logs_attempted_username_not_password() -> None:
    """Failed login audit metadata should include username context but not the submitted password."""
    with (
        patch("api.routers.auth.authenticate_user", return_value=False),
        patch("api.routers.auth._log_security_event") as mock_security_event,
        pytest.raises(HTTPException),
    ):
        await login_for_access_token(_request(), _form(username="alice", password="do-not-log"))

    kwargs = mock_security_event.call_args.kwargs
    assert kwargs["attempted_username"] == "alice"
    assert "do-not-log" not in str(kwargs)
