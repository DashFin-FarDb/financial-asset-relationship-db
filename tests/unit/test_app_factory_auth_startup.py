"""Unit tests for app factory auth startup verification."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from api import app_factory
from api import auth as api_auth
from api import database as api_database
from src.config.settings import DeploymentEnvironment
from src.data.database import SchemaCompatibilityError

pytestmark = pytest.mark.unit


@pytest.fixture
def base_settings() -> SimpleNamespace:
    """Provide minimal mock configuration settings layout."""
    return SimpleNamespace(
        database_url="sqlite:///:memory:",
        has_durable_graph_persistence=True,
        graph_sync_interval_seconds=1.0,
    )


@pytest.mark.asyncio
async def test_hosted_fallback_cannot_degrade_schema_incompatibility(base_settings: SimpleNamespace) -> None:
    """Schema incompatibility must fail closed even where transient failures may degrade."""
    hosted_settings = SimpleNamespace(
        **vars(base_settings),
        env=DeploymentEnvironment.PREVIEW,
        vercel_env="preview",
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            app_factory,
            "_verify_auth_database",
            lambda: (_ for _ in ()).throw(SchemaCompatibilityError("incompatible auth schema")),
        )
        with pytest.raises(SchemaCompatibilityError, match="incompatible auth schema"):
            await app_factory._initialize_application_state(  # pylint: disable=protected-access
                cast(Any, hosted_settings),
                has_persistence=True,
                hosted_startup_degradation_allowed=True,
            )


@pytest.mark.asyncio
async def test_auth_database_verification_timeout_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """A stalled auth catalog read must not block startup indefinitely."""

    async def _never_complete(*_args: object, **_kwargs: object) -> None:
        """Model a catalog call that never returns."""
        await asyncio.Event().wait()

    monkeypatch.setattr(app_factory.asyncio, "to_thread", _never_complete)
    monkeypatch.setattr(app_factory, "_AUTH_DATABASE_VERIFICATION_TIMEOUT_SECONDS", 0.001)

    with pytest.raises(SchemaCompatibilityError, match="verification timed out"):
        await app_factory._initialize_application_state(  # pylint: disable=protected-access
            cast(Any, base_settings),
            has_persistence=False,
            hosted_startup_degradation_allowed=False,
        )


def test_auth_runtime_verification_does_not_call_mutators(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auth startup verification must not create schema or seed credentials."""
    verify_schema = MagicMock()
    verify_authority = MagicMock()
    monkeypatch.setattr(api_database, "verify_schema_compatibility", verify_schema)
    monkeypatch.setattr(api_database, "verify_runtime_authority", verify_authority)
    monkeypatch.setattr(api_auth.user_repository, "has_users", lambda: True)
    initialize = MagicMock(side_effect=AssertionError("runtime DDL forbidden"))
    seed = MagicMock(side_effect=AssertionError("runtime credential seed forbidden"))
    monkeypatch.setattr(api_database, "initialize_schema", initialize)
    monkeypatch.setattr(api_auth, "seed_credentials_from_settings", seed)

    app_factory._verify_auth_database()  # pylint: disable=protected-access

    verify_schema.assert_called_once_with()
    verify_authority.assert_called_once_with()
    initialize.assert_not_called()
    seed.assert_not_called()


def test_auth_runtime_verification_sanitizes_unexpected_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Driver details must not escape the auth startup verification boundary."""
    monkeypatch.setattr(
        api_database,
        "verify_schema_compatibility",
        MagicMock(side_effect=OSError("credential-bearing driver detail")),
    )

    with pytest.raises(SchemaCompatibilityError, match=r"failed \(OSError\)") as exc_info:
        app_factory._verify_auth_database()  # pylint: disable=protected-access

    assert "credential-bearing" not in str(exc_info.value)
