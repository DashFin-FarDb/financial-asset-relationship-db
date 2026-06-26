"""Integration tests for rebuild job-list response count and cap semantics."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from api.auth import User
from api.routers.graph_admin import list_rebuild_jobs
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
    try:
        yield session_factory
    finally:
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
    response = list_rebuild_jobs(
        _current_user=User(username="admin", disabled=False),
        limit=limit,
        offset=offset,
        status_filter=status_filter,
    )
    return response.model_dump(mode="json")


def test_rebuild_job_list_caps_response_at_100_and_count_matches_returned_length(
    db_setup: Callable[[], Any],
) -> None:
    """When more than 100 jobs exist, the endpoint returns exactly the capped page."""
    _seed_jobs(db_setup, 101)

    payload = _list_rebuild_jobs_payload()

    assert len(payload["jobs"]) == 100
    assert payload["count"] == 100
    assert payload["total"] == 101
    assert payload["has_more"] is True


def test_rebuild_job_list_count_equals_seeded_total_below_cap(
    db_setup: Callable[[], Any],
) -> None:
    """When total jobs are below the cap, count equals the exact seeded total."""
    _seed_jobs(db_setup, 7)

    payload = _list_rebuild_jobs_payload()

    assert len(payload["jobs"]) == 7
    assert payload["count"] == 7
    assert payload["total"] == 7
    assert payload["has_more"] is False
    assert "hasMore" not in payload


def test_rebuild_job_list_has_more_false_when_offset_exhausts_total(
    db_setup: Callable[[], Any],
) -> None:
    """When the requested page exhausts matching jobs, has_more is false."""
    _seed_jobs(db_setup, 7)

    payload = _list_rebuild_jobs_payload(limit=3, offset=4)

    assert len(payload["jobs"]) == 3
    assert payload["count"] == 3
    assert payload["total"] == 7
    assert payload["has_more"] is False


def test_rebuild_job_list_has_more_true_with_explicit_pagination(
    db_setup: Callable[[], Any],
) -> None:
    """When more matching jobs exist after the requested page, has_more is true."""
    _seed_jobs(db_setup, 7)

    payload = _list_rebuild_jobs_payload(limit=3, offset=2)

    assert len(payload["jobs"]) == 3
    assert payload["count"] == 3
    assert payload["total"] == 7
    assert payload["has_more"] is True


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
    assert payload["has_more"] is True
    assert payload["jobs"][0]["status"] == "running"
