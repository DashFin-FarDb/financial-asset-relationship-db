"""CORS/origin policy helpers for the FastAPI application."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import get_settings
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

logger = logging.getLogger(__name__)


def _is_http_local_in_dev(origin_url: str, current_env: str) -> bool:
    """Allow HTTP localhost origins only in development."""
    return current_env == "development" and bool(re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", origin_url))


def _is_https_local(origin_url: str, current_env: str) -> bool:
    """Allow HTTPS localhost in all environments, and HTTPS loopback only in development."""
    if re.match(r"^https://localhost(:\d+)?$", origin_url):
        return True
    return current_env == "development" and bool(re.match(r"^https://127\.0\.0\.1(:\d+)?$", origin_url))


def _is_vercel_preview(origin_url: str) -> bool:
    """Return whether the origin is a Vercel preview deployment."""
    return bool(re.match(r"^https://[a-zA-Z0-9\-\.]+\.vercel\.app$", origin_url))


def _has_forbidden_origin_parts(parsed_origin: object) -> bool:
    """Reject origins with path, params, query, fragment, or userinfo."""
    return any(
        [
            getattr(parsed_origin, "path", ""),
            getattr(parsed_origin, "params", ""),
            getattr(parsed_origin, "query", ""),
            getattr(parsed_origin, "fragment", ""),
            getattr(parsed_origin, "username", None),
            getattr(parsed_origin, "password", None),
        ]
    )


def _is_valid_https_domain(origin_url: str) -> bool:
    """
    Determine whether an origin string is a valid HTTPS origin with a hostname and optional port.
    
    Accepts internationalized hostnames (IDNA) and rejects origins that include path, params, query, fragment, or userinfo, or that do not use the HTTPS scheme. On parsing or IDNA conversion errors, an observability event is emitted and the function returns `False`.
    
    Returns:
        `True` if `origin_url` is an HTTPS origin with a valid hostname (after IDNA normalization) and an optional port, `False` otherwise.
    """
    if not origin_url.startswith("https://"):
        return False
    try:
        parsed = urlparse(origin_url)
        if _has_forbidden_origin_parts(parsed):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        ascii_hostname = hostname.encode("idna").decode("ascii")
        port_suffix = f":{parsed.port}" if parsed.port else ""
        ascii_url = f"https://{ascii_hostname}{port_suffix}"
        return bool(
            re.match(
                r"^https://[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
                r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
                r"\.[a-zA-Z0-9\-]{2,}(:\d+)?$",
                ascii_url,
            )
        )
    except ValueError as exc:
        log_event(
            logger,
            logging.DEBUG,
            ObservabilityEvent(
                event="cors_origin_validation_failed",
                message=f"Failed to validate origin '{origin_url}': {exc}",
                metadata={"origin_url": origin_url, "error": str(exc)},
            ),
        )
        return False


def _is_supported_origin_format(origin_url: str, current_env: str) -> bool:
    """Return whether an origin string matches supported CORS origin formats."""
    return (
        _is_http_local_in_dev(origin_url, current_env)
        or _is_https_local(origin_url, current_env)
        or _is_vercel_preview(origin_url)
        or _is_valid_https_domain(origin_url)
    )


def validate_origin(origin_url: str) -> bool:
    """Return whether the origin is allowed by the current CORS policy."""
    if not origin_url:
        return False

    settings = get_settings()
    current_env = settings.env

    if origin_url in settings.allowed_origins:
        return True

    return _is_supported_origin_format(origin_url, current_env)


def build_allowed_origins() -> list[str]:
    """
    Constructs the list of origins allowed by CORS for the application.
    
    Includes environment-specific localhost origins (HTTPS-only in non-development, HTTP+HTTPS in development) and appends configured origins from settings that match supported origin formats. Configured origins that are rejected are skipped and emitted to observability.
    
    Returns:
        allowed_origins (list[str]): Origins suitable for FastAPI CORSMiddleware `allow_origins`.
    """
    settings = get_settings()
    allowed_origins: list[str] = []

    if settings.env == "development":
        allowed_origins.extend(
            [
                "http://localhost:3000",
                "http://localhost:7860",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:7860",
                "https://localhost:3000",
                "https://localhost:7860",
                "https://127.0.0.1:3000",
                "https://127.0.0.1:7860",
            ]
        )
    else:
        allowed_origins.extend(
            [
                "https://localhost:3000",
                "https://localhost:7860",
            ]
        )

    configured_origins = settings.allowed_origins
    for origin in configured_origins:
        if _is_supported_origin_format(origin, settings.env):
            allowed_origins.append(origin)
        else:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="cors_invalid_origin_skipped",
                    message=f"Skipping invalid CORS origin: {origin}",
                    metadata={"origin": origin},
                ),
            )

    return allowed_origins


def configure_cors(app: FastAPI) -> None:
    """Attach CORS middleware to the FastAPI application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=build_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Correlation-ID"],
        expose_headers=["X-Request-ID", "X-Correlation-ID"],
    )
