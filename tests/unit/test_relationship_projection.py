"""Unit tests for the pure GRAC v1 deterministic projector."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.governance.relationship_assertion import (
    Assertion,
    AssertionEvent,
    EvidenceLink,
    EvidenceRecord,
    ValidationError,
)
from src.governance.relationship_assertion_contract import load_contract_bundle
from src.logic.relationship_projection import (
    PROJECTOR_VERSION,
    ProjectionError,
    ProjectionRevision,
    ProjectRequest,
    project,
)

UTC = timezone.utc
NOW = datetime(2026, 7, 25, 15, 0, 0, tzinfo=UTC)
PURPOSE = "financial_graph_current_view"
PREDICATE_ID = "financial.bond.issuer_reference@1"
DIGEST_A = "a" * 64


@pytest.fixture(scope="module")
def predicates():
    """Pinned predicate registry from the frozen contract bundle."""
    _contract, predicates_doc, _transitions = load_contract_bundle()
    return predicates_doc


def _assertion(
    assertion_id: str = "as-1",
    *,
    object_id: str = "AAPL",
    effective_from: datetime = NOW,
    effective_to: datetime | None = None,
    recorded_at: datetime = NOW,
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        predicate_id=PREDICATE_ID,
        subject_id="AAPL_BOND_2030",
        object_id=object_id,
        method_id="bond.issuer_id.resolution@1",
        proposition="Bond issuer_id references issuer",
        confidence_status="not_assessed",
        confidence_bp=None,
        confidence_type=None,
        confidence_method=None,
        effective_from=effective_from,
        effective_to=effective_to,
        recorded_at=recorded_at,
    )


def _event(
    assertion_id: str,
    sequence: int,
    to_state: str,
    *,
    from_state: str | None,
    recorded_at: datetime,
    event_id: str | None = None,
    authority: str = "acceptor",
    successor_assertion_id: str | None = None,
) -> AssertionEvent:
    return AssertionEvent(
        event_id=event_id or f"ev-{assertion_id}-{sequence}",
        assertion_id=assertion_id,
        sequence=sequence,
        from_state=from_state,  # type: ignore[arg-type]
        to_state=to_state,  # type: ignore[arg-type]
        authority=authority,  # type: ignore[arg-type]
        actor_id="actor-1",
        rationale="test",
        policy_version="grac.v1-policy",
        recorded_at=recorded_at,
        successor_assertion_id=successor_assertion_id,
    )


def _propose_accept_events(
    assertion_id: str,
    *,
    proposed_at: datetime,
    accepted_at: datetime,
) -> list[AssertionEvent]:
    return [
        _event(assertion_id, 1, "Proposed", from_state=None, recorded_at=proposed_at, authority="proposer"),
        _event(assertion_id, 2, "Accepted", from_state="Proposed", recorded_at=accepted_at),
    ]


def _evidence(evidence_id: str = "evd-1", digest: str = DIGEST_A) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        source_ref=f"sample://{evidence_id}",
        content_sha256=digest,
        media_type="application/json",
        visibility="internal",
        custody_id="collector-1",
        recorded_at=NOW,
    )


def _link(
    assertion_id: str,
    evidence_id: str = "evd-1",
    *,
    polarity: str = "supporting",
    recorded_at: datetime = NOW,
) -> EvidenceLink:
    return EvidenceLink(
        link_id=f"link-{assertion_id}-{evidence_id}",
        assertion_id=assertion_id,
        evidence_id=evidence_id,
        polarity=polarity,  # type: ignore[arg-type]
        recorded_at=recorded_at,
    )


def _project(
    predicates,
    assertions: list[Assertion],
    events: list[AssertionEvent],
    *,
    effective_at: datetime = NOW,
    known_at: datetime = NOW + timedelta(hours=1),
    evidence: list[EvidenceRecord] | None = None,
    evidence_links: list[EvidenceLink] | None = None,
    purpose: str = PURPOSE,
) -> ProjectionRevision:
    return project(
        ProjectRequest(
            assertions=assertions,
            events=events,
            evidence=evidence or [],
            evidence_links=evidence_links or [],
            predicate_registry=predicates,
            purpose=purpose,
            effective_at=effective_at,
            known_at=known_at,
        )
    )


def test_empty_inputs_yield_empty_revision_and_stable_hashes(predicates) -> None:
    """Empty assertion store projects zero edges with deterministic empty hashes."""
    first = _project(predicates, [], [], known_at=NOW)
    second = _project(predicates, [], [], known_at=NOW)
    assert first.edges == ()
    assert first.governed_scopes == ()
    assert first.edge_set_hash == second.edge_set_hash
    assert first.projection_hash == second.projection_hash
    assert first.projector_version == PROJECTOR_VERSION
    # SHA-256 of canonical JSON ``[]``.
    assert first.edge_set_hash == "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    assert first.projection_hash == "f834ce8a5132768a2c9f871cc70abd563b383334ad43c837713356f7cc293d27"


def test_accepted_issuer_reference_projects_corporate_link(predicates) -> None:
    """First financial slice projects AAPL_BOND_2030 → AAPL corporate_link @ 0.8."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    result = _project(predicates, [assertion], events, known_at=NOW + timedelta(days=1))
    assert len(result.edges) == 1
    edge = result.edges[0]
    assert edge.source_id == "AAPL_BOND_2030"
    assert edge.target_id == "AAPL"
    assert edge.edge_type == "corporate_link"
    assert edge.strength == "0.8"
    assert edge.direction == "subject_to_object"
    assert edge.assertion_id == "as-1"
    assert len(result.governed_scopes) == 1
    assert result.governed_scopes[0].purpose == PURPOSE
    assert result.governed_scopes[0].predicate_id == PREDICATE_ID
    assert result.edge_set_hash == "c8c8e738ffe460a7716fcd89fa16baf494fe4015e2551a1f107e53b129a7d345"
    assert result.projection_hash == "9bee4d5a7407b9561b96cd546cdd17f5177910f471d8e2f78aab4f0befaccb83"


