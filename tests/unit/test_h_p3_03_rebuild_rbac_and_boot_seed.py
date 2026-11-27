"""Unit tests for H-P3-03: rebuild RBAC and disabling silent admin upsert on boot."""

from __future__ import annotations

import secrets
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from api.auth import (
    User,
    get_current_rebuild_operator_user,
    seed_credentials_from_settings,
)
from src.config.settings import DeploymentEnvironment, Settings


def test_seed_credentials_blocks_silent_admin_upsert_in_production_and_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Staging and production refuse silent boot-time admin upserts unless explicitly opted in."""
    monkeypatch.delenv("ALLOW_BOOT_ADMIN_UPSERT", raising=False)
    for env in (DeploymentEnvironment.PRODUCTION, DeploymentEnvironment.STAGING):
        mock_repo = MagicMock()
        settings = Settings(
            env=env,
            secret_key=secrets.token_urlsafe(32),
            admin_username="admin",
            admin_password=secrets.token_urlsafe(24),
        )
        written = seed_credentials_from_settings(mock_repo, settings)
        assert written is False
        mock_repo.create_or_update_user.assert_not_called()

        # Explicit force_upsert override (e.g., operator CLI) is permitted
        written_forced = seed_credentials_from_settings(mock_repo, settings, force_upsert=True)
        assert written_forced is True
        mock_repo.create_or_update_user.assert_called_once()


def test_rebuild_rbac_allows_configured_operator_roles_and_denies_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REBUILD_OPERATOR_USERNAMES grants RBAC access to named operators while denying others."""
    monkeypatch.setenv("REBUILD_OPERATOR_USERNAMES", "alice_ops, bob_ops")
    settings = Settings(
        env=DeploymentEnvironment.DEVELOPMENT,
        secret_key=secrets.token_urlsafe(32),
        admin_username=None,
    )

    alice = User(username="alice_ops", disabled=False)
    bob = User(username="bob_ops", disabled=False)
    viewer = User(username="readonly_user", disabled=False)

    assert get_current_rebuild_operator_user(alice, settings) is alice
    assert get_current_rebuild_operator_user(bob, settings) is bob

    with pytest.raises(HTTPException) as exc_info:
        get_current_rebuild_operator_user(viewer, settings)
    assert exc_info.value.status_code == 403


def test_rebuild_rbac_fails_closed_when_no_operators_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """When neither REBUILD_OPERATOR_USERNAMES nor ADMIN_USERNAME is set, returns 503."""
    monkeypatch.delenv("REBUILD_OPERATOR_USERNAMES", raising=False)
    settings = Settings(
        env=DeploymentEnvironment.DEVELOPMENT,
        secret_key=secrets.token_urlsafe(32),
        admin_username=None,
    )
    user = User(username="anyone", disabled=False)
    with pytest.raises(HTTPException) as exc_info:
        get_current_rebuild_operator_user(user, settings)
    assert exc_info.value.status_code == 503
