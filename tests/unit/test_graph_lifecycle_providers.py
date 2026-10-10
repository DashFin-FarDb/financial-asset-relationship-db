"""Unit tests for graph lifecycle provider persistence helpers."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

import api.graph_lifecycle_providers as providers
from src.config.settings import Settings, get_settings, load_settings
from src.logic.asset_graph import AssetRelationshipGraph

pytestmark = pytest.mark.unit


def test_get_graph_lifecycle_settings_maps_rebuild_lock_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that GraphLifecycleSettings mirrors rebuild_lock_ttl_seconds from base Settings."""
    base_settings = Settings(rebuild_lock_ttl_seconds=450)

    monkeypatch.setattr(providers, "get_settings", lambda: base_settings)
    lifecycle_settings = providers.get_graph_lifecycle_settings()

    assert lifecycle_settings.rebuild_lock_ttl_seconds == base_settings.rebuild_lock_ttl_seconds


def test_get_graph_lifecycle_settings_maps_rebuild_lock_ttl_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default rebuild_lock_ttl_seconds should propagate unchanged through the lifecycle boundary."""
    base_settings = Settings()

    monkeypatch.setattr(providers, "get_settings", lambda: base_settings)
    lifecycle_settings = providers.get_graph_lifecycle_settings()

    assert lifecycle_settings.rebuild_lock_ttl_seconds == base_settings.rebuild_lock_ttl_seconds
    assert lifecycle_settings.rebuild_lock_ttl_seconds == 300


def test_graph_lifecycle_settings_is_frozen() -> None:
    """Verify that GraphLifecycleSettings remains an immutable configuration boundary."""
    lifecycle_settings = providers.GraphLifecycleSettings(rebuild_lock_ttl_seconds=120)

    with pytest.raises(FrozenInstanceError):
        lifecycle_settings.rebuild_lock_ttl_seconds = 999  # type: ignore[misc]


def test_get_graph_lifecycle_settings_propagates_ttl_from_loaded_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that get_graph_lifecycle_settings propagates the TTL from the loaded settings."""
    monkeypatch.setenv("REBUILD_LOCK_TTL_SECONDS", "600")
    get_settings.cache_clear()
    providers.clear_graph_lifecycle_settings_cache()
    base_settings = load_settings()
    lifecycle_settings = providers.get_graph_lifecycle_settings()
    assert base_settings.rebuild_lock_ttl_seconds == 600
    assert lifecycle_settings.rebuild_lock_ttl_seconds == base_settings.rebuild_lock_ttl_seconds


def test_resolve_hosted_graph_database_url_prefers_explicit_asset_graph_url() -> None:
    """Explicit graph persistence should override any shared hosted fallback."""
    settings = providers.GraphLifecycleSettings(
        asset_graph_database_url="postgresql://graph",
        database_url="postgresql://app",
        env=providers.DeploymentEnvironment.PREVIEW,
    )

    assert providers.resolve_hosted_graph_database_url(settings) == "postgresql://graph"


def test_resolve_hosted_graph_database_url_uses_shared_hosted_database_fallback() -> None:
    """Preview/staging deployments may fall back to the shared hosted database boundary."""
    settings = providers.GraphLifecycleSettings(
        asset_graph_database_url=None,
        database_url="postgresql://shared",
        env=providers.DeploymentEnvironment.PREVIEW,
    )

    assert providers.resolve_hosted_graph_database_url(settings) == "postgresql://shared"


@pytest.mark.parametrize(
    ("vercel_env", "expected_url"),
    [
        (providers.DeploymentEnvironment.PREVIEW, "postgresql://shared"),
        (None, None),
    ],
    ids=["vercel-preview", "no-hosted-marker"],
)
def test_resolve_hosted_graph_database_url_honors_vercel_environment(
    vercel_env: providers.DeploymentEnvironment | None,
    expected_url: str | None,
) -> None:
    """Vercel deployments should fall back only when the hosted env marker is present."""
    settings = providers.GraphLifecycleSettings(
        asset_graph_database_url=None,
        database_url="postgresql://shared",
        env=providers.DeploymentEnvironment.DEVELOPMENT,
        vercel_env=vercel_env,
    )

    assert providers.resolve_hosted_graph_database_url(settings) == expected_url


def test_resolve_hosted_graph_database_url_supports_legacy_settings_objects() -> None:
    """Legacy settings objects should keep the old database_url compatibility seam."""

    class LegacySettings:
        """Mock settings object representing legacy configuration."""

        database_url = "postgresql://legacy"
        vercel_env = providers.DeploymentEnvironment.PREVIEW

    assert providers.resolve_hosted_graph_database_url(LegacySettings()) == "postgresql://legacy"


