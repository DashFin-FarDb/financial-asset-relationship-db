"""Integration tests for governed projection publication."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.data.database import create_session_factory, init_db
from src.data.relationship_assertion_repository import (
    PublishProjectionRequest,
    RelationshipAssertionRepository,
)
from src.data.relationship_projection_persistence import PersistProjectionRequest
from src.data.repository import AssetGraphRepository
from src.governance.relationship_assertion import ValidationError
from src.governance.relationship_assertion_contract import (
    PredicatesDocument,
    PredicateSpec,
    ProjectionSpec,
)
from src.logic.relationship_projection import ProjectRequest, project
from tests.conftest import enable_sqlite_foreign_keys

UTC = timezone.utc


def new_execution_id() -> str:
    """Generate a new execution ID."""
    return str(uuid4())


def now_utc() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


def sample_predicate_registry() -> PredicatesDocument:
    """Create sample predicate registry."""
    return PredicatesDocument(
        predicates=[
            PredicateSpec(
                id="test_predicate",
                subject_type="test_subject",
                object_type="test_object",
                conflict_key=["predicate_id", "subject_id"],
                method_ids=["test_method"],
                projection=ProjectionSpec(
                    purpose="test_purpose",
                    edge_type="TEST_EDGE",
                    strength="1.0",
                    direction="subject_to_object",
                ),
            )
        ]
    )


def create_test_rebuild_job(session: Session, execution_id: str) -> str:
    """Helper to create a succeeded rebuild job."""
    repo = AssetGraphRepository(session)
    job_id = repo.create_rebuild_job(requested_by="test_user")
    repo.mark_rebuild_job_running(job_id, execution_id)
    repo.mark_rebuild_job_succeeded(
        job_id,
        execution_id=execution_id,
        node_count=0,
        edge_count=0,
        duration_ms=100,
    )
    return job_id


class TestPublicationBaseline:
    """Test basic publication scenarios."""

    def test_empty_publication(self, session: Session) -> None:
        """Test publishing an empty projection."""
        repo = RelationshipAssertionRepository(session)
        predicates = sample_predicate_registry()
        execution_id = new_execution_id()
        job_id = create_test_rebuild_job(session, execution_id)

        # Create empty projection
        revision = project(
            ProjectRequest(
                assertions=[],
                events=[],
                evidence=[],
                evidence_links=[],
                predicate_registry=predicates,
                purpose="test_purpose",
                effective_at=now_utc(),
                known_at=now_utc(),
            )
        )

        # Persist and publish
        persisted = repo.persist_projection_revision(PersistProjectionRequest(revision=revision))
        published = repo.publish_projection_revision(
            PublishProjectionRequest(
                revision_id=persisted.revision_id,
                rebuild_job_id=job_id,
                execution_id=execution_id,
            )
        )

        assert published.revision_id == persisted.revision_id
        assert published.execution_id == execution_id
        assert len(revision.edges) == 0

    def test_double_publication_rejected(self, session: Session) -> None:
        """Test that one rebuild cannot publish twice."""
        repo = RelationshipAssertionRepository(session)
        predicates = sample_predicate_registry()
        execution_id = new_execution_id()
        job_id = create_test_rebuild_job(session, execution_id)

        # First publication
        revision1 = project(
            ProjectRequest(
                assertions=[],
                events=[],
                evidence=[],
                evidence_links=[],
                predicate_registry=predicates,
                purpose="test_purpose",
                effective_at=now_utc(),
                known_at=now_utc(),
            )
        )
        persisted1 = repo.persist_projection_revision(PersistProjectionRequest(revision=revision1))
        repo.publish_projection_revision(
            PublishProjectionRequest(
                revision_id=persisted1.revision_id,
                rebuild_job_id=job_id,
                execution_id=execution_id,
            )
        )

        # Attempt second publication
        revision2 = project(
            ProjectRequest(
                assertions=[],
                events=[],
                evidence=[],
                evidence_links=[],
                predicate_registry=predicates,
                purpose="test_purpose",
                effective_at=now_utc(),
                known_at=now_utc(),
            )
        )
        persisted2 = repo.persist_projection_revision(PersistProjectionRequest(revision=revision2))

        from src.governance.relationship_assertion import ConcurrencyConflict

        with pytest.raises(ConcurrencyConflict, match="already published"):
            repo.publish_projection_revision(
                PublishProjectionRequest(
                    revision_id=persisted2.revision_id,
                    rebuild_job_id=job_id,
                    execution_id=execution_id,
                )
            )

    def test_execution_id_mismatch_rejected(self, session: Session) -> None:
        """Test that mismatched execution_id is rejected."""
        repo = RelationshipAssertionRepository(session)
        predicates = sample_predicate_registry()
        execution_id = new_execution_id()
        job_id = create_test_rebuild_job(session, execution_id)

        revision = project(
            ProjectRequest(
                assertions=[],
                events=[],
                evidence=[],
                evidence_links=[],
                predicate_registry=predicates,
                purpose="test_purpose",
                effective_at=now_utc(),
                known_at=now_utc(),
            )
        )
        persisted = repo.persist_projection_revision(PersistProjectionRequest(revision=revision))

        with pytest.raises(ValidationError, match="execution_id.*does not match"):
            repo.publish_projection_revision(
                PublishProjectionRequest(
                    revision_id=persisted.revision_id,
                    rebuild_job_id=job_id,
                    execution_id="wrong-id",
                )
            )


class TestPublicationSafety:
    """Test publication safety constraints."""

    def test_failed_job_cannot_publish(self, session: Session) -> None:
        """Test that failed rebuild jobs cannot publish."""
        repo = AssetGraphRepository(session)
        grac_repo = RelationshipAssertionRepository(session)
        predicates = sample_predicate_registry()
        execution_id = new_execution_id()

        # Create job but leave it in running state
        job_id = repo.create_rebuild_job(requested_by="test_user")
        repo.mark_rebuild_job_running(job_id, execution_id)

        revision = project(
            ProjectRequest(
                assertions=[],
                events=[],
                evidence=[],
                evidence_links=[],
                predicate_registry=predicates,
                purpose="test_purpose",
                effective_at=now_utc(),
                known_at=now_utc(),
            )
        )
        persisted = grac_repo.persist_projection_revision(PersistProjectionRequest(revision=revision))

        with pytest.raises(ValidationError, match="must be succeeded"):
            grac_repo.publish_projection_revision(
                PublishProjectionRequest(
                    revision_id=persisted.revision_id,
                    rebuild_job_id=job_id,
                    execution_id=execution_id,
                )
            )

    def test_nonexistent_revision_rejected(self, session: Session) -> None:
        """Test that publishing nonexistent revision fails."""
        repo = RelationshipAssertionRepository(session)
        execution_id = new_execution_id()
        job_id = create_test_rebuild_job(session, execution_id)

        with pytest.raises(ValidationError, match="revision.*not found"):
            repo.publish_projection_revision(
                PublishProjectionRequest(
                    revision_id="nonexistent-id",
                    rebuild_job_id=job_id,
                    execution_id=execution_id,
                )
            )

    def test_nonexistent_job_rejected(self, session: Session) -> None:
        """Test that publishing for nonexistent job fails."""
        repo = RelationshipAssertionRepository(session)
        predicates = sample_predicate_registry()

        revision = project(
            ProjectRequest(
                assertions=[],
                events=[],
                evidence=[],
                evidence_links=[],
                predicate_registry=predicates,
                purpose="test_purpose",
                effective_at=now_utc(),
                known_at=now_utc(),
            )
        )
        persisted = repo.persist_projection_revision(PersistProjectionRequest(revision=revision))

        with pytest.raises(ValidationError, match="rebuild job.*not found"):
            repo.publish_projection_revision(
                PublishProjectionRequest(
                    revision_id=persisted.revision_id,
                    rebuild_job_id="nonexistent-job",
                    execution_id="some-id",
                )
            )


class TestGovernedScopeContinuity:
    """Test governed scope continuity across publications."""

    def test_scope_loading(self, session: Session) -> None:
        """Test loading established scopes from previous publication."""
        repo = RelationshipAssertionRepository(session)

        # Initially no scopes
        scopes = repo.latest_published_scopes("test_purpose")
        assert len(scopes) == 0


@pytest.fixture
def session(tmp_path: pytest.TempPathFactory) -> Generator[Session, None, None]:
    """Provide a self-contained SQLite session with the full GRAC schema."""
    engine = create_engine(f"sqlite:///{tmp_path / 'vertical_slice.db'}")
    enable_sqlite_foreign_keys(engine)
    init_db(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    yield db_session
    db_session.close()
    engine.dispose()
