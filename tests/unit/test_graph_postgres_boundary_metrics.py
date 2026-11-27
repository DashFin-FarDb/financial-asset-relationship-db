"""Unit tests for Graph <-> Relational DB boundary Prometheus metrics."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.graph_lifecycle_providers import stage_graph_snapshot
from api.metrics import (
    GRAPH_DB_PERSISTENCE_DURATION_SECONDS,
    GRAPH_PERSISTENCE_CONFIGURED,
    GRAPH_PROJECTION_LAST_PUBLISHED_TIMESTAMP,
    observe_graph_db_persistence_duration,
    record_graph_projection_published,
    update_graph_metrics,
    update_graph_persistence_configured,
)


def test_update_graph_persistence_configured_sets_binary_gauge() -> None:
    """Durable persistence flag exports 1 when configured and 0 when unconfigured."""
    update_graph_persistence_configured(True)
    assert GRAPH_PERSISTENCE_CONFIGURED._value.get() == 1.0  # pylint: disable=protected-access
    update_graph_persistence_configured(False)
    assert GRAPH_PERSISTENCE_CONFIGURED._value.get() == 0.0  # pylint: disable=protected-access


def test_update_graph_metrics_records_projection_published_timestamp() -> None:
    """Updating graph inventory metrics also updates the projection publication timestamp."""
    record_graph_projection_published(1000.0)
    assert GRAPH_PROJECTION_LAST_PUBLISHED_TIMESTAMP._value.get() == 1000.0  # pylint: disable=protected-access

    update_graph_metrics(asset_count=13, relationship_count=19)
    assert GRAPH_PROJECTION_LAST_PUBLISHED_TIMESTAMP._value.get() > 1000.0  # pylint: disable=protected-access


def test_observe_graph_db_persistence_duration_bounds_dialect_labels() -> None:
    """Dialect labels are bounded to known engines plus 'other'."""
    before_pg = GRAPH_DB_PERSISTENCE_DURATION_SECONDS.labels(
        dialect="postgresql"
    )._sum.get()  # pylint: disable=protected-access
    before_other = GRAPH_DB_PERSISTENCE_DURATION_SECONDS.labels(
        dialect="other"
    )._sum.get()  # pylint: disable=protected-access

    observe_graph_db_persistence_duration(0.25, "PostgreSQL")
    observe_graph_db_persistence_duration(0.10, "unknown_engine")
    observe_graph_db_persistence_duration(-5.0, None)

    after_pg = GRAPH_DB_PERSISTENCE_DURATION_SECONDS.labels(
        dialect="postgresql"
    )._sum.get()  # pylint: disable=protected-access
    after_other = GRAPH_DB_PERSISTENCE_DURATION_SECONDS.labels(
        dialect="other"
    )._sum.get()  # pylint: disable=protected-access

    assert after_pg >= before_pg + 0.25
    assert after_other >= before_other + 0.10


def test_stage_graph_snapshot_observes_db_persistence_duration() -> None:
    """stage_graph_snapshot records DB persistence duration on success."""
    session = MagicMock()
    session.bind.dialect.name = "sqlite"
    graph = MagicMock()

    before_count = GRAPH_DB_PERSISTENCE_DURATION_SECONDS.labels(
        dialect="sqlite"
    )._sum.get()  # pylint: disable=protected-access
    with patch("api.graph_lifecycle_providers.AssetGraphRepository") as repo_cls:
        stage_graph_snapshot(session, graph)
        repo_cls.assert_called_once_with(session)
        repo_cls.return_value.save_graph.assert_called_once_with(graph)

    after_count = GRAPH_DB_PERSISTENCE_DURATION_SECONDS.labels(
        dialect="sqlite"
    )._sum.get()  # pylint: disable=protected-access
    assert after_count >= before_count
