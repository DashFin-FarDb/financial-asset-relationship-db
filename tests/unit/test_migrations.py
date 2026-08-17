"""Unit tests for the retired PostgreSQL heartbeat-migration entry point."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.data.database import SchemaCompatibilityError
from src.data.migrations import (
    apply_postgresql_heartbeat_migration,
    postgresql_heartbeat_schema_gaps,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_col(name: str, length: int | None = None) -> dict:
    """Return a minimal column-info dict like SQLAlchemy's inspector produces."""
    col_type = MagicMock()
    col_type.length = length
    return {"name": name, "type": col_type}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApplyPostgresqlHeartbeatMigration:
    """The retired imperative helper must never inspect or mutate PostgreSQL."""

    @staticmethod
    def test_fails_closed_without_touching_engine() -> None:
        """All PostgreSQL rebuild DDL now belongs to the profile-scoped ledger."""
        engine = MagicMock()

        with pytest.raises(SchemaCompatibilityError, match="profile-scoped Supabase ledger"):
            apply_postgresql_heartbeat_migration(engine=engine)

        engine.begin.assert_not_called()
        engine.connect.assert_not_called()


class TestPostgresqlHeartbeatSchemaGaps:
    """Read-only compatibility reporting for PostgreSQL rebuild schema."""

    @staticmethod
    def test_reports_missing_columns_width_and_status_constraint() -> None:
        """Every migration-owned incompatibility should be reported without DDL."""
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["rebuild_jobs"]
        inspector.get_columns.return_value = [
            _make_col("active_worker_id", length=255),
            _make_col("last_heartbeat_at"),
        ]
        inspector.get_check_constraints.return_value = []

        gaps = postgresql_heartbeat_schema_gaps(inspector)

        assert "rebuild_jobs.execution_id" in gaps
        assert "rebuild_jobs.active_worker_id width <= 64" in gaps
        assert "ck_rebuild_jobs_status" in gaps

    @staticmethod
    def test_accepts_current_compatibility_shape() -> None:
        """The current columns, widths, and status set should have no gaps."""
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["rebuild_jobs"]
        inspector.get_columns.return_value = [
            _make_col("active_worker_id", length=64),
            _make_col("last_heartbeat_at"),
            _make_col("execution_id", length=64),
            _make_col("checkpoint_data"),
            _make_col("cancellation_requested_at"),
        ]
        inspector.get_check_constraints.return_value = [
            {
                "name": "ck_rebuild_jobs_status",
                "sqltext": "status IN ('pending', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled')",
            }
        ]

        assert postgresql_heartbeat_schema_gaps(inspector) == []

    @staticmethod
    def test_reports_missing_rebuild_jobs_table() -> None:
        """An absent rebuild_jobs table should short-circuit to one gap."""
        inspector = MagicMock()
        inspector.get_table_names.return_value = []

        assert postgresql_heartbeat_schema_gaps(inspector) == ["rebuild_jobs table"]

    @staticmethod
    @pytest.mark.parametrize("length", [None, 255])
    def test_reports_unbounded_or_wide_execution_id(length: int | None) -> None:
        """Unbounded and oversized identifier columns are incompatible."""
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["rebuild_jobs"]
        inspector.get_columns.return_value = [
            _make_col("active_worker_id", length=64),
            _make_col("last_heartbeat_at"),
            _make_col("execution_id", length=length),
            _make_col("checkpoint_data"),
            _make_col("cancellation_requested_at"),
        ]
        inspector.get_check_constraints.return_value = [
            {
                "name": "ck_rebuild_jobs_status",
                "sqltext": "status IN ('pending', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled')",
            }
        ]

        assert "rebuild_jobs.execution_id width <= 64" in postgresql_heartbeat_schema_gaps(inspector)

    @staticmethod
    @pytest.mark.parametrize(
        "sqltext",
        [
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled', 'paused')",
            ("status IN ('pending', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled') " "OR TRUE"),
            ("other_status IN " "('pending', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled')"),
        ],
    )
    def test_reports_noncanonical_status_domain(sqltext: str) -> None:
        """Missing or additional statuses must fail exact-domain verification."""
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["rebuild_jobs"]
        inspector.get_columns.return_value = [
            _make_col("active_worker_id", length=64),
            _make_col("last_heartbeat_at"),
            _make_col("execution_id", length=64),
            _make_col("checkpoint_data"),
            _make_col("cancellation_requested_at"),
        ]
        inspector.get_check_constraints.return_value = [{"name": "ck_rebuild_jobs_status", "sqltext": sqltext}]

        assert "ck_rebuild_jobs_status" in postgresql_heartbeat_schema_gaps(inspector)

    @staticmethod
    def test_accepts_postgresql_any_status_constraint_rendering() -> None:
        """PostgreSQL deparsing of the exact status predicate should remain compatible."""
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["rebuild_jobs"]
        inspector.get_columns.return_value = [
            _make_col("active_worker_id", length=64),
            _make_col("last_heartbeat_at"),
            _make_col("execution_id", length=64),
            _make_col("checkpoint_data"),
            _make_col("cancellation_requested_at"),
        ]
        inspector.get_check_constraints.return_value = [
            {
                "name": "ck_rebuild_jobs_status",
                "sqltext": (
                    "((status)::text = ANY ((ARRAY['cancelled'::character varying, "
                    "'cancel_requested'::character varying, 'failed'::character varying, "
                    "'pending'::character varying, 'running'::character varying, "
                    "'succeeded'::character varying])::text[]))"
                ),
            }
        ]

        assert postgresql_heartbeat_schema_gaps(inspector) == []
