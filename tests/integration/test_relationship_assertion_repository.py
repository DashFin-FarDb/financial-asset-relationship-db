"""Integration tests for GRAC v1 append-only assertion repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import DBAPIError

from src.data.database import create_session_factory, init_db
from src.data.relationship_assertion_db_models import (
    RelationshipAssertionEventORM,
    RelationshipAssertionORM,
)
from src.data.relationship_assertion_repository import (
    RegisterEvidenceRequest,
    RelationshipAssertionRepository,
    RepositoryTransitionRequest,
    SupersedeAtomicRequest,
)
from src.governance.relationship_assertion import (
    AssertionProposal,
    AuthorityContext,
    ConcurrencyConflict,
    EvidenceRecord,
    IllegalTransition,
    SupersessionCycle,
    UnauthorizedTransition,
    ValidationError,
)
from tests.conftest import enable_sqlite_foreign_keys

UTC = timezone.utc
NOW = datetime(2026, 7, 25, 15, 0, 0, tzinfo=UTC)
DIGEST = "b" * 64


@pytest.fixture
def repo_session(tmp_path):
    """SQLite session with GRAC schema + immutability guards."""
    engine = create_engine(f"sqlite:///{tmp_path / 'grac_repo.db'}")
    enable_sqlite_foreign_keys(engine)
    init_db(engine)
    factory = create_session_factory(engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def repo(repo_session) -> RelationshipAssertionRepository:
    """Repository bound to the test session with a frozen clock."""
    stamps = {"t": NOW}

    def clock() -> datetime:
        current = stamps["t"]
        stamps["t"] = current + timedelta(milliseconds=1)
        return current

    return RelationshipAssertionRepository(repo_session, clock=clock)


def _ctx(*roles: str) -> AuthorityContext:
    return AuthorityContext(
        actor_id="actor-1",
        roles=frozenset(roles),  # type: ignore[arg-type]
        policy_version="grac.v1-policy",
        correlation_id="corr-repo",
    )


def _proposal(assertion_id: str = "as-1", **overrides: object) -> AssertionProposal:
    payload = {
        "assertion_id": assertion_id,
        "predicate_id": "financial.bond.issuer_reference@1",
        "subject_id": "AAPL_BOND_2030",
        "object_id": "AAPL",
        "method_id": "bond.issuer_id.resolution@1",
        "proposition": "Bond issuer_id references AAPL",
        "effective_from": NOW,
    }
    payload.update(overrides)
    return AssertionProposal(**payload)  # type: ignore[arg-type]


def _evidence(evidence_id: str = "ev-1") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        source_ref="sample://AAPL_BOND_2030",
        content_sha256=DIGEST,
        media_type="application/json",
        visibility="internal",
        custody_id="collector-1",
        recorded_at=NOW,
    )


def _transition(fields: dict[str, object]) -> RepositoryTransitionRequest:
    """Build a transition request from a single field mapping (keeps arg count low)."""
    return RepositoryTransitionRequest(**fields)  # type: ignore[arg-type]


def _propose_accepted(repo: RelationshipAssertionRepository, assertion_id: str = "as-1") -> None:
    """Helper: propose then accept an assertion."""
    repo.propose(_proposal(assertion_id), _ctx("proposer"))
    repo.transition(
        _transition(
            {
                "assertion_id": assertion_id,
                "to_state": "Accepted",
                "ctx": _ctx("acceptor"),
                "expected_sequence": 1,
                "rationale": "accept",
            }
        )
    )


class TestProposeIdempotency:
    """Idempotent assertion creation."""

    def test_propose_persists_proposed_event(self, repo, repo_session) -> None:
        """First propose inserts assertion + sequence-1 Proposed event."""
        assertion, event = repo.propose(_proposal(), _ctx("proposer"))
        repo_session.commit()
        assert assertion.assertion_id == "as-1"
        assert event.sequence == 1
        assert event.to_state == "Proposed"
        assert repo.current_state("as-1") == "Proposed"
        assert repo_session.get(RelationshipAssertionORM, "as-1") is not None

    def test_propose_is_idempotent_for_identical_payload(self, repo, repo_session) -> None:
        """Repeating propose with the same payload returns the original row/event."""
        first, event_a = repo.propose(_proposal(), _ctx("proposer"))
        second, event_b = repo.propose(_proposal(), _ctx("proposer"))
        repo_session.commit()
        assert first.assertion_id == second.assertion_id
        assert event_a.event_id == event_b.event_id
        events = (
            repo_session.execute(
                select(RelationshipAssertionEventORM).where(RelationshipAssertionEventORM.assertion_id == "as-1")
            )
            .scalars()
            .all()
        )
        assert len(events) == 1

    def test_propose_conflict_on_different_payload(self, repo) -> None:
        """Same id with a different proposition fails closed."""
        repo.propose(_proposal(), _ctx("proposer"))
        proposal = _proposal(proposition="Different proposition text")
        ctx = _ctx("proposer")
        with pytest.raises(ValidationError, match="different proposition"):
            repo.propose(proposal, ctx)


class TestTransitionsAndIllegal:
    """Persisted lifecycle transitions and illegal rejection."""

    def test_full_happy_path_accept_dispute_reaffirm(self, repo, repo_session) -> None:
        """Accepted → Disputed → Accepted persists ordered events."""
        repo.propose(_proposal(), _ctx("proposer"))
        repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Accepted",
                    "ctx": _ctx("acceptor"),
                    "expected_sequence": 1,
                    "rationale": "a",
                }
            )
        )
        repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Disputed",
                    "ctx": _ctx("disputer"),
                    "expected_sequence": 2,
                    "rationale": "d",
                }
            )
        )
        repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Accepted",
                    "ctx": _ctx("acceptor"),
                    "expected_sequence": 3,
                    "rationale": "r",
                }
            )
        )
        repo_session.commit()
        assert repo.current_state("as-1") == "Accepted"
        assert repo.max_sequence("as-1") == 4

    def test_illegal_transition_rejected(self, repo) -> None:
        """Out-of-matrix transitions never append events."""
        repo.propose(_proposal(), _ctx("proposer"))
        request = _transition(
            {
                "assertion_id": "as-1",
                "to_state": "Disputed",
                "ctx": _ctx("disputer"),
                "expected_sequence": 1,
                "rationale": "illegal",
            }
        )
        with pytest.raises(IllegalTransition):
            repo.transition(request)
        assert repo.max_sequence("as-1") == 1

    def test_unauthorized_transition_rejected(self, repo) -> None:
        """Wrong authority does not mutate history."""
        repo.propose(_proposal(), _ctx("proposer"))
        request = _transition(
            {
                "assertion_id": "as-1",
                "to_state": "Accepted",
                "ctx": _ctx("proposer"),
                "expected_sequence": 1,
                "rationale": "nope",
            }
        )
        with pytest.raises(UnauthorizedTransition):
            repo.transition(request)
        assert repo.current_state("as-1") == "Proposed"

    def test_assertion_rows_remain_immutable(self, repo, repo_session) -> None:
        """Schema immutability guards still reject UPDATE on assertion rows."""
        repo.propose(_proposal(), _ctx("proposer"))
        repo_session.commit()
        row = repo_session.get(RelationshipAssertionORM, "as-1")
        assert row is not None
        row.proposition = "mutated"
        with pytest.raises(DBAPIError):
            repo_session.commit()
        repo_session.rollback()


class TestConcurrency:
    """expected_sequence CAS behaviour."""

    def test_stale_expected_sequence_conflicts(self, repo) -> None:
        """Two writers with the same expected_sequence: second fails."""
        repo.propose(_proposal(), _ctx("proposer"))
        repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Accepted",
                    "ctx": _ctx("acceptor"),
                    "expected_sequence": 1,
                    "rationale": "a",
                }
            )
        )
        request = _transition(
            {
                "assertion_id": "as-1",
                "to_state": "Disputed",
                "ctx": _ctx("disputer"),
                "expected_sequence": 1,
                "rationale": "stale",
            }
        )
        with pytest.raises(ConcurrencyConflict):
            repo.transition(request)
        assert repo.current_state("as-1") == "Accepted"
        assert repo.max_sequence("as-1") == 2


class TestEvidenceRegistration:
    """Digest-validated evidence + append-only links."""

    def test_register_evidence_with_digest(self, repo, repo_session) -> None:
        """Evidence digests are normalized and links are queryable as-of known_at."""
        repo.propose(_proposal(), _ctx("proposer"))
        evidence, link = repo.register_evidence(
            RegisterEvidenceRequest(
                assertion_id="as-1",
                evidence=_evidence(),
                polarity="supporting",
                ctx=_ctx("proposer"),
            )
        )
        repo_session.commit()
        assert evidence.content_sha256 == DIGEST
        assert link.polarity == "supporting"
        as_of = repo.get_as_of("as-1", known_at=NOW + timedelta(hours=1))
        assert as_of is not None
        assert len(as_of.evidence_links) == 1

    def test_invalid_digest_rejected(self, repo) -> None:
        """Malformed digests never insert evidence rows."""
        repo.propose(_proposal(), _ctx("proposer"))
        bad = EvidenceRecord(
            evidence_id="ev-bad",
            source_ref="sample://x",
            content_sha256="not-a-digest",
            media_type="application/json",
            visibility="internal",
            custody_id="c1",
            recorded_at=NOW,
        )
        request = RegisterEvidenceRequest(
            assertion_id="as-1",
            evidence=bad,
            polarity="supporting",
            ctx=_ctx("proposer"),
        )
        with pytest.raises(ValidationError, match="content_sha256"):
            repo.register_evidence(request)

    def test_evidence_link_idempotent(self, repo) -> None:
        """Duplicate assertion/evidence link returns the original polarity link."""
        repo.propose(_proposal(), _ctx("proposer"))
        req = RegisterEvidenceRequest(
            assertion_id="as-1",
            evidence=_evidence(),
            polarity="supporting",
            ctx=_ctx("proposer"),
        )
        _, link_a = repo.register_evidence(req)
        _, link_b = repo.register_evidence(req)
        assert link_a.link_id == link_b.link_id

    def test_evidence_metadata_mismatch_rejected(self, repo) -> None:
        """Reusing an evidence id with different immutable metadata fails closed."""
        repo.propose(_proposal(), _ctx("proposer"))
        repo.register_evidence(
            RegisterEvidenceRequest(
                assertion_id="as-1",
                evidence=_evidence(),
                polarity="supporting",
                ctx=_ctx("proposer"),
            )
        )
        changed = EvidenceRecord(
            evidence_id="ev-1",
            source_ref="sample://AAPL_BOND_2030",
            content_sha256=DIGEST,
            media_type="application/json",
            visibility="internal",
            custody_id="collector-1",
            recorded_at=NOW,
            licensing="CC-BY-4.0",
        )
        request = RegisterEvidenceRequest(
            assertion_id="as-1",
            evidence=changed,
            polarity="supporting",
            ctx=_ctx("proposer"),
        )
        with pytest.raises(ValidationError, match="different metadata"):
            repo.register_evidence(request)


class TestSupersessionAtomics:
    """Atomic successor acceptance + predecessor supersession."""

    def test_supersede_atomic_commits_both_sides(self, repo, repo_session) -> None:
        """Successor Accepted and predecessor Superseded land together."""
        _propose_accepted(repo, "as-pred")
        successor, propose_event, accept_event, supersede_event = repo.supersede_atomic(
            SupersedeAtomicRequest(
                predecessor_id="as-pred",
                successor_proposal=_proposal("as-succ"),
                ctx=_ctx("proposer", "acceptor"),
                expected_sequence=2,
                rationale="refresh evidence",
            )
        )
        repo_session.commit()
        assert successor.assertion_id == "as-succ"
        assert propose_event.to_state == "Proposed"
        assert accept_event.to_state == "Accepted"
        assert supersede_event.to_state == "Superseded"
        assert supersede_event.successor_assertion_id == "as-succ"
        assert repo.current_state("as-pred") == "Superseded"
        assert repo.current_state("as-succ") == "Accepted"

    def test_supersede_atomic_rolls_back_on_concurrency(self, repo, repo_session) -> None:
        """Failed CAS leaves neither orphan successor nor superseded predecessor."""
        _propose_accepted(repo, "as-pred")
        repo_session.commit()
        request = SupersedeAtomicRequest(
            predecessor_id="as-pred",
            successor_proposal=_proposal("as-succ"),
            ctx=_ctx("proposer", "acceptor"),
            expected_sequence=1,
            rationale="stale supersede",
        )
        with pytest.raises(ConcurrencyConflict):
            repo.supersede_atomic(request)
        repo_session.rollback()
        assert repo_session.get(RelationshipAssertionORM, "as-succ") is None
        assert repo.current_state("as-pred") == "Accepted"

    def test_self_supersession_rejected(self, repo) -> None:
        """Self-supersession is forbidden at the repository boundary."""
        _propose_accepted(repo, "as-1")
        request = SupersedeAtomicRequest(
            predecessor_id="as-1",
            successor_proposal=_proposal("as-1"),
            ctx=_ctx("proposer", "acceptor"),
            expected_sequence=2,
            rationale="self",
        )
        with pytest.raises(SupersessionCycle):
            repo.supersede_atomic(request)

    @pytest.mark.parametrize(
        ("successor_id", "seed_proposed", "match"),
        [
            ("as-missing", False, "unknown successor"),
            ("as-succ", True, "must be Accepted"),
        ],
        ids=["unknown_successor", "inactive_successor"],
    )
    def test_transition_supersede_requires_accepted_successor(
        self,
        repo,
        successor_id: str,
        seed_proposed: bool,
        match: str,
    ) -> None:
        """Direct supersession requires an existing Accepted successor."""
        _propose_accepted(repo, "as-pred")
        if seed_proposed:
            repo.propose(_proposal(successor_id), _ctx("proposer"))
        request = _transition(
            {
                "assertion_id": "as-pred",
                "to_state": "Superseded",
                "ctx": _ctx("acceptor"),
                "expected_sequence": 2,
                "rationale": "invalid successor",
                "successor_assertion_id": successor_id,
            }
        )
        with pytest.raises(ValidationError, match=match):
            repo.transition(request)
        assert repo.current_state("as-pred") == "Accepted"
        if seed_proposed:
            assert repo.current_state(successor_id) == "Proposed"


class TestGetAsOf:
    """Bitemporal reconstruction."""

    def test_get_as_of_hides_future_events(self, repo) -> None:
        """Events recorded after known_at do not affect reconstructed state."""
        t0 = NOW
        repo.propose(_proposal(), _ctx("proposer"), recorded_at=t0)
        repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Accepted",
                    "ctx": _ctx("acceptor"),
                    "expected_sequence": 1,
                    "rationale": "accept",
                    "recorded_at": t0 + timedelta(hours=2),
                }
            )
        )
        early = repo.get_as_of("as-1", known_at=t0 + timedelta(hours=1))
        late = repo.get_as_of("as-1", known_at=t0 + timedelta(hours=3))
        assert early is not None and early.state == "Proposed"
        assert late is not None and late.state == "Accepted"

    def test_get_as_of_effective_window(self, repo) -> None:
        """effective_at outside the assertion window returns None."""
        repo.propose(
            _proposal(effective_from=NOW, effective_to=NOW + timedelta(days=1)),
            _ctx("proposer"),
        )
        assert repo.get_as_of("as-1", known_at=NOW + timedelta(hours=1), effective_at=NOW) is not None
        assert (
            repo.get_as_of(
                "as-1",
                known_at=NOW + timedelta(hours=1),
                effective_at=NOW + timedelta(days=2),
            )
            is None
        )
