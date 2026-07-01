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
    Check whether an origin is a valid HTTPS origin with a hostname and optional port.

    Accepts internationalized hostnames (IDNA). Rejects origins that include path, params, query, fragment, or
    userinfo, or that do not use the HTTPS scheme. On parsing or IDNA conversion errors, emits an observability
    event ("cors_origin_validation_failed") and returns `False`.

    Returns:
        `True` if the origin uses HTTPS, contains a hostname (after IDNA normalization), and optionally a port;
            `False` otherwise.
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
                message=f"Failed to validate origin '{origin_url}': {type(exc).__name__}",
                metadata={"origin_url": origin_url, "error": type(exc).__name__},
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
    Build the CORS allowlist by combining environment-specific localhost entries with validated configured origins.

    Configured origins that do not match supported origin formats are skipped and emitted to observability as
    `cors_invalid_origin_skipped`.

    Returns:
        allowed_origins (list[str]): List of origin strings suitable for FastAPI CORSMiddleware `allow_origins`.
    """
    settings = get_settings()
    allowed_origins: list[str] = []

    frontend_port = getattr(settings, "frontend_port", 3000)
    gradio_port = getattr(settings, "gradio_port", 7860)

    def _local_origins(port_list: list[int], include_http_local_in_dev: bool) -> list[str]:
        items = []
        for port in port_list:
            if include_http_local_in_dev:
                items.extend(
                    [
                        f"http://localhost:{port}",
                        f"http://127.0.0.1:{port}",
                    ]
                )
            items.extend(
                [
                    f"https://localhost:{port}",
                    f"https://127.0.0.1:{port}",
                ]
            )
        if settings.env != "development":
            # for production, only keep https localhost entries (if desired)
            items = [i for i in items if i.startswith("https://")]
        return items

    if settings.env == "development":
        allowed_origins.extend(_local_origins([frontend_port, gradio_port], include_http_local_in_dev=True))
    else:
        allowed_origins.extend(_local_origins([frontend_port, gradio_port], include_http_local_in_dev=False))

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