def test_save_graph_with_session_runs_pre_commit_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-commit check should execute before committing graph persistence."""
    session = MagicMock()
    pre_commit_check = MagicMock()
    graph = AssetRelationshipGraph()

    monkeypatch.setattr(providers.AssetGraphRepository, "save_graph", lambda self, _graph: None)

    providers._save_graph_with_session(
        session, graph, pre_commit_check=pre_commit_check
    )  # pylint: disable=protected-access

    pre_commit_check.assert_called_once_with()
    session.commit.assert_called_once_with()


def test_save_graph_with_session_rolls_back_when_pre_commit_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-commit check failure should roll back and raise GraphPersistenceSaveError."""
    session = MagicMock()
    graph = AssetRelationshipGraph()

    monkeypatch.setattr(providers.AssetGraphRepository, "save_graph", lambda self, _graph: None)

    def fail_pre_commit() -> None:
        """Raise a RuntimeError to simulate a pre-commit check failure."""
        raise RuntimeError("lost lock")

    with pytest.raises(RuntimeError):
        providers._save_graph_with_session(
            session, graph, pre_commit_check=fail_pre_commit
        )  # pylint: disable=protected-access

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_build_rebuild_graph_fails_closed_when_no_source_available() -> None:
    """build_rebuild_graph must fail closed when neither cache nor real data is available."""
    settings = providers.GraphLifecycleSettings(
        graph_cache_path=None,
        use_real_data_fetcher=False,
    )

    with pytest.raises(
        providers.AuthoritativeGraphUnavailableError,
        match="No valid rebuild source available.",
    ):
        providers.build_rebuild_graph(settings)


def test_build_rebuild_graph_uses_cache_when_available(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_rebuild_graph must load cache when configured cache path exists."""
    cache_file = tmp_path / "cache.json"  # type: ignore[operator]
    cache_file.write_text("{}", encoding="utf-8")
    expected_graph = AssetRelationshipGraph()

    monkeypatch.setattr(
        providers,
        "load_graph_from_cache_path",
        lambda path, enable_network: (expected_graph, "cache"),
    )

    settings = providers.GraphLifecycleSettings(
        graph_cache_path=str(cache_file),
        use_real_data_fetcher=False,
    )
    graph, source = providers.build_rebuild_graph(settings)

    assert graph is expected_graph
    assert source == "cache"


def test_build_rebuild_graph_uses_real_data_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_rebuild_graph must use real data fetcher when enabled."""
    expected_graph = AssetRelationshipGraph()

    class MockFetcher:
        """Mock RealDataFetcher for unit testing."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize mock fetcher."""

        def fetch_raw_data_with_source(self, cancel_event: object = None) -> tuple[dict, list, str]:
            """Return mock raw data."""
            return ({}, [], "real_data")

        def _persist_cache(self, graph: object) -> None:
            """Mock cache persistence without disk writes."""

    class MockExecutor:
        """Mock RebuildExecutor for unit testing."""

        def run_rebuild(self, **kwargs: object) -> AssetRelationshipGraph:
            return expected_graph

    monkeypatch.setattr("src.data.real_data_fetcher.RealDataFetcher", MockFetcher)
    monkeypatch.setattr("src.logic.rebuild_executor.RebuildExecutor", MockExecutor)

    settings = providers.GraphLifecycleSettings(
        graph_cache_path=None,
        use_real_data_fetcher=True,
    )
    graph, source = providers.build_rebuild_graph(settings)

    assert graph is expected_graph
    assert source == "real_data"


def test_build_rebuild_graph_cancels_before_cache_load(tmp_path: object) -> None:
    """build_rebuild_graph must raise RebuildCancelledError when cancel_event is set prior to loading cache."""
    cache_file = tmp_path / "cache.json"  # type: ignore[operator]
    cache_file.write_text("{}", encoding="utf-8")

    settings = providers.GraphLifecycleSettings(
        graph_cache_path=str(cache_file),
        use_real_data_fetcher=False,
    )
    import threading

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(providers.RebuildCancelledError, match="Rebuild cancelled"):
        providers.build_rebuild_graph(settings, cancel_event=cancel_event)


def test_build_rebuild_graph_propagates_cancellation_during_cache_validation(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_rebuild_graph must propagate RebuildCancelledError when cancelled during cache loading."""
    cache_file = tmp_path / "cache.json"  # type: ignore[operator]
    cache_file.write_text("{}", encoding="utf-8")

    import threading

    cancel_event = threading.Event()

    def mock_load_cache(path: str, enable_network: bool, cancel_event: threading.Event | None = None):
        raise providers.RebuildCancelledError("Cancelled in cache validation")

    monkeypatch.setattr(providers, "load_graph_from_cache_path", mock_load_cache)

    settings = providers.GraphLifecycleSettings(
        graph_cache_path=str(cache_file),
        use_real_data_fetcher=False,
    )

    with pytest.raises(providers.RebuildCancelledError, match="Cancelled in cache validation"):
        providers.build_rebuild_graph(settings, cancel_event=cancel_event)
