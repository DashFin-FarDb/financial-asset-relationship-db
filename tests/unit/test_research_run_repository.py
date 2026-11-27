"""Unit tests for immutable ResearchRun provenance contract and repository."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.data.database import create_engine_from_url
from src.data.research_run_repository import (
    ResearchRunConflictError,
    ResearchRunNotFoundError,
    ResearchRunRepository,
)
from src.governance.research_run import ResearchRunCreate, ResearchRunRecord

_VALID_SHA = "a" * 64
_FIXED_TS = datetime(2026, 11, 27, 19, 0, 0, tzinfo=timezone.utc)


def _make_repo() -> tuple[ResearchRunRepository, object]:
    engine = create_engine_from_url("sqlite:///:memory:")
    repo = ResearchRunRepository(engine)
    repo.ensure_sqlite_schema()
    return repo, engine


def test_research_run_digest_is_deterministic_and_rejects_floats() -> None:
    """Canonical digest is identical regardless of dict key order and rejects floats."""
    p1 = ResearchRunCreate(
        run_id="run-001",
        domain_id="financial",
        method_id="filing_extract@1",
        input_digest_sha256=_VALID_SHA,
        parameters={"b": "2", "a": "1"},
        actor_id="analyst-1",
        created_at=_FIXED_TS,
    )
    p2 = ResearchRunCreate(
        run_id="run-001",
        domain_id="financial",
        method_id="filing_extract@1",
        input_digest_sha256=_VALID_SHA,
        parameters={"a": "1", "b": "2"},
        actor_id="analyst-1",
        created_at=_FIXED_TS,
    )
    assert ResearchRunRecord.from_create(p1).canonical_digest == ResearchRunRecord.from_create(p2).canonical_digest

    with pytest.raises(ValidationError, match="floating-point"):
        ResearchRunCreate(
            run_id="run-002",
            domain_id="financial",
            method_id="filing_extract@1",
            input_digest_sha256=_VALID_SHA,
            parameters={"threshold": 0.75},
            actor_id="analyst-1",
            created_at=_FIXED_TS,
        )


def test_create_get_list_and_idempotency() -> None:
    """Repository persists runs, supports idempotent replay, rejects conflicts, and paginates."""
    repo, engine = _make_repo()
    try:
        payload = ResearchRunCreate(
            run_id="run-alpha",
            domain_id="financial",
            method_id="sec_10k_parser@1",
            input_digest_sha256=_VALID_SHA,
            parameters={"year": 2026},
            actor_id="analyst-1",
            tenant_id="tenant-a",
            created_at=_FIXED_TS,
        )
        created = repo.create_run(payload)
        replayed = repo.create_run(payload)
        assert replayed == created

        conflicting = payload.model_copy(update={"parameters": {"year": 2025}})
        with pytest.raises(ResearchRunConflictError):
            repo.create_run(conflicting)

        assert repo.get_run("run-alpha", tenant_id="tenant-a") == created
        assert repo.get_run("run-alpha", tenant_id="tenant-b") is None

        runs, total = repo.list_runs(domain_id="financial", tenant_id="tenant-a", limit=10, offset=0)
        assert total == 1
        assert runs == [created]
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_sqlite_immutability_triggers_reject_update_and_delete() -> None:
    """SQLite BEFORE UPDATE and BEFORE DELETE triggers block mutation of persisted runs."""
    repo, engine = _make_repo()
    try:
        repo.create_run(
            ResearchRunCreate(
                run_id="run-imm",
                domain_id="human_resources",
                method_id="org_chart_sync@1",
                input_digest_sha256=_VALID_SHA,
                actor_id="analyst-hr",
                created_at=_FIXED_TS,
            )
        )
        with pytest.raises(IntegrityError, match="immutable"):
            with engine.begin() as conn:  # type: ignore[attr-defined]
                conn.execute(text("UPDATE research_runs SET domain_id = 'tampered' WHERE run_id = 'run-imm'"))

        with pytest.raises(IntegrityError, match="immutable"):
            with engine.begin() as conn:  # type: ignore[attr-defined]
                conn.execute(text("DELETE FROM research_runs WHERE run_id = 'run-imm'"))
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_assertion_linkage_is_idempotent_and_validates_run_existence() -> None:
    """Linking assertions requires an existing run in the same tenant and is idempotent."""
    repo, engine = _make_repo()
    try:
        repo.create_run(
            ResearchRunCreate(
                run_id="run-link",
                domain_id="financial",
                method_id="m@1",
                input_digest_sha256=_VALID_SHA,
                actor_id="analyst-1",
                tenant_id="default",
                created_at=_FIXED_TS,
            )
        )
        repo.link_assertion("run-link", "assert-1", tenant_id="default")
        repo.link_assertion("run-link", "assert-1", tenant_id="default")
        repo.link_assertion("run-link", "assert-2", tenant_id="default")
        assert repo.list_linked_assertions("run-link", tenant_id="default") == ["assert-1", "assert-2"]

        with pytest.raises(ResearchRunNotFoundError):
            repo.link_assertion("run-missing", "assert-3", tenant_id="default")
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_ensure_sqlite_schema_fails_closed_on_postgresql() -> None:
    """PostgreSQL DDL must fail closed at runtime (owned by Supabase ledger)."""
    fake_engine = MagicMock()
    fake_engine.url = "postgresql+psycopg://user:pass@localhost:5432/fardb"
    repo = ResearchRunRepository(fake_engine)
    with pytest.raises(RuntimeError, match="Supabase ledger"):
        repo.ensure_sqlite_schema()
