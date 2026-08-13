"""Focused tests for unambiguous GRAC runtime relationship ownership."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Literal

import pytest

from src.governance.relationship_assertion import Assertion, AssertionEvent
from src.governance.relationship_assertion_contract import (
    PredicatesDocument,
    PredicateSpec,
    ProjectionSpec,
)
from src.logic.relationship_projection import ProjectionError, ProjectionRevision, ProjectRequest, project

UTC = timezone.utc
NOW = datetime(2026, 8, 2, 6, 0, tzinfo=UTC)
PURPOSE = "financial_graph_current_view"
METHOD_ID = "test.relationship.resolution@1"


def _predicate(
    predicate_id: str,
    *,
    edge_type: str = "corporate_link",
    strength: str = "0.8",
    direction: Literal["subject_to_object", "object_to_subject", "bidirectional"] = "subject_to_object",
) -> PredicateSpec:
    """Build one test predicate with a distinct contract conflict domain."""
    return PredicateSpec(
        id=predicate_id,
        subject_type="Asset",
        object_type="Asset",
        method_ids=[METHOD_ID],
        projection=ProjectionSpec(
            edge_type=edge_type,
            strength=strength,
            direction=direction,
            purpose=PURPOSE,
        ),
        conflict_key=["subject_id", "object_id", "method_id"],
    )


def _assertion(
    assertion_id: str,
    predicate_id: str,
    *,
    subject_id: str = "BOND",
    object_id: str = "ISSUER",
) -> Assertion:
    """Build one immutable assertion eligible for the test projection window."""
    return Assertion(
        assertion_id=assertion_id,
        predicate_id=predicate_id,
        subject_id=subject_id,
        object_id=object_id,
        method_id=METHOD_ID,
        proposition="Test relationship",
        confidence_status="not_assessed",
        confidence_bp=None,
        confidence_type=None,
        confidence_method=None,
        effective_from=NOW,
        effective_to=None,
        recorded_at=NOW,
    )


def _accepted_events(assertion_id: str, *, disputed: bool = False) -> list[AssertionEvent]:
    """Build a valid Proposed→Accepted lifecycle, optionally ending Disputed."""
    events = [
        AssertionEvent(
            event_id=f"event-{assertion_id}-1",
            assertion_id=assertion_id,
            sequence=1,
            from_state=None,
            to_state="Proposed",
            authority="proposer",
            actor_id="proposer-1",
            rationale="test proposal",
            policy_version="grac.v1-policy",
            recorded_at=NOW,
        ),
        AssertionEvent(
            event_id=f"event-{assertion_id}-2",
            assertion_id=assertion_id,
            sequence=2,
            from_state="Proposed",
            to_state="Accepted",
            authority="acceptor",
            actor_id="reviewer-1",
            rationale="test acceptance",
            policy_version="grac.v1-policy",
            recorded_at=NOW + timedelta(minutes=1),
        ),
    ]
    if disputed:
        events.append(
            AssertionEvent(
                event_id=f"event-{assertion_id}-3",
                assertion_id=assertion_id,
                sequence=3,
                from_state="Accepted",
                to_state="Disputed",
                authority="disputer",
                actor_id="reviewer-2",
                rationale="test dispute",
                policy_version="grac.v1-policy",
                recorded_at=NOW + timedelta(minutes=2),
            )
        )
    return events


def _project(
    assertions: Sequence[Assertion],
    events: Sequence[AssertionEvent],
    predicates: Sequence[PredicateSpec],
) -> ProjectionRevision:
    """Project supplied test inputs at one stable bitemporal window."""
    return project(
        ProjectRequest(
            assertions=assertions,
            events=events,
            evidence=[],
            evidence_links=[],
            predicate_registry=PredicatesDocument(predicates=list(predicates)),
            purpose=PURPOSE,
            effective_at=NOW,
            known_at=NOW + timedelta(hours=1),
        )
    )


def _collision_error(
    assertions: Sequence[Assertion],
    events: Sequence[AssertionEvent],
    predicates: Sequence[PredicateSpec],
) -> str:
    """Return the fail-closed collision error for supplied projection inputs."""
    with pytest.raises(ProjectionError) as exc_info:
        _project(assertions, events, predicates)
    return str(exc_info.value)


def test_cross_predicate_runtime_collision_fails_closed_deterministically() -> None:
    """Distinct contract domains cannot claim one indistinguishable runtime edge."""
    predicates = [_predicate("predicate-a"), _predicate("predicate-b", strength="0.6")]
    assertions = [
        _assertion("assertion-a", "predicate-a"),
        _assertion("assertion-b", "predicate-b"),
    ]
    events = _accepted_events("assertion-a") + _accepted_events("assertion-b")

    forward = _collision_error(assertions, events, predicates)
    reverse = _collision_error(list(reversed(assertions)), list(reversed(events)), list(reversed(predicates)))

    assert forward == reverse
    assert "ambiguous projected runtime relationship" in forward
    assert "('BOND', 'ISSUER', 'corporate_link')" in forward
    assert "('assertion-a', 'predicate-a')" in forward
    assert "('assertion-b', 'predicate-b')" in forward


def test_same_endpoints_with_different_edge_types_remain_representable() -> None:
    """Different edge types retain distinct runtime and provenance identities."""
    predicates = [
        _predicate("predicate-a", edge_type="corporate_link"),
        _predicate("predicate-b", edge_type="legal_issuer"),
    ]
    assertions = [
        _assertion("assertion-a", "predicate-a"),
        _assertion("assertion-b", "predicate-b"),
    ]
    events = _accepted_events("assertion-a") + _accepted_events("assertion-b")

    revision = _project(assertions, events, predicates)

    assert [(edge.edge_type, edge.assertion_id) for edge in revision.edges] == [
        ("corporate_link", "assertion-a"),
        ("legal_issuer", "assertion-b"),
    ]


def test_same_edge_type_with_different_endpoints_remains_representable() -> None:
    """The same edge type may govern multiple distinct runtime relationships."""
    predicates = [_predicate("predicate-a"), _predicate("predicate-b")]
    assertions = [
        _assertion("assertion-a", "predicate-a"),
        _assertion("assertion-b", "predicate-b", subject_id="BOND-2", object_id="ISSUER-2"),
    ]
    events = _accepted_events("assertion-a") + _accepted_events("assertion-b")

    revision = _project(assertions, events, predicates)

    assert len(revision.edges) == 2


@pytest.mark.parametrize(
    ("directed_subject", "directed_object", "expected_key"),
    [
        ("BOND", "ISSUER", "('BOND', 'ISSUER', 'corporate_link')"),
        ("ISSUER", "BOND", "('ISSUER', 'BOND', 'corporate_link')"),
    ],
)
def test_bidirectional_edge_reserves_forward_and_reverse_runtime_keys(
    directed_subject: str,
    directed_object: str,
    expected_key: str,
) -> None:
    """A directed edge cannot collide with either side of a bidirectional edge."""
    predicates = [
        _predicate("predicate-bidirectional", direction="bidirectional"),
        _predicate("predicate-directed"),
    ]
    assertions = [
        _assertion("assertion-bidirectional", "predicate-bidirectional"),
        _assertion(
            "assertion-directed",
            "predicate-directed",
            subject_id=directed_subject,
            object_id=directed_object,
        ),
    ]
    events = _accepted_events("assertion-bidirectional") + _accepted_events("assertion-directed")

    error = _collision_error(assertions, events, predicates)

    assert expected_key in error


def test_inactive_colliding_assertion_does_not_block_projection() -> None:
    """Only assertions Accepted at the projection window own runtime relationships."""
    predicates = [_predicate("predicate-a"), _predicate("predicate-b")]
    assertions = [
        _assertion("assertion-a", "predicate-a"),
        _assertion("assertion-b", "predicate-b"),
    ]
    events = _accepted_events("assertion-a") + _accepted_events("assertion-b", disputed=True)

    revision = _project(assertions, events, predicates)

    assert [edge.assertion_id for edge in revision.edges] == ["assertion-a"]


def test_bidirectional_self_loop_does_not_collide_with_itself() -> None:
    """Runtime-key expansion deduplicates a bidirectional self-loop candidate."""
    predicate = _predicate("predicate-a", direction="bidirectional")
    assertion = _assertion("assertion-a", "predicate-a", subject_id="ENTITY", object_id="ENTITY")

    revision = _project([assertion], _accepted_events("assertion-a"), [predicate])

    assert [edge.assertion_id for edge in revision.edges] == ["assertion-a"]
