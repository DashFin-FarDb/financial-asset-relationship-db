"""Clean restart-recovery path using the real lifecycle and persistence seams."""

from pathlib import Path

import pytest

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as graph_lifecycle_providers
from tests.integration import restart_recovery_helpers as helpers
from tests.integration.facade import (
    AssetGraphRepository,
    DistributedLock,
    LockState,
    RecoveryGate,
    session_scope,
)

pytestmark = pytest.mark.integration


def test_clean_restart_pipeline_loads_graph_after_gate_and_lock_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load persisted graph truth after acquiring the rebuild lock."""
    db_url, engine, session_factory = helpers.database(tmp_path)
    lock = None
    try:
        helpers.persist_graph(session_factory, helpers.graph())
        helpers.persist_graph(session_factory, helpers.graph())
        monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", db_url)
        graph_lifecycle.reset_graph()
        graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

        startup_graph, startup_source = graph_lifecycle.get_graph_with_startup_source()
        assert startup_source is not None
        assert startup_source.source == graph_lifecycle.GraphStartupSource.PERSISTED
        helpers.assert_graph_contents(startup_graph)

        lock = DistributedLock(
            session_factory,
            helpers.LOCK_NAME,
            ttl_seconds=helpers.LOCK_TTL,
        )
        claim = getattr(lock, "acquire")
        assert claim()
        assert lock.check_state() == LockState.VALID

        RecoveryGate(
            session_factory=session_factory,
            lock=lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=helpers.LOCK_TTL,
            enable_automatic_recovery=True,
        ).ensure_safe_to_execute()
        assert lock.check_state() == LockState.VALID

        with session_scope(session_factory) as session:
            durable_graph = AssetGraphRepository(session).load_graph()
        helpers.assert_graph_contents(durable_graph)
    finally:
        if lock is not None:
            try:
                lock.release()
            except Exception:  # noqa: BLE001
                pass
        graph_lifecycle.reset_graph()
        graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
        engine.dispose()
