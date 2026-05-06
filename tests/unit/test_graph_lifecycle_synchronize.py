"""Tests for graph lifecycle runtime synchronization."""

from __future__ import annotations

import sys
from typing import Iterator, cast  # noqa: UP035

import pytest  # pylint: disable=import-error

import api.graph_lifecycle as graph_lifecycle

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_lifecycle() -> Iterator[None]:
    """Reset lifecycle graph state around each test."""
    graph_lifecycle.reset_graph()
    yield
    graph_lifecycle.reset_graph()


def test_synchronize_runtime_graph_updates_both_mirrors() -> None:
    """Runtime sync should update lifecycle state and api.main mirror."""
    import api.main as api_main  # pylint: disable=import-outside-toplevel

    graph_instance = cast(
        graph_lifecycle.AssetRelationshipGraph,
        object(),
    )

    graph_lifecycle.synchronize_runtime_graph(graph_instance)

    assert graph_lifecycle.graph_state.graph is graph_instance
    assert api_main.graph is graph_instance


def test_synchronize_runtime_graph_no_op_when_api_main_not_loaded() -> None:
    """Synchronizing should not import api.main when it is absent."""
    saved_api_main = sys.modules.pop("api.main", None)
    graph_instance = cast(
        graph_lifecycle.AssetRelationshipGraph,
        object(),
    )

    try:
        graph_lifecycle.synchronize_runtime_graph(graph_instance)
    finally:
        if saved_api_main is not None:
            sys.modules["api.main"] = saved_api_main

    assert graph_lifecycle.graph_state.graph is graph_instance
