"""Append-only repository for immutable ResearchRun provenance records.

SQLite creates local tables and BEFORE UPDATE / BEFORE DELETE immutability
triggers via ``ensure_sqlite_schema``. PostgreSQL schema mutation is owned by
the profile-scoped Supabase ledger and fails closed at runtime.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url

from src.governance.research_run import ResearchRunCreate, ResearchRunRecord

_UTC = timezone.utc


class ResearchRunConflictError(ValueError):
    """Raised when a run_id already exists with a different canonical digest."""


class ResearchRunNotFoundError(LookupError):
    """Raised when a referenced ResearchRun does not exist."""


class ResearchRunRepository:
    """Append-only repository for immutable ResearchRun records and assertion links."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a SQLAlchemy Engine."""
        self._engine = engine

    def ensure_sqlite_schema(self) -> None:
        """Install additive SQLite tables and immutability triggers (rejects PostgreSQL DDL)."""
        backend = make_url(str(self._engine.url)).get_backend_name()
        if backend == "postgresql":
            raise RuntimeError("PostgreSQL research_runs DDL is owned by the profile-scoped Supabase ledger")
        if backend != "sqlite":
            raise RuntimeError(f"Unsupported backend for local schema bootstrap: {backend}")

        with self._engine.begin() as conn:
            conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS research_runs (
                        run_id TEXT PRIMARY KEY,
                        contract_version TEXT NOT NULL,
                        domain_id TEXT NOT NULL,
                        method_id TEXT NOT NULL,
                        input_digest_sha256 TEXT NOT NULL,
                        parameters_json TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL DEFAULT 'default',
                        created_at TEXT NOT NULL,
                        canonical_digest TEXT NOT NULL
                    )
                    """))
            conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_research_runs_domain_tenant
                    ON research_runs (tenant_id, domain_id, created_at)
                    """))
            conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS research_run_assertion_links (
                        run_id TEXT NOT NULL,
                        assertion_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL DEFAULT 'default',
                        linked_at TEXT NOT NULL,
                        PRIMARY KEY (run_id, assertion_id),
                        FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
                    )
                    """))
            conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS tr_research_runs_no_update
                    BEFORE UPDATE ON research_runs
                    BEGIN
                        SELECT RAISE(ABORT, 'research_runs rows are immutable');
                    END
                    """))
            conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS tr_research_runs_no_delete
                    BEFORE DELETE ON research_runs
                    BEGIN
                        SELECT RAISE(ABORT, 'research_runs rows are immutable');
                    END
                    """))
            conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS tr_research_run_links_no_update
                    BEFORE UPDATE ON research_run_assertion_links
                    BEGIN
                        SELECT RAISE(ABORT, 'research_run_assertion_links rows are immutable');
                    END
                    """))
            conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS tr_research_run_links_no_delete
                    BEFORE DELETE ON research_run_assertion_links
                    BEGIN
                        SELECT RAISE(ABORT, 'research_run_assertion_links rows are immutable');
                    END
                    """))

    @staticmethod
    def _row_to_record(row: Any) -> ResearchRunRecord:
        """Convert a SQL result mapping into an immutable ResearchRunRecord."""
        return ResearchRunRecord(
            run_id=row["run_id"],
            contract_version=row["contract_version"],
            domain_id=row["domain_id"],
            method_id=row["method_id"],
            input_digest_sha256=row["input_digest_sha256"],
            parameters=json.loads(row["parameters_json"]),
            actor_id=row["actor_id"],
            tenant_id=row["tenant_id"],
            created_at=row["created_at"],
            canonical_digest=row["canonical_digest"],
        )

    def create_run(self, payload: ResearchRunCreate) -> ResearchRunRecord:
        """Persist a new immutable ResearchRun (idempotent for identical canonical_digest)."""
        record = ResearchRunRecord.from_create(payload)
        params_json = json.dumps(record.parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

        with self._engine.begin() as conn:
            existing = (
                conn.execute(
                    text("SELECT * FROM research_runs WHERE run_id = :run_id"),
                    {"run_id": record.run_id},
                )
                .mappings()
                .first()
            )
            if existing is not None:
                if existing["canonical_digest"] == record.canonical_digest:
                    return self._row_to_record(existing)
                raise ResearchRunConflictError(
                    f"ResearchRun {record.run_id!r} already exists with a different canonical digest"
                )

            conn.execute(
                text("""
                    INSERT INTO research_runs (
                        run_id, contract_version, domain_id, method_id,
                        input_digest_sha256, parameters_json, actor_id,
                        tenant_id, created_at, canonical_digest
                    ) VALUES (
                        :run_id, :contract_version, :domain_id, :method_id,
                        :input_digest_sha256, :parameters_json, :actor_id,
                        :tenant_id, :created_at, :canonical_digest
                    )
                    """),
                {
                    "run_id": record.run_id,
                    "contract_version": record.contract_version,
                    "domain_id": record.domain_id,
                    "method_id": record.method_id,
                    "input_digest_sha256": record.input_digest_sha256,
                    "parameters_json": params_json,
                    "actor_id": record.actor_id,
                    "tenant_id": record.tenant_id,
                    "created_at": record.created_at,
                    "canonical_digest": record.canonical_digest,
                },
            )
        return record

    def get_run(self, run_id: str, *, tenant_id: str | None = None) -> ResearchRunRecord | None:
        """Fetch an immutable ResearchRun by ID, optionally scoped to a tenant."""
        with self._engine.connect() as conn:
            if tenant_id is None:
                row = (
                    conn.execute(
                        text("SELECT * FROM research_runs WHERE run_id = :run_id"),
                        {"run_id": run_id},
                    )
                    .mappings()
                    .first()
                )
            else:
                row = (
                    conn.execute(
                        text("SELECT * FROM research_runs WHERE run_id = :run_id AND tenant_id = :tenant_id"),
                        {"run_id": run_id, "tenant_id": tenant_id},
                    )
                    .mappings()
                    .first()
                )
        return self._row_to_record(row) if row is not None else None

    def list_runs(
        self,
        *,
        domain_id: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchRunRecord], int]:
        """List ResearchRuns ordered newest-first with total count for pagination."""
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": max(1, min(limit, 200)), "offset": max(0, offset)}
        if domain_id is not None:
            clauses.append("domain_id = :domain_id")
            params["domain_id"] = domain_id
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._engine.connect() as conn:
            total = int(conn.execute(text(f"SELECT COUNT(*) FROM research_runs {where_sql}"), params).scalar_one())
            rows = (
                conn.execute(
                    text(
                        f"SELECT * FROM research_runs {where_sql} "
                        "ORDER BY created_at DESC, run_id ASC LIMIT :limit OFFSET :offset"
                    ),
                    params,
                )
                .mappings()
                .all()
            )
        return [self._row_to_record(row) for row in rows], total

    def link_assertion(self, run_id: str, assertion_id: str, *, tenant_id: str = "default") -> None:
        """Link an assertion_id to an existing ResearchRun (idempotent on duplicate link)."""
        linked_at = datetime.now(_UTC).isoformat()
        with self._engine.begin() as conn:
            run_row = (
                conn.execute(
                    text("SELECT run_id FROM research_runs WHERE run_id = :run_id AND tenant_id = :tenant_id"),
                    {"run_id": run_id, "tenant_id": tenant_id},
                )
                .mappings()
                .first()
            )
            if run_row is None:
                raise ResearchRunNotFoundError(f"ResearchRun {run_id!r} not found for tenant {tenant_id!r}")

            existing = (
                conn.execute(
                    text(
                        "SELECT 1 FROM research_run_assertion_links "
                        "WHERE run_id = :run_id AND assertion_id = :assertion_id"
                    ),
                    {"run_id": run_id, "assertion_id": assertion_id},
                )
                .mappings()
                .first()
            )
            if existing is not None:
                return

            conn.execute(
                text("""
                    INSERT INTO research_run_assertion_links (run_id, assertion_id, tenant_id, linked_at)
                    VALUES (:run_id, :assertion_id, :tenant_id, :linked_at)
                    """),
                {
                    "run_id": run_id,
                    "assertion_id": assertion_id,
                    "tenant_id": tenant_id,
                    "linked_at": linked_at,
                },
            )

    def list_linked_assertions(self, run_id: str, *, tenant_id: str | None = None) -> list[str]:
        """Return assertion IDs linked to a ResearchRun in deterministic order."""
        with self._engine.connect() as conn:
            if tenant_id is None:
                rows = conn.execute(
                    text(
                        "SELECT assertion_id FROM research_run_assertion_links WHERE run_id = :run_id ORDER BY assertion_id"
                    ),
                    {"run_id": run_id},
                ).all()
            else:
                rows = conn.execute(
                    text(
                        "SELECT assertion_id FROM research_run_assertion_links "
                        "WHERE run_id = :run_id AND tenant_id = :tenant_id ORDER BY assertion_id"
                    ),
                    {"run_id": run_id, "tenant_id": tenant_id},
                ).all()
        return [str(row[0]) for row in rows]
