"""End-to-end proof for atomic GRAC projection publication."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import api.routers.graph_admin as graph_admin
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.db_models import RebuildJobORM, RebuildJobStatus
from src.data.relationship_assertion_db_models import (
    RelationshipProjectionPublicationORM,
    RelationshipProjectionRevisionORM,
)
from src.data.relationship_assertion_repository import (
    RelationshipAssertionRepository,
    RepositoryTransitionRequest,
)
from src.data.repository import AssetGraphRepository, CoordinationLockRepository, session_scope
from src.data.sample_data import create_sample_database
from src.governance.relationship_assertion import AssertionProposal, AuthorityContext, ValidationError
from src.logic.reconciliation_engine import RebuildCancelledError

UTC = timezone.utc
PURPOSE = "financial_graph_current_view"
PREDICATE_ID = "financial.bond.issuer_reference@1"

pytestmark = pytest.mark.integration


@pytest.fixture
def publication_session_factory(tmp_path: Path) -> Iterator[sessionmaker]:
    """Create one durable SQLite database for publication/restart proof."""
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'grac-publication.db'}")
    init_db(engine)
    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def _authority(actor_id: str, role: str) -> AuthorityContext:
    return AuthorityContext(
        actor_id=actor_id,
        roles=frozenset({role}),  # type: ignore[arg-type]
        policy_version="grac.v1-policy",
        correlation_id="corr-publication",
    )


def _create_running_job(
    factory: sessionmaker,
    *,
    execution_id: str = "exec-publication",
    persist_graph: bool = True,
) -> str:
    """Create an owner-bound running rebuild with an optional prior snapshot."""
    with session_scope(factory) as session:
        repo = AssetGraphRepository(session)
        if persist_graph:
            repo.save_graph(create_sample_database())
        job_id = repo.create_rebuild_job(requested_by="integration-test")
        repo.mark_rebuild_job_running(job_id, execution_id)
        return job_id


def _finalize(
    factory: sessionmaker,
    job_id: str,
    **overrides: Any,
):
    """Invoke the production atomic publication boundary."""
    arguments: dict[str, Any] = {
        "session_factory": factory,
        "job_id": job_id,
        "execution_id": "exec-publication",
        "graph": create_sample_database(),
        "source": "sample",
        "job_started_at": perf_counter(),
        "lock_lost": threading.Event(),
        "cancel_event": threading.Event(),
    }
    arguments.update(overrides)
    return graph_admin._finalize_rebuild_success(  # pylint: disable=protected-access
        **arguments,
    )


def _publication_count(session: Session) -> int:
    return session.execute(select(func.count()).select_from(RelationshipProjectionPublicationORM)).scalar_one()


def _revision_count(session: Session) -> int:
    return session.execute(select(func.count()).select_from(RelationshipProjectionRevisionORM)).scalar_one()


def _canonical_relationships(relationships):
    """Return relationship tuples ordered for semantic snapshot comparison."""
    return {
        source_id: sorted(entries, key=lambda entry: (entry[0], entry[1], entry[2]))
        for source_id, entries in sorted(relationships.items())
    }


def test_empty_unestablished_store_preserves_legacy_graph_and_publishes_once(
    publication_session_factory: sessionmaker,
) -> None:
    """An empty unestablished assertion store leaves graph behaviour unchanged."""
    graph = create_sample_database()
    legacy_relationships = {source: list(entries) for source, entries in graph.relationships.items()}
    job_id = _create_running_job(publication_session_factory)

    response = _finalize(publication_session_factory, job_id, graph=graph)

    assert response.relationship_count == sum(len(entries) for entries in legacy_relationships.values())
    with session_scope(publication_session_factory) as session:
        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        assert job.status == RebuildJobStatus.SUCCEEDED
        assert _publication_count(session) == 1
        assert _revision_count(session) == 1
        publication = session.execute(select(RelationshipProjectionPublicationORM)).scalar_one()
        assert publication.execution_id is not None
        assert publication.execution_id == job.execution_id
        assert publication.rebuild_job_id == job_id
        latest = RelationshipAssertionRepository(session).latest_published_projection(PURPOSE)
        assert latest is not None
        assert latest.revision.edges == ()
        assert latest.revision.governed_scopes == ()
        assert _canonical_relationships(AssetGraphRepository(session).load_graph().relationships) == (
            _canonical_relationships(legacy_relationships)
        )

    with pytest.raises(ValueError):
        _finalize(publication_session_factory, job_id)
    with session_scope(publication_session_factory) as session:
        assert _publication_count(session) == 1
        assert _revision_count(session) == 1


@pytest.mark.parametrize(
    ("execution_id", "expected_error"),
    [
        ("stale-owner", ValueError),
        (None, ValidationError),
        ("", ValidationError),
    ],
)
def test_invalid_publication_identity_rolls_back_everything(
    publication_session_factory: sessionmaker,
    execution_id: str | None,
    expected_error: type[Exception],
) -> None:
    """Null, empty, and mismatched identities cannot expose a candidate."""
    job_id = _create_running_job(publication_session_factory, execution_id="owner-execution")

    with pytest.raises(expected_error):
        _finalize(publication_session_factory, job_id, execution_id=execution_id)

    with session_scope(publication_session_factory) as session:
        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        assert job.status == RebuildJobStatus.RUNNING
        assert _publication_count(session) == 0
        assert _revision_count(session) == 0


def test_dangling_assertion_endpoints_are_deferred_without_blocking_publication(
    publication_session_factory: sessionmaker,
) -> None:
    """Assertions outside the rebuilt asset universe stay dormant instead of violating graph FKs."""
    with session_scope(publication_session_factory) as session:
        repo = RelationshipAssertionRepository(session)
        repo.propose(
            AssertionProposal(
                assertion_id="assertion-missing-bond",
                predicate_id=PREDICATE_ID,
                subject_id="MISSING_BOND",
                object_id="AAPL",
                method_id="bond.issuer_id.resolution@1",
                proposition="AAPL is the issuer of a currently absent bond",
                effective_from=datetime.now(tz=UTC) - timedelta(days=1),
            ),
            _authority("actor-proposer", "proposer"),
            event_id="event-missing-proposed",
        )
        repo.transition(
            RepositoryTransitionRequest(
                assertion_id="assertion-missing-bond",
                to_state="Accepted",
                ctx=_authority("actor-determiner", "acceptor"),
                expected_sequence=1,
                rationale="independent determination",
                event_id="event-missing-accepted",
            )
        )

    job_id = _create_running_job(publication_session_factory)
    _finalize(publication_session_factory, job_id)

    with session_scope(publication_session_factory) as session:
        job = session.get(RebuildJobORM, job_id)
        latest = RelationshipAssertionRepository(session).latest_published_projection(PURPOSE)
        assert job is not None and job.status == RebuildJobStatus.SUCCEEDED
        assert latest is not None and latest.revision.edges == ()
        assert latest.revision.governed_scopes == ()
        restarted = AssetGraphRepository(session).load_graph()
        assert ("AAPL", "corporate_link", 0.9) in restarted.relationships["AAPL_BOND_2030"]
        assert _publication_count(session) == 1


def test_publication_time_is_monotonic_when_a_prior_worker_clock_is_ahead(
    publication_session_factory: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Database ordering keeps a later commit latest despite skewed prior publication time."""
    future_time = datetime.now(tz=UTC) + timedelta(days=1)
    original_next_time = RelationshipAssertionRepository.next_publication_time
    monkeypatch.setattr(
        RelationshipAssertionRepository,
        "next_publication_time",
        lambda _repo, _purpose: future_time,
    )
    first_job_id = _create_running_job(publication_session_factory)
    _finalize(publication_session_factory, first_job_id)
    monkeypatch.setattr(RelationshipAssertionRepository, "next_publication_time", original_next_time)

    second_job_id = _create_running_job(publication_session_factory, persist_graph=False)
    _finalize(publication_session_factory, second_job_id)

    with session_scope(publication_session_factory) as session:
        second = session.execute(
            select(RelationshipProjectionPublicationORM).where(
                RelationshipProjectionPublicationORM.rebuild_job_id == second_job_id
            )
        ).scalar_one()
        latest = RelationshipAssertionRepository(session).latest_published_projection(PURPOSE)
        assert second.published_at.replace(tzinfo=UTC) > future_time
        assert latest is not None and latest.revision_id == second.revision_id


