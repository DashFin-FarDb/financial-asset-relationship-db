"""CORS origin validation utilities for the Financial Asset Relationship API.

This module provides validation logic for HTTP origins based on environment
and security requirements.
"""

import logging
import os
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_HTTP_LOCAL_RE = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")
_HTTPS_LOCAL_RE = re.compile(r"^https://(localhost|127\.0\.0\.1)(:\d+)?$")
_VERCEL_PREVIEW_RE = re.compile(r"^https://[a-zA-Z0-9\-\.]+\.vercel\.app$")
_HTTPS_DOMAIN_RE = re.compile(
    r"^https://[a-zA-Z0-9]"
    r"([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,}$"
)


def _is_allowed_list_origin(origin: str, allowed_origins: list[str]) -> bool:
    return bool(origin) and origin in allowed_origins


def _is_http_local_in_dev(origin: str, current_env: str) -> bool:
    return current_env == "development" and bool(_HTTP_LOCAL_RE.match(origin))


def _is_https_local(origin: str) -> bool:
    return bool(_HTTPS_LOCAL_RE.match(origin))


def _is_vercel_preview(origin: str) -> bool:
    return bool(_VERCEL_PREVIEW_RE.match(origin))


def _is_valid_https_domain(origin: str) -> bool:
    return bool(_HTTPS_DOMAIN_RE.match(origin))


def _is_valid_https_idn(origin: str) -> bool:
    parsed = urlparse(origin)
    if parsed.scheme != "https":
        return False
    if not parsed.netloc:
        return False
    if parsed.hostname is None:
        return False

    try:
        ascii_host = parsed.hostname.encode("idna").decode("ascii")
    except UnicodeError as e:
        logger.debug("Failed to IDNA-encode hostname for origin %s: %s", origin, e)
        return False

    ascii_origin = f"https://{ascii_host}"
    if parsed.port:
        ascii_origin += f":{parsed.port}"
    return bool(_HTTPS_DOMAIN_RE.match(ascii_origin))


def validate_origin(origin: str) -> bool:
    """
    Determine whether an HTTP origin is permitted by the application's CORS rules.

    Allows explicitly configured origins, HTTPS origins with a valid domain,
    Vercel preview hostnames, HTTPS localhost/127.0.0.1 in any environment,
    and HTTP localhost/127.0.0.1 when ENV is "development".

    Parameters:
        origin (str): Origin URL to validate (for example "https://example.com" or "http://localhost:3000").

    Returns:
        True if the origin is allowed, False otherwise.
    """
    # Read environment dynamically to support runtime overrides (e.g., during tests)
    current_env = os.getenv("ENV", "development").lower()

    # Get allowed origins from environment variable or use default
    allowed_origins = [origin for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin]

    checks = (
        _is_allowed_list_origin(origin, allowed_origins),
        _is_http_local_in_dev(origin, current_env),
        _is_https_local(origin),
        _is_vercel_preview(origin),
        _is_valid_https_domain(origin),
        _is_valid_https_idn(origin),
    )
    return any(checks)
