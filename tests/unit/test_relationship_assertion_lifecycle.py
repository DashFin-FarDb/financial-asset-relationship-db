"""Unit tests for GRAC v1 pure lifecycle planners and authority guards."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.governance.relationship_assertion import (
    MAX_RATIONALE_LEN,
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
        with pytest.raises(UnauthorizedTransition):
            validate_authority(_ctx("proposer"), "acceptor")

    def test_validate_authority_accepts_any_of_set(self) -> None:
        """Evidence-style any-of role sets succeed when one role matches."""
        validate_authority(_ctx("acceptor"), {"proposer", "acceptor"})

    def test_rationale_bound(self) -> None:
        """Oversized rationale is rejected."""
        with pytest.raises(ValidationError, match="rationale"):
            plan_transition(
                "as-1",
                "Proposed",
                "Accepted",
                _ctx("acceptor"),
                expected_sequence=1,
                rationale="x" * (MAX_RATIONALE_LEN + 1),
                recorded_at=NOW,
            )

    def test_digest_normalization(self) -> None:
        """Hyphenated digests normalize to 64 lowercase hex chars."""
        grouped = "aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa-aaaa"
        assert normalize_sha256_hex(grouped) == DIGEST

    def test_invalid_digest_rejected(self) -> None:
        """Short digests fail validation."""
        with pytest.raises(ValidationError, match="content_sha256"):
            normalize_sha256_hex("deadbeef")


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
        with pytest.raises(UnauthorizedTransition):
            plan_propose(_proposal(), _ctx("acceptor"), recorded_at=NOW)

    def test_resolve_state_folds_sequence(self) -> None:
        """State resolution follows the highest sequence event."""
        _, e1 = plan_propose(_proposal(), _ctx("proposer"), recorded_at=NOW)
        e2 = plan_accept(
            "as-1",
            "Proposed",
            _ctx("acceptor"),
            expected_sequence=1,
            rationale="ok",
            recorded_at=NOW + timedelta(seconds=1),
        )
        assert resolve_state([e1, e2]) == "Accepted"


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
        kwargs: dict = {
            "expected_sequence": 1,
            "rationale": "matrix",
            "recorded_at": NOW,
            "transitions": transitions,
        }
        if to_state == "Superseded":
            kwargs["successor_assertion_id"] = "as-successor"
        event = plan_transition("as-1", from_state, to_state, _ctx(role), **kwargs)
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
        with pytest.raises(IllegalTransition):
            plan_transition(
                "as-1",
                from_state,
                to_state,
                _ctx("acceptor", "proposer", "disputer", "retractor"),
                expected_sequence=1,
                rationale="illegal",
                recorded_at=NOW,
                transitions=transitions,
            )

    def test_wrong_role_rejected(self, transitions) -> None:
        """Correct edge with wrong authority fails closed."""
        with pytest.raises(UnauthorizedTransition):
            plan_accept(
                "as-1",
                "Proposed",
                _ctx("proposer"),
                expected_sequence=1,
                rationale="nope",
                recorded_at=NOW,
                transitions=transitions,
            )

    def test_supersession_requires_successor(self, transitions) -> None:
        """Supersession without successor_assertion_id is illegal."""
        with pytest.raises(ValidationError, match="successor_assertion_id"):
            plan_transition(
                "as-1",
                "Accepted",
                "Superseded",
                _ctx("acceptor"),
                expected_sequence=1,
                rationale="missing successor",
                recorded_at=NOW,
                transitions=transitions,
            )

    def test_non_supersession_forbids_successor(self, transitions) -> None:
        """Non-supersession edges must not carry a successor pointer."""
        with pytest.raises(IllegalTransition, match="must not set successor"):
            plan_transition(
                "as-1",
                "Proposed",
                "Accepted",
                _ctx("acceptor"),
                expected_sequence=1,
                rationale="bad successor",
                recorded_at=NOW,
                successor_assertion_id="as-2",
                transitions=transitions,
            )


class TestConcurrencyGuard:
    """expected_sequence planning rules."""

    def test_expected_sequence_must_be_positive(self) -> None:
        """expected_sequence < 1 is a concurrency conflict."""
        with pytest.raises(ConcurrencyConflict):
            plan_accept(
                "as-1",
                "Proposed",
                _ctx("acceptor"),
                expected_sequence=0,
                rationale="bad",
                recorded_at=NOW,
            )

    def test_next_sequence_is_expected_plus_one(self) -> None:
        """Planned event sequence is always expected_sequence + 1."""
        event = plan_reject(
            "as-1",
            "Proposed",
            _ctx("acceptor"),
            expected_sequence=3,
            rationale="reject",
            recorded_at=NOW,
        )
        assert event.sequence == 4


class TestSupersessionCycles:
    """Cycle and self-supersession prevention."""

    def test_self_supersession_forbidden(self) -> None:
        """An assertion cannot supersede itself."""
        with pytest.raises(SupersessionCycle):
            plan_supersede(
                "as-1",
                "Accepted",
                _ctx("acceptor"),
                expected_sequence=1,
                rationale="self",
                recorded_at=NOW,
                successor_assertion_id="as-1",
            )

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
        assert plan_register_evidence("as-1", "Proposed", link, _ctx("proposer"), evidence=evidence) is link

    def test_evidence_forbidden_in_rejected(self) -> None:
        """Terminal Rejected state cannot gain evidence links."""
        link = EvidenceLink(
            link_id="link-1",
            assertion_id="as-1",
            evidence_id="ev-1",
            polarity="contextual",
            recorded_at=NOW,
        )
        with pytest.raises(IllegalTransition):
            plan_register_evidence("as-1", "Rejected", link, _ctx("acceptor"))

    def test_evidence_requires_proposer_or_acceptor(self) -> None:
        """Disputer alone cannot register evidence links."""
        link = EvidenceLink(
            link_id="link-1",
            assertion_id="as-1",
            evidence_id="ev-1",
            polarity="opposing",
            recorded_at=NOW,
        )
        with pytest.raises(UnauthorizedTransition):
            plan_register_evidence("as-1", "Accepted", link, _ctx("disputer"))


class TestNamedPlanners:
    """Smoke coverage for named transition planners."""

    def test_withdraw_and_dispute_and_retract(self) -> None:
        """Named planners emit the expected to_state values."""
        withdrawn = plan_withdraw(
            "as-1",
            "Proposed",
            _ctx("proposer"),
            expected_sequence=1,
            rationale="withdraw",
            recorded_at=NOW,
        )
        disputed = plan_dispute(
            "as-1",
            "Accepted",
            _ctx("disputer"),
            expected_sequence=2,
            rationale="dispute",
            recorded_at=NOW,
        )
        retracted = plan_retract(
            "as-1",
            "Accepted",
            _ctx("retractor"),
            expected_sequence=2,
            rationale="retract",
            recorded_at=NOW,
        )
        assert withdrawn.to_state == "Withdrawn"
        assert disputed.to_state == "Disputed"
        assert retracted.to_state == "Retracted"
