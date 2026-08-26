"""Unit tests for opt-in FastAPI Sentry initialization."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import pytest
from sentry_sdk.utils import BadDsn

import api
from src.config.settings import DeploymentEnvironment, Settings, get_settings, load_settings
from src.observability.sentry import initialize_sentry

pytestmark = pytest.mark.unit

_SYNTHETIC_DSN = "synthetic://unit-test-dsn"


@pytest.mark.parametrize("dsn", [None, "", "   "])
def test_initialize_sentry_skips_missing_or_blank_dsn(dsn: str | None) -> None:
    """Missing or blank configuration must not initialize the SDK."""
    with patch("src.observability.sentry.sentry_sdk.init") as mock_init:
        initialized = initialize_sentry(Settings(sentry_dsn=dsn))

    assert initialized is False
    mock_init.assert_not_called()


def test_initialize_sentry_uses_fixed_privacy_profile() -> None:
    """A synthetic DSN must initialize only with the ratified safe options."""
    settings = Settings(
        env=DeploymentEnvironment.STAGING,
        sentry_dsn=_SYNTHETIC_DSN,
        sentry_environment="preview",
        sentry_release="synthetic-release",
    )

    with patch("src.observability.sentry.sentry_sdk.init") as mock_init:
        initialized = initialize_sentry(settings)

    assert initialized is True
    mock_init.assert_called_once_with(
        dsn=_SYNTHETIC_DSN,
        environment="preview",
        release="synthetic-release",
        send_default_pii=False,
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
    )


def test_initialize_sentry_skips_reinitialization_when_client_is_active() -> None:
    """Repeated application-factory calls must not initialize the process-wide SDK twice."""
    settings = Settings(sentry_dsn=_SYNTHETIC_DSN)

    with (
        patch("src.observability.sentry.sentry_sdk.get_client") as mock_get_client,
        patch("src.observability.sentry.sentry_sdk.init") as mock_init,
    ):
        mock_get_client.return_value.is_active.return_value = True
        initialized = initialize_sentry(settings)

    assert initialized is True
    mock_get_client.return_value.is_active.assert_called_once_with()
    mock_init.assert_not_called()


@pytest.mark.parametrize("release", [None, "", "   "])
def test_initialize_sentry_omits_unconfigured_release(release: str | None) -> None:
    """An unset or blank release must not be passed to the SDK."""
    settings = Settings(env=DeploymentEnvironment.TEST, sentry_dsn=_SYNTHETIC_DSN, sentry_release=release)

    with patch("src.observability.sentry.sentry_sdk.init") as mock_init:
        initialize_sentry(settings)

    assert "release" not in mock_init.call_args.kwargs
    assert mock_init.call_args.kwargs["environment"] == "test"


def test_initialize_sentry_does_not_expose_dsn(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    """Initialization must not print, log, or return the configured DSN."""
    settings = Settings(sentry_dsn=_SYNTHETIC_DSN)
    with patch("src.observability.sentry.sentry_sdk.init"):
        result = initialize_sentry(settings)

    captured = capsys.readouterr()
    assert result is True
    assert _SYNTHETIC_DSN not in captured.out
    assert _SYNTHETIC_DSN not in captured.err
    assert _SYNTHETIC_DSN not in caplog.text
    assert _SYNTHETIC_DSN not in repr(result)
    assert _SYNTHETIC_DSN not in repr(settings)
    assert "sentry_dsn" not in settings.model_dump()
    assert _SYNTHETIC_DSN not in settings.model_dump_json()


def test_initialize_sentry_rejects_malformed_dsn_without_logging(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    """A malformed optional DSN must not break startup or expose its value."""
    malformed_dsn = "synthetic-malformed-dsn"
    with patch("src.observability.sentry.sentry_sdk.init", side_effect=BadDsn("invalid synthetic DSN")):
        initialized = initialize_sentry(Settings(sentry_dsn=malformed_dsn))

    captured = capsys.readouterr()
    assert initialized is False
    assert malformed_dsn not in captured.out
    assert malformed_dsn not in captured.err
    assert malformed_dsn not in caplog.text


def test_load_settings_reads_sentry_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Centralized settings must load each Sentry value from its named environment variable."""
    monkeypatch.setenv("SENTRY_DSN", _SYNTHETIC_DSN)
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "preview")
    monkeypatch.setenv("SENTRY_RELEASE", "synthetic-release")

    settings = load_settings()

    assert settings.sentry_dsn == _SYNTHETIC_DSN
    assert settings.sentry_environment == "preview"
    assert settings.sentry_release == "synthetic-release"


def test_create_app_succeeds_without_sentry_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """The FastAPI application factory must remain available when Sentry is disabled."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    get_settings.cache_clear()
    monkeypatch.delitem(sys.modules, "api.app_factory", raising=False)
    monkeypatch.delattr(api, "app_factory", raising=False)

    try:
        with patch("sentry_sdk.init") as mock_init:
            app_factory = importlib.import_module("api.app_factory")
            app = app_factory.create_app()

        assert app.title == "Financial Asset Relationship API"
        route_paths = [getattr(route, "path", "").lower() for route in app.routes]
        assert all("sentry" not in path and "crash" not in path for path in route_paths)
        mock_init.assert_not_called()
    finally:
        get_settings.cache_clear()


def test_create_app_succeeds_with_malformed_sentry_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid optional monitoring configuration must not prevent app creation."""
    monkeypatch.setenv("SENTRY_DSN", "synthetic-malformed-dsn")
    get_settings.cache_clear()
    monkeypatch.delitem(sys.modules, "api.app_factory", raising=False)
    monkeypatch.delattr(api, "app_factory", raising=False)

    try:
        with patch("sentry_sdk.init", side_effect=BadDsn("invalid synthetic DSN")) as mock_init:
            app_factory = importlib.import_module("api.app_factory")
            app = app_factory.create_app()

        assert app.title == "Financial Asset Relationship API"
        assert mock_init.call_count >= 1
    finally:
        get_settings.cache_clear()


def test_create_app_invokes_sentry_initializer(monkeypatch: pytest.MonkeyPatch) -> None:
    """The production FastAPI factory must invoke the isolated initialization seam."""
    monkeypatch.delitem(sys.modules, "api.app_factory", raising=False)
    monkeypatch.delattr(api, "app_factory", raising=False)
    with patch("src.observability.sentry.initialize_sentry") as mock_initialize:
        app_factory = importlib.import_module("api.app_factory")
        mock_initialize.reset_mock()
        app = app_factory.create_app()

    assert app.title == "Financial Asset Relationship API"
    mock_initialize.assert_called_once_with()
