"""Integration tests for GRAC v1 append-only assertion repository."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from inspect import signature
from queue import Queue
from threading import Event
from time import monotonic, sleep
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

from src.data.database import create_session_factory, init_db
from src.data.relationship_assertion_db_models import (
    RelationshipAssertionEventORM,
    RelationshipAssertionORM,
    RelationshipEvidenceORM,
)
from src.data.relationship_assertion_repository import (
    RegisterEvidenceRequest,
    RelationshipAssertionRepository,
    RepositoryTransitionRequest,
    SupersedeAtomicRequest,
)
from src.governance.relationship_assertion import (
    Assertion,
    AssertionEvent,
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
SUPERSESSION_LOCK_NAMESPACE = 0x46415244
SUPERSESSION_LOCK_RESOURCE = 0x47524143
pytestmark = pytest.mark.integration


def _postgres_url() -> str | None:
    """Return the explicitly configured PostgreSQL integration-test URL."""
    for variable in ("ASSET_GRAPH_DATABASE_URL", "GRAC_SCHEMA_DATABASE_URL"):
        url = os.getenv(variable)
        if url and url.startswith("postgresql"):
            return url
    return None


@pytest.fixture
def postgres_engine():
    """Yield a disposable schema-isolated PostgreSQL engine."""
    postgres_url = _postgres_url()
    if postgres_url is None:
        pytest.skip("PostgreSQL URL not set (ASSET_GRAPH_DATABASE_URL / GRAC_SCHEMA_DATABASE_URL)")

    schema_name = f"grac_test_{uuid4().hex}"
    admin_engine = create_engine(postgres_url, future=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema_name))
    isolated_engine = create_engine(
        postgres_url,
        future=True,
        connect_args={"options": f"-csearch_path={schema_name}"},
    )
    try:
        init_db(isolated_engine)
        yield isolated_engine
    finally:
        isolated_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema_name, cascade=True, if_exists=True))
        admin_engine.dispose()


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
    """Repository bound to the test session with a deterministic advancing clock."""
    stamps = {"t": NOW}

    def clock() -> datetime:
        current = stamps["t"]
        stamps["t"] = current + timedelta(milliseconds=1)
        return current

    return RelationshipAssertionRepository(repo_session, clock=clock)


def _ctx(*roles: str, actor_id: str = "actor-1") -> AuthorityContext:
    return AuthorityContext(
        actor_id=actor_id,
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


def _pending_evidence_row(evidence_id: str) -> RelationshipEvidenceORM:
    """Build unrelated pending outer-transaction work for savepoint tests."""
    return RelationshipEvidenceORM(
        id=evidence_id,
        source_ref=f"sample://{evidence_id}",
        content_sha256=DIGEST,
        media_type="application/json",
        visibility="internal",
        custody_id="collector-outer",
        recorded_at=NOW,
    )


def _transition(fields: dict[str, object]) -> RepositoryTransitionRequest:
    """Build a transition request from a single field mapping (keeps arg count low)."""
    return RepositoryTransitionRequest(**fields)  # type: ignore[arg-type]


def _propose_accepted(repo: RelationshipAssertionRepository, assertion_id: str = "as-1") -> None:
    """Helper: propose then accept an assertion."""
    repo.propose(_proposal(assertion_id), _ctx("proposer", actor_id="proposer-1"))
    repo.transition(
        _transition(
            {
                "assertion_id": assertion_id,
                "to_state": "Accepted",
                "ctx": _ctx("acceptor", actor_id="determiner-1"),
                "expected_sequence": 1,
                "rationale": "accept",
            }
        )
    )


def _track_supersession_lock_order(repo, monkeypatch) -> list[str]:
    """Spy on graph locking and cycle validation without replacing behavior."""
    calls: list[str] = []
    original_lock = repo._lock_supersession_graph
    original_lookup = repo._successor_chain_lookup

    def track_lock() -> None:
        calls.append("lock")
        original_lock()

    def track_chain_lookup(assertion_id: str):
        calls.append("cycle")
        return original_lookup(assertion_id)

    monkeypatch.setattr(repo, "_lock_supersession_graph", track_lock)
    monkeypatch.setattr(repo, "_successor_chain_lookup", track_chain_lookup)
    return calls


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

    def test_propose_idempotent_reuse_revalidates_proposer_role(self, repo) -> None:
        """An idempotency hit does not bypass current proposer authority."""
        repo.propose(_proposal(), _ctx("proposer", actor_id="owner"))
        proposal = _proposal()
        ctx = _ctx("acceptor", actor_id="owner")

        with pytest.raises(UnauthorizedTransition):
            repo.propose(proposal, ctx)

        assert repo.max_sequence("as-1") == 1

    def test_propose_idempotent_reuse_requires_proposer_of_record(self, repo) -> None:
        """A foreign proposer cannot reuse another actor's assertion id."""
        repo.propose(_proposal(), _ctx("proposer", actor_id="owner"))
        proposal = _proposal()
        ctx = _ctx("proposer", actor_id="foreign-proposer")

        with pytest.raises(UnauthorizedTransition, match="proposer of record"):
            repo.propose(proposal, ctx)

        assert repo.max_sequence("as-1") == 1

    def test_propose_conflict_on_different_payload(self, repo) -> None:
        """Same id with a different proposition fails closed."""
        repo.propose(_proposal(), _ctx("proposer"))
        proposal = _proposal(proposition="Different proposition text")
        ctx = _ctx("proposer")
        with pytest.raises(ValidationError, match="different proposition"):
            repo.propose(proposal, ctx)

    def test_propose_race_preserves_pending_outer_work(self, repo, repo_session, monkeypatch) -> None:
        """A raced proposal insert rolls back only its savepoint."""
        proposal = _proposal()
        repo.propose(proposal, _ctx("proposer"))
        repo_session.commit()
        existing = repo_session.get(RelationshipAssertionORM, proposal.assertion_id)
        assert existing is not None
        repo_session.expunge(existing)
        pending = _pending_evidence_row("ev-outer-propose")
        repo_session.add(pending)
        original_get = repo_session.get
        get_mock = Mock(side_effect=(None, existing))
        monkeypatch.setattr(repo_session, "get", get_mock)
        assertion, _event = repo.propose(proposal, _ctx("proposer"))
        monkeypatch.setattr(repo_session, "get", original_get)

        assert assertion.assertion_id == proposal.assertion_id
        assert get_mock.call_count == 2
        assert repo_session.get(RelationshipEvidenceORM, pending.id) is not None
        repo_session.commit()


