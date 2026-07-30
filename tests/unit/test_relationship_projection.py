"""Unit tests for the pure GRAC v1 deterministic projector."""

from __future__ import annotations

from dataclasses import dataclass
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
    GovernedScope,
    ProjectionError,
    ProjectionRevision,
    ProjectRequest,
    canonicalize_governed_scopes,
    project,
)

UTC = timezone.utc
NOW = datetime(2026, 7, 25, 15, 0, 0, tzinfo=UTC)
PURPOSE = "financial_graph_current_view"
PREDICATE_ID = "financial.bond.issuer_reference@1"
DIGEST_A = "a" * 64


def _sha256_hex(*chunks: str) -> str:
    return "".join(chunks)


EMPTY_EDGE_SET_HASH = _sha256_hex(
    "4f53cda18c2baa0",
    "c0354bb5f9a3ecbe",
    "5ed12ab4d8e11ba8",
    "73c2f11161202b945",
)
EMPTY_PROJECTION_HASH = _sha256_hex(
    "924520d579a2fb60",
    "47d770f7997bae36",
    "efad3e48b62e1867",
    "12ce9990236b2cc5",
)
GOLDEN_EDGE_SET_HASH = _sha256_hex(
    "c8c8e738ffe460a7",
    "716fcd89fa16baf4",
    "94fe4015e2551a1f",
    "107e53b129a7d345",
)
GOLDEN_PROJECTION_HASH = _sha256_hex(
    "9f061549b5713b51",
    "78153dfd886c7a6e",
    "f7bcd81027d53dac",
    "d9222c480bea3ff6",
)


@pytest.fixture(scope="module")
def predicates():
    """Pinned predicate registry from the frozen contract bundle."""
    _contract, predicates_doc, _transitions = load_contract_bundle()
    return predicates_doc


@dataclass(frozen=True)
class _AssertionSpec:
    """Fixture knobs for issuer-reference assertions."""

    assertion_id: str = "as-1"
    object_id: str = "AAPL"
    effective_from: datetime = NOW
    effective_to: datetime | None = None
    recorded_at: datetime = NOW


@dataclass(frozen=True)
class _EventSpec:
    """Fixture knobs for lifecycle events."""

    assertion_id: str
    sequence: int
    to_state: str
    from_state: str | None
    recorded_at: datetime
    event_id: str | None = None
    authority: str = "acceptor"
    actor_id: str = "determiner-1"
    successor_assertion_id: str | None = None


@dataclass(frozen=True)
class _ProjectSpec:
    """Fixture knobs for projector invocations."""

    assertions: list[Assertion]
    events: list[AssertionEvent]
    effective_at: datetime = NOW
    known_at: datetime = NOW + timedelta(hours=1)
    evidence: list[EvidenceRecord] | None = None
    evidence_links: list[EvidenceLink] | None = None
    purpose: str = PURPOSE
    previously_published_scopes: tuple[GovernedScope, ...] = ()


def _assertion(spec: _AssertionSpec | None = None) -> Assertion:
    cfg = spec or _AssertionSpec()
    return Assertion(
        assertion_id=cfg.assertion_id,
        predicate_id=PREDICATE_ID,
        subject_id="AAPL_BOND_2030",
        object_id=cfg.object_id,
        method_id="bond.issuer_id.resolution@1",
        proposition="Bond issuer_id references issuer",
        confidence_status="not_assessed",
        confidence_bp=None,
        confidence_type=None,
        confidence_method=None,
        effective_from=cfg.effective_from,
        effective_to=cfg.effective_to,
        recorded_at=cfg.recorded_at,
    )


def _event(spec: _EventSpec) -> AssertionEvent:
    return AssertionEvent(
        event_id=spec.event_id or f"ev-{spec.assertion_id}-{spec.sequence}",
        assertion_id=spec.assertion_id,
        sequence=spec.sequence,
        from_state=spec.from_state,  # type: ignore[arg-type]
        to_state=spec.to_state,  # type: ignore[arg-type]
        authority=spec.authority,  # type: ignore[arg-type]
        actor_id=spec.actor_id,
        rationale="test",
        policy_version="grac.v1-policy",
        recorded_at=spec.recorded_at,
        successor_assertion_id=spec.successor_assertion_id,
    )


