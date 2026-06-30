"""Integration tests for rebuild job-list response count and cap semantics."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.auth import User, get_current_rebuild_operator_user
from api.main import app
from src.config.settings import get_settings
from src.data.database import create_engine_from_url
from src.data.db_models import RebuildJobStatus
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
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", db_url)
    get_settings.cache_clear()
    engine = create_engine_from_url(db_url)
    init_db(engine)
    session_factory = create_session_factory(engine)
    app.dependency_overrides[get_current_rebuild_operator_user] = lambda: User(username="admin", disabled=False)
    try:
        yield session_factory
    finally:
        if get_current_rebuild_operator_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_rebuild_operator_user]
        engine.dispose()
        get_settings.cache_clear()


def _seed_jobs(session_factory: Callable[[], Any], count: int) -> list[str]:
    """Seed rebuild jobs and preserve insertion order in persistence."""
    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        return [
            repo.create_rebuild_job(
                requested_by="operator",
                source=f"seed-{index:03d}",
            )
            for index in range(count)
        ]


def _list_rebuild_jobs_payload(
    *,
    limit: int = 100,
    offset: int = 0,
    status_filter: RebuildJobStatus | None = None,
) -> dict[str, Any]:
    """Call the rebuild job-list endpoint boundary and return JSON-ready payload."""
    with TestClient(app) as client:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status_filter is not None:
            params["status"] = status_filter.value
        response = client.get("/api/graph/rebuild/jobs", params=params)
        assert response.status_code == 200
        return response.json()


def test_rebuild_job_list_caps_response_at_100_and_count_matches_returned_length(
    db_setup: Callable[[], Any],
) -> None:
    """When more than 100 jobs exist, the endpoint returns exactly the capped page."""
    _seed_jobs(db_setup, 101)

    payload = _list_rebuild_jobs_payload()

    assert len(payload["jobs"]) == 100
    assert payload["count"] == 100
    assert payload["total"] == 101
    assert payload["hasMore"] is True


def test_rebuild_job_list_count_equals_seeded_total_below_cap(
    db_setup: Callable[[], Any],
) -> None:
    """When total jobs are below the cap, count equals the exact seeded total."""
    _seed_jobs(db_setup, 7)

    payload = _list_rebuild_jobs_payload()

    assert len(payload["jobs"]) == 7
    assert payload["count"] == 7
    assert payload["total"] == 7
    assert payload["hasMore"] is False


@pytest.mark.parametrize(
    ("offset", "expected_has_more"),
    [
        (4, False),
        (2, True),
    ],
)
def test_rebuild_job_list_has_more_with_explicit_pagination(
    db_setup: Callable[[], Any],
    offset: int,
    expected_has_more: bool,
) -> None:
    """When more matching jobs exist after the requested page, has_more follows the page boundary."""
    _seed_jobs(db_setup, 7)

    payload = _list_rebuild_jobs_payload(limit=3, offset=offset)

    assert len(payload["jobs"]) == 3
    assert payload["count"] == 3
    assert payload["total"] == 7
    assert payload["hasMore"] is expected_has_more


def test_rebuild_job_list_total_and_has_more_respect_status_filter(
    db_setup: Callable[[], Any],
) -> None:
    """Status filters should constrain total and has_more calculations."""
    job_ids = _seed_jobs(db_setup, 5)
    with session_scope(db_setup) as session:
        repo = AssetGraphRepository(session)
        repo.mark_rebuild_job_running(job_ids[0], "exec-0")
        repo.mark_rebuild_job_running(job_ids[1], "exec-1")

    payload = _list_rebuild_jobs_payload(limit=1, status_filter=RebuildJobStatus.RUNNING)

    assert len(payload["jobs"]) == 1
    assert payload["count"] == 1
    assert payload["total"] == 2
    assert payload["hasMore"] is True
    assert payload["jobs"][0]["status"] == "running"