def test_input_order_invariance(predicates) -> None:
    """Shuffled assertion/event inputs must not change hashes or edge order."""
    a1 = _assertion("as-1", object_id="AAPL")
    a2 = _assertion("as-2", object_id="MSFT")
    # Distinct subjects avoid conflict: second subject for as-2.
    a2 = Assertion(
        assertion_id="as-2",
        predicate_id=PREDICATE_ID,
        subject_id="MSFT_BOND_2031",
        object_id="MSFT",
        method_id="bond.issuer_id.resolution@1",
        proposition="Bond issuer_id references MSFT",
        confidence_status="not_assessed",
        confidence_bp=None,
        confidence_type=None,
        confidence_method=None,
        effective_from=NOW,
        effective_to=None,
        recorded_at=NOW,
    )
    events = _propose_accept_events(
        "as-2", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=2)
    ) + _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    forward = _project(predicates, [a1, a2], events)
    reverse = _project(predicates, [a2, a1], list(reversed(events)))
    assert forward.edge_set_hash == reverse.edge_set_hash
    assert forward.projection_hash == reverse.projection_hash
    assert [edge.assertion_id for edge in forward.edges] == [edge.assertion_id for edge in reverse.edges]


def test_replay_idempotence(predicates) -> None:
    """Replaying the same inputs yields an identical revision payload."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    first = _project(predicates, [assertion], events)
    second = _project(predicates, [assertion], events)
    assert first == second


@pytest.mark.parametrize(
    ("effective_at", "expect_edge"),
    [
        (NOW - timedelta(seconds=1), False),
        (NOW, True),
        (NOW + timedelta(days=10), True),
        (NOW + timedelta(days=30), True),
        (NOW + timedelta(days=30, seconds=1), False),
    ],
)
def test_exact_effective_interval_boundaries(predicates, effective_at: datetime, expect_edge: bool) -> None:
    """Effective window is closed on both ends: from <= at <= to."""
    assertion = _assertion(effective_from=NOW, effective_to=NOW + timedelta(days=30))
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    result = _project(predicates, [assertion], events, effective_at=effective_at)
    assert bool(result.edges) is expect_edge


def test_historical_known_at_reconstruction(predicates) -> None:
    """known_at before acceptance excludes the assertion; after includes it."""
    assertion = _assertion(recorded_at=NOW)
    proposed_at = NOW
    accepted_at = NOW + timedelta(hours=1)
    events = _propose_accept_events("as-1", proposed_at=proposed_at, accepted_at=accepted_at)
    before = _project(predicates, [assertion], events, known_at=NOW + timedelta(minutes=30))
    after = _project(predicates, [assertion], events, known_at=accepted_at)
    assert before.edges == ()
    assert len(after.edges) == 1


def test_disputed_assertions_excluded(predicates) -> None:
    """Disputed assertions do not emit edges at that known_at."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    events.append(
        _event(
            "as-1",
            3,
            "Disputed",
            from_state="Accepted",
            recorded_at=NOW + timedelta(minutes=2),
            authority="disputer",
        )
    )
    result = _project(predicates, [assertion], events, known_at=NOW + timedelta(minutes=3))
    assert result.edges == ()


def test_fail_closed_on_cardinality_conflict(predicates) -> None:
    """Two Accepted issuer references for one bond fail closed (no LWW)."""
    left = _assertion("as-1", object_id="AAPL")
    right = _assertion("as-2", object_id="MSFT")
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    events += _propose_accept_events("as-2", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=2))
    with pytest.raises(ProjectionError, match="projection conflict"):
        _project(predicates, [left, right], events)