class TestTransitionsAndIllegal:
    """Persisted lifecycle transitions and illegal rejection."""

    def test_full_happy_path_accept_dispute_reaffirm(self, repo, repo_session) -> None:
        """Accepted → Disputed → Accepted persists ordered events."""
        repo.propose(_proposal(), _ctx("proposer", actor_id="proposer"))
        repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Accepted",
                    "ctx": _ctx("acceptor", actor_id="determiner"),
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
                    "ctx": _ctx("disputer", actor_id="disputer"),
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
                    "ctx": _ctx("acceptor", actor_id="determiner"),
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

    @pytest.mark.parametrize("to_state", ["Accepted", "Rejected"])
    def test_proposer_cannot_make_own_determination(self, repo, to_state: str) -> None:
        """Accept and reject require a principal distinct from the proposer."""
        repo.propose(_proposal(), _ctx("proposer", actor_id="owner"))
        request = _transition(
            {
                "assertion_id": "as-1",
                "to_state": to_state,
                "ctx": _ctx("acceptor", actor_id="owner"),
                "expected_sequence": 1,
                "rationale": "self determination",
            }
        )

        with pytest.raises(UnauthorizedTransition, match="must differ"):
            repo.transition(request)

        assert repo.current_state("as-1") == "Proposed"

    def test_proposer_cannot_reaffirm_own_assertion(self, repo) -> None:
        """Reaffirmation preserves proposer/determiner separation."""
        repo.propose(_proposal(), _ctx("proposer", actor_id="owner"))
        repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Accepted",
                    "ctx": _ctx("acceptor", actor_id="reviewer"),
                    "expected_sequence": 1,
                    "rationale": "accept",
                }
            )
        )
        repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Disputed",
                    "ctx": _ctx("disputer", actor_id="challenger"),
                    "expected_sequence": 2,
                    "rationale": "dispute",
                }
            )
        )

        request = _transition(
            {
                "assertion_id": "as-1",
                "to_state": "Accepted",
                "ctx": _ctx("acceptor", actor_id="owner"),
                "expected_sequence": 3,
                "rationale": "self reaffirm",
            }
        )
        with pytest.raises(UnauthorizedTransition, match="must differ"):
            repo.transition(request)

        assert repo.current_state("as-1") == "Disputed"

    def test_withdrawal_requires_proposer_of_record(self, repo) -> None:
        """A proposer role cannot withdraw another actor's proposal."""
        repo.propose(_proposal(), _ctx("proposer", actor_id="owner"))
        foreign_request = _transition(
            {
                "assertion_id": "as-1",
                "to_state": "Withdrawn",
                "ctx": _ctx("proposer", actor_id="foreign-proposer"),
                "expected_sequence": 1,
                "rationale": "foreign withdrawal",
            }
        )

        with pytest.raises(UnauthorizedTransition, match="proposer of record"):
            repo.transition(foreign_request)

        event = repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Withdrawn",
                    "ctx": _ctx("proposer", actor_id="owner"),
                    "expected_sequence": 1,
                    "rationale": "owner withdrawal",
                }
            )
        )
        assert event.actor_id == "owner"
        assert repo.current_state("as-1") == "Withdrawn"

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
                    "ctx": _ctx("acceptor", actor_id="determiner"),
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

    def test_event_insert_conflict_preserves_pending_outer_work(self, repo, repo_session) -> None:
        """A failed guarded event insert does not roll back unrelated work."""
        _propose_accepted(repo)
        existing_event_id = (
            repo_session.execute(
                select(RelationshipAssertionEventORM.id).where(RelationshipAssertionEventORM.assertion_id == "as-1")
            )
            .scalars()
            .first()
        )
        repo_session.commit()
        pending = _pending_evidence_row("ev-outer-event")
        repo_session.add(pending)
        request = _transition(
            {
                "assertion_id": "as-1",
                "to_state": "Disputed",
                "ctx": _ctx("disputer"),
                "expected_sequence": 2,
                "rationale": "duplicate event id",
                "event_id": existing_event_id,
            }
        )

        with pytest.raises(ConcurrencyConflict):
            repo.transition(request)

        assert repo_session.get(RelationshipEvidenceORM, pending.id) is not None
        assert repo.current_state("as-1") == "Accepted"
        repo_session.commit()


