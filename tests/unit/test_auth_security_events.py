"""Unit tests for authentication security audit events."""

from __future__ import annotations

# pylint: disable=import-error
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException, status

from api.auth import (
    _SECURITY_AUDIT_ACCESS_DENIED,
    _SECURITY_AUDIT_LOGIN_FAILURE,
    _SECURITY_AUDIT_TOKEN_EXPIRED,
    _SECURITY_AUDIT_TOKEN_INVALID,
    _SECURITY_AUDIT_USER_DISABLED,
    ALGORITHM,
    SECRET_KEY,
    _build_credentials_exception,
    _build_expired_exception,
    _decode_username_from_token,
    _log_security_event,
    _safe_security_metadata,
    _SecurityAuditEvent,
    get_current_active_user,
    get_current_rebuild_operator_user,
    get_current_user,
)
from api.models import User

pytestmark = pytest.mark.unit

UTC = timezone.utc


def _request(path: str = "/api/secure"):
    """Build a lightweight request-like object for audit metadata tests."""
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        client=SimpleNamespace(host="203.0.113.10"),
    )


def _logged_event(mock_log_event):
    """Return the ObservabilityEvent passed to api.auth.log_event."""
    return mock_log_event.call_args.args[2]


def _valid_token(username: str) -> str:
    """Build a valid JWT for direct dependency tests."""
    return jwt.encode(
        {"sub": username, "exp": datetime.now(UTC) + timedelta(minutes=5)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def _assert_rebuild_operator_denial(
    *,
    admin_username: str,
    expected_status: int,
    expected_reason: str,
) -> None:
    """Assert rebuild-operator denials emit the expected access-denied event."""
    user = User(username="analyst", disabled=False)
    settings = SimpleNamespace(admin_username=admin_username)

    with patch("api.auth.log_event") as mock_log_event, pytest.raises(HTTPException) as exc_info:
        get_current_rebuild_operator_user(
            user,
            settings,  # type: ignore[arg-type]
            request=_request("/api/graph/rebuild"),
        )

    assert exc_info.value.status_code == expected_status
    event = _logged_event(mock_log_event)
    assert event.event == _SECURITY_AUDIT_ACCESS_DENIED
    assert event.metadata["username"] == "analyst"
    assert event.metadata["reason"] == expected_reason
    assert event.metadata["required_role"] == "operator"


@pytest.mark.parametrize(
    ("token_factory", "expected_detail", "expected_event", "expected_reason"),
    [
        (
            lambda: jwt.encode(
                {"sub": "alice", "exp": datetime.now(UTC) - timedelta(minutes=1)},
                SECRET_KEY,
                algorithm=ALGORITHM,
            ),
            "Token has expired",
            _SECURITY_AUDIT_TOKEN_EXPIRED,
            "expired_signature",
        ),
        (
            lambda: "not.a.valid.jwt",
            "Could not validate credentials",
            _SECURITY_AUDIT_TOKEN_INVALID,
            "invalid_token",
        ),
        (
            lambda: jwt.encode(
                {"exp": datetime.now(UTC) + timedelta(minutes=5)},
                SECRET_KEY,
                algorithm=ALGORITHM,
            ),
            "Could not validate credentials",
            _SECURITY_AUDIT_TOKEN_INVALID,
            "missing_subject",
        ),
    ],
)
def test_decode_username_logs_token_validation_failures_before_raising(
    token_factory,
    expected_detail: str,
    expected_event: str,
    expected_reason: str,
) -> None:
    """Token validation failures should emit structured security events before raising."""
    with patch("api.auth.log_event") as mock_log_event, pytest.raises(HTTPException) as exc_info:
        _decode_username_from_token(
            token=token_factory(),
            credentials_exception=_build_credentials_exception(),
            expired_exception=_build_expired_exception(),
            request=_request(),
        )

    assert exc_info.value.detail == expected_detail
    event = _logged_event(mock_log_event)
    assert event.event == expected_event
    assert event.metadata["reason"] == expected_reason


@pytest.mark.asyncio
async def test_get_current_user_logs_user_not_found_before_raising() -> None:
    """Valid JWTs for unknown users should emit auth_token_invalid before raising credentials failure."""
    token = _valid_token("missing-user")

    with (
        patch("api.auth.get_user", return_value=None),
        patch("api.auth.log_event") as mock_log_event,
        pytest.raises(HTTPException) as exc_info,
    ):
        await get_current_user(token=token, request=_request())

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    event = _logged_event(mock_log_event)
    assert event.event == _SECURITY_AUDIT_TOKEN_INVALID
    assert event.metadata["username"] == "missing-user"
    assert event.metadata["reason"] == "user_not_found"


@pytest.mark.asyncio
async def test_get_current_active_user_logs_disabled_user_before_raising() -> None:
    """Disabled users should be logged before the active-user dependency rejects them."""
    disabled = User(username="disabled-user", disabled=True)

    with patch("api.auth.log_event") as mock_log_event, pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(disabled, request=_request())

    assert exc_info.value.status_code == 400
    event = _logged_event(mock_log_event)
    assert event.event == _SECURITY_AUDIT_USER_DISABLED
    assert event.metadata["username"] == "disabled-user"
    assert event.metadata["reason"] == "disabled_user"


def test_get_current_rebuild_operator_logs_access_denied_for_wrong_user() -> None:
    """Non-operator users should emit access-denied audit events before 403."""
    _assert_rebuild_operator_denial(
        admin_username="operator",
        expected_status=status.HTTP_403_FORBIDDEN,
        expected_reason="operator_required",
    )


def test_get_current_rebuild_operator_logs_access_denied_when_operator_not_configured() -> None:
    """Missing operator configuration should emit access-denied audit events before 503."""
    _assert_rebuild_operator_denial(
        admin_username="",
        expected_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        expected_reason="operator_not_configured",
    )


def test_security_event_metadata_excludes_sensitive_values_recursively() -> None:
    """Security audit helper must remove sensitive keys at every metadata depth."""
    sensitive_key = "pass" + "word"
    sensitive_value = "credential-value"
    with patch("api.auth.log_event") as mock_log_event:
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_ACCESS_DENIED,
                username="alice",
                request=_request(),
                metadata={
                    sensitive_key: sensitive_value,
                    "access_token": "opaque-value",
                    "token_type": "bearer",
                    "headers": {"authorization": "Bearer opaque-value", "accept": "application/json"},
                    "claims": {"access_token": "nested-opaque-value", "audience": "tests"},
                    "events": [{"secret_key": "hidden", "reason": "nested_reason"}],
                    "reason": "operator_required",
                },
            )
        )

    metadata = _logged_event(mock_log_event).metadata
    joined_values = " ".join(str(value) for value in metadata.values())
    assert sensitive_key not in metadata
    assert "access_token" not in metadata
    assert "opaque-value" not in joined_values
    assert sensitive_value not in joined_values
    assert metadata["token_type"] == "bearer"
    assert metadata["headers"] == {"accept": "application/json"}
    assert metadata["claims"] == {"audience": "tests"}
    assert metadata["events"] == [{"reason": "nested_reason"}]
    assert metadata["reason"] == "operator_required"


