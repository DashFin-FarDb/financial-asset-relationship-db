"""Unit tests for _sanitize_failure_message and related helpers in graph_admin."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from api.graph_lifecycle_providers import (
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    GraphPersistenceSaveError,
    GraphRebuildSourceError,
)
from api.routers.graph_admin import (
    _sanitize_failure_message,  # pylint: disable=protected-access
    _validate_coordination_database_primary,
)


@pytest.mark.unit
class TestSanitizeFailureMessage:
    """Tests for the _sanitize_failure_message helper."""

    def test_known_safe_exception_retains_message(self) -> None:
        """Known domain exceptions have their message text retained."""
        exc = GraphPersistenceNotConfiguredError("Graph persistence is not configured.")
        result = _sanitize_failure_message(exc)
        assert result == "Graph persistence is not configured."

    def test_known_safe_non_durable_retains_message(self) -> None:
        """Verify that GraphPersistenceNonDurableError message is retained."""
        exc = GraphPersistenceNonDurableError("Graph persistence must use a durable database.")
        result = _sanitize_failure_message(exc)
        assert result == "Graph persistence must use a durable database."

    def test_known_safe_rebuild_source_error_retains_message(self) -> None:
        """Verify that GraphRebuildSourceError message is retained."""
        exc = GraphRebuildSourceError("Failed to build rebuild graph.")
        result = _sanitize_failure_message(exc)
        assert result == "Failed to build rebuild graph."

    def test_known_safe_save_error_retains_message(self) -> None:
        """Verify that GraphPersistenceSaveError message is retained."""
        exc = GraphPersistenceSaveError("Failed to persist rebuilt graph.")
        result = _sanitize_failure_message(exc)
        assert result == "Failed to persist rebuilt graph."

    def test_unknown_exception_stores_class_name_only(self) -> None:
        """Unknown exceptions store only the class name to prevent secret leakage."""
        exc = RuntimeError("secret password=hunter2 host=db.internal")
        result = _sanitize_failure_message(exc)
        assert result == "InternalError[RuntimeError]"
        assert "hunter2" not in result
        assert "password" not in result

    def test_url_in_known_exception_message_is_redacted(self) -> None:
        """URL-like patterns in known domain exception messages are redacted."""
        exc = GraphPersistenceNotConfiguredError("Connection refused at postgresql://admin:s3cr3t@host:5432/db")
        result = _sanitize_failure_message(exc)
        assert "s3cr3t" not in result
        assert "[REDACTED_URL]" in result

    def test_uncommon_sqlalchemy_dialect_prefix_is_redacted(self) -> None:
        """Verify that SQLAlchemy dialect+driver DSNs are redacted."""
        exc = GraphPersistenceSaveError(
            "Persist failed for postgresql+asyncpg://admin:s3cr3t@example.invalid/asset_graph"
        )
        result = _sanitize_failure_message(exc)
        assert "s3cr3t" not in result
        assert "postgresql+asyncpg://" not in result
        assert "[REDACTED_URL]" in result

    def test_malformed_dsn_with_credentials_is_redacted(self) -> None:
        """Malformed DSN credential segments are still redacted."""
        exc = GraphPersistenceSaveError("Persist failed for postgresql:admin:s3cr3t@example.invalid/asset_graph")
        result = _sanitize_failure_message(exc)
        assert "s3cr3t" not in result
        assert "admin:" not in result
        assert "[REDACTED_URL]" in result

    def test_bare_dsn_with_credentials_is_redacted(self) -> None:
        """Bare DSN credentials (username:password@host) in known exceptions are redacted."""
        exc = GraphPersistenceSaveError("Persist failed for admin:s3cr3t@example.invalid/asset_graph")
        result = _sanitize_failure_message(exc)
        assert "s3cr3t" not in result
        assert "admin" not in result
        assert "[REDACTED_URL]" in result

    def test_sanitization_edge_cases(self) -> None:
        """Verify URL and credential redaction handles query strings, usernames with dots, and standard formats."""
        # 1. URL with query string
        exc1 = GraphPersistenceNotConfiguredError(
            "postgresql://admin:s3cr3t@host:5432/db?sslmode=require&target_session_attrs=read-write"
        )
        result = _sanitize_failure_message(exc1)
        assert "s3cr3t" not in result
        assert "[REDACTED_URL]" in result

        # 2. Username containing dot
        exc2 = GraphPersistenceSaveError("Failed connecting for first.last:s3cr3t@host:5432")
        result = _sanitize_failure_message(exc2)
        assert "s3cr3t" not in result
        assert "first.last" not in result
        assert "[REDACTED_URL]" in result

        # 3. Standard user:pass@host case
        exc3 = GraphPersistenceSaveError("Refused credentials for user:pass@host")
        result = _sanitize_failure_message(exc3)
        assert "pass" not in result
        assert "user" not in result
        assert "[REDACTED_URL]" in result

    def test_empty_message_falls_back_to_class_name(self) -> None:
        """An empty message on a known exception falls back to the class name."""
        exc = GraphPersistenceNotConfiguredError("")
        result = _sanitize_failure_message(exc)
        assert result == "GraphPersistenceNotConfiguredError"

    def test_message_truncated_to_512_chars(self) -> None:
        """Returned message is bounded to 512 characters."""
        long_message = "x" * 600
        exc = GraphPersistenceNotConfiguredError(long_message)
        result = _sanitize_failure_message(exc)
        assert len(result) <= 512

    def test_value_error_stores_class_name_only(self) -> None:
        """Generic ValueError is treated as unknown — only class name stored."""
        exc = ValueError("driver auth failed: user=sa password=P@ssw0rd")
        result = _sanitize_failure_message(exc)
        assert result == "InternalError[ValueError]"
        assert "P@ssw0rd" not in result

    def test_url_in_unknown_exception_not_leaked(self) -> None:
        """Unknown exceptions never leak URL patterns, even indirectly."""
        exc = ConnectionError("connect failed: sqlite:///secret_path/data.db")
        result = _sanitize_failure_message(exc)
        # Unknown exception → class name only, no URL exposure
        assert result == "InternalError[ConnectionError]"
        assert "secret_path" not in result


@pytest.mark.unit
class TestValidateCoordinationDatabasePrimary:
    """Tests for _validate_coordination_database_primary."""

    def test_sqlite_dialect_is_noop(self) -> None:
        """Verify that SQLite (or other non-Postgres) dialect exits cleanly without execute."""
        mock_bind = MagicMock()
        mock_bind.dialect.name = "sqlite"

        mock_session = MagicMock()
        mock_session.get_bind.return_value = mock_bind

        def fake_session_factory():
            """Return a mock session for testing."""
            return mock_session

        # Should execute successfully as a no-op without calling session.execute
        _validate_coordination_database_primary(fake_session_factory)
        mock_session.execute.assert_not_called()

    def test_postgres_primary_succeeds(self) -> None:
        """Verify that a PostgreSQL primary (pg_is_in_recovery = False) passes validation."""
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"

        mock_result = MagicMock()
        mock_result.scalar.return_value = False

        mock_session = MagicMock()
        mock_session.get_bind.return_value = mock_bind
        mock_session.execute.return_value = mock_result

        def fake_session_factory():
            """Return a mock session for testing postgres primary logic."""
            return mock_session

        _validate_coordination_database_primary(fake_session_factory)
        mock_session.execute.assert_called_once()

    def test_postgres_replica_raises_runtime_error_directly(self) -> None:
        """Verify that a PostgreSQL replica (pg_is_in_recovery = True) propagates RuntimeError directly."""
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"

        mock_result = MagicMock()
        mock_result.scalar.return_value = True

        mock_session = MagicMock()
        mock_session.get_bind.return_value = mock_bind
        mock_session.execute.return_value = mock_result

        def fake_session_factory():
            """Return a mock session for testing postgres replica logic."""
            return mock_session

        with pytest.raises(RuntimeError) as exc_info:
            _validate_coordination_database_primary(fake_session_factory)

        assert "read replica; coordination_database_url must point to the primary" in str(exc_info.value)

    def test_sqlalchemy_error_raises_wrapped_runtime_error(self) -> None:
        """Verify that a SQLAlchemyError is wrapped and chain-raised."""
        mock_session = MagicMock()
        mock_session.get_bind.side_effect = SQLAlchemyError("DB connection failed")

        def fake_session_factory():
            """Return a mock session for testing SQLAlchemyError propagation."""
            return mock_session

        with pytest.raises(RuntimeError) as exc_info:
            _validate_coordination_database_primary(fake_session_factory)

        assert "Could not verify coordination database role" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, SQLAlchemyError)

    def test_unexpected_exception_raises_wrapped_runtime_error(self) -> None:
        """Verify that any other unexpected exception is wrapped and chain-raised."""
        mock_session = MagicMock()
        mock_session.get_bind.side_effect = ValueError("Unexpected internal error")

        def fake_session_factory():
            """Return a mock session for testing unexpected exception wrapping."""
            return mock_session

        with pytest.raises(RuntimeError) as exc_info:
            _validate_coordination_database_primary(fake_session_factory)

        assert "Could not verify coordination database role" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, ValueError)
