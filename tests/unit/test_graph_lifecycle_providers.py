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

    providers._save_graph_with_session(session, graph, pre_commit_check=pre_commit_check)  # pylint: disable=protected-access

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
        providers._save_graph_with_session(session, graph, pre_commit_check=fail_pre_commit)  # pylint: disable=protected-access

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()