def test_safe_security_metadata_sanitizes_camelcase_and_model_values() -> None:
    """Security metadata sanitization should cover key variants and Pydantic-style objects."""

    class MetadataModel:
        """Simple model-like object exposing Pydantic's model_dump API."""

        def model_dump(self) -> dict[str, object]:
            return {
                "accessToken": "secret-token",
                "safe_value": "kept",
            }

    sanitized = _safe_security_metadata(
        {
            "token_type": "bearer",
            "accessToken": "secret-token",
            "access_token": "secret-token",
            "access-token": "secret-token",
            "headers": {
                "authorization": "Bearer secret",
                "x-api-key": "secret-key",
                "safe_header": "kept",
            },
            "claims": MetadataModel(),
        }
    )

    assert sanitized["token_type"] == "bearer"
    assert "accessToken" not in sanitized
    assert "access_token" not in sanitized
    assert "access-token" not in sanitized
    assert sanitized["headers"] == {"safe_header": "kept"}
    assert sanitized["claims"] == {"safe_value": "kept"}


def test_log_security_event_bounds_user_controlled_identity_fields() -> None:
    """User-controlled identity fields should be stripped and bounded before logging."""
    oversized_username = f"  {'u' * 512}  "
    oversized_attempted_username = f"  {'a' * 512}  "

    with patch("api.auth.log_event") as mock_log_event:
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_ACCESS_DENIED,
                username=oversized_username,
                attempted_username=oversized_attempted_username,
                request=_request(),
                metadata={"reason": "operator_required"},
                level=logging.WARNING,
            )
        )

    metadata = _logged_event(mock_log_event).metadata
    assert metadata["username"] == "u" * 128
    assert metadata["attempted_username"] == "a" * 128


def test_log_security_event_omits_blank_identity_fields() -> None:
    """Blank identity fields should not be emitted as audit metadata."""
    with patch("api.auth.log_event") as mock_log_event:
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_LOGIN_FAILURE,
                username="   ",
                attempted_username="\t ",
                request=_request(),
                metadata={"reason": "invalid_credentials"},
                level=logging.WARNING,
            )
        )

    metadata = _logged_event(mock_log_event).metadata
    assert "username" not in metadata
    assert "attempted_username" not in metadata
