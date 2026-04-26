"""CORS origin validation utilities for the Financial Asset Relationship API.

This module provides validation logic for HTTP origins based on environment
and security requirements.
"""

import logging
import re
from urllib.parse import urlparse

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_HTTP_LOCAL_RE = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")
_HTTPS_LOCAL_RE = re.compile(r"^https://(localhost|127\.0\.0\.1)(:\d+)?$")
_VERCEL_PREVIEW_RE = re.compile(r"^https://[a-zA-Z0-9\-\.]+\.vercel\.app$")
_HTTPS_DOMAIN_RE = re.compile(
    r"^https://[a-zA-Z0-9]"
    r"([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,}(:\d{1,5})?$"
)


def _is_allowed_list_origin(origin: str, allowed_origins: list[str]) -> bool:
    """
    Determine whether the origin is non-empty and in the allowlist.

    Returns:
        True if origin is non-empty and present in allowed_origins,
        False otherwise.
    """
    return bool(origin) and origin in allowed_origins


def _is_http_local_in_dev(origin: str, current_env: str) -> bool:
    """
    Check if origin is HTTP localhost and environment is "development".

    Parameters:
        origin (str): Origin string (e.g., "http://localhost:3000").
        current_env (str): Environment name compared to "development".

    Returns:
        bool: True if origin is HTTP localhost/127.0.0.1 with optional port
            and current_env is "development", False otherwise.
    """
    return current_env == "development" and bool(_HTTP_LOCAL_RE.match(origin))


def _is_https_local(origin: str) -> bool:
    """
    Check if origin is HTTPS localhost (localhost or 127.0.0.1).

    Parameters:
        origin (str): Origin string (e.g., "https://localhost:3000").

    Returns:
        bool: True if origin matches https://localhost or https://127.0.0.1
            with optional port, False otherwise.
    """
    return bool(_HTTPS_LOCAL_RE.match(origin))


def _is_vercel_preview(origin: str) -> bool:
    """
    Determine whether an origin is a Vercel preview hostname.

    Parameters:
        origin (str): Origin to test (for example, 'https://<subdomain>.vercel.app').

    Returns:
        True if the origin matches a Vercel preview hostname, False otherwise.
    """
    return bool(_VERCEL_PREVIEW_RE.match(origin))


def _is_valid_https_domain(origin: str) -> bool:
    """
    Check if origin is HTTPS with a standard domain and optional port.

    Parameters:
        origin (str): Origin string (e.g., "https://example.com").

    Returns:
        True if origin matches the HTTPS domain regex, False otherwise.
    """
    return bool(_HTTPS_DOMAIN_RE.match(origin))


def _is_valid_https_idn(origin: str) -> bool:
    """
    Validate HTTPS origin with IDNA-encodable hostname.

    Parameters:
        origin (str): Origin URL with scheme and hostname; may include port.

    Returns:
        bool: True if origin uses https, has an IDNA-encodable hostname,
            and the ASCII origin matches the HTTPS domain regex.
    """
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
    Validate whether an HTTP origin is permitted by CORS rules.

    Permitted origins include:
    - Entries in the ALLOWED_ORIGINS allowlist
    - HTTPS domains matching the configured domain pattern
    - Vercel preview hostnames
    - HTTPS localhost/127.0.0.1 (any environment)
    - HTTP localhost/127.0.0.1 when ENV is "development"

    Origins with path, params, query, fragment, username, or password
    components are rejected. Internationalized hostnames are accepted
    when their IDNA-encoded ASCII form matches the HTTPS domain pattern.

    Parameters:
        origin (str): Origin URL to validate (e.g., "https://example.com").

    Returns:
        bool: True if the origin is allowed, False otherwise.
    """
    # Get runtime settings from centralized typed settings layer
    settings = get_settings()
    current_env = settings.env
    allowed_origins = settings.allowed_origins

    if _is_allowed_list_origin(origin, allowed_origins):
        return True
    if _is_http_local_in_dev(origin, current_env):
        return True
    if _is_https_local(origin):
        return True
    if _is_vercel_preview(origin):
        return True
    if _is_valid_https_domain(origin):
        return True
    parsed = urlparse(origin)
    has_extra_components = any(
        [parsed.path, parsed.params, parsed.query, parsed.fragment, parsed.username, parsed.password]
    )
    if has_extra_components:
        return False
    try:
        return _is_valid_https_idn(origin)
    except ValueError:
        return False
