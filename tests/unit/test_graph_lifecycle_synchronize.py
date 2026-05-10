"""Tests for graph lifecycle runtime synchronization."""

from __future__ import annotations

import sys
from typing import cast

import pytest  # pylint: disable=import-error

import api.graph_lifecycle as graph_lifecycle

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_lifecycle():
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


def test_synchronize_runtime_graph_preserves_rebuild_until_completion() -> None:
    """Runtime sync during rebuild should not complete the rebuild lifecycle."""
    graph_instance = cast(
        graph_lifecycle.AssetRelationshipGraph,
        object(),
    )

    graph_lifecycle.begin_rebuild()
    graph_lifecycle.synchronize_runtime_graph(graph_instance)

    assert graph_lifecycle.graph_state.graph is graph_instance
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.REBUILDING

    graph_lifecycle.complete_rebuild(succeeded=True)
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.READY


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


def test_lifecycle_state_is_uninitialized_after_reset() -> None:
    """Reset lifecycle should return runtime state to UNINITIALIZED."""
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.UNINITIALIZED


@pytest.mark.parametrize(
    ("transitions", "next_state"),
    [
        (
            [],
            graph_lifecycle.GraphRuntimeLifecycleState.READY,
        ),
        (
            [
                graph_lifecycle.GraphRuntimeLifecycleState.INITIALIZING,
                graph_lifecycle.GraphRuntimeLifecycleState.READY,
            ],
            graph_lifecycle.GraphRuntimeLifecycleState.INITIALIZING,
        ),
        (
            [
                graph_lifecycle.GraphRuntimeLifecycleState.INITIALIZING,
                graph_lifecycle.GraphRuntimeLifecycleState.FAILED,
            ],
            graph_lifecycle.GraphRuntimeLifecycleState.READY,
        ),
        (
            # STOPPED is terminal for normal operations; only STOPPED→UNINITIALIZED is
            # permitted for explicit reset/restart paths. Direct advance to READY must be rejected.
            [
                graph_lifecycle.GraphRuntimeLifecycleState.INITIALIZING,
                graph_lifecycle.GraphRuntimeLifecycleState.READY,
                graph_lifecycle.GraphRuntimeLifecycleState.SHUTTING_DOWN,
                graph_lifecycle.GraphRuntimeLifecycleState.STOPPED,
            ],
            graph_lifecycle.GraphRuntimeLifecycleState.READY,
        ),
    ],
)
def test_lifecycle_rejects_invalid_transition(
    transitions: list[graph_lifecycle.GraphRuntimeLifecycleState],
    next_state: graph_lifecycle.GraphRuntimeLifecycleState,
) -> None:
    """Direct invalid lifecycle transitions should fail predictably."""
    for state in transitions:
        graph_lifecycle.transition_runtime_lifecycle_state(state)

    initial_state = graph_lifecycle.get_runtime_lifecycle_state()
    expected_message = f"Invalid graph runtime lifecycle transition: {initial_state.value} -> {next_state.value}"
    with pytest.raises(RuntimeError, match=expected_message):
        graph_lifecycle.transition_runtime_lifecycle_state(next_state)
    assert graph_lifecycle.get_runtime_lifecycle_state() == initial_state


def test_rebuild_transition_semantics() -> None:
    """Rebuild transitions should move through REBUILDING then READY or FAILED."""
    graph_lifecycle.begin_rebuild()
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.REBUILDING

    graph_lifecycle.complete_rebuild(succeeded=True)
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.READY

    graph_lifecycle.begin_rebuild()
    graph_lifecycle.complete_rebuild(succeeded=False)
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.FAILED


def test_shutdown_transition_semantics() -> None:
    """Shutdown must progress through SHUTTING_DOWN and reach STOPPED as the terminal state."""
    graph_lifecycle.begin_rebuild()
    graph_lifecycle.complete_rebuild(succeeded=True)

    graph_lifecycle.begin_shutdown()
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.STOPPED


def test_stopped_state_is_terminal_for_direct_advance() -> None:
    """STOPPED must reject direct transitions to operational states."""
    graph_lifecycle.begin_shutdown()
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.STOPPED

    expected = "Invalid graph runtime lifecycle transition: STOPPED -> READY"
    with pytest.raises(RuntimeError, match=expected):
        graph_lifecycle.transition_runtime_lifecycle_state(graph_lifecycle.GraphRuntimeLifecycleState.READY)

    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.STOPPED


def test_stopped_state_allows_reset_to_uninitialized() -> None:
    """STOPPED must permit an explicit reset to UNINITIALIZED for restart/test-isolation paths."""
    graph_lifecycle.begin_shutdown()
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.STOPPED

    graph_lifecycle.transition_runtime_lifecycle_state(graph_lifecycle.GraphRuntimeLifecycleState.UNINITIALIZED)
    assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.UNINITIALIZED
