"""Integration tests for distributed rebuild coordination and synchronization."""

import threading

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

import api.graph_lifecycle_providers as providers
from api.app_factory import create_app
from api.auth import User, get_current_active_user
from api.graph_lifecycle import get_graph, graph_state, reset_graph, sync_with_latest_rebuild
from src.config.settings import get_settings
from src.data.database import create_session_factory, init_db
from src.data.distributed_lock import DistributedLock
from src.data.repository import AssetGraphRepository, session_scope
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


@pytest.fixture
def authorized_app(monkeypatch, tmp_path):
    """Create an app with an authorized operator and file-backed SQLite."""
    db_path = tmp_path / "asset_graph.db"
    db_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", db_url)
    monkeypatch.setenv("ADMIN_USERNAME", "operator")

    # Initialize DB
    engine = create_engine(db_url)
    init_db(engine)
    engine.dispose()

    get_settings.cache_clear()
    providers.clear_graph_lifecycle_settings_cache()
    reset_graph()

    app = create_app()

    def active_user() -> User:
        """Return a mock active operator user for dependency override."""
        return User(username="operator", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user

    yield app

    reset_graph()
    providers.clear_graph_lifecycle_settings_cache()
    get_settings.cache_clear()


@pytest.mark.integration
def test_distributed_lock_allows_only_one_holder_across_instances(authorized_app):
    """Verify two independent holders cannot both acquire the same distributed lock."""
    db_url = get_settings().asset_graph_database_url
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine1 = create_engine(db_url, connect_args=connect_args)
    engine2 = create_engine(db_url, connect_args=connect_args)
    session_factory1 = create_session_factory(engine1)
    session_factory2 = create_session_factory(engine2)
    lock1 = DistributedLock(session_factory1, "graph_rebuild", holder_id="instance-1", ttl_seconds=60)
    lock2 = DistributedLock(session_factory2, "graph_rebuild", holder_id="instance-2", ttl_seconds=60)

    barrier = threading.Barrier(2)
    results: dict[str, bool] = {}
    errors: dict[str, Exception] = {}

    from src.data.distributed_lock import LockAcquisitionTimeout

    def attempt(holder: str, lock: DistributedLock) -> None:
        """Attempt to acquire a lock and record the success or failure."""
        try:
            barrier.wait()
            results[holder] = bool(lock.acquire())
        except threading.BrokenBarrierError:
            results[holder] = False
        except LockAcquisitionTimeout:
            results[holder] = False
        except SQLAlchemyError as exc:
            errors[holder] = exc
            results[holder] = False

    t1 = threading.Thread(target=attempt, args=("instance-1", lock1))
    t2 = threading.Thread(target=attempt, args=("instance-2", lock2))
    try:
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)
        assert not t1.is_alive() and not t2.is_alive()
        assert not errors, f"Unexpected SQLAlchemy error(s): {errors}"
        assert sorted(results.values()) == [False, True]
    finally:
        if results.get("instance-1"):
            lock1.release()
        if results.get("instance-2"):
            lock2.release()
        engine1.dispose()
        engine2.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_instance_synchronization_detects_new_job(authorized_app):
    """Verify that sync_with_latest_rebuild detects and loads a new graph."""
    db_url = get_settings().asset_graph_database_url

    # 1. Initially, we have some graph
    graph1 = AssetRelationshipGraph()
    graph1.add_asset(Equity(id="A1", symbol="A1", name="A1", asset_class=AssetClass.EQUITY, sector="S1", price=10.0))

    # Manually persist it as a successful job
    engine = create_engine(db_url)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        repo.save_graph(graph1)
        job_id = repo.create_rebuild_job(requested_by="user1", source="sample")
        repo.mark_rebuild_job_running(job_id)
        repo.mark_rebuild_job_succeeded(job_id, node_count=1, edge_count=0, duration_ms=100)

    # Load it into the app
    sync_with_latest_rebuild()
    assert "A1" in get_graph().assets
    assert graph_state.last_synced_job_id == job_id

    # 2. Simulate another instance performing a rebuild
    graph2 = AssetRelationshipGraph()
    graph2.add_asset(Equity(id="A2", symbol="A2", name="A2", asset_class=AssetClass.EQUITY, sector="S2", price=20.0))

    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        repo.save_graph(graph2)
        job_id2 = repo.create_rebuild_job(requested_by="user2", source="sample")
        repo.mark_rebuild_job_running(job_id2)
        repo.mark_rebuild_job_succeeded(job_id2, node_count=1, edge_count=0, duration_ms=200)

    # 3. Trigger sync and verify it updated
    sync_with_latest_rebuild()
    assert "A2" in get_graph().assets
    assert "A1" not in get_graph().assets
    assert graph_state.last_synced_job_id == job_id2

    engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_data(authorized_app):
    """Verify that the /metrics endpoint is accessible and returns Prometheus format."""
    transport = ASGITransport(app=authorized_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        assert "graph_rebuild_requests_total" in response.text
        assert "graph_assets_count" in response.text
        assert "graph_relationships_count" in response.text
        assert response.headers["content-type"].startswith("text/plain")