def _propose_accept_events(
    assertion_id: str,
    *,
    proposed_at: datetime,
    accepted_at: datetime,
) -> list[AssertionEvent]:
    return [
        _event(
            _EventSpec(
                assertion_id,
                1,
                "Proposed",
                from_state=None,
                recorded_at=proposed_at,
                authority="proposer",
                actor_id="proposer-1",
            )
        ),
        _event(
            _EventSpec(
                assertion_id,
                2,
                "Accepted",
                from_state="Proposed",
                recorded_at=accepted_at,
            )
        ),
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


def _project(predicates, spec: _ProjectSpec) -> ProjectionRevision:
    return project(
        ProjectRequest(
            assertions=spec.assertions,
            events=spec.events,
            evidence=spec.evidence or [],
            evidence_links=spec.evidence_links or [],
            predicate_registry=predicates,
            purpose=spec.purpose,
            effective_at=spec.effective_at,
            known_at=spec.known_at,
            previously_published_scopes=spec.previously_published_scopes,
        )
    )


def test_empty_inputs_yield_empty_revision_and_stable_hashes(predicates) -> None:
    """Empty assertion store projects zero edges with deterministic empty hashes."""
    first = _project(predicates, _ProjectSpec(assertions=[], events=[], known_at=NOW))
    second = _project(predicates, _ProjectSpec(assertions=[], events=[], known_at=NOW))
    assert first.edges == ()
    assert first.governed_scopes == ()
    assert first.edge_set_hash == second.edge_set_hash
    assert first.projection_hash == second.projection_hash
    assert first.projector_version == PROJECTOR_VERSION
    # SHA-256 of canonical JSON ``[]``.
    assert first.edge_set_hash == EMPTY_EDGE_SET_HASH
    assert first.projection_hash == EMPTY_PROJECTION_HASH


def test_empty_edge_revision_preserves_previously_published_scope(predicates) -> None:
    """A later empty revision retains its durable governed scope."""
    result = _project(
        predicates,
        _ProjectSpec(
            assertions=[],
            events=[],
            known_at=NOW,
            previously_published_scopes=(GovernedScope(PURPOSE, PREDICATE_ID),),
        ),
    )
    assert result.edges == ()
    assert result.governed_scopes == (GovernedScope(PURPOSE, PREDICATE_ID),)
    assert result.edge_set_hash == EMPTY_EDGE_SET_HASH
    assert result.projection_hash != EMPTY_PROJECTION_HASH


def test_governed_scope_canonicalization_deduplicates_and_sorts() -> None:
    """The shared canonicalizer yields one stable scope set for projection and persistence."""
    scopes = canonicalize_governed_scopes(
        (GovernedScope(PURPOSE, "z"), GovernedScope(PURPOSE, "a"), GovernedScope(PURPOSE, "z")),
        PURPOSE,
    )
    assert scopes == (GovernedScope(PURPOSE, "a"), GovernedScope(PURPOSE, "z"))


def test_accepted_issuer_reference_projects_corporate_link(predicates) -> None:
    """First financial slice projects AAPL_BOND_2030 → AAPL corporate_link @ 0.8."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    result = _project(
        predicates,
        _ProjectSpec(assertions=[assertion], events=events, known_at=NOW + timedelta(days=1)),
    )
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
    assert result.edge_set_hash == GOLDEN_EDGE_SET_HASH
    assert result.projection_hash == GOLDEN_PROJECTION_HASH


def test_input_order_invariance(predicates) -> None:
    """Shuffled assertion/event inputs must not change hashes or edge order."""
    a1 = _assertion(_AssertionSpec(assertion_id="as-1", object_id="AAPL"))
    # Distinct subject avoids conflict with a1 under the issuer_reference key.
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
    forward = _project(predicates, _ProjectSpec(assertions=[a1, a2], events=events))
    reverse = _project(predicates, _ProjectSpec(assertions=[a2, a1], events=list(reversed(events))))
    assert forward.edge_set_hash == reverse.edge_set_hash
    assert forward.projection_hash == reverse.projection_hash
    assert [edge.assertion_id for edge in forward.edges] == [edge.assertion_id for edge in reverse.edges]


def test_replay_idempotence(predicates) -> None:
    """Replaying the same inputs yields an identical revision payload."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    first = _project(predicates, _ProjectSpec(assertions=[assertion], events=events))
    second = _project(predicates, _ProjectSpec(assertions=[assertion], events=events))
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
    assertion = _assertion(_AssertionSpec(effective_from=NOW, effective_to=NOW + timedelta(days=30)))
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    result = _project(
        predicates,
        _ProjectSpec(assertions=[assertion], events=events, effective_at=effective_at),
    )
    assert bool(result.edges) is expect_edge


def test_historical_known_at_reconstruction(predicates) -> None:
    """known_at before acceptance excludes the assertion; after includes it."""
    assertion = _assertion(_AssertionSpec(recorded_at=NOW))
    proposed_at = NOW
    accepted_at = NOW + timedelta(hours=1)
    events = _propose_accept_events("as-1", proposed_at=proposed_at, accepted_at=accepted_at)
    before = _project(
        predicates,
        _ProjectSpec(assertions=[assertion], events=events, known_at=NOW + timedelta(minutes=30)),
    )
    after = _project(
        predicates,
        _ProjectSpec(assertions=[assertion], events=events, known_at=accepted_at),
    )
    assert before.edges == ()
    assert len(after.edges) == 1


def test_disputed_assertions_excluded(predicates) -> None:
    """Disputed assertions do not emit edges at that known_at."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    events.append(
        _event(
            _EventSpec(
                "as-1",
                3,
                "Disputed",
                from_state="Accepted",
                recorded_at=NOW + timedelta(minutes=2),
                authority="disputer",
            )
        )
    )
    result = _project(
        predicates,
        _ProjectSpec(assertions=[assertion], events=events, known_at=NOW + timedelta(minutes=3)),
    )
    assert result.edges == ()


def test_fail_closed_on_cardinality_conflict(predicates) -> None:
    """Two Accepted issuer references for one bond fail closed (no LWW)."""
    left = _assertion(_AssertionSpec(assertion_id="as-1", object_id="AAPL"))
    right = _assertion(_AssertionSpec(assertion_id="as-2", object_id="MSFT"))
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    events += _propose_accept_events("as-2", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=2))
    spec = _ProjectSpec(assertions=[left, right], events=events)
    with pytest.raises(ProjectionError, match="projection conflict"):
        _project(predicates, spec)


def test_supersession_selection_changes_projection(predicates) -> None:
    """After supersession, only the Accepted successor projects."""
    predecessor = _assertion(_AssertionSpec(assertion_id="as-1", object_id="AAPL"))
    successor = _assertion(_AssertionSpec(assertion_id="as-2", object_id="AAPL_NEW"))
    t0 = NOW
    t1 = NOW + timedelta(minutes=1)
    t2 = NOW + timedelta(minutes=2)
    t3 = NOW + timedelta(minutes=3)
    events = _propose_accept_events("as-1", proposed_at=t0, accepted_at=t1)
    events += _propose_accept_events("as-2", proposed_at=t2, accepted_at=t2 + timedelta(seconds=1))
    events.append(
        _event(
            _EventSpec(
                "as-1",
                3,
                "Superseded",
                from_state="Accepted",
                recorded_at=t3,
                successor_assertion_id="as-2",
            )
        )
    )
    before = _project(
        predicates,
        _ProjectSpec(
            assertions=[predecessor, successor],
            events=events,
            known_at=t1 + timedelta(seconds=1),
        ),
    )
    after = _project(
        predicates,
        _ProjectSpec(assertions=[predecessor, successor], events=events, known_at=t3),
    )
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
    without = _project(predicates, _ProjectSpec(assertions=[assertion], events=events))
    with_evidence = _project(
        predicates,
        _ProjectSpec(
            assertions=[assertion],
            events=events,
            evidence=[_evidence()],
            evidence_links=[_link("as-1")],
        ),
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
    left = _project(predicates, _ProjectSpec(assertions=[plain], events=events))
    right = _project(predicates, _ProjectSpec(assertions=[assessed], events=events))
    assert left.edges[0].strength == "0.8"
    assert right.edges[0].strength == "0.8"
    assert left.edge_set_hash == right.edge_set_hash
    assert left.projection_hash == right.projection_hash


def _terminal_state_events(to_state: str) -> list[AssertionEvent]:
    """Build propose→terminal or accept→retract event streams for exclusion tests."""
    if to_state == "Retracted":
        return _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1)) + [
            _event(
                _EventSpec(
                    "as-1",
                    3,
                    "Retracted",
                    from_state="Accepted",
                    recorded_at=NOW + timedelta(minutes=2),
                    authority="retractor",
                )
            )
        ]
    authority = "acceptor" if to_state == "Rejected" else "proposer"
    actor_id = "determiner-1" if to_state == "Rejected" else "proposer-1"
    return [
        _event(
            _EventSpec(
                "as-1",
                1,
                "Proposed",
                from_state=None,
                recorded_at=NOW,
                authority="proposer",
                actor_id="proposer-1",
            )
        ),
        _event(
            _EventSpec(
                "as-1",
                2,
                to_state,
                from_state="Proposed",
                recorded_at=NOW + timedelta(minutes=1),
                authority=authority,
                actor_id=actor_id,
            )
        ),
    ]


@pytest.mark.parametrize("to_state", ["Rejected", "Withdrawn", "Retracted"])
def test_rejected_withdrawn_retracted_excluded(predicates, to_state: str) -> None:
    """Terminal non-accepted states never emit edges."""
    events = _terminal_state_events(to_state)
    result = _project(
        predicates,
        _ProjectSpec(assertions=[_assertion()], events=events, known_at=NOW + timedelta(hours=1)),
    )
    assert result.edges == ()


def test_naive_datetime_rejected(predicates) -> None:
    """Projector requires timezone-aware UTC instants."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    request = ProjectRequest(
        assertions=[assertion],
        events=events,
        evidence=[],
        evidence_links=[],
        predicate_registry=predicates,
        purpose=PURPOSE,
        effective_at=datetime(2026, 7, 25, 15, 0, 0),
        known_at=NOW,
    )
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        project(request)


