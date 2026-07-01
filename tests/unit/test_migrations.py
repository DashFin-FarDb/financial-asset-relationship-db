"""Unit tests for src/data/migrations.py — apply_postgresql_heartbeat_migration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.data.migrations import apply_postgresql_heartbeat_migration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_col(name: str, length: int | None = None) -> dict:
    """Return a minimal column-info dict like SQLAlchemy's inspector produces."""
    col_type = MagicMock()
    col_type.length = length
    return {"name": name, "type": col_type}


def _assert_with_message(condition: bool, message: str) -> None:
    """Fail the test with a readable message when condition is false."""
    if not condition:
        pytest.fail(message)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApplyPostgresqlHeartbeatMigration:
    """Unit tests for apply_postgresql_heartbeat_migration behaviour."""

    def _run(self, table_names, columns, recheck_scalar=None):
        """Execute apply_postgresql_heartbeat_migration.

        Uses a fully mocked engine and returns begin_conn for assertion.
        """
        engine = MagicMock()

        inspector = MagicMock()
        inspector.get_table_names.return_value = table_names
        inspector.get_columns.return_value = columns

        begin_conn = MagicMock()
        begin_conn.execute.return_value.scalar.return_value = recheck_scalar
        engine.begin.return_value.__enter__ = MagicMock(return_value=begin_conn)
        engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.data.migrations.inspect", return_value=inspector):
            apply_postgresql_heartbeat_migration(engine)

        return begin_conn

    # --- early-exit ---

    def test_no_rebuild_jobs_table_does_nothing(self):
        """Function must return without touching the engine when the table is absent."""
        begin_conn = self._run(table_names=[], columns=[])
        begin_conn.execute.assert_not_called()

    # --- no DDL needed ---

    def test_all_columns_present_correct_width_no_ddl(self):
        """DDL only for status constraint update when all columns already exist."""
        cols = [
            _make_col("active_worker_id", length=64),
            _make_col("last_heartbeat_at"),
            _make_col("execution_id"),
            _make_col("checkpoint_data"),
            _make_col("cancellation_requested_at"),
        ]
        begin_conn = self._run(["rebuild_jobs"], cols)
        # 2 calls: DROP CONSTRAINT, ADD CONSTRAINT
        assert begin_conn.execute.call_count == 2

    # --- ADD COLUMN batching ---

    def test_missing_both_columns_adds_both(self):
        """When heartbeat columns are absent, ADD COLUMN statements are batched (plus constraint)."""
        begin_conn = self._run(["rebuild_jobs"], columns=[])
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        assert any("active_worker_id" in s for s in executed_sql)
        assert any("last_heartbeat_at" in s for s in executed_sql)
        assert any("execution_id" in s for s in executed_sql)
        assert any("checkpoint_data" in s for s in executed_sql)
        assert any("cancellation_requested_at" in s for s in executed_sql)
        # 5 ADD COLUMNs + 2 constraint update calls = 7
        assert begin_conn.execute.call_count == 7

    def test_missing_last_heartbeat_at_only(self):
        """Only the missing columns are added (plus constraint)."""
        cols = [
            _make_col("active_worker_id", length=64),
            _make_col("execution_id"),
            _make_col("checkpoint_data"),
            _make_col("cancellation_requested_at"),
        ]
        begin_conn = self._run(["rebuild_jobs"], cols)
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        assert any("last_heartbeat_at" in s for s in executed_sql)
        assert not any("active_worker_id" in s and "ALTER TABLE" in s and "ADD COLUMN" in s for s in executed_sql)
        # 1 ADD COLUMN + 2 constraint update calls = 3
        assert begin_conn.execute.call_count == 3

    # --- width normalisation ---

    def test_wide_column_empty_table_normalises(self):
        """Normalise wide active_worker_id column when table is empty.

        The ALTER COLUMN TYPE statement must be included in the same
        atomic DDL batch.
        """
        cols = [_make_col("active_worker_id", length=255), _make_col("last_heartbeat_at")]
        begin_conn = self._run(["rebuild_jobs"], cols, recheck_scalar=None)

        # ALTER COLUMN TYPE must be part of the atomic DDL batch
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        _assert_with_message(
            any("ALTER COLUMN active_worker_id TYPE VARCHAR(64)" in s for s in executed_sql),
            "Expected normalization ALTER to be executed.",
        )
        _assert_with_message(
            sum("ALTER COLUMN active_worker_id TYPE VARCHAR(64)" in s for s in executed_sql) == 1,
            "Expected exactly one normalization ALTER execution.",
        )

    def test_wide_column_short_data_normalises(self):
        """Normalise wide active_worker_id column when data is short.

        When the longest stored value is ≤ 64 chars, ALTER COLUMN TYPE
        must be batched with the DDL.
        """
        cols = [_make_col("active_worker_id", length=255), _make_col("last_heartbeat_at")]
        begin_conn = self._run(["rebuild_jobs"], cols, recheck_scalar=32)
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        _assert_with_message(
            any("ALTER COLUMN active_worker_id TYPE VARCHAR(64)" in s for s in executed_sql),
            "Expected normalization ALTER to be executed.",
        )
        _assert_with_message(
            sum("ALTER COLUMN active_worker_id TYPE VARCHAR(64)" in s for s in executed_sql) == 1,
            "Expected exactly one normalization ALTER execution.",
        )

    def test_wide_column_long_data_skips_normalisation_and_warns(self, caplog):
        """Skip normalisation when data is too long and log a warning.

        When the longest stored value exceeds 64 chars, the ALTER COLUMN TYPE
        statement must NOT be batched.
        """
        import logging

        cols = [_make_col("active_worker_id", length=255), _make_col("last_heartbeat_at")]

        with caplog.at_level(logging.WARNING, logger="src.data.migrations"):
            begin_conn = self._run(["rebuild_jobs"], cols, recheck_scalar=200)

        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        assert not any("ALTER COLUMN" in s for s in executed_sql)
        assert "Skipping active_worker_id width normalization" in caplog.text
        # Warning must not include exc_info (stack trace) — per project logging convention
        assert "Traceback" not in caplog.text

    def test_wide_column_alter_runs_in_same_transaction_as_add_columns(self):
        """Batch ADD COLUMN and ALTER COLUMN TYPE in same transaction.

        Ensures atomic DDL execution for schema upgrades and normalisation.
        """
        # Simulate: active_worker_id is wide (255) and last_heartbeat_at is missing.
        # This triggers both the ALTER COLUMN and ADD COLUMN paths.
        cols_with_wide = [_make_col("active_worker_id", length=255)]
        begin_conn = self._run(["rebuild_jobs"], cols_with_wide, recheck_scalar=10)

        # DDL statements must be batched in the same engine.begin() block
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        _assert_with_message(
            any("ADD COLUMN IF NOT EXISTS last_heartbeat_at" in s for s in executed_sql),
            "Expected last_heartbeat_at ADD COLUMN statement in DDL batch.",
        )
        _assert_with_message(
            any("ALTER COLUMN active_worker_id TYPE VARCHAR(64)" in s for s in executed_sql),
            "Expected normalization ALTER statement in DDL batch.",
        )
        _assert_with_message(
            sum("ALTER COLUMN active_worker_id TYPE VARCHAR(64)" in s for s in executed_sql) == 1,
            "Expected exactly one normalization ALTER execution in DDL batch.",
        )
