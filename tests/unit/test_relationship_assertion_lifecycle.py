"""Unit tests for GRAC v1 pure lifecycle planners and authority guards."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.governance.relationship_assertion import (
    MAX_RATIONALE_LEN,
    AssertionEvent,
    AssertionProposal,
    AuthorityContext,
    ConcurrencyConflict,
    EvidenceLink,
    EvidenceRecord,
    IllegalTransition,
    SupersessionCycle,
    UnauthorizedTransition,
    ValidationError,
)
from src.governance.relationship_assertion_contract import load_contract_bundle
from src.governance.relationship_assertion_lifecycle import (
    EvidenceRegistrationPlan,
    SupersedePlan,
    TransitionPlan,
    TransitionTiming,
    assert_no_cycle,
    load_transitions,
    normalize_sha256_hex,
    plan_accept,
    plan_dispute,
    plan_propose,
    plan_register_evidence,
    plan_reject,
    plan_retract,
    plan_supersede,
    plan_transition,
    plan_withdraw,
    resolve_state,
    validate_authority,
)

UTC = timezone.utc
NOW = datetime(2026, 7, 25, 12, 0, 0, tzinfo=UTC)
DIGEST = "a" * 64


def _ctx(*roles: str) -> AuthorityContext:
    return AuthorityContext(
        actor_id="actor-1",
        roles=frozenset(roles),  # type: ignore[arg-type]
        policy_version="grac.v1-policy",
        correlation_id="corr-1",
    )


def _timing(**overrides: object) -> TransitionTiming:
    payload = {"expected_sequence": 1, "rationale": "matrix", "recorded_at": NOW}
    payload.update(overrides)
    return TransitionTiming(**payload)  # type: ignore[arg-type]


def _proposal(assertion_id: str = "as-1") -> AssertionProposal:
    return AssertionProposal(
        assertion_id=assertion_id,
        predicate_id="financial.bond.issuer_reference@1",
        subject_id="AAPL_BOND_2030",
        object_id="AAPL",
        method_id="bond.issuer_id.resolution@1",
        proposition="Bond issuer_id references AAPL",
        effective_from=NOW,
    )


class TestAuthorityAndBounds:
    """AuthorityContext and field-bound validation."""

    def test_validate_authority_requires_role(self) -> None:
        """Missing required role fails closed."""
        ctx = _ctx("proposer")
        with pytest.raises(UnauthorizedTransition):
            validate_authority(ctx, "acceptor")

    def test_validate_authority_accepts_any_of_set(self) -> None:
        """Evidence-style any-of role sets succeed when one role matches."""
        validate_authority(_ctx("acceptor"), {"proposer", "acceptor"})

    def test_rationale_bound(self) -> None:
        """Oversized rationale is rejected."""
        plan = TransitionPlan(
            assertion_id="as-1",
            current="Proposed",
            to_state="Accepted",
            ctx=_ctx("acceptor"),
            timing=_timing(rationale="x" * (MAX_RATIONALE_LEN + 1)),
        )
        with pytest.raises(ValidationError, match="rationale"):
            plan_transition(plan)

    def test_digest_normalization(self) -> None:
        """Hyphenated digests normalize to 64 lowercase hex chars."""
        grouped = "aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa"
        assert normalize_sha256_hex(grouped) == DIGEST

    def test_plain_digest_normalization(self) -> None:
        """Plain 64-character digests remain supported and normalize case."""
        assert normalize_sha256_hex("A" * 64) == DIGEST

    def test_invalid_digest_rejected(self) -> None:
        """Short digests fail validation."""
        with pytest.raises(ValidationError, match="content_sha256"):
            normalize_sha256_hex("deadbeef")

    def test_digest_with_non_hyphen_garbage_rejected(self) -> None:
        """Malformed digests fail closed instead of dropping bad characters."""
        with pytest.raises(ValidationError, match="content_sha256"):
            normalize_sha256_hex(f"{DIGEST}!bad")

    @pytest.mark.parametrize(
        "digest",
        [
            f"-{DIGEST}",
            f"{DIGEST}-",
            f"{DIGEST[:4]}--{DIGEST[4:]}",
            f"{DIGEST[:8]}-{DIGEST[8:]}",
        ],
        ids=["leading", "trailing", "repeated", "arbitrary"],
    )
    def test_malformed_digest_hyphen_placement_rejected(self, digest: str) -> None:
        """Only the canonical sixteen groups of four hex characters are accepted."""
        with pytest.raises(ValidationError, match="content_sha256"):
            normalize_sha256_hex(digest)

    def test_proposal_requires_zero_utc_offset(self) -> None:
        """Timezone-aware non-UTC timestamps are rejected."""
        non_utc = timezone(timedelta(hours=2))
        proposal = _proposal()
        shifted = AssertionProposal(
            assertion_id=proposal.assertion_id,
            predicate_id=proposal.predicate_id,
            subject_id=proposal.subject_id,
            object_id=proposal.object_id,
            method_id=proposal.method_id,
            proposition=proposal.proposition,
            effective_from=datetime(2026, 7, 25, 14, 0, 0, tzinfo=non_utc),
        )
        ctx = _ctx("proposer")
        with pytest.raises(ValidationError, match="effective_from"):
            plan_propose(shifted, ctx, recorded_at=NOW)

    def test_proposal_rejects_malformed_datetime_type(self) -> None:
        """Malformed runtime timestamp types produce a domain validation error."""
        proposal = _proposal()
        malformed = AssertionProposal(
            assertion_id=proposal.assertion_id,
            predicate_id=proposal.predicate_id,
            subject_id=proposal.subject_id,
            object_id=proposal.object_id,
            method_id=proposal.method_id,
            proposition=proposal.proposition,
            effective_from="not-a-datetime",  # type: ignore[arg-type]
        )
        with pytest.raises(ValidationError, match="effective_from"):
            plan_propose(malformed, _ctx("proposer"), recorded_at=NOW)

    def test_assessed_confidence_rejects_bool(self) -> None:
        """confidence_bp must be an integer value, not bool."""
        proposal = _proposal()
        assessed = AssertionProposal(
            assertion_id=proposal.assertion_id,
            predicate_id=proposal.predicate_id,
            subject_id=proposal.subject_id,
            object_id=proposal.object_id,
            method_id=proposal.method_id,
            proposition=proposal.proposition,
            effective_from=proposal.effective_from,
            confidence_status="assessed",
            confidence_bp=True,
            confidence_type="review",
            confidence_method="manual",
        )
        ctx = _ctx("proposer")
        with pytest.raises(ValidationError, match="confidence_bp"):
            plan_propose(assessed, ctx, recorded_at=NOW)


class TestProposeAndResolve:
    """Proposal planning and event folding."""

    def test_plan_propose_sequence_one(self) -> None:
        """Propose yields Proposed at sequence 1."""
        assertion, event = plan_propose(_proposal(), _ctx("proposer"), recorded_at=NOW)
        assert assertion.assertion_id == "as-1"
        assert event.sequence == 1
        assert event.from_state is None
        assert event.to_state == "Proposed"
        assert event.authority == "proposer"

    def test_propose_requires_proposer(self) -> None:
        """Non-proposer cannot create assertions."""
        proposal = _proposal()
        ctx = _ctx("acceptor")
        with pytest.raises(UnauthorizedTransition):
            plan_propose(proposal, ctx, recorded_at=NOW)

    def test_resolve_state_folds_sequence(self) -> None:
        """State resolution follows the highest sequence event."""
        _, e1 = plan_propose(_proposal(), _ctx("proposer"), recorded_at=NOW)
        e2 = plan_accept(
            "as-1",
            "Proposed",
            _ctx("acceptor"),
            timing=_timing(
                rationale="ok",
                recorded_at=NOW + timedelta(seconds=1),
            ),
        )
        assert resolve_state([e1, e2]) == "Accepted"

    def test_resolve_state_rejects_invalid_initial_event(self) -> None:
        """Persisted streams must begin with a proper propose event."""
        event = AssertionEvent(
            event_id="event-1",
            assertion_id="as-1",
            sequence=1,
            from_state="Proposed",
            to_state="Accepted",
            authority="acceptor",
            actor_id="actor-1",
            rationale="bad",
            policy_version="grac.v1-policy",
            recorded_at=NOW,
        )
        with pytest.raises(ValidationError, match="initial event"):
            resolve_state([event])

    def test_resolve_state_rejects_state_continuity_gap(self) -> None:
        """Persisted streams must align each edge with the previous state."""
        _, e1 = plan_propose(_proposal(), _ctx("proposer"), recorded_at=NOW)
        e2 = plan_retract(
            "as-1",
            "Accepted",
            _ctx("retractor"),
            timing=_timing(
                rationale="gap",
                recorded_at=NOW + timedelta(seconds=1),
            ),
        )
        with pytest.raises(ValidationError, match="continuity"):
            resolve_state([e1, e2])


class TestTransitionMatrix:
    """Complete frozen transition matrix coverage."""

    @pytest.fixture
    def transitions(self):
        """Load pinned transitions for matrix tests."""
        return load_transitions()

    def test_bundle_loads(self) -> None:
        """Contract bundle remains loadable from lifecycle helpers."""
        contract, _predicates, transitions = load_contract_bundle()
        assert contract.contract_version == "grac.v1"
        assert len(transitions.transitions) >= 9

    @pytest.mark.parametrize(
        ("from_state", "to_state", "role"),
        [
            ("Proposed", "Accepted", "acceptor"),
            ("Proposed", "Rejected", "acceptor"),
            ("Proposed", "Withdrawn", "proposer"),
            ("Accepted", "Disputed", "disputer"),
            ("Accepted", "Retracted", "retractor"),
            ("Accepted", "Superseded", "acceptor"),
            ("Disputed", "Accepted", "acceptor"),
            ("Disputed", "Retracted", "retractor"),
            ("Disputed", "Superseded", "acceptor"),
        ],
    )
    def test_allowed_matrix_edges(self, from_state, to_state, role, transitions) -> None:
        """Every registry edge plans successfully with the required authority."""
        timing = _timing(transitions=transitions)
        successor_assertion_id = "as-successor" if to_state == "Superseded" else None
        event = plan_transition(
            TransitionPlan(
                assertion_id="as-1",
                current=from_state,
                to_state=to_state,
                ctx=_ctx(role),
                timing=timing,
                successor_assertion_id=successor_assertion_id,
            )
        )
        assert event.to_state == to_state
        assert event.authority == role
        assert event.sequence == 2

    @pytest.mark.parametrize(
        ("from_state", "to_state"),
        [
            ("Rejected", "Accepted"),
            ("Withdrawn", "Proposed"),
            ("Retracted", "Accepted"),
            ("Superseded", "Accepted"),
            ("Proposed", "Disputed"),
            ("Accepted", "Withdrawn"),
            ("Disputed", "Withdrawn"),
        ],
    )
    def test_illegal_edges_rejected(self, from_state, to_state, transitions) -> None:
        """Out-of-matrix and terminal-exit edges raise IllegalTransition."""
        plan = TransitionPlan(
            assertion_id="as-1",
            current=from_state,
            to_state=to_state,
            ctx=_ctx("acceptor", "proposer", "disputer", "retractor"),
            timing=_timing(rationale="illegal", transitions=transitions),
        )
        with pytest.raises(IllegalTransition):
            plan_transition(plan)

    def test_wrong_role_rejected(self, transitions) -> None:
        """Correct edge with wrong authority fails closed."""
        ctx = _ctx("proposer")
        timing = _timing(rationale="nope", transitions=transitions)
        with pytest.raises(UnauthorizedTransition):
            plan_accept("as-1", "Proposed", ctx, timing=timing)

    @pytest.mark.parametrize(
        ("plan", "exc_type", "match"),
        [
            (
                TransitionPlan(
                    assertion_id="as-1",
                    current="Accepted",
                    to_state="Superseded",
                    ctx=_ctx("acceptor"),
                    timing=_timing(rationale="missing successor"),
                ),
                ValidationError,
                "successor_assertion_id",
            ),
            (
                TransitionPlan(
                    assertion_id="as-1",
                    current="Proposed",
                    to_state="Accepted",
                    ctx=_ctx("acceptor"),
                    timing=_timing(rationale="bad successor"),
                    successor_assertion_id="as-2",
                ),
                IllegalTransition,
                "must not set successor",
            ),
        ],
        ids=["supersession_requires_successor", "non_supersession_forbids_successor"],
    )
    def test_successor_pointer_rules(self, transitions, plan, exc_type, match) -> None:
        """Successor pointer is required only on supersession edges."""
        plan = TransitionPlan(
            assertion_id=plan.assertion_id,
            current=plan.current,
            to_state=plan.to_state,
            ctx=plan.ctx,
            timing=_timing(rationale=plan.timing.rationale, transitions=transitions),
            successor_assertion_id=plan.successor_assertion_id,
        )
        with pytest.raises(exc_type, match=match):
            plan_transition(plan)


class TestConcurrencyGuard:
    """expected_sequence planning rules."""

    def test_expected_sequence_must_be_positive(self) -> None:
        """expected_sequence < 1 is a concurrency conflict."""
        ctx = _ctx("acceptor")
        timing = _timing(expected_sequence=0, rationale="bad")
        with pytest.raises(ConcurrencyConflict):
            plan_accept("as-1", "Proposed", ctx, timing=timing)

    def test_expected_sequence_rejects_bool(self) -> None:
        """expected_sequence must be an integer sequence, not bool."""
        ctx = _ctx("acceptor")
        timing = _timing(expected_sequence=True, rationale="bad")  # type: ignore[arg-type]
        with pytest.raises(ValidationError, match="expected_sequence"):
            plan_accept("as-1", "Proposed", ctx, timing=timing)

    def test_next_sequence_is_expected_plus_one(self) -> None:
        """Planned event sequence is always expected_sequence + 1."""
        event = plan_reject(
            "as-1",
            "Proposed",
            _ctx("acceptor"),
            timing=_timing(expected_sequence=3, rationale="reject"),
        )
        assert event.sequence == 4


class TestSupersessionCycles:
    """Cycle and self-supersession prevention."""

    def test_self_supersession_forbidden(self) -> None:
        """An assertion cannot supersede itself."""
        plan = SupersedePlan(
            transition=TransitionPlan(
                assertion_id="as-1",
                current="Accepted",
                to_state="Superseded",
                ctx=_ctx("acceptor"),
                timing=_timing(rationale="self"),
                successor_assertion_id="as-1",
            )
        )
        with pytest.raises(SupersessionCycle):
            plan_supersede(plan)

    def test_cycle_via_lookup_forbidden(self) -> None:
        """Successor chains that reach the predecessor are rejected."""
        chain = {"as-2": ("as-3",), "as-3": ("as-1",)}
        with pytest.raises(SupersessionCycle):
            assert_no_cycle("as-1", "as-2", chain)

    def test_acyclic_chain_allowed(self) -> None:
        """Forward-only successor chains are accepted."""
        assert_no_cycle("as-1", "as-2", {"as-2": ("as-3",), "as-3": ()})


class TestEvidencePlanning:
    """Evidence registration gates."""

    def test_evidence_allowed_in_proposed(self) -> None:
        """Proposer may attach supporting evidence while Proposed."""
        link = EvidenceLink(
            link_id="link-1",
            assertion_id="as-1",
            evidence_id="ev-1",
            polarity="supporting",
            recorded_at=NOW,
        )
        evidence = EvidenceRecord(
            evidence_id="ev-1",
            source_ref="sample://bond",
            content_sha256=DIGEST,
            media_type="application/json",
            visibility="internal",
            custody_id="collector-1",
            recorded_at=NOW,
        )
        assert (
            plan_register_evidence(
                EvidenceRegistrationPlan(
                    assertion_id="as-1",
                    state="Proposed",
                    link=link,
                    ctx=_ctx("proposer"),
                    evidence=evidence,
                )
            )
            is link
        )

    @pytest.mark.parametrize(
        ("state", "role", "polarity", "exc_type"),
        [
            ("Rejected", "acceptor", "contextual", IllegalTransition),
            ("Accepted", "disputer", "opposing", UnauthorizedTransition),
        ],
        ids=["forbidden_in_rejected", "requires_proposer_or_acceptor"],
    )
    def test_evidence_gate_failures(self, state, role, polarity, exc_type) -> None:
        """Rejected state and insufficient authority both reject evidence links."""
        link = EvidenceLink(
            link_id="link-1",
            assertion_id="as-1",
            evidence_id="ev-1",
            polarity=polarity,
            recorded_at=NOW,
        )
        plan = EvidenceRegistrationPlan(
            assertion_id="as-1",
            state=state,
            link=link,
            ctx=_ctx(role),
        )
        with pytest.raises(exc_type):
            plan_register_evidence(plan)


class TestNamedPlanners:
    """Smoke coverage for named transition planners."""

    def test_withdraw_and_dispute_and_retract(self) -> None:
        """Named planners emit the expected to_state values."""
        withdrawn = plan_withdraw(
            "as-1",
            "Proposed",
            _ctx("proposer"),
            timing=_timing(rationale="withdraw"),
        )
        disputed = plan_dispute(
            "as-1",
            "Accepted",
            _ctx("disputer"),
            timing=_timing(expected_sequence=2, rationale="dispute"),
        )
        retracted = plan_retract(
            "as-1",
            "Accepted",
            _ctx("retractor"),
            timing=_timing(expected_sequence=2, rationale="retract"),
        )
        assert withdrawn.to_state == "Withdrawn"
        assert disputed.to_state == "Disputed"
        assert retracted.to_state == "Retracted"