def test_purpose_filter_excludes_other_purposes(predicates) -> None:
    """Assertions whose predicate purpose differs from the request are ignored."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    result = _project(
        predicates,
        _ProjectSpec(assertions=[assertion], events=events, purpose="other_purpose"),
    )
    assert result.edges == ()
    assert result.governed_scopes == ()


def test_missing_evidence_record_for_link_fails_closed(predicates) -> None:
    """Projection fails closed when a link references missing evidence."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    spec = _ProjectSpec(
        assertions=[assertion],
        events=events,
        evidence_links=[_link("as-1")],
    )
    with pytest.raises(ProjectionError, match="missing evidence record"):
        _project(predicates, spec)


def test_empty_projection_hashes_are_lowercase_hex(predicates) -> None:
    """Empty projection content hashes are lowercase hexadecimal digests."""
    result = _project(predicates, _ProjectSpec(assertions=[], events=[]))
    assert all(ch in "0123456789abcdef" for ch in result.edge_set_hash)
    assert all(ch in "0123456789abcdef" for ch in result.projection_hash)


def test_same_object_conflict_still_fails_closed(predicates) -> None:
    """Two Accepted assertions on one conflict key fail even with identical objects."""
    left = _assertion(_AssertionSpec(assertion_id="as-1", object_id="AAPL"))
    right = _assertion(_AssertionSpec(assertion_id="as-2", object_id="AAPL"))
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    events += _propose_accept_events("as-2", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=2))
    spec = _ProjectSpec(assertions=[left, right], events=events)
    with pytest.raises(ProjectionError, match="projection conflict"):
        _project(predicates, spec)


