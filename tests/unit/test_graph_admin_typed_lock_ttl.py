"""Contract tests for typed rebuild lock TTL access in graph admin.

Ensures Task 3.1 (#1233): graph admin uses GraphLifecycleSettings.rebuild_lock_ttl_seconds
directly without defensive getattr fallbacks or duplicate runtime validation.
"""

from __future__ import annotations

import ast
import functools
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
UTC = timezone.utc


@functools.lru_cache(maxsize=1)
def _graph_admin_module_ast() -> ast.Module:
    """Parse graph_admin source once for structural contract checks."""
    source = Path(graph_admin.__file__).read_text(encoding="utf-8")
    return ast.parse(source)


def _is_getattr_for_rebuild_lock_ttl(node: ast.AST) -> bool:
    """Return True if node is getattr(..., 'rebuild_lock_ttl_seconds', ...)."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Name) or func.id != "getattr":
        return False
    if len(node.args) < 2:
        return False
    name_arg = node.args[1]
    return isinstance(name_arg, ast.Constant) and name_arg.value == "rebuild_lock_ttl_seconds"


def _is_non_positive_lock_ttl_compare(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "lock_ttl"):
        return False
    for op, comp in zip(node.ops, node.comparators, strict=False):
        if isinstance(op, ast.LtE) and isinstance(comp, ast.Constant) and comp.value == 0:
            return True
        if isinstance(op, ast.Lt) and isinstance(comp, ast.Constant) and comp.value == 1:
            return True
    return False


def _is_lock_ttl_isinstance_check(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "isinstance"
        and bool(node.args)
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "lock_ttl"
    )


def _is_lock_ttl_runtime_guard(node: ast.AST) -> bool:
    """Return True if node re-validates or corrects lock_ttl at runtime."""
    return _is_non_positive_lock_ttl_compare(node) or _is_lock_ttl_isinstance_check(node)


def test_graph_admin_does_not_use_getattr_for_rebuild_lock_ttl() -> None:
    """Rebuild lock TTL must not use defensive getattr fallbacks."""
    for node in ast.walk(_graph_admin_module_ast()):
        if _is_getattr_for_rebuild_lock_ttl(node):
            pytest.fail(f"Found getattr fallback for rebuild_lock_ttl_seconds at line {getattr(node, 'lineno', '?')}")


def test_graph_admin_does_not_correct_lock_ttl_at_runtime() -> None:
    """Lock TTL must not be re-validated or silently corrected in graph admin."""
    for node in ast.walk(_graph_admin_module_ast()):
        if _is_lock_ttl_runtime_guard(node):
            pytest.fail(f"Found runtime lock_ttl guard at line {getattr(node, 'lineno', '?')}")


def test_perform_rebuild_uses_typed_lock_ttl_for_distributed_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify that DistributedLock receives TTL from GraphLifecycleSettings without fallback injection."""
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
        """Capture DistributedLock kwargs for TTL contract verification."""
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
        lambda *_args, **_kwargs: ("job-typed-ttl", datetime.now(UTC)),
    )

    @contextmanager
    def fake_heartbeat(*_args: object, **_kwargs: object):
        """No-op heartbeat context for isolated rebuild sync testing."""
        yield threading.Event(), threading.Event()

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
        execution_id="test_exec_id",
    )

    assert captured["ttl_seconds"] == settings.rebuild_lock_ttl_seconds
    assert captured["ttl_seconds"] == 42
    assert response.source == "sample"