class TestEvidenceRegistration:
    """Digest-validated evidence + append-only links."""

    def test_register_evidence_with_digest(self, repo, repo_session) -> None:
        """Evidence digests are normalized and links are queryable as-of known_at."""
        repo.propose(_proposal(), _ctx("proposer"))
        grouped_upper_digest = "-".join(["B" * 4] * 16)
        evidence, link = repo.register_evidence(
            RegisterEvidenceRequest(
                assertion_id="as-1",
                evidence=EvidenceRecord(
                    evidence_id="ev-1",
                    source_ref="sample://AAPL_BOND_2030",
                    content_sha256=grouped_upper_digest,
                    media_type="application/json",
                    visibility="internal",
                    custody_id="collector-1",
                    recorded_at=NOW,
                ),
                polarity="supporting",
                ctx=_ctx("proposer"),
            )
        )
        repo_session.commit()
        assert evidence.content_sha256 == DIGEST
        assert evidence.recorded_at == NOW + timedelta(milliseconds=1)
        assert link.recorded_at == evidence.recorded_at
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

    def test_evidence_link_re_registration_rejects_conflicting_polarity(self, repo) -> None:
        """An existing assertion/evidence pair cannot change polarity."""
        repo.propose(_proposal(), _ctx("proposer"))
        evidence = _evidence()
        ctx = _ctx("proposer")
        supporting_request = RegisterEvidenceRequest(
            assertion_id="as-1",
            evidence=evidence,
            polarity="supporting",
            ctx=ctx,
        )
        opposing_request = RegisterEvidenceRequest(
            assertion_id="as-1",
            evidence=evidence,
            polarity="opposing",
            ctx=ctx,
        )
        repo.register_evidence(supporting_request)

        with pytest.raises(ValidationError, match="different polarity"):
            repo.register_evidence(opposing_request)

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

    def test_link_insert_conflict_preserves_pending_outer_work(self, repo, repo_session) -> None:
        """A failed guarded evidence-link insert does not roll back unrelated work."""
        repo.propose(_proposal("as-1"), _ctx("proposer"))
        repo.propose(_proposal("as-2"), _ctx("proposer"))
        repo.register_evidence(
            RegisterEvidenceRequest(
                assertion_id="as-1",
                evidence=_evidence("ev-1"),
                polarity="supporting",
                ctx=_ctx("proposer"),
                link_id="link-shared",
            )
        )
        repo_session.commit()
        pending = _pending_evidence_row("ev-outer-link")
        repo_session.add(pending)
        request = RegisterEvidenceRequest(
            assertion_id="as-2",
            evidence=_evidence("ev-2"),
            polarity="supporting",
            ctx=_ctx("proposer"),
            link_id="link-shared",
        )

        with pytest.raises(ConcurrencyConflict):
            repo.register_evidence(request)

        assert repo_session.get(RelationshipEvidenceORM, pending.id) is not None
        repo_session.commit()


