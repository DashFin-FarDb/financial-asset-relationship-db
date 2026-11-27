"""Unit tests for JWT key rotation (kid) and token revocation (jti + logout)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import api.auth as auth_module
from api.app_factory import create_app
from src.config.settings import get_settings


def _clear_caches() -> None:
    get_settings.cache_clear()
    auth_module._TOKEN_REVOCATION_STORE.clear()


def test_create_access_token_embeds_jti_and_kid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issued JWTs include a unique jti claim and active kid header."""
    monkeypatch.setenv("JWT_KEY_ID", "k-2026-11")
    _clear_caches()
    try:
        token = auth_module.create_access_token({"sub": "alice"})
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, auth_module.SECRET_KEY, algorithms=[auth_module.ALGORITHM])
        assert header["kid"] == "k-2026-11"
        assert isinstance(payload["jti"], str) and len(payload["jti"]) >= 16
        assert payload["sub"] == "alice"
    finally:
        _clear_caches()


def test_zero_downtime_key_rotation_verifies_previous_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tokens signed with a rotated previous key still verify during the rotation window."""
    old_secret = "old-rotation-secret-key-at-least-32-chars!"
    new_secret = "new-primary-secret-key-at-least-32-chars!!"
    old_token = jwt.encode(
        {
            "sub": "alice",
            "jti": "legacy-jti-001",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        old_secret,
        algorithm=auth_module.ALGORITHM,
        headers={"kid": "k-2026-10"},
    )

    monkeypatch.setattr(auth_module, "SECRET_KEY", new_secret)
    monkeypatch.setenv("SECRET_KEY", new_secret)
    monkeypatch.setenv("JWT_KEY_ID", "k-2026-11")
    monkeypatch.setenv("JWT_PREVIOUS_SECRET_KEYS", f"k-2026-10:{old_secret}")
    _clear_caches()
    try:
        username = auth_module._decode_username_from_token(
            token=old_token,
            credentials_exception=auth_module._build_credentials_exception(),
            expired_exception=auth_module._build_expired_exception(),
        )
        assert username == "alice"
    finally:
        _clear_caches()


def test_unknown_key_still_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tokens signed with an unrecognized secret fail with 401."""
    rogue_token = jwt.encode(
        {
            "sub": "mallory",
            "jti": "rogue-jti-001",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        "completely-unknown-secret-key-32-chars-long!",
        algorithm=auth_module.ALGORITHM,
        headers={"kid": "k-unknown"},
    )
    _clear_caches()
    with pytest.raises(HTTPException) as exc_info:
        auth_module._decode_username_from_token(
            token=rogue_token,
            credentials_exception=auth_module._build_credentials_exception(),
            expired_exception=auth_module._build_expired_exception(),
        )
    assert exc_info.value.status_code == 401


def test_revoked_jti_rejected_and_expired_entries_pruned() -> None:
    """Revoking a token immediately blocks reuse, and expired entries prune automatically."""
    _clear_caches()
    token = auth_module.create_access_token({"sub": "alice"})
    jti = auth_module.revoke_access_token(token)
    assert jti is not None
    assert auth_module.is_token_revoked(jti)

    with pytest.raises(HTTPException) as exc_info:
        auth_module._decode_username_from_token(
            token=token,
            credentials_exception=auth_module._build_credentials_exception(),
            expired_exception=auth_module._build_expired_exception(),
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token has been revoked"

    # Expired revocation entry should not remain in the store
    auth_module.revoke_token("already-expired-jti", expires_at=datetime.now(timezone.utc) - timedelta(seconds=5))
    assert not auth_module.is_token_revoked("already-expired-jti")
    _clear_caches()


def test_logout_endpoint_revokes_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/auth/logout revokes the caller's token so subsequent /api/users/me returns 401."""
    _clear_caches()
    fake_user = auth_module.UserInDB(
        username="alice",
        email="alice@example.com",
        full_name="Alice",
        disabled=False,
        hashed_password="x",  # noqa: S106
    )
    monkeypatch.setattr(
        auth_module, "get_user", lambda username, repository=None: fake_user if username == "alice" else None
    )

    app = create_app()
    client = TestClient(app)
    token = auth_module.create_access_token({"sub": "alice"})
    headers = {"Authorization": f"Bearer {token}"}

    me_before = client.get("/api/users/me", headers=headers)
    assert me_before.status_code == 200

    logout_resp = client.post("/api/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {"status": "logged_out"}

    me_after = client.get("/api/users/me", headers=headers)
    assert me_after.status_code == 401
    assert me_after.json()["detail"] == "Token has been revoked"
    _clear_caches()
