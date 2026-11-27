"""Rate limiting configuration for the Financial Asset Relationship Database API (H-P3-02).

Provides:
- Proxy-aware client IP extraction with strict IP validation (resistant to header spoofing).
- Configurable global default rate limits (``RATE_LIMIT_DEFAULT``, default ``120/minute``).
- Optional shared storage backend (``RATE_LIMIT_STORAGE_URI``, e.g. ``redis://...``,
  defaulting to ``memory://`` for local/single-instance development).
"""

from __future__ import annotations

import ipaddress
import os

from fastapi import Request

# pylint: disable=import-error
from slowapi import Limiter  # type: ignore[import-not-found]
from slowapi.util import get_remote_address  # type: ignore[import-not-found]

# pylint: enable=import-error

DEFAULT_RATE_LIMIT = "120/minute"
DEFAULT_STORAGE_URI = "memory://"


def _trust_proxy_headers() -> bool:
    """Return True when reverse-proxy IP headers should be trusted."""
    raw = os.getenv("TRUST_PROXY_HEADERS")
    if raw is not None and raw.strip():
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    # Trust Vercel edge proxy headers automatically in Vercel deployments.
    return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))


def _trusted_proxy_hops() -> int:
    """Return the number of trusted reverse-proxy hops (minimum 1)."""
    raw = os.getenv("TRUSTED_PROXY_COUNT", "1").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def _parse_valid_ip(candidate: str | None) -> str | None:
    """Validate and normalize a candidate IP literal, returning None if invalid."""
    if not candidate:
        return None
    cleaned = candidate.strip()
    if not cleaned:
        return None
    try:
        return str(ipaddress.ip_address(cleaned))
    except ValueError:
        return None


def get_client_ip(request: Request) -> str:
    """Extract the client IP address with optional proxy-header awareness (H-P3-02)."""
    if _trust_proxy_headers():
        vercel_ip = _parse_valid_ip(request.headers.get("x-vercel-forwarded-for"))
        if vercel_ip is not None:
            return vercel_ip

        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            parts = [part.strip() for part in forwarded_for.split(",") if part.strip()]
            if parts:
                hops = _trusted_proxy_hops()
                target_index = max(0, len(parts) - hops)
                candidate = _parse_valid_ip(parts[target_index])
                if candidate is not None:
                    return candidate

        real_ip = _parse_valid_ip(request.headers.get("x-real-ip"))
        if real_ip is not None:
            return real_ip

    return str(get_remote_address(request) or "127.0.0.1")


def resolve_rate_limit_storage_uri() -> str:
    """Return the configured rate-limit storage URI (shared store or in-memory fallback)."""
    uri = (os.getenv("RATE_LIMIT_STORAGE_URI") or "").strip()
    return uri or DEFAULT_STORAGE_URI


def resolve_default_rate_limits() -> list[str]:
    """Return the global default rate limits for all API endpoints."""
    raw = (os.getenv("RATE_LIMIT_DEFAULT") or DEFAULT_RATE_LIMIT).strip()
    if not raw or raw.lower() in {"off", "none", "disabled"}:
        return []
    return [limit.strip() for limit in raw.split(";") if limit.strip()]


def build_limiter(
    *,
    default_limits: list[str] | None = None,
    storage_uri: str | None = None,
) -> Limiter:
    """Build a configured SlowAPI Limiter with proxy-aware IP extraction and shared-store support."""
    limits = resolve_default_rate_limits() if default_limits is None else default_limits
    resolved_storage = resolve_rate_limit_storage_uri() if storage_uri is None else storage_uri
    return Limiter(
        key_func=get_client_ip,
        default_limits=limits,  # type: ignore[arg-type]
        storage_uri=resolved_storage,
        headers_enabled=False,
    )


# Shared rate limiter instance used across the application
limiter = build_limiter()
