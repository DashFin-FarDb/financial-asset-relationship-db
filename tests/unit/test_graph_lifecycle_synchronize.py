"""Tests for graph lifecycle runtime synchronization."""

from __future__ import annotations

import sys
from typing import Iterator

import pytest  # pylint: disable=import-error

import api.graph_lifecycle as graph_lifecycle
from src.logic.asset_graph import AssetRelationshipGraph

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_lifecycle() -> Iterator[None]:
    """
    Reset the global lifecycle graph before each test and restore it after the test completes.

    Calls `graph_lifecycle.reset_graph()` prior to the test and again after the test yields to ensure a clean lifecycle state for each case.
    """
    graph_lifecycle.reset_graph()
    yield
    graph_lifecycle.reset_graph()


def test_synchronize_runtime_graph_updates_both_mirrors() -> None:
    """Synchronizing should update lifecycle state and the api.main compatibility mirror."""
    import api.main as api_main  # pylint: disable=import-outside-toplevel

    graph = AssetRelationshipGraph()

    graph_lifecycle.synchronize_runtime_graph(graph)

    assert graph_lifecycle.get_graph() is graph
    assert api_main.graph is graph


def test_synchronize_runtime_graph_no_op_when_api_main_not_loaded() -> None:
    """Synchronizing should not import api.main when it is absent from sys.modules."""
    saved_api_main = sys.modules.pop("api.main", None)
    graph = AssetRelationshipGraph()

    try:
        graph_lifecycle.synchronize_runtime_graph(graph)
    finally:
        if saved_api_main is not None:
            sys.modules["api.main"] = saved_api_main

    assert graph_lifecycle.get_graph() is graph