def test_publication_guard_supports_a_separate_coordination_database(
    publication_session_factory: sessionmaker,
    tmp_path: Path,
) -> None:
    """A held coordination predicate can safely guard a separate domain commit."""
    coordination_engine = create_engine_from_url(f"sqlite:///{tmp_path / 'grac-coordination.db'}")
    init_db(coordination_engine)
    coordination_factory = create_session_factory(coordination_engine)
    try:
        with session_scope(coordination_factory) as session:
            result = CoordinationLockRepository(session).acquire_lock(
                lock_name="graph_rebuild",
                holder_id="split-worker",
                ttl_seconds=30,
            )
            assert result.success is True

        job_id = _create_running_job(publication_session_factory)
        _finalize(
            publication_session_factory,
            job_id,
            lock_holder_id="split-worker",
            lock_ttl_seconds=30,
            coordination_session_factory=coordination_factory,
            coordination_is_domain=False,
        )

        with session_scope(publication_session_factory) as session:
            job = session.get(RebuildJobORM, job_id)
            assert job is not None and job.status == RebuildJobStatus.SUCCEEDED
            assert _publication_count(session) == 1
    finally:
        coordination_engine.dispose()


class _TripGate:
    """Safety verifier that fails only at one named execution stage."""

    def __init__(self, verifier, *, target_stage: str, event_name: str, error_type: type[Exception]) -> None:
        self._verifier = verifier
        self._target_stage = target_stage
        self._event_name = event_name
        self._error_type = error_type

    def __call__(self, lock_lost, cancel_event, stage: str) -> None:
        if stage == self._target_stage:
            raise self._error_type(f"{self._event_name} at stage={stage}")
        self._verifier(lock_lost, cancel_event, stage)


