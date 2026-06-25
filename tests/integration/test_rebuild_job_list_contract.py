"""Integration tests for rebuild job-list response count and cap semantics."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.app_factory import create_app
from api.auth import User, get_current_active_user
from src.config.settings import get_settings
from src.data.database import create_engine_from_url
from tests.integration.facade import (
    AssetGraphRepository,
    create_session_factory,
    init_db,
    session_scope,
)

pytestmark = pytest.mark.integration


@pytest.fixture()
def db_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[[], Any]]:
    """Provide a configured persistence database and session factory."""
    db_url = f"sqlite:///{tmp_path / 'rebuild-jobs.db'}"
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", db_url)
    get_settings.cache_clear()
    engine = create_engine_from_url(db_url)
    init_db(engine)
    session_factory = create_session_factory(engine)
    try:
        yield session_factory
    finally:
        engine.dispose()
        get_settings.cache_clear()


@pytest.fixture()
def operator_client(
    db_setup: Callable[[], Any],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Provide a TestClient authenticated as the configured rebuild operator."""
    _ = db_setup
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    get_settings.cache_clear()
    app = create_app()

    def active_user() -> User:
        """Return an active operator user for auth dependency override."""
        return User(username="admin", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def _seed_jobs(session_factory: Callable[[], Any], count: int) -> None:
    """Seed rebuild jobs and preserve insertion order in persistence."""
    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        for index in range(count):
            repo.create_rebuild_job(
                requested_by="operator",
                source=f"seed-{index:03d}",
            )


def test_rebuild_job_list_caps_response_at_100_and_count_matches_returned_length(
    operator_client: TestClient,
    db_setup: Callable[[], Any],
) -> None:
    """When more than 100 jobs exist, the endpoint returns exactly the capped page."""
    _seed_jobs(db_setup, 101)

    response = operator_client.get("/api/graph/rebuild/jobs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["jobs"]) == 100
    assert payload["count"] == 100


def test_rebuild_job_list_count_equals_seeded_total_below_cap(
    operator_client: TestClient,
    db_setup: Callable[[], Any],
) -> None:
    """When total jobs are below the cap, count equals the exact seeded total."""
    _seed_jobs(db_setup, 7)

    response = operator_client.get("/api/graph/rebuild/jobs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["jobs"]) == 7
    assert payload["count"] == 7
    assert "total" not in payload
    assert "has_more" not in payload
    assert "hasMore" not in payload
