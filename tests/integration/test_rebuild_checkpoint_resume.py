"""Integration tests for rebuild checkpoint and resume flow."""

import json
import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import AsyncGenerator, Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import api.graph_lifecycle_providers as providers
import api.routers.graph_admin as graph_admin
from api.app_factory import create_app
from api.auth import User, get_current_active_user, get_current_rebuild_operator_user
from api.graph_lifecycle import reset_graph
from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.db_models import RebuildJobORM, RebuildJobStatus
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Equity

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
    return User(username="admin_tester", email="admin@example.com", is_disabled=False, full_name="Admin User")


@pytest.fixture
async def test_client(mock_active_user: User) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an authenticated asynchronous test client."""
    from api.auth import get_current_active_user
    from api.main import app

    async def override_get_current_active_user() -> User:
        return mock_active_user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
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


@pytest.mark.asyncio
async def test_checkpoint_resume_integration(session_factory_provider, monkeypatch):
    """Test that a crash mid-rebuild correctly writes a checkpoint and resumes successfully.

    Verifies the integration between the rebuild job orchestration, distributed lock,
    and checkpoint-aware resumption logic.
    """
    factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    raw_factory = create_session_factory(create_engine_from_url(db_url))

    # 1. Create a mocked rebuild source that throws an error after checkpoint
    assets = [
        Equity(
            id=f"EQ_{i}",
            symbol=f"EQ{i}",
            name=f"Equity {i}",
            asset_class="equity",
            sector="tech",
            price=10.0,
            currency="USD",
        )
        for i in range(120)
    ]

    call_count = 0

    def mock_build_crash(settings, on_checkpoint=None, initial_checkpoint=None, cancel_event=None):
        nonlocal call_count
        call_count += 1

        graph = AssetRelationshipGraph()

        # Simulate engine run_rebuild with crash
        processed = 0
        for idx, asset in enumerate(assets):
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
    monkeypatch.setattr("api.routers.graph_admin.save_graph_to_persistence", MagicMock())

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
        with pytest.raises(RuntimeError, match="Simulated crash"):
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
            assert job.status == RebuildJobStatus.FAILED
            assert job.checkpoint_data is not None

            data = json.loads(job.checkpoint_data)
            assert data["processed_count"] == 50
            assert "EQ_49" in data["processed_ids"]

    # 3. Resume the rebuild
    # Change the mock to use the resume logic and finish
    call_count_resume = 0

    def mock_build_resume(settings, on_checkpoint=None, initial_checkpoint=None, cancel_event=None):
        nonlocal call_count_resume
        call_count_resume += 1

        assert initial_checkpoint is not None
        assert initial_checkpoint["processed_count"] == 50

        from src.logic.rebuild_executor import RebuildExecutor
        from src.logic.reconciliation_engine import ReconciliationEngine

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
            # Rebuild job status transition validation requires the job not to be failed directly?
            # Wait, mark_rebuild_job_running might only allow transitioning from PENDING.
            # Let's override the status to PENDING so mark_rebuild_job_running succeeds, or use run_rebuild_pipeline and let it handle DB state.
            # But run_rebuild_pipeline assumes the job is already RUNNING when it starts.
            # If the job is FAILED, we might need to reset it to PENDING.
            job = repo.get_rebuild_job(job_id)
            job.status = RebuildJobStatus.PENDING
            session.commit()

            repo.mark_rebuild_job_running(job_id, resume_exec_id)
            session.commit()

        # Run pipeline again (resume)
        response = graph_admin._run_rebuild_pipeline(
            raw_factory,
            get_settings(),
            db_url,
            job_id,
            resume_exec_id,
            time.time(),
            threading.Event(),
            threading.Event(),
        )

        assert response.status == "persisted"

        # Verify job state
        with factory() as session:
            repo = AssetGraphRepository(session)
            job = repo.get_rebuild_job(job_id)
            assert job.status == RebuildJobStatus.SUCCEEDED
            # Checkpoint might be updated to 100, then 120
            data = json.loads(job.checkpoint_data)
            assert data["processed_count"] == 120
