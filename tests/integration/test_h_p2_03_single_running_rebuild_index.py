"""Tests for H-P2-03: partial unique index enforcing at most one RUNNING rebuild job."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.db_models import RebuildJobORM, RebuildJobStatus
from src.data.migrations import apply_migrations


def _make_job(job_id: str, status: RebuildJobStatus) -> RebuildJobORM:
    """Create a minimal RebuildJobORM row for uniqueness-index testing."""
    now = datetime.now(timezone.utc)
    return RebuildJobORM(
        job_id=job_id,
        requested_by="operator",
        status=status.value,
        created_at=now,
        updated_at=now,
    )


def test_sqlite_partial_unique_index_enforces_single_running_rebuild_job(tmp_path: Path) -> None:
    """SQLite enforces at most one RUNNING rebuild job while allowing multiple non-running jobs."""
    db_path = tmp_path / "single-running.db"
    engine = create_engine_from_url(f"sqlite:///{db_path}")
    try:
        init_db(engine)
        index_names = {idx["name"] for idx in inspect(engine).get_indexes("rebuild_jobs")}
        assert "uq_rebuild_jobs_single_running" in index_names

        session_factory = create_session_factory(engine)
        with session_factory() as session:
            session.add(_make_job("job-running-1", RebuildJobStatus.RUNNING))
            session.add(_make_job("job-pending-1", RebuildJobStatus.PENDING))
            session.add(_make_job("job-pending-2", RebuildJobStatus.PENDING))
            session.add(_make_job("job-succeeded-1", RebuildJobStatus.SUCCEEDED))
            session.add(_make_job("job-succeeded-2", RebuildJobStatus.SUCCEEDED))
            session.commit()

        with session_factory() as session:
            session.add(_make_job("job-running-2", RebuildJobStatus.RUNNING))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        with session_factory() as session:
            job = session.get(RebuildJobORM, "job-running-1")
            assert job is not None
            job.status = RebuildJobStatus.SUCCEEDED.value
            session.commit()

        with session_factory() as session:
            session.add(_make_job("job-running-2", RebuildJobStatus.RUNNING))
            session.commit()
    finally:
        engine.dispose()


def test_legacy_sqlite_migration_adds_single_running_index_idempotently(tmp_path: Path) -> None:
    """Legacy SQLite databases gain uq_rebuild_jobs_single_running via apply_migrations."""
    db_path = tmp_path / "legacy-single-running.db"
    migration_001 = Path(__file__).resolve().parents[2] / "migrations" / "001_initial.sql"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(migration_001.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO rebuild_jobs (job_id, requested_by, status, created_at, updated_at) "
            "VALUES ('LEGACY-RUN-1', 'op', 'running', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
        )
        connection.commit()

    apply_migrations(db_path)
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO rebuild_jobs (job_id, requested_by, status, created_at, updated_at) "
                "VALUES ('LEGACY-RUN-2', 'op', 'running', '2026-01-01T00:00:01Z', '2026-01-01T00:00:01Z')"
            )


def test_postgresql_migration_declares_single_running_partial_unique_index() -> None:
    """The PostgreSQL graph ledger migration creates the partial unique index on status='running'."""
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "supabase"
        / "ledgers"
        / "graph"
        / "migrations"
        / "20261127030000_enforce_single_running_rebuild_job.sql"
    )
    sql = migration_path.read_text(encoding="utf-8")
    assert "CREATE UNIQUE INDEX uq_rebuild_jobs_single_running" in sql
    assert "ON public.rebuild_jobs (status)" in sql
    assert "WHERE (status = 'running')" in sql
