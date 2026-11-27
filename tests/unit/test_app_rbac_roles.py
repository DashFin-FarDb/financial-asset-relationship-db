"""Unit tests for application RBAC role hierarchy, require_roles(), and assertion proposer guards."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException

from api.auth import User, enforce_assertion_proposer_rbac, require_roles, resolve_user_roles
from api.metrics import AUTH_ACCESS_DENIED_TOTAL
from src.config.settings import Settings


def _settings(admin_username: str = "admin") -> Settings:
    return cast(Settings, SimpleNamespace(admin_username=admin_username))


def test_resolve_user_roles_hierarchy(monkeypatch) -> None:
    """Admin inherits operator+analyst+viewer; operator inherits analyst+viewer; viewer is baseline."""
    monkeypatch.setenv("REBUILD_OPERATOR_USERNAMES", "ops_alice")
    monkeypatch.setenv("ANALYST_USERNAMES", "analyst_bob")
    settings = _settings("root_admin")

    assert resolve_user_roles("root_admin", settings) == frozenset({"admin", "operator", "analyst", "viewer"})
    assert resolve_user_roles("ops_alice", settings) == frozenset({"operator", "analyst", "viewer"})
    assert resolve_user_roles("analyst_bob", settings) == frozenset({"analyst", "viewer"})
    assert resolve_user_roles("readonly_carol", settings) == frozenset({"viewer"})


def test_require_roles_allows_authorized_and_denies_viewer(monkeypatch) -> None:
    """require_roles allows matching roles and raises 403 + increments metric otherwise."""
    monkeypatch.setenv("REBUILD_OPERATOR_USERNAMES", "ops_alice")
    monkeypatch.delenv("ANALYST_USERNAMES", raising=False)
    settings = _settings("root_admin")
    dep = require_roles("operator", "admin")

    ops_user = User(username="ops_alice")
    assert dep(current_user=ops_user, settings=settings, request=None) is ops_user

    before = AUTH_ACCESS_DENIED_TOTAL.labels(
        required_role="admin,operator"
    )._value.get()  # pylint: disable=protected-access
    viewer_user = User(username="readonly_carol")
    with pytest.raises(HTTPException) as exc_info:
        dep(current_user=viewer_user, settings=settings, request=None)
    assert exc_info.value.status_code == 403
    assert (
        AUTH_ACCESS_DENIED_TOTAL.labels(required_role="admin,operator")._value.get() == before + 1
    )  # pylint: disable=protected-access


def test_enforce_assertion_proposer_rbac_strict_and_opt_in(monkeypatch) -> None:
    """Assertion proposer RBAC stays backwards-compatible by default and enforces 403 when configured."""
    settings = _settings("root_admin")
    viewer = User(username="readonly_carol")
    analyst = User(username="analyst_bob")

    # Default (no ANALYST_USERNAMES, strict false): allows active users for backwards compatibility
    monkeypatch.delenv("ANALYST_USERNAMES", raising=False)
    monkeypatch.delenv("STRICT_ASSERTION_PROPOSER_RBAC", raising=False)
    assert enforce_assertion_proposer_rbac(viewer, settings) is viewer

    # Configured ANALYST_USERNAMES: allows analyst, denies viewer with 403
    monkeypatch.setenv("ANALYST_USERNAMES", "analyst_bob")
    assert enforce_assertion_proposer_rbac(analyst, settings) is analyst
    with pytest.raises(HTTPException) as exc_info:
        enforce_assertion_proposer_rbac(viewer, settings)
    assert exc_info.value.status_code == 403