class TestSupersessionAtomics:
    """Atomic successor acceptance + predecessor supersession."""

    def test_supersede_atomic_commits_both_sides(self, repo, repo_session) -> None:
        """Successor Accepted and predecessor Superseded land together."""
        _propose_accepted(repo, "as-pred")
        successor, propose_event, accept_event, supersede_event = repo.supersede_atomic(
            SupersedeAtomicRequest(
                predecessor_id="as-pred",
                successor_proposal=_proposal("as-succ"),
                proposal_ctx=_ctx("proposer", actor_id="successor-proposer"),
                determination_ctx=_ctx("acceptor", actor_id="supersession-determiner"),
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
        assert propose_event.actor_id == "successor-proposer"
        assert accept_event.actor_id == "supersession-determiner"
        assert supersede_event.actor_id == "supersession-determiner"
        assert propose_event.recorded_at < accept_event.recorded_at
        assert accept_event.recorded_at < supersede_event.recorded_at
        assert repo.current_state("as-pred") == "Superseded"
        assert repo.current_state("as-succ") == "Accepted"

    def test_supersede_atomic_preserves_cross_stream_temporal_order(self, repo_session) -> None:
        """A backward clock cannot backdate any successor or supersession event."""
        clock_values = iter(
            (
                NOW + timedelta(hours=1),
                NOW + timedelta(hours=1, milliseconds=1),
                NOW,
                NOW,
                NOW,
            )
        )

        def clock() -> datetime:
            return next(clock_values, NOW)

        repository = RelationshipAssertionRepository(repo_session, clock=clock)
        repository.propose(
            _proposal("as-pred"),
            _ctx("proposer", actor_id="proposer-1"),
        )
        predecessor_accepted = repository.transition(
            _transition(
                {
                    "assertion_id": "as-pred",
                    "to_state": "Accepted",
                    "ctx": _ctx("acceptor", actor_id="reviewer-1"),
                    "expected_sequence": 1,
                    "rationale": "accept",
                }
            )
        )
        _successor, proposed, accepted, superseded = repository.supersede_atomic(
            SupersedeAtomicRequest(
                predecessor_id="as-pred",
                successor_proposal=_proposal("as-succ"),
                proposal_ctx=_ctx("proposer", actor_id="successor-proposer"),
                determination_ctx=_ctx("acceptor", actor_id="supersession-determiner"),
                expected_sequence=2,
                rationale="refresh evidence",
            )
        )

        successor_at_predecessor_acceptance = repository.get_as_of(
            "as-succ",
            known_at=predecessor_accepted.recorded_at,
        )
        predecessor_as_of_proposal = repository.get_as_of("as-pred", known_at=proposed.recorded_at)
        successor_as_of_proposal = repository.get_as_of("as-succ", known_at=proposed.recorded_at)
        predecessor_as_of_acceptance = repository.get_as_of("as-pred", known_at=accepted.recorded_at)
        successor_as_of_acceptance = repository.get_as_of("as-succ", known_at=accepted.recorded_at)
        assert predecessor_accepted.recorded_at < proposed.recorded_at < accepted.recorded_at < superseded.recorded_at
        assert successor_at_predecessor_acceptance is None
        assert predecessor_as_of_proposal is not None and predecessor_as_of_proposal.state == "Accepted"
        assert successor_as_of_proposal is not None and successor_as_of_proposal.state == "Proposed"
        assert predecessor_as_of_acceptance is not None and predecessor_as_of_acceptance.state == "Accepted"
        assert successor_as_of_acceptance is not None and successor_as_of_acceptance.state == "Accepted"

    def test_supersede_atomic_locks_graph_before_chain_validation(self, repo, monkeypatch) -> None:
        """Atomic supersession takes the graph lock before validating its chain."""
        _propose_accepted(repo, "as-pred")
        calls = _track_supersession_lock_order(repo, monkeypatch)
        repo.supersede_atomic(
            SupersedeAtomicRequest(
                predecessor_id="as-pred",
                successor_proposal=_proposal("as-succ"),
                proposal_ctx=_ctx("proposer", actor_id="successor-proposer"),
                determination_ctx=_ctx("acceptor", actor_id="supersession-determiner"),
                expected_sequence=2,
                rationale="refresh evidence",
            )
        )

        assert calls[:2] == ["lock", "cycle"]

    def test_supersede_atomic_rolls_back_on_concurrency(self, repo, repo_session) -> None:
        """Failed CAS leaves neither orphan successor nor superseded predecessor."""
        _propose_accepted(repo, "as-pred")
        repo_session.commit()
        request = SupersedeAtomicRequest(
            predecessor_id="as-pred",
            successor_proposal=_proposal("as-succ"),
            proposal_ctx=_ctx("proposer", actor_id="successor-proposer"),
            determination_ctx=_ctx("acceptor", actor_id="supersession-determiner"),
            expected_sequence=1,
            rationale="stale supersede",
        )
        with pytest.raises(ConcurrencyConflict):
            repo.supersede_atomic(request)
        assert repo_session.get(RelationshipAssertionORM, "as-succ") is None
        assert repo.current_state("as-pred") == "Accepted"
        repo_session.rollback()

    def test_supersede_atomic_rolls_back_after_late_authority_failure(self, repo, repo_session) -> None:
        """A failed successor determination leaves no orphan and preserves outer work."""
        _propose_accepted(repo, "as-pred")
        repo_session.commit()
        pending = _pending_evidence_row("ev-outer-supersede")
        repo_session.add(pending)
        request = SupersedeAtomicRequest(
            predecessor_id="as-pred",
            successor_proposal=_proposal("as-succ"),
            proposal_ctx=_ctx("proposer", actor_id="successor-proposer"),
            determination_ctx=_ctx("disputer", actor_id="unauthorized-determiner"),
            expected_sequence=2,
            rationale="unauthorized supersede",
        )

        with pytest.raises(UnauthorizedTransition):
            repo.supersede_atomic(request)

        assert repo_session.get(RelationshipAssertionORM, "as-succ") is None
        assert repo.current_state("as-pred") == "Accepted"
        assert repo_session.get(RelationshipEvidenceORM, pending.id) is not None
        repo_session.commit()

    @pytest.mark.parametrize("determination_actor", ["proposer-1", "successor-proposer"])
    def test_supersede_atomic_requires_distinct_determiner(self, repo, repo_session, determination_actor: str) -> None:
        """The determiner must differ from both predecessor and successor proposers."""
        _propose_accepted(repo, "as-pred")
        repo_session.commit()
        request = SupersedeAtomicRequest(
            predecessor_id="as-pred",
            successor_proposal=_proposal("as-succ"),
            proposal_ctx=_ctx("proposer", actor_id="successor-proposer"),
            determination_ctx=_ctx("acceptor", actor_id=determination_actor),
            expected_sequence=2,
            rationale="same-actor supersede",
        )

        with pytest.raises(UnauthorizedTransition, match="must differ"):
            repo.supersede_atomic(request)

        assert repo_session.get(RelationshipAssertionORM, "as-succ") is None
        assert repo.current_state("as-pred") == "Accepted"
        repo_session.rollback()

    def test_self_supersession_rejected(self, repo) -> None:
        """Self-supersession is forbidden at the repository boundary."""
        _propose_accepted(repo, "as-1")
        request = SupersedeAtomicRequest(
            predecessor_id="as-1",
            successor_proposal=_proposal("as-1"),
            proposal_ctx=_ctx("proposer", actor_id="successor-proposer"),
            determination_ctx=_ctx("acceptor", actor_id="supersession-determiner"),
            expected_sequence=2,
            rationale="self",
        )
        with pytest.raises(SupersessionCycle):
            repo.supersede_atomic(request)

    def test_multi_hop_supersession_cycle_rejected(self, repo) -> None:
        """A successor cannot supersede back to an assertion in its chain."""
        _propose_accepted(repo, "as-a")
        repo.supersede_atomic(
            SupersedeAtomicRequest(
                predecessor_id="as-a",
                successor_proposal=_proposal("as-b"),
                proposal_ctx=_ctx("proposer", actor_id="successor-proposer"),
                determination_ctx=_ctx("acceptor", actor_id="supersession-determiner"),
                expected_sequence=2,
                rationale="replace A with B",
            )
        )
        cycle_request = SupersedeAtomicRequest(
            predecessor_id="as-b",
            successor_proposal=_proposal("as-a"),
            proposal_ctx=_ctx("proposer", actor_id="next-proposer"),
            determination_ctx=_ctx("acceptor", actor_id="next-determiner"),
            expected_sequence=2,
            rationale="replace B with A",
        )

        with pytest.raises(SupersessionCycle):
            repo.supersede_atomic(cycle_request)

    def test_transition_rejects_direct_supersession(self, repo) -> None:
        """Supersession is available only through the atomic repository path."""
        _propose_accepted(repo, "as-pred")
        request = _transition(
            {
                "assertion_id": "as-pred",
                "to_state": "Superseded",
                "ctx": _ctx("acceptor", actor_id="supersession-determiner"),
                "expected_sequence": 2,
                "rationale": "direct bypass",
                "successor_assertion_id": "as-succ",
            }
        )

        with pytest.raises(IllegalTransition, match="only through supersede_atomic"):
            repo.transition(request)

        assert repo.current_state("as-pred") == "Accepted"


class TestPostgresSupersessionSerialization:
    """Transaction-scoped serialization on two independent PostgreSQL sessions."""

    def test_failed_supersession_releases_advisory_lock(self, postgres_engine) -> None:
        """A failed atomic operation releases its lock while preserving outer work."""
        factory = create_session_factory(postgres_engine)
        token = uuid4().hex[:8]
        predecessor_a = f"{token}-pred-a"
        predecessor_b = f"{token}-pred-b"
        successor_a = f"{token}-succ-a"
        successor_b = f"{token}-succ-b"
        pending_id = f"{token}-outer"

        setup_session = factory()
        try:
            setup_repo = RelationshipAssertionRepository(setup_session)
            _propose_accepted(setup_repo, predecessor_a)
            _propose_accepted(setup_repo, predecessor_b)
            setup_session.commit()
        finally:
            setup_session.close()

        first_session = factory()
        second_session = factory()
        try:
            first_repo = RelationshipAssertionRepository(first_session)
            first_session.add(_pending_evidence_row(pending_id))
            failed_request = SupersedeAtomicRequest(
                predecessor_id=predecessor_a,
                successor_proposal=_proposal(successor_a),
                proposal_ctx=_ctx("proposer", actor_id="successor-proposer-a"),
                determination_ctx=_ctx("disputer", actor_id="unauthorized-determiner"),
                expected_sequence=2,
                rationale="failed serialized supersession",
            )

            with pytest.raises(UnauthorizedTransition):
                first_repo.supersede_atomic(failed_request)

            assert first_repo.current_state(predecessor_a) == "Accepted"
            assert first_session.get(RelationshipAssertionORM, successor_a) is None
            assert first_session.get(RelationshipEvidenceORM, pending_id) is not None
            assert first_session.in_transaction()

            lock_available = second_session.execute(
                text("SELECT pg_try_advisory_xact_lock(:namespace, :resource)"),
                {
                    "namespace": SUPERSESSION_LOCK_NAMESPACE,
                    "resource": SUPERSESSION_LOCK_RESOURCE,
                },
            ).scalar_one()
            assert lock_available is True

            second_repo = RelationshipAssertionRepository(second_session)
            successor, _propose, _accept, _supersede = second_repo.supersede_atomic(
                SupersedeAtomicRequest(
                    predecessor_id=predecessor_b,
                    successor_proposal=_proposal(successor_b),
                    proposal_ctx=_ctx("proposer", actor_id="successor-proposer-b"),
                    determination_ctx=_ctx("acceptor", actor_id="supersession-determiner-b"),
                    expected_sequence=2,
                    rationale="successful serialized supersession",
                )
            )
            assert successor.assertion_id == successor_b
            second_session.commit()
            first_session.commit()
        finally:
            second_session.rollback()
            second_session.close()
            first_session.rollback()
            first_session.close()

    def test_atomic_supersessions_share_advisory_transaction_lock(self, postgres_engine) -> None:
        """A second atomic supersession waits until the first transaction releases its lock."""
        factory = create_session_factory(postgres_engine)
        token = uuid4().hex[:8]
        predecessor_a = f"{token}-pred-a"
        predecessor_b = f"{token}-pred-b"
        successor_a = f"{token}-succ-a"
        successor_b = f"{token}-succ-b"

        setup_session = factory()
        try:
            setup_repo = RelationshipAssertionRepository(setup_session)
            _propose_accepted(setup_repo, predecessor_a)
            _propose_accepted(setup_repo, predecessor_b)
            setup_session.commit()
        finally:
            setup_session.close()

        second_pid_queue: Queue[int] = Queue(maxsize=1)
        second_request = SupersedeAtomicRequest(
            predecessor_id=predecessor_b,
            successor_proposal=_proposal(successor_b),
            proposal_ctx=_ctx("proposer", actor_id="successor-proposer-b"),
            determination_ctx=_ctx("acceptor", actor_id="supersession-determiner-b"),
            expected_sequence=2,
            rationale="second serialized supersession",
        )

        def run_second() -> str:
            second_session = factory()
            try:
                second_pid = int(second_session.execute(text("SELECT pg_backend_pid()")).scalar_one())
                second_session.execute(text("SET LOCAL statement_timeout = '10s'"))
                second_pid_queue.put(second_pid)
                second_repo = RelationshipAssertionRepository(second_session)
                successor, _propose, _accept, _supersede = second_repo.supersede_atomic(second_request)
                second_session.commit()
                return successor.assertion_id
            finally:
                second_session.rollback()
                second_session.close()

        first_session = factory()
        try:
            first_pid = int(first_session.execute(text("SELECT pg_backend_pid()")).scalar_one())
            first_repo = RelationshipAssertionRepository(first_session)
            first_repo.supersede_atomic(
                SupersedeAtomicRequest(
                    predecessor_id=predecessor_a,
                    successor_proposal=_proposal(successor_a),
                    proposal_ctx=_ctx("proposer", actor_id="successor-proposer-a"),
                    determination_ctx=_ctx("acceptor", actor_id="supersession-determiner-a"),
                    expected_sequence=2,
                    rationale="first serialized supersession",
                )
            )
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_second)
                try:
                    second_pid = second_pid_queue.get(timeout=5)
                    assert second_pid != first_pid
                    observed = (False, False, False)
                    deadline = monotonic() + 5
                    with postgres_engine.connect() as monitor:
                        while monotonic() < deadline:
                            row = monitor.execute(
                                text("""
                                    SELECT
                                        EXISTS (
                                            SELECT 1 FROM pg_locks
                                            WHERE pid = :first_pid
                                                AND locktype = 'advisory'
                                                AND granted
                                                AND classid::bigint = :namespace
                                                AND objid::bigint = :resource
                                        ),
                                        EXISTS (
                                            SELECT 1 FROM pg_locks
                                            WHERE pid = :second_pid
                                                AND locktype = 'advisory'
                                                AND NOT granted
                                                AND classid::bigint = :namespace
                                                AND objid::bigint = :resource
                                        ),
                                        :first_pid = ANY(pg_blocking_pids(:second_pid))
                                    """),
                                {
                                    "first_pid": first_pid,
                                    "second_pid": second_pid,
                                    "namespace": SUPERSESSION_LOCK_NAMESPACE,
                                    "resource": SUPERSESSION_LOCK_RESOURCE,
                                },
                            ).one()
                            observed = (bool(row[0]), bool(row[1]), bool(row[2]))
                            if all(observed) or future.done():
                                break
                            sleep(0.02)
                    assert observed == (True, True, True)
                    assert not future.done()
                    first_session.commit()
                    assert future.result(timeout=5) == successor_b
                finally:
                    if first_session.in_transaction():
                        first_session.rollback()
        finally:
            first_session.rollback()
            first_session.close()

        verification_session = factory()
        try:
            verification_repo = RelationshipAssertionRepository(verification_session)
            assert verification_repo.current_state(predecessor_a) == "Superseded"
            assert verification_repo.current_state(predecessor_b) == "Superseded"
            assert verification_repo.current_state(successor_a) == "Accepted"
            assert verification_repo.current_state(successor_b) == "Accepted"
        finally:
            verification_session.close()

    def test_atomic_supersession_rejects_concurrent_successor_proposal(self, postgres_engine) -> None:
        """Atomic supersession never adopts a proposal committed by another transaction."""
        factory = create_session_factory(postgres_engine)
        token = uuid4().hex[:8]
        predecessor_id = f"{token}-pred"
        successor_id = f"{token}-succ"
        proposal = _proposal(successor_id)
        proposal_ctx = _ctx("proposer", actor_id="racing-proposer")
        reached_strict_insert = Event()
        release_strict_insert = Event()

        setup_session = factory()
        try:
            _propose_accepted(RelationshipAssertionRepository(setup_session), predecessor_id)
            setup_session.commit()
        finally:
            setup_session.close()

        class _PausingRepository(RelationshipAssertionRepository):
            def _propose_new(
                self,
                pending_proposal: AssertionProposal,
                ctx: AuthorityContext,
                *,
                after: datetime,
            ) -> tuple[Assertion, AssertionEvent]:
                reached_strict_insert.set()
                if not release_strict_insert.wait(timeout=5):
                    raise AssertionError("timed out waiting for the concurrent proposal")
                return super()._propose_new(pending_proposal, ctx, after=after)

        atomic_request = SupersedeAtomicRequest(
            predecessor_id=predecessor_id,
            successor_proposal=proposal,
            proposal_ctx=proposal_ctx,
            determination_ctx=_ctx("acceptor", actor_id="supersession-determiner"),
            expected_sequence=2,
            rationale="reject concurrent successor",
        )

        def run_atomic() -> None:
            atomic_session = factory()
            try:
                atomic_session.execute(text("SET LOCAL statement_timeout = '10s'"))
                atomic_repo = _PausingRepository(atomic_session)
                with pytest.raises(ConcurrencyConflict, match="concurrent successor proposal"):
                    atomic_repo.supersede_atomic(atomic_request)
            finally:
                atomic_session.rollback()
                atomic_session.close()

        ordinary_session = factory()
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_atomic)
                try:
                    assert reached_strict_insert.wait(timeout=5)
                    ordinary_repo = RelationshipAssertionRepository(ordinary_session)
                    ordinary_repo.propose(proposal, proposal_ctx)
                    ordinary_session.commit()
                finally:
                    release_strict_insert.set()
                future.result(timeout=5)
        finally:
            ordinary_session.rollback()
            ordinary_session.close()

        verification_session = factory()
        try:
            verification_repo = RelationshipAssertionRepository(verification_session)
            assert verification_repo.current_state(predecessor_id) == "Accepted"
            assert verification_repo.current_state(successor_id) == "Proposed"
        finally:
            verification_session.close()


