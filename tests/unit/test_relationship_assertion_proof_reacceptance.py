"""Regression tests for GRAC staging-proof historical reconstruction."""

from __future__ import annotations

from types import SimpleNamespace

from scripts.check_relationship_assertion_proof import ProofValidator


def _event(
    sequence: int,
    transition: tuple[str | None, str],
    authority: str,
    actor_id: str,
) -> SimpleNamespace:
    """Build the lifecycle fields consumed by the proof validator."""
    from_state, to_state = transition
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
        _event(1, (None, "Proposed"), "proposer", "proposer-1"),
        _event(2, ("Proposed", "Accepted"), "acceptor", "acceptor-1"),
        _event(3, ("Accepted", "Disputed"), "disputer", "acceptor-1"),
        _event(4, ("Disputed", "Accepted"), "acceptor", "acceptor-1"),
    ]

    assert validator._validate_reconstructed_assertion("assertion-1", events) is True
    assert validator.errors == []


def test_reconstructed_assertion_rejects_duplicate_initial_acceptance() -> None:
    """Cardinality remains fail-closed for two Proposed -> Accepted determinations."""
    validator = ProofValidator({})
    events = [
        _event(1, (None, "Proposed"), "proposer", "proposer-1"),
        _event(2, ("Proposed", "Accepted"), "acceptor", "acceptor-1"),
        _event(3, ("Proposed", "Accepted"), "acceptor", "acceptor-2"),
    ]

    assert validator._validate_reconstructed_assertion("assertion-1", events) is False
    assert validator.errors == ["Assertion assertion-1 must have exactly one proposer and one initial acceptance event"]


def test_reconstructed_assertion_rejects_illegal_transition_into_accepted() -> None:
    """Only Proposed or Disputed may transition into Accepted during reconstruction."""
    validator = ProofValidator({})
    events = [
        _event(1, (None, "Proposed"), "proposer", "proposer-1"),
        _event(2, ("Proposed", "Accepted"), "acceptor", "acceptor-1"),
        _event(3, ("Accepted", "Accepted"), "acceptor", "acceptor-1"),
    ]

    assert validator._validate_reconstructed_assertion("assertion-1", events) is False
    assert validator.errors == ["Assertion assertion-1 has invalid transition into Accepted"]


def test_reconstructed_assertion_rejects_proposer_reacceptance() -> None:
    """Reacceptance keeps the proposer/acceptor separation-of-duties boundary."""
    validator = ProofValidator({})
    events = [
        _event(1, (None, "Proposed"), "proposer", "proposer-1"),
        _event(2, ("Proposed", "Accepted"), "acceptor", "acceptor-1"),
        _event(3, ("Accepted", "Disputed"), "disputer", "acceptor-1"),
        _event(4, ("Disputed", "Accepted"), "acceptor", "proposer-1"),
    ]

    assert validator._validate_reconstructed_assertion("assertion-1", events) is False
    assert validator.errors == ["Assertion assertion-1 reacceptance actor is missing or not distinct from proposer"]


def test_reconstructed_assertion_rejects_discontinuous_reacceptance_chain() -> None:
    """A claimed reacceptance must follow a persisted event that actually entered Disputed."""
    validator = ProofValidator({})
    events = [
        _event(1, (None, "Proposed"), "proposer", "proposer-1"),
        _event(2, ("Proposed", "Accepted"), "acceptor", "acceptor-1"),
        _event(3, ("Accepted", "Withdrawn"), "withdrawer", "acceptor-1"),
        _event(4, ("Disputed", "Accepted"), "acceptor", "acceptor-1"),
    ]

    assert validator._validate_reconstructed_assertion("assertion-1", events) is False
    assert validator.errors == ["Assertion assertion-1 lifecycle state chain is discontinuous"]


def test_reconstructed_assertion_rejects_reacceptance_without_dispute_event() -> None:
    """A Disputed -> Accepted event cannot appear unless the preceding event entered Disputed."""
    validator = ProofValidator({})
    events = [
        _event(1, (None, "Proposed"), "proposer", "proposer-1"),
        _event(2, ("Proposed", "Accepted"), "acceptor", "acceptor-1"),
        _event(3, ("Disputed", "Accepted"), "acceptor", "acceptor-1"),
    ]

    assert validator._validate_reconstructed_assertion("assertion-1", events) is False
    assert validator.errors == ["Assertion assertion-1 lifecycle state chain is discontinuous"]
