"""Integration tests for GRAC v1 projection revision persistence and hash parity."""

from __future__ import annotations

import os
from collections.abc import Generator, Iterator
from datetime import datetime, timedelta, timezone
from typing import TypeVar
from unittest import TestCase

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, ProgrammingError

from src.data.database import Base, create_session_factory, init_db
from src.data.db_models import RebuildJobORM
from src.data.relationship_assertion_db_models import RelationshipProjectionPublicationORM
from src.data.relationship_assertion_repository import (
    PersistProjectionRequest,
    RegisterEvidenceRequest,
    RelationshipAssertionRepository,
    RepositoryTransitionRequest,
    SupersedeAtomicRequest,
)
from src.data.relationship_projection_persistence import ProjectionRevisionStore
from src.governance.relationship_assertion import (
    Assertion,
    AssertionEvent,
    AssertionProposal,
    AuthorityContext,
    EvidenceLink,
    EvidenceRecord,
)
from src.governance.relationship_assertion_contract import load_contract_bundle
from src.logic.relationship_projection import GovernedScope, ProjectRequest, project
from tests.conftest import enable_sqlite_foreign_keys

UTC = timezone.utc
NOW = datetime(2026, 7, 25, 15, 0, 0, tzinfo=UTC)
KNOWN_AT = NOW + timedelta(days=1)
PURPOSE = "financial_graph_current_view"
PREDICATE_ID = "financial.bond.issuer_reference@1"
DIGEST = "c" * 64
_T = TypeVar("_T")


def _sha256_hex(*chunks: str) -> str:
    return "".join(chunks)


# PEP 695 type-parameter syntax is a SyntaxError on the Python 3.10/3.11 CI matrix.
def _require_present(value: _T | None, label: str) -> _T:  # noqa: UP047
    if value is None:
        raise AssertionError(f"Expected {label} to be present")
    return value


# Pinned golden hashes for the fixed-timestamp vertical-slice fixture.
GOLDEN_EDGE_SET_HASH = _sha256_hex(
    "c8c8e738ffe460a7",
    "716fcd89fa16baf4",
    "94fe4015e2551a1f",
    "107e53b129a7d345",
)
GOLDEN_PROJECTION_HASH = _sha256_hex(
    "d8a4b70b62f827bc",
    "292ff922874c99de",
    "63a30ea0292253f1",
    "32808f1e9720dbd4",
)
ASSERT = TestCase()
pytestmark = pytest.mark.integration
_MUTATION_ERRORS = (DBAPIError, IntegrityError, OperationalError, ProgrammingError)


def _postgres_url() -> str | None:
    """Return a PostgreSQL URL when CI/local opt-in provides one."""
    url = os.getenv("ASSET_GRAPH_DATABASE_URL") or os.getenv("GRAC_SCHEMA_DATABASE_URL")
    if url and url.startswith("postgresql"):
        return url
    return None


