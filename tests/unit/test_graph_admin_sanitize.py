"""Unit tests for _sanitize_failure_message and related helpers in graph_admin."""

import pytest

from api.graph_lifecycle_providers import (
    GraphPersistenceNotConfiguredError,
    GraphPersistenceNonDurableError,
    GraphPersistenceSaveError,
    GraphRebuildSourceError,
)
from api.routers.graph_admin import _sanitize_failure_message  # pylint: disable=protected-access


@pytest.mark.unit
class TestSanitizeFailureMessage:
    """Tests for the _sanitize_failure_message helper."""

    def test_known_safe_exception_retains_message(self) -> None:
        """Known domain exceptions have their message text retained."""
        exc = GraphPersistenceNotConfiguredError("Graph persistence is not configured.")
        result = _sanitize_failure_message(exc)
        assert result == "Graph persistence is not configured."

    def test_known_safe_non_durable_retains_message(self) -> None:
        """GraphPersistenceNonDurableError message is retained."""
        exc = GraphPersistenceNonDurableError("Graph persistence must use a durable database.")
        result = _sanitize_failure_message(exc)
        assert result == "Graph persistence must use a durable database."

    def test_known_safe_rebuild_source_error_retains_message(self) -> None:
        """GraphRebuildSourceError message is retained."""
        exc = GraphRebuildSourceError("Failed to build rebuild graph.")
        result = _sanitize_failure_message(exc)
        assert result == "Failed to build rebuild graph."

    def test_known_safe_save_error_retains_message(self) -> None:
        """GraphPersistenceSaveError message is retained."""
        exc = GraphPersistenceSaveError("Failed to persist rebuilt graph.")
        result = _sanitize_failure_message(exc)
        assert result == "Failed to persist rebuilt graph."

    def test_unknown_exception_stores_class_name_only(self) -> None:
        """Unknown exceptions store only the class name to prevent secret leakage."""
        exc = RuntimeError("secret password=hunter2 host=db.internal")
        result = _sanitize_failure_message(exc)
        assert result == "RuntimeError"
        assert "hunter2" not in result
        assert "password" not in result

    def test_url_in_known_exception_message_is_redacted(self) -> None:
        """URL-like patterns in known domain exception messages are redacted."""
        exc = GraphPersistenceNotConfiguredError(
            "Connection refused at postgresql://admin:s3cr3t@host:5432/db"
        )
        result = _sanitize_failure_message(exc)
        assert "s3cr3t" not in result
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
        assert result == "ValueError"
        assert "P@ssw0rd" not in result

    def test_url_in_unknown_exception_not_leaked(self) -> None:
        """Unknown exceptions never leak URL patterns, even indirectly."""
        exc = ConnectionError("connect failed: sqlite:///secret_path/data.db")
        result = _sanitize_failure_message(exc)
        # Unknown exception → class name only, no URL exposure
        assert result == "ConnectionError"
        assert "secret_path" not in result
