"""End-to-end proof for atomic GRAC projection publication."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import cast

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
from src.data.repository import AssetGraphRepository, session_scope
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
    *,
    execution_id: str = "exec-publication",
    graph=None,
    lock_lost=None,
    cancel_event=None,
):
    """Invoke the production atomic publication boundary."""
    return graph_admin._finalize_rebuild_success(  # pylint: disable=protected-access
        session_factory=factory,
        job_id=job_id,
        execution_id=execution_id,
        graph=graph or create_sample_database(),
        source="sample",
        job_started_at=perf_counter(),
        lock_lost=lock_lost or threading.Event(),
        cancel_event=cancel_event or threading.Event(),
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
        assert publication.execution_id == "exec-publication"
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
        (cast(str, None), ValidationError),
        ("", ValidationError),
    ],
)
def test_invalid_publication_identity_rolls_back_everything(
    publication_session_factory: sessionmaker,
    execution_id: str,
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


class _TripEvent:
    """Event-like test double that trips on a selected safety check."""

    def __init__(self, trip_on: int) -> None:
        self._trip_on = trip_on
        self._checks = 0

    def is_set(self) -> bool:
        self._checks += 1
        return self._checks >= self._trip_on


@pytest.mark.parametrize(
    ("event_name", "expected_error"),
    [
        ("lock_lost", graph_admin._DistributedLockLostError),  # pylint: disable=protected-access
        ("cancel_event", RebuildCancelledError),
    ],
)
def test_final_safety_gate_rolls_back_graph_candidate_success_and_publication(
    publication_session_factory: sessionmaker,
    event_name: str,
    expected_error: type[Exception],
) -> None:
    """Lock loss or cancellation at the final gate leaves no visible candidate."""
    initial_graph = create_sample_database()
    initial_relationships = {source: list(entries) for source, entries in initial_graph.relationships.items()}
    job_id = _create_running_job(publication_session_factory)
    lock_lost = _TripEvent(3) if event_name == "lock_lost" else threading.Event()
    cancel_event = _TripEvent(3) if event_name == "cancel_event" else threading.Event()

    with pytest.raises(expected_error):
        _finalize(
            publication_session_factory,
            job_id,
            lock_lost=lock_lost,
            cancel_event=cancel_event,
        )

    with session_scope(publication_session_factory) as session:
        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        assert job.status == RebuildJobStatus.RUNNING
        assert _publication_count(session) == 0
        assert _revision_count(session) == 0
        assert _canonical_relationships(AssetGraphRepository(session).load_graph().relationships) == (
            _canonical_relationships(initial_relationships)
        )


def test_governed_issuer_slice_survives_restart_and_empty_successor(
    publication_session_factory: sessionmaker,
) -> None:
    """Publish, reload, then retain governed scope after the edge is retracted."""
    proposer = _authority("actor-proposer", "proposer")
    determiner = _authority("actor-determiner", "acceptor")
    retractor = _authority("actor-retractor", "retractor")
    effective_from = datetime.now(tz=UTC) - timedelta(days=1)

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
                effective_from=effective_from,
            ),
            proposer,
            event_id="event-proposed",
        )
        repo.transition(
            RepositoryTransitionRequest(
                assertion_id="assertion-issuer",
                to_state="Accepted",
                ctx=determiner,
                expected_sequence=1,
                rationale="independent determination",
                event_id="event-accepted",
            )
        )

    first_job_id = _create_running_job(publication_session_factory)
    _finalize(publication_session_factory, first_job_id)

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
        assert history.events[0].actor_id == "actor-proposer"
        assert history.events[1].actor_id == "actor-determiner"
        assert history.events[0].actor_id != history.events[1].actor_id

        repo.transition(
            RepositoryTransitionRequest(
                assertion_id="assertion-issuer",
                to_state="Retracted",
                ctx=retractor,
                expected_sequence=2,
                rationale="issuer relationship withdrawn",
                event_id="event-retracted",
            )
        )

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
