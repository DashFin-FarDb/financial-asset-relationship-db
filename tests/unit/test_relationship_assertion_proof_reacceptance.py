"""Regression tests for GRAC staging-proof historical reconstruction."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scripts.check_relationship_assertion_proof import ProofValidator


def _event(
    sequence: int,
    from_state: str | None,
    to_state: str,
    authority: str,
    actor_id: str,
) -> Any:
    """Build the lifecycle fields consumed by the proof validator."""
    return SimpleNamespace(
        sequence=sequence,
        from_state=from_state,
        to_state=to_state,
        authority=authority,
        actor_id=actor_id,
    )


def test_reconstructed_assertion_allows_reacceptance_after_dispute() -> None:
    """A legal Accepted -> Disputed -> Accepted cycle must not look like duplicate initial acceptance."""
    validator = ProofValidator({})
    events = [
        _event(1, None, "Proposed", "proposer", "proposer-1"),
        _event(2, "Proposed", "Accepted", "acceptor", "acceptor-1"),
        _event(3, "Accepted", "Disputed", "disputer", "acceptor-1"),
        _event(4, "Disputed", "Accepted", "acceptor", "acceptor-1"),
    ]

    assert validator._validate_reconstructed_assertion("assertion-1", events) is True
    assert validator.errors == []


def test_reconstructed_assertion_rejects_duplicate_initial_acceptance() -> None:
    """Cardinality remains fail-closed for two Proposed -> Accepted determinations."""
    validator = ProofValidator({})
    events = [
        _event(1, None, "Proposed", "proposer", "proposer-1"),
        _event(2, "Proposed", "Accepted", "acceptor", "acceptor-1"),
        _event(3, "Proposed", "Accepted", "acceptor", "acceptor-2"),
    ]

    assert validator._validate_reconstructed_assertion("assertion-1", events) is False
    assert validator.errors == [
        "Assertion assertion-1 must have exactly one proposer and one initial acceptance event"
    ]