def test_unregistered_method_id_fails_closed(predicates) -> None:
    """Accepted assertions with unregistered method_id do not project."""
    assertion = Assertion(
        assertion_id="as-1",
        predicate_id=PREDICATE_ID,
        subject_id="AAPL_BOND_2030",
        object_id="AAPL",
        method_id="not.a.registered.method@1",
        proposition="Bond issuer_id references issuer",
        confidence_status="not_assessed",
        confidence_bp=None,
        confidence_type=None,
        confidence_method=None,
        effective_from=NOW,
        effective_to=None,
        recorded_at=NOW,
    )
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    spec = _ProjectSpec(assertions=[assertion], events=events)
    with pytest.raises(ProjectionError, match="not registered for predicate"):
        _project(predicates, spec)


def test_duplicate_evidence_id_fails_closed(predicates) -> None:
    """Duplicate evidence ids in projection inputs fail closed before hashing."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    evidence = [_evidence("evd-1", DIGEST_A), _evidence("evd-1", "d" * 64)]
    evidence_links = [_link("as-1")]
    spec = _ProjectSpec(
        assertions=[assertion],
        events=events,
        evidence=evidence,
        evidence_links=evidence_links,
    )
    with pytest.raises(ProjectionError, match="duplicate evidence id"):
        _project(predicates, spec)


def test_future_evidence_record_fails_closed_for_historical_known_at(predicates) -> None:
    """Evidence recorded after known_at must not enter projection_hash."""
    assertion = _assertion()
    events = _propose_accept_events("as-1", proposed_at=NOW, accepted_at=NOW + timedelta(minutes=1))
    future_evidence = EvidenceRecord(
        evidence_id="evd-1",
        source_ref="sample://evd-1",
        content_sha256=DIGEST_A,
        media_type="application/json",
        visibility="internal",
        custody_id="collector-1",
        recorded_at=NOW + timedelta(days=2),
    )
    evidence_links = [_link("as-1", recorded_at=NOW + timedelta(minutes=2))]
    spec = _ProjectSpec(
        assertions=[assertion],
        events=events,
        known_at=NOW + timedelta(hours=1),
        evidence=[future_evidence],
        evidence_links=evidence_links,
    )
    with pytest.raises(ProjectionError, match="recorded after known_at"):
        _project(predicates, spec)
