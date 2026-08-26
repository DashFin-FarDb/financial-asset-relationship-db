"""Opt-in Sentry initialization for the production FastAPI application."""

from __future__ import annotations

from typing import Any

import sentry_sdk
from sentry_sdk.utils import BadDsn

from src.config.settings import Settings, get_settings
from src.observability.events import APPLICATION_STARTUP_FAILED_EVENT


def _filter_duplicate_startup_log_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    """Drop the top-level startup log whose exception is always subsequently re-raised."""
    extra = event.get("extra")
    is_duplicate_startup_log = (
        event.get("exception") is None
        and isinstance(event.get("logentry"), dict)
        and isinstance(extra, dict)
        and extra.get("event") == APPLICATION_STARTUP_FAILED_EVENT
    )
    return None if is_duplicate_startup_log else event


def _configured_value(value: str | None) -> str | None:
    """Return a stripped configuration value, or ``None`` when it is blank."""
    if value is None:
        return None
    stripped_value = value.strip()
    return stripped_value or None


def initialize_sentry(settings: Settings | None = None) -> bool:
    """Initialize Sentry with the fixed privacy profile when a DSN is configured."""
    current_settings = settings or get_settings()
    dsn = _configured_value(current_settings.sentry_dsn)
    if dsn is None:
        return False

    if sentry_sdk.get_client().is_active():
        return True

    environment = _configured_value(current_settings.sentry_environment) or current_settings.env.value
    options: dict[str, Any] = {
        "dsn": dsn,
        "environment": environment,
        "send_default_pii": False,
        "traces_sample_rate": 0.0,
        "profiles_sample_rate": 0.0,
        "before_send": _filter_duplicate_startup_log_event,
    }
    release = _configured_value(current_settings.sentry_release)
    if release is not None:
        options["release"] = release

    try:
        sentry_sdk.init(**options)
    except BadDsn:
        return False
    return True