@pytest.fixture(params=["sqlite", "postgresql"])
def projection_engine(request, tmp_path) -> Generator[Engine, None, None]:
    """Provide SQLite always; PostgreSQL when an ephemeral URL is configured."""
    dialect = request.param
    if dialect == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'grac_projection.db'}")
        enable_sqlite_foreign_keys(engine)
        init_db(engine)
        yield engine
        engine.dispose()
        return

    pg_url = _postgres_url()
    if not pg_url:
        pytest.skip("PostgreSQL URL not set (ASSET_GRAPH_DATABASE_URL / GRAC_SCHEMA_DATABASE_URL)")
    pytest.importorskip("psycopg2")
    engine = create_engine(pg_url, future=True)
    Base.metadata.drop_all(engine)
    init_db(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def repo(projection_engine) -> Iterator[RelationshipAssertionRepository]:
    """Repository bound to the parametrized engine with a deterministic clock."""
    factory = create_session_factory(projection_engine)
    session = factory()
    stamps = {"t": NOW}

    def clock() -> datetime:
        current = stamps["t"]
        stamps["t"] = current + timedelta(milliseconds=1)
        return current

    repository = RelationshipAssertionRepository(session, clock=clock)
    yield repository
    session.close()


def _ctx(actor_id: str, *roles: str) -> AuthorityContext:
    return AuthorityContext(
        actor_id=actor_id,
        roles=frozenset(roles),  # type: ignore[arg-type]
        policy_version="grac.v1-policy",
        correlation_id="corr-projection",
    )


def _proposal(assertion_id: str = "as-1", **overrides: object) -> AssertionProposal:
    payload = {
        "assertion_id": assertion_id,
        "predicate_id": PREDICATE_ID,
        "subject_id": "AAPL_BOND_2030",
        "object_id": "AAPL",
        "method_id": "bond.issuer_id.resolution@1",
        "proposition": "Bond issuer_id references AAPL",
        "effective_from": NOW,
    }
    payload.update(overrides)
    return AssertionProposal(**payload)  # type: ignore[arg-type]


def _transition(fields: dict[str, object]) -> RepositoryTransitionRequest:
    return RepositoryTransitionRequest(**fields)  # type: ignore[arg-type]


def _propose_accepted(repo: RelationshipAssertionRepository, assertion_id: str = "as-1") -> None:
    """Propose and accept with fixed timestamps so hashes are dialect-stable."""
    repo.propose(
        _proposal(assertion_id),
        _ctx(f"proposer-{assertion_id}", "proposer"),
        event_id=f"ev-{assertion_id}-1",
    )
    repo.transition(
        _transition(
            {
                "assertion_id": assertion_id,
                "to_state": "Accepted",
                "ctx": _ctx(f"determiner-{assertion_id}", "acceptor"),
                "expected_sequence": 1,
                "rationale": "accept",
                "event_id": f"ev-{assertion_id}-2",
            }
        )
    )


def _project_from_repo(
    repo: RelationshipAssertionRepository,
    assertion_ids: list[str],
    *,
    evidence: list[EvidenceRecord] | None = None,
    evidence_links=None,
):
    """Build a projection revision from persisted assertions at a fixed known_at."""
    _contract, predicates, _transitions = load_contract_bundle()
    assertions: list[Assertion] = []
    events: list[AssertionEvent] = []
    links: list[EvidenceLink] = list(evidence_links or [])
    for assertion_id in assertion_ids:
        as_of = _require_present(repo.get_as_of(assertion_id, known_at=KNOWN_AT), f"{assertion_id} as-of state")
        assertions.append(as_of.assertion)
        events.extend(as_of.events)
        if evidence_links is None:
            links.extend(as_of.evidence_links)
    return project(
        ProjectRequest(
            assertions=assertions,
            events=events,
            evidence=evidence or [],
            evidence_links=links,
            predicate_registry=predicates,
            purpose=PURPOSE,
            effective_at=NOW,
            known_at=KNOWN_AT,
        )
    )


def test_persist_and_reload_projection_revision(repo: RelationshipAssertionRepository) -> None:
    """Persisting a candidate revision round-trips hashes and edges."""
    _propose_accepted(repo, "as-1")
    stored_evidence, link = repo.register_evidence(
        RegisterEvidenceRequest(
            assertion_id="as-1",
            evidence=EvidenceRecord(
                evidence_id="evd-1",
                source_ref="sample://AAPL_BOND_2030",
                content_sha256=DIGEST,
                media_type="application/json",
                visibility="internal",
                custody_id="collector-1",
                recorded_at=NOW,
            ),
            polarity="supporting",
            ctx=_ctx("proposer-as-1", "proposer"),
            link_id="link-1",
        )
    )
    revision = _project_from_repo(
        repo,
        ["as-1"],
        evidence=[stored_evidence],
        evidence_links=[link],
    )
    persisted = repo.persist_projection_revision(
        PersistProjectionRequest(
            revision=revision,
            revision_id="rev-1",
            created_at=NOW + timedelta(hours=2),
            edge_ids=["edge-1"],
        )
    )
    repo._session.commit()
    loaded = _require_present(repo.get_projection_revision("rev-1"), "rev-1 projection revision")
    ASSERT.assertEqual(loaded.revision_id, "rev-1")
    ASSERT.assertEqual(loaded.revision.edge_set_hash, revision.edge_set_hash)
    ASSERT.assertEqual(loaded.revision.projection_hash, revision.projection_hash)
    ASSERT.assertEqual(loaded.revision.edges, revision.edges)
    ASSERT.assertEqual(loaded.revision.governed_scopes, revision.governed_scopes)
    ASSERT.assertEqual(len(loaded.revision.governed_scopes), 1)
    ASSERT.assertEqual(loaded.revision.governed_scopes[0].predicate_id, PREDICATE_ID)
    ASSERT.assertEqual(persisted.edge_ids, ("edge-1",))


def test_identical_hashes_across_dialects(projection_engine, repo: RelationshipAssertionRepository) -> None:
    """SQLite and PostgreSQL produce and persist identical golden content hashes."""
    _propose_accepted(repo, "as-1")
    revision = _project_from_repo(repo, ["as-1"])
    ASSERT.assertEqual(revision.edge_set_hash, GOLDEN_EDGE_SET_HASH)
    ASSERT.assertEqual(revision.projection_hash, GOLDEN_PROJECTION_HASH)
    repo.persist_projection_revision(
        PersistProjectionRequest(
            revision=revision,
            revision_id=f"rev-{projection_engine.dialect.name}",
            created_at=NOW + timedelta(hours=3),
            edge_ids=[f"edge-{projection_engine.dialect.name}"],
        )
    )
    repo._session.commit()
    loaded = _require_present(
        repo.get_projection_revision(f"rev-{projection_engine.dialect.name}"),
        f"rev-{projection_engine.dialect.name} projection revision",
    )
    ASSERT.assertEqual(loaded.revision.edge_set_hash, GOLDEN_EDGE_SET_HASH)
    ASSERT.assertEqual(loaded.revision.projection_hash, GOLDEN_PROJECTION_HASH)
    ASSERT.assertEqual(loaded.revision.edges[0].strength, "0.8")


def test_latest_published_scopes_are_durable_and_deterministic(repo: RelationshipAssertionRepository) -> None:
    """Latest successful publication carries canonical scopes through an empty-edge revision."""
    _propose_accepted(repo, "as-1")
    source = _project_from_repo(repo, ["as-1"])
    repo.persist_projection_revision(
        PersistProjectionRequest(source, revision_id="rev-source", created_at=NOW, edge_ids=["edge-source"])
    )
    repo._session.add(
        RebuildJobORM(
            job_id="job-a",
            requested_by="tester",
            status="succeeded",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repo._session.flush()
    repo._session.add(
        RelationshipProjectionPublicationORM(
            id="pub-a",
            revision_id="rev-source",
            rebuild_job_id="job-a",
            published_at=KNOWN_AT,
            execution_id="exec-a",
        )
    )
    repo._session.flush()
    store = ProjectionRevisionStore(repo._session, clock=lambda: NOW)
    retained_scopes = store.latest_published_scopes(PURPOSE)
    assert retained_scopes == (GovernedScope(PURPOSE, PREDICATE_ID),)
    empty = project(
        ProjectRequest(
            assertions=[],
            events=[],
            evidence=[],
            evidence_links=[],
            predicate_registry=load_contract_bundle()[1],
            purpose=PURPOSE,
            effective_at=NOW,
            known_at=KNOWN_AT,
            previously_published_scopes=retained_scopes,
        )
    )
    repo.persist_projection_revision(PersistProjectionRequest(empty, revision_id="rev-empty", created_at=KNOWN_AT))
    for job_id in ("job-z",):
        repo._session.add(
            RebuildJobORM(
                job_id=job_id,
                requested_by="tester",
                status="succeeded",
                created_at=NOW,
                updated_at=NOW,
            )
        )
    repo._session.flush()
    repo._session.add_all(
        [
            RelationshipProjectionPublicationORM(
                id="pub-z",
                revision_id="rev-empty",
                rebuild_job_id="job-z",
                published_at=KNOWN_AT,
                execution_id="exec-z",
            ),
        ]
    )
    repo._session.commit()
    store = ProjectionRevisionStore(repo._session, clock=lambda: NOW)
    assert store.latest_published_scopes(PURPOSE) == retained_scopes
    loaded = store.get("rev-empty")
    assert loaded is not None
    assert loaded.revision.edges == ()
    assert loaded.revision.governed_scopes == retained_scopes


def test_supersession_changes_persisted_hashes(repo: RelationshipAssertionRepository) -> None:
    """Persisted revisions before/after supersession have distinct hashes."""
    _propose_accepted(repo, "as-1")
    before = _project_from_repo(repo, ["as-1"])
    repo.persist_projection_revision(
        PersistProjectionRequest(
            revision=before,
            revision_id="rev-before",
            created_at=NOW + timedelta(hours=1),
            edge_ids=["edge-before"],
        )
    )
    supersede_at = NOW + timedelta(hours=2)
    repo.supersede_atomic(
        SupersedeAtomicRequest(
            predecessor_id="as-1",
            successor_proposal=_proposal("as-2", object_id="AAPL_NEW"),
            proposal_ctx=_ctx("proposer-as-2", "proposer"),
            determination_ctx=_ctx("supersession-determiner", "acceptor"),
            expected_sequence=2,
            rationale="refresh issuer",
        )
    )
    after = _project_from_repo(repo, ["as-1", "as-2"])
    repo.persist_projection_revision(
        PersistProjectionRequest(
            revision=after,
            revision_id="rev-after",
            created_at=supersede_at + timedelta(minutes=1),
            edge_ids=["edge-after"],
        )
    )
    repo._session.commit()
    loaded_before = repo.get_projection_revision("rev-before")
    loaded_after = repo.get_projection_revision("rev-after")
    loaded_before = _require_present(loaded_before, "rev-before projection revision")
    loaded_after = _require_present(loaded_after, "rev-after projection revision")
    ASSERT.assertEqual(loaded_before.revision.edges[0].target_id, "AAPL")
    ASSERT.assertEqual(loaded_after.revision.edges[0].target_id, "AAPL_NEW")
    ASSERT.assertEqual(loaded_before.revision.edge_set_hash, GOLDEN_EDGE_SET_HASH)
    ASSERT.assertNotEqual(loaded_before.revision.edge_set_hash, loaded_after.revision.edge_set_hash)
    ASSERT.assertNotEqual(loaded_before.revision.projection_hash, loaded_after.revision.projection_hash)


def test_projection_revision_rows_are_immutable(repo: RelationshipAssertionRepository) -> None:
    """UPDATE/DELETE on projection revision tables remain rejected."""
    _contract, predicates, _transitions = load_contract_bundle()
    revision = project(
        ProjectRequest(
            assertions=[],
            events=[],
            evidence=[],
            evidence_links=[],
            predicate_registry=predicates,
            purpose=PURPOSE,
            effective_at=NOW,
            known_at=NOW,
        )
    )
    repo.persist_projection_revision(
        PersistProjectionRequest(
            revision=revision,
            revision_id="rev-empty",
            created_at=NOW,
            edge_ids=[],
        )
    )
    repo._session.commit()

    def _mutate(statement: str) -> None:
        repo._session.execute(text(statement))
        repo._session.commit()

    with pytest.raises(_MUTATION_ERRORS):
        _mutate("UPDATE relationship_projection_revisions SET purpose = 'x' WHERE id = 'rev-empty'")
    repo._session.rollback()
    with pytest.raises(_MUTATION_ERRORS):
        _mutate("DELETE FROM relationship_projection_revisions WHERE id = 'rev-empty'")
    repo._session.rollback()


def test_published_projection_binding_for_rebuild_job(repo: RelationshipAssertionRepository) -> None:
    """Return binding only for succeeded rebuild jobs."""
    assert repo.published_projection_binding_for_rebuild_job("non-existent-job") is None

    _contract, predicates, _transitions = load_contract_bundle()
    revision = project(
        ProjectRequest(
            assertions=[],
            events=[],
            evidence=[],
            evidence_links=[],
            predicate_registry=predicates,
            purpose=PURPOSE,
            effective_at=NOW,
            known_at=NOW,
        )
    )
    repo.persist_projection_revision(
        PersistProjectionRequest(
            revision=revision,
            revision_id="rev-1",
            created_at=NOW,
            edge_ids=[],
        )
    )

    job = RebuildJobORM(
        job_id="job-test-1",
        requested_by="admin",
        status="running",
        source="sample",
        created_at=NOW,
        updated_at=NOW,
        execution_id="exec-1",
    )
    publication = RelationshipProjectionPublicationORM(
        id="pub-1",
        rebuild_job_id="job-test-1",
        revision_id="rev-1",
        execution_id="exec-1",
        published_at=NOW,
    )
    repo._session.add(job)
    repo._session.add(publication)
    repo._session.commit()

    assert repo.published_projection_binding_for_rebuild_job("job-test-1") is None

    job.status = "succeeded"
    repo._session.commit()

    binding = repo.published_projection_binding_for_rebuild_job("job-test-1")
    assert binding == ("rev-1", "pub-1")