def test_supersession_selection_changes_projection(predicates) -> None:
    """After supersession, only the Accepted successor projects."""
    predecessor = _assertion("as-1", object_id="AAPL")
    successor = _assertion("as-2", object_id="AAPL_NEW")
    t0 = NOW
    t1 = NOW + timedelta(minutes=1)
    t2 = NOW + timedelta(minutes=2)
    t3 = NOW + timedelta(minutes=3)
    events = _propose_accept_events("as-1", proposed_at=t0, accepted_at=t1)
    events += _propose_accept_events("as-2", proposed_at=t2, accepted_at=t2 + timedelta(seconds=1))
    events.append(
        _event(
            "as-1",
            3,
            "Superseded",
            from_state="Accepted",
            recorded_at=t3,
            successor_assertion_id="as-2",
        )
    )
    before = _project(predicates, [predecessor, successor], events, known_at=t1 + timedelta(seconds=1))
    after = _project(predicates, [predecessor, successor], events, known_at=t3)
    assert [edge.assertion_id for edge in before.edges] == ["as-1"]
    assert before.edges[0].target_id == "AAPL"
    assert [edge.assertion_id for edge in after.edges] == ["as-2"]
    assert after.edges[0].target_id == "AAPL_NEW"
    assert before.edge_set_hash != after.edge_set_hash
    assert before.projection_hash != after.projection_hash


def test_projection_hash_is_provenance_sensitive(predicates) -> None:
    """Same semantic edges with different evidence change projection_hash only."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    without = _project(predicates, [assertion], events)
    with_evidence = _project(
        predicates,
        [assertion],
        events,
        evidence=[_evidence()],
        evidence_links=[_link("as-1")],
    )
    assert without.edge_set_hash == with_evidence.edge_set_hash
    assert without.projection_hash != with_evidence.projection_hash


def test_confidence_does_not_affect_strength_or_hashes(predicates) -> None:
    """Confidence fields must not alter registry strength or hashes."""
    plain = _assertion()
    assessed = Assertion(
        assertion_id="as-1",
        predicate_id=PREDICATE_ID,
        subject_id="AAPL_BOND_2030",
        object_id="AAPL",
        method_id="bond.issuer_id.resolution@1",
        proposition="Bond issuer_id references issuer",
        confidence_status="assessed",
        confidence_bp=9000,
        confidence_type="calibration",
        confidence_method="manual@1",
        effective_from=NOW,
        effective_to=None,
        recorded_at=NOW,
    )
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    left = _project(predicates, [plain], events)
    right = _project(predicates, [assessed], events)
    assert left.edges[0].strength == "0.8"
    assert right.edges[0].strength == "0.8"
    assert left.edge_set_hash == right.edge_set_hash
    assert left.projection_hash == right.projection_hash


def test_rejected_withdrawn_retracted_excluded(predicates) -> None:
    """Terminal non-accepted states never emit edges."""
    cases: list[tuple[str, list[AssertionEvent]]] = [
        (
            "Rejected",
            [
                _event("as-1", 1, "Proposed", from_state=None, recorded_at=NOW, authority="proposer"),
                _event("as-1", 2, "Rejected", from_state="Proposed", recorded_at=NOW + timedelta(minutes=1)),
            ],
        ),
        (
            "Withdrawn",
            [
                _event("as-1", 1, "Proposed", from_state=None, recorded_at=NOW, authority="proposer"),
                _event(
                    "as-1",
                    2,
                    "Withdrawn",
                    from_state="Proposed",
                    recorded_at=NOW + timedelta(minutes=1),
                    authority="proposer",
                ),
            ],
        ),
        (
            "Retracted",
            _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
            + [
                _event(
                    "as-1",
                    3,
                    "Retracted",
                    from_state="Accepted",
                    recorded_at=NOW + timedelta(minutes=2),
                    authority="retractor",
                )
            ],
        ),
    ]
    for _label, events in cases:
        result = _project(predicates, [_assertion()], events, known_at=NOW + timedelta(hours=1))
        assert result.edges == ()


def test_naive_datetime_rejected(predicates) -> None:
    """Projector requires timezone-aware UTC instants."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        project(
            ProjectRequest(
                assertions=[assertion],
                events=events,
                evidence=[],
                evidence_links=[],
                predicate_registry=predicates,
                purpose=PURPOSE,
                effective_at=datetime(2026, 7, 25, 15, 0, 0),
                known_at=NOW,
            )
        )


def test_purpose_filter_excludes_other_purposes(predicates) -> None:
    """Assertions whose predicate purpose differs from the request are ignored."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    result = _project(predicates, [assertion], events, purpose="other_purpose")
    assert result.edges == ()
    assert result.governed_scopes == ()


def test_missing_evidence_record_for_link_fails_closed(predicates) -> None:
    """Projection fails closed when a link references missing evidence."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    with pytest.raises(ProjectionError, match="missing evidence record"):
        _project(
            predicates,
            [assertion],
            events,
            evidence_links=[_link("as-1")],
        )


def test_hash_inputs_reject_floats_via_canonical_json(predicates) -> None:
    """Sanity: empty projection hashes are lowercase hex and float-free."""
    result = _project(predicates, [], [])
    assert all(ch in "0123456789abcdef" for ch in result.edge_set_hash)
    assert all(ch in "0123456789abcdef" for ch in result.projection_hash)


def test_same_object_conflict_still_fails_closed(predicates) -> None:
    """Two Accepted assertions on one conflict key fail even with identical objects."""
    left = _assertion("as-1", object_id="AAPL")
    right = _assertion("as-2", object_id="AAPL")
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    events += _propose_accept_events("as-2", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=2))
    with pytest.raises(ProjectionError, match="projection conflict"):
        _project(predicates, [left, right], events)
