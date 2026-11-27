"""Integration tests for the /api/research-runs provenance REST API."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import User, get_current_active_user
from api.routers.research_runs import get_research_run_repository
from api.routers.research_runs import router as research_runs_router
from src.config.settings import get_settings
from src.data.database import create_engine_from_url
from src.data.research_run_repository import ResearchRunRepository

_VALID_SHA = "b" * 64


def _build_test_client(user: User) -> tuple[TestClient, object]:
    engine = create_engine_from_url("sqlite:///:memory:")
    repo = ResearchRunRepository(engine)
    repo.ensure_sqlite_schema()

    fake_settings = SimpleNamespace(
        admin_username="admin",
        rebuild_operator_usernames=(),
        analyst_usernames=("alice",),
    )

    app = FastAPI()
    app.include_router(research_runs_router)
    app.dependency_overrides[get_research_run_repository] = lambda: repo
    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_settings] = lambda: fake_settings
    return TestClient(app), engine


def test_analyst_can_create_list_get_and_link_assertions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Analyst user can create a ResearchRun, link assertions, and fetch paginated results."""
    monkeypatch.setenv("ANALYST_USERNAMES", "alice")
    monkeypatch.delenv("REBUILD_OPERATOR_USERNAMES", raising=False)
    analyst = User(username="alice", roles=("analyst",))
    client, engine = _build_test_client(analyst)
    try:
        create_resp = client.post(
            "/api/research-runs",
            json={
                "run_id": "run-api-001",
                "domain_id": "financial",
                "method_id": "filing_extract@1",
                "input_digest_sha256": _VALID_SHA,
                "parameters": {"source": "10-K"},
            },
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["run_id"] == "run-api-001"
        assert created["actor_id"] == "alice"
        assert len(created["canonical_digest"]) == 64

        dup_resp = client.post(
            "/api/research-runs",
            json={
                "run_id": "run-api-001",
                "domain_id": "financial",
                "method_id": "filing_extract@1",
                "input_digest_sha256": _VALID_SHA,
                "parameters": {"source": "10-K"},
            },
        )
        assert dup_resp.status_code == 409

        link_resp = client.post(
            "/api/research-runs/run-api-001/assertions",
            json={"assertion_id": "assert-99"},
        )
        assert link_resp.status_code == 201
        assert link_resp.json()["linked_assertion_ids"] == ["assert-99"]

        missing_link_resp = client.post(
            "/api/research-runs/run-does-not-exist/assertions",
            json={"assertion_id": "assert-99"},
        )
        assert missing_link_resp.status_code == 404

        get_resp = client.get("/api/research-runs/run-api-001")
        assert get_resp.status_code == 200
        assert get_resp.json()["linked_assertion_ids"] == ["assert-99"]

        missing_get_resp = client.get("/api/research-runs/run-does-not-exist")
        assert missing_get_resp.status_code == 404

        list_resp = client.get("/api/research-runs?domain_id=financial&limit=10&offset=0")
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert body["total"] == 1
        assert body["count"] == 1
        assert body["has_more"] is False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_viewer_is_denied_creating_research_runs_and_floats_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Viewer role receives 403 on write endpoints; float parameters return 422."""
    monkeypatch.setenv("ANALYST_USERNAMES", "alice")
    monkeypatch.delenv("REBUILD_OPERATOR_USERNAMES", raising=False)
    viewer = User(username="bob", roles=("viewer",))
    client, engine = _build_test_client(viewer)
    try:
        resp = client.post(
            "/api/research-runs",
            json={
                "domain_id": "financial",
                "method_id": "m@1",
                "input_digest_sha256": _VALID_SHA,
            },
        )
        assert resp.status_code == 403
    finally:
        engine.dispose()  # type: ignore[attr-defined]

    analyst = User(username="alice", roles=("analyst",))
    client2, engine2 = _build_test_client(analyst)
    try:
        bad_resp = client2.post(
            "/api/research-runs",
            json={
                "domain_id": "financial",
                "method_id": "m@1",
                "input_digest_sha256": _VALID_SHA,
                "parameters": {"bad_float": 0.5},
            },
        )
        assert bad_resp.status_code == 422
    finally:
        engine2.dispose()  # type: ignore[attr-defined]
