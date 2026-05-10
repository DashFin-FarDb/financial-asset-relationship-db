"""Unit tests for AssetGraphRepository rebuild job methods."""

import pytest
from sqlalchemy import create_engine

from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository


@pytest.fixture
def repository_factory(tmp_path):
    """
    Create a factory for producing AssetGraphRepository instances with fresh sessions.

    The factory ensures all sessions are properly closed and the engine is disposed after tests.

    Parameters:
        tmp_path (pathlib.Path): Temporary directory fixture for creating the test database.

    Returns:
        Callable[[], AssetGraphRepository]: A factory function that creates new repository instances.
    """
    db_path = tmp_path / "test_rebuild_jobs.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = create_session_factory(engine)
    sessions = []

    def make_repository():
        session = factory()
        sessions.append(session)
        return AssetGraphRepository(session)

    yield make_repository

    for session in sessions:
        session.close()
    engine.dispose()


@pytest.mark.unit
class TestRebuildJobRepository:
    """Test cases for rebuild job repository methods."""

    def test_create_rebuild_job(self, repository_factory):
        """Test creating a new rebuild job."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user", source="sample")

        assert job_id is not None
        assert isinstance(job_id, str)

        repo.session.commit()

        # Verify job was persisted
        reader = repository_factory()
        job = reader.get_rebuild_job(job_id)
        assert job is not None
        assert job.job_id == job_id
        assert job.requested_by == "test_user"
        assert job.status == "pending"
        assert job.source == "sample"
        assert job.started_at is None
        assert job.completed_at is None

    def test_create_rebuild_job_without_source(self, repository_factory):
        """Test creating a rebuild job without specifying a source."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user")

        repo.session.commit()

        reader = repository_factory()
        job = reader.get_rebuild_job(job_id)
        assert job is not None
        assert job.source is None

    def test_create_rebuild_job_requested_by_too_long(self, repository_factory):
        """Test that requested_by exceeding 64 characters raises ValueError."""
        repo = repository_factory()
        with pytest.raises(ValueError, match="requested_by must not exceed 64 characters"):
            repo.create_rebuild_job(requested_by="x" * 65)

    def test_create_rebuild_job_source_too_long(self, repository_factory):
        """Test that source exceeding 32 characters raises ValueError."""
        repo = repository_factory()
        with pytest.raises(ValueError, match="source must not exceed 32 characters"):
            repo.create_rebuild_job(requested_by="test_user", source="x" * 33)

    def test_mark_rebuild_job_running(self, repository_factory):
        """Test transitioning a rebuild job from pending to running."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user", source="cache")
        repo.session.commit()

        repo.mark_rebuild_job_running(job_id)
        repo.session.commit()

        reader = repository_factory()
        job = reader.get_rebuild_job(job_id)
        assert job is not None
        assert job.status == "running"
        assert job.started_at is not None
        assert job.completed_at is None

    def test_mark_rebuild_job_running_not_found(self, repository_factory):
        """Test marking a non-existent job as running raises ValueError."""
        repo = repository_factory()
        with pytest.raises(ValueError, match="Rebuild job .* not found"):
            repo.mark_rebuild_job_running("non-existent-job-id")

    def test_mark_rebuild_job_running_invalid_transition(self, repository_factory):
        """Test that transitioning from non-pending status to running raises ValueError."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user")
        repo.mark_rebuild_job_running(job_id)
        repo.session.flush()  # Flush changes without committing

        # Try to mark as running again (should fail)
        with pytest.raises(ValueError, match="Cannot transition job .* from running to running"):
            repo.mark_rebuild_job_running(job_id)

    def test_mark_rebuild_job_succeeded(self, repository_factory):
        """Test marking a rebuild job as succeeded with metadata."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user", source="real_data")
        repo.mark_rebuild_job_running(job_id)
        repo.mark_rebuild_job_succeeded(
            job_id,
            node_count=100,
            edge_count=250,
            duration_ms=1234,
        )
        repo.session.commit()

        reader = repository_factory()
        job = reader.get_rebuild_job(job_id)
        assert job is not None
        assert job.status == "succeeded"
        assert job.node_count == 100
        assert job.edge_count == 250
        assert job.duration_ms == 1234
        assert job.completed_at is not None
        assert job.sanitized_failure_category is None
        assert job.sanitized_failure_message is None

    def test_mark_rebuild_job_succeeded_not_found(self, repository_factory):
        """Test marking a non-existent job as succeeded raises ValueError."""
        repo = repository_factory()
        with pytest.raises(ValueError, match="Rebuild job .* not found"):
            repo.mark_rebuild_job_succeeded(
                "non-existent-job-id",
                node_count=0,
                edge_count=0,
                duration_ms=0,
            )

    def test_mark_rebuild_job_succeeded_invalid_transition(self, repository_factory):
        """Test that marking a non-running job as succeeded raises ValueError."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user")
        repo.session.commit()

        with pytest.raises(ValueError, match="Cannot transition job .* from pending to succeeded"):
            repo.mark_rebuild_job_succeeded(
                job_id,
                node_count=0,
                edge_count=0,
                duration_ms=0,
            )

    def test_mark_rebuild_job_failed(self, repository_factory):
        """Test marking a rebuild job as failed with sanitized failure metadata."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user", source="cache")
        repo.mark_rebuild_job_running(job_id)
        repo.mark_rebuild_job_failed(
            job_id,
            failure_category="rebuild_source_error",
            failure_message="Failed to load graph from cache",
            duration_ms=500,
        )
        repo.session.commit()

        reader = repository_factory()
        job = reader.get_rebuild_job(job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.sanitized_failure_category == "rebuild_source_error"
        assert job.sanitized_failure_message == "Failed to load graph from cache"
        assert job.duration_ms == 500
        assert job.completed_at is not None
        assert job.node_count is None
        assert job.edge_count is None

    def test_mark_rebuild_job_failed_from_pending(self, repository_factory):
        """Test marking a pending rebuild job as failed (allowed transition)."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user")
        repo.session.commit()

        repo.mark_rebuild_job_failed(
            job_id,
            failure_category="persistence_not_configured",
            failure_message="No persistence configured",
            duration_ms=10,
        )
        repo.session.commit()

        reader = repository_factory()
        job = reader.get_rebuild_job(job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.sanitized_failure_category == "persistence_not_configured"

    def test_mark_rebuild_job_failed_category_too_long(self, repository_factory):
        """Test that failure_category exceeding 64 characters raises ValueError."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user")
        repo.mark_rebuild_job_running(job_id)
        repo.session.flush()  # Flush changes without committing

        with pytest.raises(ValueError, match="failure_category must not exceed 64 characters"):
            repo.mark_rebuild_job_failed(
                job_id,
                failure_category="x" * 65,
                failure_message="error",
                duration_ms=0,
            )

    def test_mark_rebuild_job_failed_message_too_long(self, repository_factory):
        """Test that failure_message exceeding 512 characters raises ValueError."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user")
        repo.mark_rebuild_job_running(job_id)
        repo.session.flush()  # Flush changes without committing

        with pytest.raises(ValueError, match="failure_message must not exceed 512 characters"):
            repo.mark_rebuild_job_failed(
                job_id,
                failure_category="error",
                failure_message="x" * 513,
                duration_ms=0,
            )

    def test_mark_rebuild_job_failed_invalid_transition(self, repository_factory):
        """Test that marking a succeeded job as failed raises ValueError."""
        repo = repository_factory()
        job_id = repo.create_rebuild_job(requested_by="test_user")
        repo.mark_rebuild_job_running(job_id)
        repo.mark_rebuild_job_succeeded(
            job_id,
            node_count=10,
            edge_count=20,
            duration_ms=100,
        )
        repo.session.flush()  # Flush changes without committing

        with pytest.raises(ValueError, match="Cannot transition job .* from succeeded to failed"):
            repo.mark_rebuild_job_failed(
                job_id,
                failure_category="error",
                failure_message="test",
                duration_ms=0,
            )

    def test_get_rebuild_job_not_found(self, repository_factory):
        """Test getting a non-existent rebuild job returns None."""
        repo = repository_factory()
        job = repo.get_rebuild_job("non-existent-job-id")
        assert job is None

    def test_list_rebuild_jobs_empty(self, repository_factory):
        """Test listing rebuild jobs when none exist."""
        repo = repository_factory()
        jobs = repo.list_rebuild_jobs()
        assert jobs == []

    def test_list_rebuild_jobs(self, repository_factory):
        """Test listing multiple rebuild jobs ordered by created_at and job_id descending."""
        repo = repository_factory()

        job_id_1 = repo.create_rebuild_job(requested_by="user1", source="sample")
        repo.session.commit()
        job_id_2 = repo.create_rebuild_job(requested_by="user2", source="cache")
        repo.session.commit()
        job_id_3 = repo.create_rebuild_job(requested_by="user3", source="real_data")
        repo.session.commit()

        reader = repository_factory()
        jobs = reader.list_rebuild_jobs()

        assert len(jobs) == 3
        assert {j.job_id for j in jobs} == {job_id_1, job_id_2, job_id_3}
        # Verify ordering matches (created_at DESC, job_id DESC)
        expected_order = sorted(
            jobs,
            key=lambda j: (j.created_at, j.job_id),
            reverse=True,
        )
        assert [j.job_id for j in jobs] == [j.job_id for j in expected_order]

    def test_list_rebuild_jobs_with_limit(self, repository_factory):
        """Test listing rebuild jobs with a limit."""
        repo = repository_factory()

        for i in range(5):
            repo.create_rebuild_job(requested_by=f"user{i}")
            repo.session.commit()

        reader = repository_factory()
        jobs = reader.list_rebuild_jobs(limit=2)

        assert len(jobs) == 2

    def test_list_rebuild_jobs_with_status_filter(self, repository_factory):
        """Test listing rebuild jobs filtered by status."""
        repo = repository_factory()

        job_id_pending = repo.create_rebuild_job(requested_by="user1")
        job_id_running = repo.create_rebuild_job(requested_by="user2")
        repo.mark_rebuild_job_running(job_id_running)
        job_id_succeeded = repo.create_rebuild_job(requested_by="user3")
        repo.mark_rebuild_job_running(job_id_succeeded)
        repo.mark_rebuild_job_succeeded(job_id_succeeded, node_count=10, edge_count=20, duration_ms=100)
        repo.session.commit()

        pending_jobs = repo.list_rebuild_jobs(status="pending")
        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == job_id_pending

        running_jobs = repo.list_rebuild_jobs(status="running")
        assert len(running_jobs) == 1
        assert running_jobs[0].job_id == job_id_running

        succeeded_jobs = repo.list_rebuild_jobs(status="succeeded")
        assert len(succeeded_jobs) == 1
        assert succeeded_jobs[0].job_id == job_id_succeeded

        failed_jobs = repo.list_rebuild_jobs(status="failed")
        assert len(failed_jobs) == 0

    def test_list_rebuild_jobs_invalid_status_raises(self, repository_factory):
        """Test that an invalid status value raises ValueError."""
        repo = repository_factory()
        with pytest.raises(ValueError, match="Invalid rebuild job status"):
            repo.list_rebuild_jobs(status="invalid_status")
