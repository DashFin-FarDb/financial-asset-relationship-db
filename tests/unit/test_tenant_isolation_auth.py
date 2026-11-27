"""Unit tests for TenantContext, JWT tenant_id claims, and cross-tenant RBAC boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.auth import ALGORITHM, SECRET_KEY, User, create_access_token, get_current_active_user, resolve_user_tenant
from api.metrics import AUTH_ACCESS_DENIED_TOTAL
from api.tenant_context import TenantContext, get_tenant_context, normalize_tenant_id, require_tenant_access
from src.config.settings import get_settings


def test_create_access_token_embeds_default_and_explicit_tenant_id() -> None:
    """JWT access tokens include tenant_id defaulting to 'default' or preserving explicit value."""
    default_token = create_access_token({"sub": "alice"})
    decoded_default = jwt.decode(default_token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded_default["tenant_id"] == "default"

    explicit_token = create_access_token({"sub": "alice", "tenant_id": "tenant-alpha"})
    decoded_explicit = jwt.decode(explicit_token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded_explicit["tenant_id"] == "tenant-alpha"


def test_resolve_user_tenant_reads_bindings_and_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """resolve_user_tenant binds explicit users from TENANT_USER_BINDINGS and falls back cleanly."""
    monkeypatch.setenv("TENANT_USER_BINDINGS", "alice:tenant-alpha, bob:tenant-beta")
    settings = SimpleNamespace(default_tenant_id="default")
    assert resolve_user_tenant("alice", settings) == "tenant-alpha"  # type: ignore[arg-type]
    assert resolve_user_tenant("bob", settings) == "tenant-beta"  # type: ignore[arg-type]
    assert resolve_user_tenant("charlie", settings) == "default"  # type: ignore[arg-type]


def test_get_tenant_context_enforces_header_match_and_emits_denial_metric() -> None:
    """Matching X-Tenant-ID passes; mismatched returns 403 + metric; invalid format returns 400."""
    app = FastAPI()

    @app.get("/tenant-ping")
    def _ping(ctx: Annotated[TenantContext, Depends(get_tenant_context)]) -> dict[str, str]:
        return {"tenant_id": ctx.tenant_id, "actor_id": ctx.actor_id}

    user = User(username="alice", tenant_id="tenant-alpha")
    settings = SimpleNamespace(tenant_isolation_enforced=True, default_tenant_id="default")
    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_settings] = lambda: settings

    client = TestClient(app)

    ok_no_header = client.get("/tenant-ping")
    assert ok_no_header.status_code == 200
    assert ok_no_header.json() == {"tenant_id": "tenant-alpha", "actor_id": "alice"}

    ok_matching = client.get("/tenant-ping", headers={"X-Tenant-ID": "tenant-alpha"})
    assert ok_matching.status_code == 200

    bad_header = client.get("/tenant-ping", headers={"X-Tenant-ID": "bad tenant!!"})
    assert bad_header.status_code == 400

    before = AUTH_ACCESS_DENIED_TOTAL.labels(required_role="tenant_boundary")._value.get()
    denied = client.get("/tenant-ping", headers={"X-Tenant-ID": "tenant-beta"})
    after = AUTH_ACCESS_DENIED_TOTAL.labels(required_role="tenant_boundary")._value.get()
    assert denied.status_code == 403
    assert after == before + 1


def test_require_tenant_access_blocks_cross_tenant_targets() -> None:
    """require_tenant_access permits matching tenant and raises 403 for cross-tenant targets."""
    ctx = TenantContext(tenant_id="tenant-alpha", actor_id="alice", isolation_enforced=True)
    require_tenant_access("tenant-alpha", ctx)

    assert normalize_tenant_id("Tenant_01") == "tenant_01"
    with pytest.raises(ValueError, match="Invalid tenant_id"):
        normalize_tenant_id("invalid space")

    with pytest.raises(Exception) as exc_info:
        require_tenant_access("tenant-beta", ctx)
    assert getattr(exc_info.value, "status_code", None) == 403
