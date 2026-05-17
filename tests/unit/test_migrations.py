"""Unit tests for src/data/migrations.py — apply_postgresql_heartbeat_migration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.data.migrations import apply_postgresql_heartbeat_migration

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
    """Unit tests for apply_postgresql_heartbeat_migration behaviour."""

    def _run(self, table_names, columns, max_length_scalar=None):
        """
        Execute apply_postgresql_heartbeat_migration with a fully mocked engine
        and return (begin_conn, connect_conn) for assertion.
        """
        engine = MagicMock()

        inspector = MagicMock()
        inspector.get_table_names.return_value = table_names
        inspector.get_columns.return_value = columns

        connect_conn = MagicMock()
        connect_conn.execute.return_value.scalar.return_value = max_length_scalar
        engine.connect.return_value.__enter__ = MagicMock(return_value=connect_conn)
        engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        begin_conn = MagicMock()
        begin_conn.execute.return_value.scalar.return_value = max_length_scalar
        engine.begin.return_value.__enter__ = MagicMock(return_value=begin_conn)
        engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.data.migrations.inspect", return_value=inspector):
            apply_postgresql_heartbeat_migration(engine)

        return begin_conn, connect_conn

    # --- early-exit ---

    def test_no_rebuild_jobs_table_does_nothing(self):
        """Function must return without touching the engine when the table is absent."""
        begin_conn, connect_conn = self._run(table_names=[], columns=[])
        begin_conn.execute.assert_not_called()
        connect_conn.execute.assert_not_called()

    # --- no DDL needed ---

    def test_all_columns_present_correct_width_no_ddl(self):
        """No DDL when both columns already exist at the target width (64)."""
        cols = [
            _make_col("active_worker_id", length=64),
            _make_col("last_heartbeat_at"),
        ]
        begin_conn, connect_conn = self._run(["rebuild_jobs"], cols)
        begin_conn.execute.assert_not_called()
        connect_conn.execute.assert_not_called()

    # --- ADD COLUMN batching ---

    def test_missing_both_columns_adds_both(self):
        """When both heartbeat columns are absent, two ADD COLUMN statements are batched."""
        begin_conn, _ = self._run(["rebuild_jobs"], columns=[])
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        assert any("active_worker_id" in s for s in executed_sql)
        assert any("last_heartbeat_at" in s for s in executed_sql)
        assert begin_conn.execute.call_count == 2

    def test_missing_last_heartbeat_at_only(self):
        """Only the missing last_heartbeat_at column is added."""
        cols = [_make_col("active_worker_id", length=64)]
        begin_conn, _ = self._run(["rebuild_jobs"], cols)
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        assert any("last_heartbeat_at" in s for s in executed_sql)
        assert not any("active_worker_id" in s and "ALTER COLUMN" in s for s in executed_sql)
        assert begin_conn.execute.call_count == 1

    # --- width normalisation ---

    def test_wide_column_empty_table_normalises(self):
        """
        When active_worker_id is VARCHAR(255) and the table is empty
        (max_length=None), the ALTER COLUMN TYPE statement must be included
        in the same atomic DDL batch.
        """
        cols = [_make_col("active_worker_id", length=255), _make_col("last_heartbeat_at")]
        begin_conn, connect_conn = self._run(["rebuild_jobs"], cols, max_length_scalar=None)

        # Read-only pre-check was performed outside the transaction
        connect_conn.execute.assert_called_once()

        # ALTER COLUMN TYPE must be part of the atomic DDL batch
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        assert any("ALTER COLUMN active_worker_id TYPE VARCHAR(64)" in s for s in executed_sql)

    def test_wide_column_short_data_normalises(self):
        """
        When active_worker_id is VARCHAR(255) and the longest stored value
        is ≤ 64 chars, ALTER COLUMN TYPE must be batched with the DDL.
        """
        cols = [_make_col("active_worker_id", length=255), _make_col("last_heartbeat_at")]
        begin_conn, connect_conn = self._run(["rebuild_jobs"], cols, max_length_scalar=32)

        connect_conn.execute.assert_called_once()
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        assert any("ALTER COLUMN active_worker_id TYPE VARCHAR(64)" in s for s in executed_sql)

    def test_wide_column_long_data_skips_normalisation_and_warns(self, caplog):
        """
        When the longest stored value exceeds 64 chars, the ALTER COLUMN TYPE
        statement must NOT be batched, and a warning must be logged.
        """
        import logging

        cols = [_make_col("active_worker_id", length=255), _make_col("last_heartbeat_at")]

        with caplog.at_level(logging.WARNING, logger="src.data.migrations"):
            begin_conn, _ = self._run(["rebuild_jobs"], cols, max_length_scalar=200)

        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        assert not any("ALTER COLUMN" in s for s in executed_sql)
        assert "Skipping active_worker_id width normalization" in caplog.text
        # Warning must not include exc_info (stack trace) — per project logging convention
        assert "Traceback" not in caplog.text

    def test_wide_column_alter_runs_in_same_transaction_as_add_columns(self):
        """
        ADD COLUMN and ALTER COLUMN TYPE must execute inside the same
        engine.begin() transaction (single atomic DDL block).
        """
        # Simulate: active_worker_id is wide (255) and last_heartbeat_at is missing.
        # This triggers both the ALTER COLUMN and ADD COLUMN paths.
        cols_with_wide = [_make_col("active_worker_id", length=255)]
        begin_conn, _ = self._run(["rebuild_jobs"], cols_with_wide, max_length_scalar=10)

        # DDL statements must be batched in the same engine.begin() block
        executed_sql = [str(c.args[0]) for c in begin_conn.execute.call_args_list]
        assert any("ADD COLUMN IF NOT EXISTS last_heartbeat_at" in s for s in executed_sql)
        assert any("ALTER COLUMN active_worker_id TYPE VARCHAR(64)" in s for s in executed_sql)
