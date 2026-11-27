"""Integration tests verifying strict multi-tenant isolation across ResearchRun and rebuild APIs."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import User, get_current_active_user, get_current_rebuild_operator_user
from api.metrics import AUTH_ACCESS_DENIED_TOTAL
from api.routers.graph_admin import router as graph_admin_router
from api.routers.research_runs import get_research_run_repository
from api.routers.research_runs import router as research_runs_router
from src.config.settings import get_settings
from src.data.database import create_engine_from_url
from src.data.research_run_repository import ResearchRunRepository

_VALID_SHA = "c" * 64


def _build_multi_tenant_app(repo: ResearchRunRepository, active_user_holder: dict[str, User]) -> TestClient:
    """Create a FastAPI TestClient whose active user can be switched between tenants."""
    fake_settings = SimpleNamespace(
        admin_username="admin",
        tenant_isolation_enforced=True,
        default_tenant_id="default",
    )

    app = FastAPI()
    app.include_router(research_runs_router)
    app.include_router(graph_admin_router)
    app.dependency_overrides[get_research_run_repository] = lambda: repo
    app.dependency_overrides[get_current_active_user] = lambda: active_user_holder["user"]
    app.dependency_overrides[get_current_rebuild_operator_user] = lambda: active_user_holder["user"]
    app.dependency_overrides[get_settings] = lambda: fake_settings
    return TestClient(app)


def test_cross_tenant_research_run_isolation_and_header_spoofing_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tenant B cannot read, list, link, or spoof X-Tenant-ID to access Tenant A's ResearchRuns."""
    monkeypatch.setenv("ANALYST_USERNAMES", "alice,bob")
    monkeypatch.delenv("REBUILD_OPERATOR_USERNAMES", raising=False)

    engine = create_engine_from_url("sqlite:///:memory:")
    repo = ResearchRunRepository(engine)
    repo.ensure_sqlite_schema()

    tenant_a_user = User(username="alice", tenant_id="tenant-a")
    tenant_b_user = User(username="bob", tenant_id="tenant-b")
    holder = {"user": tenant_a_user}
    client = _build_multi_tenant_app(repo, holder)

    try:
        # Tenant A creates a ResearchRun and links an assertion.
        created = client.post(
            "/api/research-runs",
            headers={"X-Tenant-ID": "tenant-a"},
            json={
                "run_id": "run-tenant-a-001",
                "domain_id": "human_resources",
                "method_id": "org_snapshot@1",
                "input_digest_sha256": _VALID_SHA,
                "parameters": {"quarter": "2026Q4"},
            },
        )
        assert created.status_code == 201
        assert created.json()["tenant_id"] == "tenant-a"

        linked = client.post(
            "/api/research-runs/run-tenant-a-001/assertions",
            headers={"X-Tenant-ID": "tenant-a"},
            json={"assertion_id": "assert-tenant-a-1"},
        )
        assert linked.status_code == 201
        assert linked.json()["linked_assertion_ids"] == ["assert-tenant-a-1"]

        # Switch caller to Tenant B.
        holder["user"] = tenant_b_user

        # Tenant B sees zero runs in list.
        list_b = client.get("/api/research-runs", headers={"X-Tenant-ID": "tenant-b"})
        assert list_b.status_code == 200
        assert list_b.json()["total"] == 0
        assert list_b.json()["items"] == []

        # Tenant B gets 404 when fetching or mutating Tenant A's run ID.
        get_b = client.get("/api/research-runs/run-tenant-a-001", headers={"X-Tenant-ID": "tenant-b"})
        assert get_b.status_code == 404

        link_b = client.post(
            "/api/research-runs/run-tenant-a-001/assertions",
            headers={"X-Tenant-ID": "tenant-b"},
            json={"assertion_id": "assert-injected"},
        )
        assert link_b.status_code == 404

        # Tenant B spoofing X-Tenant-ID: tenant-a is rejected with 403 + metric.
        before = AUTH_ACCESS_DENIED_TOTAL.labels(required_role="tenant_boundary")._value.get()
        spoofed = client.get("/api/research-runs/run-tenant-a-001", headers={"X-Tenant-ID": "tenant-a"})
        after = AUTH_ACCESS_DENIED_TOTAL.labels(required_role="tenant_boundary")._value.get()
        assert spoofed.status_code == 403
        assert after == before + 1

        # Tenant B cannot trigger or cancel rebuilds under Tenant A's header.
        rebuild_spoof = client.post("/api/graph/rebuild", headers={"X-Tenant-ID": "tenant-a"})
        assert rebuild_spoof.status_code == 403

        cancel_spoof = client.post("/api/graph/rebuild/jobs/job-123/cancel", headers={"X-Tenant-ID": "tenant-a"})
        assert cancel_spoof.status_code == 403
    finally:
        engine.dispose()
