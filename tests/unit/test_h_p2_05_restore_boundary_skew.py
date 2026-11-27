"""Unit tests for H-P2-05: cross-boundary restore skew check (Graph vs Coordination)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.check_restore_boundary_skew import (
    CHECK_FAILED,
    SUCCESS,
    USAGE_ERROR,
    evaluate_restore_boundary_skew,
    main,
)
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.db_models import DistributedLockORM, RebuildJobORM, RebuildJobStatus

UTC = timezone.utc


def _init_sqlite(path: Path) -> str:
    """Create and initialize a SQLite database file and return its URL."""
    url = f"sqlite:///{path}"
    engine = create_engine_from_url(url)
    try:
        init_db(engine)
    finally:
        engine.dispose()
    return url


def test_clean_post_restore_separate_boundaries_passes(tmp_path: Path, capsys) -> None:
    """Clean post-restore Graph and Coordination DBs pass with exit 0 and redacted output."""
    graph_url = _init_sqlite(tmp_path / "graph.db")
    coord_url = _init_sqlite(tmp_path / "coord.db")
    now = datetime.now(UTC)

    graph_engine = create_engine_from_url(graph_url)
    with create_session_factory(graph_engine)() as session:
        session.add(
            RebuildJobORM(
                job_id="job-1",
                requested_by="op",
                status=RebuildJobStatus.SUCCEEDED.value,
                created_at=now - timedelta(seconds=30),
                updated_at=now - timedelta(seconds=10),
            )
        )
        session.commit()
    graph_engine.dispose()

    rc = main(["--graph-url", graph_url, "--coordination-url", coord_url, "--max-skew-seconds", "300"])
    assert rc == SUCCESS
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["same_boundary"] is False
    assert payload["running_jobs_count"] == 0
    assert payload["active_locks_count"] == 0


def test_post_restore_leftover_running_job_or_active_lock_fails(tmp_path: Path) -> None:
    """Leftover RUNNING jobs on Graph or active locks on Coordination fail post-restore check."""
    graph_url = _init_sqlite(tmp_path / "graph_dirty.db")
    coord_url = _init_sqlite(tmp_path / "coord_dirty.db")
    now = datetime.now(UTC)

    g_eng = create_engine_from_url(graph_url)
    with create_session_factory(g_eng)() as session:
        session.add(
            RebuildJobORM(
                job_id="job-run",
                requested_by="op",
                status=RebuildJobStatus.RUNNING.value,
                active_worker_id="worker-1",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    g_eng.dispose()

    c_eng = create_engine_from_url(coord_url)
    with create_session_factory(c_eng)() as session:
        session.add(
            DistributedLockORM(
                lock_name="graph_rebuild",
                holder_id="worker-1",
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(seconds=300),
            )
        )
        session.commit()
    c_eng.dispose()

    report = evaluate_restore_boundary_skew(graph_url, coord_url, now=now)
    assert report.status == "FAIL"
    assert any(r.startswith("post_restore_running_jobs_present") for r in report.reasons)
    assert any(r.startswith("post_restore_active_locks_present") for r in report.reasons)

    # With --allow-active, matched worker passes
    live_report = evaluate_restore_boundary_skew(graph_url, coord_url, allow_active=True, now=now)
    assert live_report.status == "PASS"


def test_timestamp_skew_between_graph_and_coordination_fails(tmp_path: Path) -> None:
    """Excessive timestamp skew between Graph and Coordination fails the skew check."""
    graph_url = _init_sqlite(tmp_path / "graph_skew.db")
    coord_url = _init_sqlite(tmp_path / "coord_skew.db")
    now = datetime.now(UTC)

    g_eng = create_engine_from_url(graph_url)
    with create_session_factory(g_eng)() as session:
        session.add(
            RebuildJobORM(
                job_id="job-old",
                requested_by="op",
                status=RebuildJobStatus.SUCCEEDED.value,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
            )
        )
        session.commit()
    g_eng.dispose()

    c_eng = create_engine_from_url(coord_url)
    with create_session_factory(c_eng)() as session:
        session.add(
            DistributedLockORM(
                lock_name="graph_rebuild",
                holder_id="worker-old",
                created_at=now - timedelta(seconds=120),
                updated_at=now - timedelta(seconds=60),
                expires_at=now - timedelta(seconds=10),
            )
        )
        session.commit()
    c_eng.dispose()

    report = evaluate_restore_boundary_skew(graph_url, coord_url, max_skew_seconds=300.0, now=now)
    assert report.status == "FAIL"
    assert report.boundary_skew_seconds is not None and report.boundary_skew_seconds > 300.0
    assert any(r.startswith("boundary_timestamp_skew_exceeded") for r in report.reasons)

    rc = main(["--graph-url", graph_url, "--coordination-url", coord_url, "--max-skew-seconds", "300"])
    assert rc == CHECK_FAILED


def test_missing_graph_url_returns_usage_error(monkeypatch) -> None:
    """Missing ASSET_GRAPH_DATABASE_URL returns exit code 2."""
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    monkeypatch.delenv("COORDINATION_DATABASE_URL", raising=False)
    assert main([]) == USAGE_ERROR