@pytest.mark.parametrize(
    ("event_name", "expected_error", "target_stage"),
    [
        ("lock_lost", graph_admin._DistributedLockLostError, "publication-pre-commit"),
        ("cancel_event", RebuildCancelledError, "publication-pre-commit"),
        ("lock_lost", graph_admin._DistributedLockLostError, "publication-domain-commit"),
        ("cancel_event", RebuildCancelledError, "publication-domain-commit"),
    ],
)
def test_final_safety_gate_rolls_back_graph_candidate_success_and_publication(
    publication_session_factory: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
    event_name: str,
    expected_error: type[Exception],
    target_stage: str,
) -> None:
    """Lock loss or cancellation at the named final gate leaves no visible candidate."""
    initial_graph = create_sample_database()
    initial_relationships = {source: list(entries) for source, entries in initial_graph.relationships.items()}
    job_id = _create_running_job(publication_session_factory)
    monkeypatch.setattr(
        graph_admin,
        "_verify_execution_state",
        _TripGate(
            graph_admin._verify_execution_state,  # pylint: disable=protected-access
            target_stage=target_stage,
            event_name=event_name,
            error_type=expected_error,
        ),
    )

    with pytest.raises(expected_error):
        _finalize(publication_session_factory, job_id, graph=initial_graph)

    assert _canonical_relationships(initial_graph.relationships) == _canonical_relationships(initial_relationships)

    with session_scope(publication_session_factory) as session:
        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        assert job.status == RebuildJobStatus.RUNNING
        assert _publication_count(session) == 0
        assert _revision_count(session) == 0
        assert _canonical_relationships(AssetGraphRepository(session).load_graph().relationships) == (
            _canonical_relationships(initial_relationships)
        )


def _accept_issuer_assertion(publication_session_factory: sessionmaker) -> None:
    """Create and independently accept the canonical issuer assertion."""
    with session_scope(publication_session_factory) as session:
        repo = RelationshipAssertionRepository(session)
        repo.propose(
            AssertionProposal(
                assertion_id="assertion-issuer",
                predicate_id=PREDICATE_ID,
                subject_id="AAPL_BOND_2030",
                object_id="AAPL",
                method_id="bond.issuer_id.resolution@1",
                proposition="AAPL is the issuer of AAPL_BOND_2030",
                effective_from=datetime.now(tz=UTC) - timedelta(days=1),
            ),
            _authority("actor-proposer", "proposer"),
            event_id="event-proposed",
        )
        repo.transition(
            RepositoryTransitionRequest(
                assertion_id="assertion-issuer",
                to_state="Accepted",
                ctx=_authority("actor-determiner", "acceptor"),
                expected_sequence=1,
                rationale="independent determination",
                event_id="event-accepted",
            )
        )


def _verify_first_publication_and_retract(publication_session_factory: sessionmaker) -> None:
    """Verify restart state and retract the accepted issuer assertion."""
    with session_scope(publication_session_factory) as session:
        repo = RelationshipAssertionRepository(session)
        first = repo.latest_published_projection(PURPOSE)
        assert first is not None
        assert first.revision.governed_scopes[0].predicate_id == PREDICATE_ID
        assert first.revision.edges[0].assertion_id == "assertion-issuer"
        restarted = AssetGraphRepository(session).load_graph()
        assert ("AAPL", "corporate_link", 0.8) in restarted.relationships["AAPL_BOND_2030"]
        history = repo.get_as_of("assertion-issuer", known_at=datetime.now(tz=UTC))
        assert history is not None
        assert [event.actor_id for event in history.events] == ["actor-proposer", "actor-determiner"]
        repo.transition(
            RepositoryTransitionRequest(
                assertion_id="assertion-issuer",
                to_state="Retracted",
                ctx=_authority("actor-retractor", "retractor"),
                expected_sequence=2,
                rationale="issuer relationship withdrawn",
                event_id="event-retracted",
            )
        )


def test_governed_issuer_slice_survives_restart_and_empty_successor(
    publication_session_factory: sessionmaker,
) -> None:
    """Publish, reload, then retain governed scope after the edge is retracted."""
    _accept_issuer_assertion(publication_session_factory)
    first_job_id = _create_running_job(publication_session_factory)
    _finalize(publication_session_factory, first_job_id)
    _verify_first_publication_and_retract(publication_session_factory)
    second_job_id = _create_running_job(publication_session_factory, persist_graph=False)
    _finalize(publication_session_factory, second_job_id)

    with session_scope(publication_session_factory) as session:
        repo = RelationshipAssertionRepository(session)
        second = repo.latest_published_projection(PURPOSE)
        assert second is not None
        assert second.revision.edges == ()
        assert second.revision.governed_scopes[0].predicate_id == PREDICATE_ID
        restarted = AssetGraphRepository(session).load_graph()
        assert all(
            relationship_type != "corporate_link"
            for entries in restarted.relationships.values()
            for _target_id, relationship_type, _strength in entries
        )
        assert _publication_count(session) == 2
