"""Unit tests for typed rebuild lock TTL access in graph admin."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import api.routers.graph_admin as graph_admin
from api.api_models import GraphRebuildResponse
from api.graph_lifecycle_providers import GraphLifecycleSettings
from src.data.distributed_lock import LockLifecycleState, LockState

pytestmark = pytest.mark.unit

_GRAPH_ADMIN_SOURCE = Path(graph_admin.__file__).read_text(encoding="utf-8")


def test_graph_admin_does_not_use_getattr_for_rebuild_lock_ttl() -> None:
    """Rebuild lock TTL must not use defensive getattr fallbacks."""
    assert 'getattr(settings, "rebuild_lock_ttl_seconds"' not in _GRAPH_ADMIN_SOURCE
    assert "getattr(settings, 'rebuild_lock_ttl_seconds'" not in _GRAPH_ADMIN_SOURCE


def test_graph_admin_does_not_correct_lock_ttl_at_runtime() -> None:
    """Lock TTL must not be re-validated or silently corrected in graph admin."""
    assert "if lock_ttl <= 0" not in _GRAPH_ADMIN_SOURCE
    assert "if not isinstance(lock_ttl" not in _GRAPH_ADMIN_SOURCE


def test_perform_rebuild_uses_typed_lock_ttl_for_distributed_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DistributedLock must receive TTL from GraphLifecycleSettings without fallback injection."""
    db_url = f"sqlite:///{tmp_path / 'graph.db'}"
    settings = GraphLifecycleSettings(
        asset_graph_database_url=db_url,
        coordination_database_url=db_url,
        rebuild_lock_ttl_seconds=42,
    )
    captured: dict[str, object] = {}

    mock_lock = MagicMock()
    mock_lock.acquire.return_value = MagicMock()
    mock_lock.check_state.return_value = LockState.VALID
    mock_lock.holder_id = "test-holder"
    mock_lock.state = LockLifecycleState.ACQUIRED

    def distributed_lock_factory(**kwargs: object) -> MagicMock:
        captured["ttl_seconds"] = kwargs.get("ttl_seconds")
        return mock_lock

    monkeypatch.setattr(graph_admin, "DistributedLock", distributed_lock_factory)
    monkeypatch.setattr(
        graph_admin.RecoveryGate,
        "ensure_safe_to_execute",
        lambda self: None,
    )
    monkeypatch.setattr(
        graph_admin,
        "_create_and_start_rebuild_job",
        lambda *_args, **_kwargs: ("job-typed-ttl", datetime.now(timezone.utc)),
    )

    @contextmanager
    def fake_heartbeat(*_args: object, **_kwargs: object):
        yield threading.Event()

    monkeypatch.setattr(graph_admin, "_orchestrate_heartbeat", fake_heartbeat)
    monkeypatch.setattr(
        graph_admin,
        "_run_rebuild_pipeline",
        lambda *_args, **_kwargs: GraphRebuildResponse(
            source="sample",
            asset_count=0,
            relationship_count=0,
            regulatory_event_count=0,
        ),
    )

    response = graph_admin._perform_rebuild_and_persist_sync(  # pylint: disable=protected-access
        settings,
        user_ref="operator",
    )

    assert captured["ttl_seconds"] == settings.rebuild_lock_ttl_seconds
    assert captured["ttl_seconds"] == 42
    assert response.source == "sample"
