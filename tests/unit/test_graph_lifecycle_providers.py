"""Unit tests for graph lifecycle provider persistence helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import api.graph_lifecycle_providers as providers
from src.logic.asset_graph import AssetRelationshipGraph

pytestmark = pytest.mark.unit


def test_save_graph_with_session_runs_pre_commit_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-commit check should execute before committing graph persistence."""
    session = MagicMock()
    pre_commit_check = MagicMock()
    graph = AssetRelationshipGraph()

    monkeypatch.setattr(providers.AssetGraphRepository, "save_graph", lambda self, _graph: None)

    providers._save_graph_with_session(session, graph, pre_commit_check=pre_commit_check)  # pylint: disable=protected-access

    pre_commit_check.assert_called_once_with()
    session.commit.assert_called_once_with()


def test_save_graph_with_session_rolls_back_when_pre_commit_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-commit check failure should roll back and raise GraphPersistenceSaveError."""
    session = MagicMock()
    graph = AssetRelationshipGraph()

    monkeypatch.setattr(providers.AssetGraphRepository, "save_graph", lambda self, _graph: None)

    def fail_pre_commit() -> None:
        raise RuntimeError("lost lock")

    with pytest.raises(providers.GraphPersistenceSaveError):
        providers._save_graph_with_session(session, graph, pre_commit_check=fail_pre_commit)  # pylint: disable=protected-access

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()
