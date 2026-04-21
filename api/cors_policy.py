"""CORS/origin policy helpers for the FastAPI application."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _is_http_local_in_dev(origin_url: str, current_env: str) -> bool:
    """Allow HTTP localhost origins only in development."""
    return current_env == "development" and bool(re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", origin_url))


def _is_https_local(origin_url: str) -> bool:
    """Return whether the origin is HTTPS localhost or 127.0.0.1."""
    return bool(re.match(r"^https://(localhost|127\.0\.0\.1)(:\d+)?$", origin_url))


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
    """Validate a secure HTTPS origin with hostname and optional port."""
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
        logger.debug("Failed to validate origin '%s': %s", origin_url, exc)
        return False


def _is_supported_origin_format(origin_url: str, current_env: str) -> bool:
    """Return whether an origin string matches supported CORS origin formats."""
    return (
        _is_http_local_in_dev(origin_url, current_env)
        or _is_https_local(origin_url)
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
    """Build the allow-origins list for FastAPI CORS middleware."""
    settings = get_settings()
    allowed_origins: list[str] = []

    if settings.env == "development":
        allowed_origins.extend(
            [
                "http://localhost:3000",
                "http://localhost:7860",
                "https://localhost:3000",
                "https://localhost:7860",
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
            logger.warning("Skipping invalid CORS origin: %s", origin)

    return allowed_origins


def configure_cors(app: FastAPI) -> None:
    """Attach CORS middleware to the FastAPI application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=build_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
