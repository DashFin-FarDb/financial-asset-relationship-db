"""Integration tests for rebuild checkpoint and resume flow."""

import json
import threading
import time
from collections.abc import AsyncGenerator, Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import api.graph_lifecycle_providers as providers
import api.routers.graph_admin as graph_admin
from api.auth import User
from api.graph_lifecycle import reset_graph
from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.db_models import RebuildJobStatus
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset, AssetClass, Equity

pytestmark = pytest.mark.integration


def _sqlite_url(tmp_path: Path) -> str:
    """Generate an isolated SQLite DB URL for a test."""
    db_path = tmp_path / "test_resume.db"
    return f"sqlite:///{db_path}"


def _init_empty_db(url: str) -> None:
    """Initialize the database schema using canonical schemas."""
    engine = create_engine(url)
    init_db(engine)
    engine.dispose()


def _configure_persistence(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """Override environment parameters cleanly to target test sandboxes."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    providers.clear_graph_lifecycle_settings_cache()


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset graph environment configuration states and route locks before each run execution."""
    for name in (
        "ASSET_GRAPH_DATABASE_URL",
        "DATABASE_URL",
        "GRAPH_CACHE_PATH",
        "REAL_DATA_CACHE_PATH",
        "USE_REAL_DATA_FETCHER",
        "REBUILD_LOCK_TTL_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    get_settings.cache_clear()
    providers.clear_graph_lifecycle_settings_cache()
    graph_admin._REBUILD_RUNTIME.lock = None
    graph_admin._REBUILD_RUNTIME.lock_loop = None
    graph_admin.shutdown_rebuild_executor_sync()
    reset_graph()


@pytest.fixture
def mock_active_user() -> User:
    """Provide a mock active admin user for integration tests."""
    return User(username="admin_tester", email="admin@example.com", disabled=False, full_name="Admin User")


@pytest.fixture
async def test_client(mock_active_user: User) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an authenticated asynchronous test client."""
    from api.auth import get_current_active_user
    from api.main import app

    def override_get_current_active_user() -> User:
        """Mock active user override."""
        return mock_active_user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    # DevSkim: ignore all
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def session_factory_provider(tmp_path: Path):
    """Provide an isolated, production-contract-compliant database context session factory."""
    db_url = _sqlite_url(tmp_path)
    engine = create_engine_from_url(db_url)
    init_db(engine)
    factory = create_session_factory(engine)

    @contextmanager
    def bound_session_factory() -> Iterator[Session]:
        """Provide state-isolated contextual sessions matching factory lifecycle models."""
        session = factory()
        try:
            yield session
        finally:
            session.close()

    yield bound_session_factory, db_url
    engine.dispose()


@pytest.fixture
def raw_engine_provider(session_factory_provider):
    """Provide and manage lifecycle for raw database engine."""
    _, db_url = session_factory_provider
    engine = create_engine_from_url(db_url)
    yield engine
    engine.dispose()


@pytest.mark.asyncio
async def test_checkpoint_resume_integration(session_factory_provider, raw_engine_provider, monkeypatch):
    """Test that a crash mid-rebuild correctly writes a checkpoint and resumes successfully.

    Verifies the integration between the rebuild job orchestration, distributed lock,
    and checkpoint-aware resumption logic.
    """
    factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    raw_factory = create_session_factory(raw_engine_provider)

    # 1. Create a mocked rebuild source that throws an error after checkpoint
    assets: list[Asset] = [
        Equity(
            id=f"EQ_{i}",
            symbol=f"EQ{i}",
            name=f"Equity {i}",
            asset_class=AssetClass.EQUITY,
            sector="tech",
            price=10.0,
            currency="USD",
        )
        for i in range(120)
    ]

    call_count = 0

    def mock_build_crash(settings, on_checkpoint=None, initial_checkpoint=None, cancel_event=None):
        """Mock the build execution logic to crash after writing a checkpoint."""
        nonlocal call_count
        call_count += 1

        graph = AssetRelationshipGraph()

        # Simulate engine run_rebuild with crash
        processed = 0
        for _, asset in enumerate(assets):
            graph.add_asset(asset)
            processed += 1
            if on_checkpoint and processed % 50 == 0:
                on_checkpoint(
                    {
                        "processed_ids": list(graph.assets.keys()),
                        "last_asset_id": asset.id,
                        "processed_count": len(graph.assets),
                    }
                )

            if processed == 70:
                # Crash after 1st checkpoint but before 2nd
                raise RuntimeError("Simulated crash at 70")

        return graph, "sample"

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", mock_build_crash)

    # Create mock lock
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True

    with patch("api.routers.graph_admin.DistributedLock", return_value=mock_lock):
        job_id = "job_checkpoint_test"
        execution_id = "exec_1"

        with factory() as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(requested_by="admin_tester")
            repo.mark_rebuild_job_running(job_id, execution_id)
            session.commit()

        # Run pipeline
        with (
            patch("api.routers.graph_admin.save_graph_to_persistence", MagicMock()),
            pytest.raises(RuntimeError, match="Simulated crash"),
        ):
            graph_admin._run_rebuild_pipeline(
                raw_factory,
                get_settings(),
                db_url,
                job_id,
                execution_id,
                time.time(),
                threading.Event(),
                threading.Event(),
            )

        # 2. Verify checkpoint was written
        with factory() as session:
            repo = AssetGraphRepository(session)
            job = repo.get_rebuild_job(job_id)
            assert job is not None
            assert job.status == RebuildJobStatus.FAILED
            assert job.checkpoint_data is not None

            data = json.loads(job.checkpoint_data)
            assert data["processed_count"] == 50
            assert "EQ_49" in data["processed_ids"]

    # 3. Resume the rebuild
    # Change the mock to use the resume logic and finish
    call_count_resume = 0

    def mock_build_resume(settings, on_checkpoint=None, initial_checkpoint=None, cancel_event=None):
        """Mock the build execution logic to resume from an existing checkpoint."""
        nonlocal call_count_resume
        call_count_resume += 1

        assert initial_checkpoint is not None
        assert initial_checkpoint["processed_count"] == 50

        from src.logic.rebuild_executor import RebuildExecutor

        executor = RebuildExecutor()
        graph = executor.run_rebuild(
            assets=assets,
            regulatory_events=[],
            on_checkpoint=on_checkpoint,
            initial_checkpoint=initial_checkpoint,
            cancel_event=cancel_event,
        )
        return graph, "sample"

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", mock_build_resume)

    with patch("api.routers.graph_admin.DistributedLock", return_value=mock_lock):
        resume_exec_id = "exec_2"

        with factory() as session:
            repo = AssetGraphRepository(session)

            # Use the real recovery entrypoint pattern: create a new job to represent the retry attempt,
            # and copy the checkpoint data to it, rather than rewriting a terminal job in-place.
            failed_job = repo.get_rebuild_job(job_id)
            assert failed_job is not None
            assert failed_job.checkpoint_data is not None
            checkpoint_data = failed_job.checkpoint_data

            resume_job_id = repo.create_rebuild_job(requested_by="admin_tester")
            repo.mark_rebuild_job_running(resume_job_id, resume_exec_id)
            repo.update_rebuild_checkpoint(resume_job_id, resume_exec_id, checkpoint_data)
            session.commit()

        # Run pipeline again (resume)
        response = graph_admin._run_rebuild_pipeline(
            raw_factory,
            get_settings(),
            db_url,
            resume_job_id,
            resume_exec_id,
            time.time(),
            threading.Event(),
            threading.Event(),
        )

        assert response.status == "persisted"

        # Verify job state
        with factory() as session:
            repo = AssetGraphRepository(session)
            job = repo.get_rebuild_job(resume_job_id)
            assert job is not None
            assert job.status == RebuildJobStatus.SUCCEEDED
            # Checkpoint might be updated to 100, then 120
            assert job.checkpoint_data is not None
            data = json.loads(job.checkpoint_data)
            assert data["processed_count"] == 120