class TestServerRecordedAt:
    """Repository-owned timestamp assignment and stream monotonicity."""

    def test_lifecycle_write_apis_expose_no_recorded_at(self) -> None:
        """Callers have no timestamp injection point on lifecycle writes."""
        assert "recorded_at" not in signature(RelationshipAssertionRepository.propose).parameters
        assert "recorded_at" not in RepositoryTransitionRequest.__dataclass_fields__
        assert "recorded_at" not in RegisterEvidenceRequest.__dataclass_fields__
        assert "recorded_at" not in SupersedeAtomicRequest.__dataclass_fields__

    @pytest.mark.parametrize(
        "clock_values",
        [
            (NOW, NOW),
            (NOW, NOW - timedelta(hours=1)),
        ],
        ids=["constant_clock", "backward_clock"],
    )
    def test_event_times_remain_strictly_monotonic(self, repo_session, clock_values) -> None:
        """A constant or backward server clock cannot backdate a later event."""
        values = iter(clock_values)

        def clock() -> datetime:
            return next(values, clock_values[-1])

        repository = RelationshipAssertionRepository(repo_session, clock=clock)
        assertion, proposed = repository.propose(
            _proposal(),
            _ctx("proposer", actor_id="owner"),
        )
        accepted = repository.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Accepted",
                    "ctx": _ctx("acceptor", actor_id="reviewer"),
                    "expected_sequence": 1,
                    "rationale": "accept",
                }
            )
        )

        rows = (
            repo_session.execute(
                select(RelationshipAssertionEventORM)
                .where(RelationshipAssertionEventORM.assertion_id == "as-1")
                .order_by(RelationshipAssertionEventORM.sequence)
            )
            .scalars()
            .all()
        )
        assert assertion.recorded_at == NOW
        assert proposed.recorded_at == NOW
        assert accepted.recorded_at > proposed.recorded_at
        assert rows[1].recorded_at > rows[0].recorded_at


class TestGetAsOf:
    """Bitemporal reconstruction."""

    def test_get_as_of_hides_future_events(self, repo) -> None:
        """Events recorded after known_at do not affect reconstructed state."""
        _assertion, proposed = repo.propose(
            _proposal(),
            _ctx("proposer", actor_id="owner"),
        )
        accepted = repo.transition(
            _transition(
                {
                    "assertion_id": "as-1",
                    "to_state": "Accepted",
                    "ctx": _ctx("acceptor", actor_id="reviewer"),
                    "expected_sequence": 1,
                    "rationale": "accept",
                }
            )
        )
        early = repo.get_as_of("as-1", known_at=proposed.recorded_at)
        late = repo.get_as_of("as-1", known_at=accepted.recorded_at)
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
