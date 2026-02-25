"""CORS origin validation utilities for the Financial Asset Relationship API.

This module provides validation logic for HTTP origins based on environment
and security requirements.
"""

import logging
import os
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def validate_origin(origin: str) -> bool:
    """
    Determine whether an HTTP origin is permitted by the application's CORS rules.

    Allows explicitly configured origins, HTTPS origins with a valid domain, Vercel preview hostnames, HTTPS localhost/127.0.0.1 in any environment, and HTTP localhost/127.0.0.1 when ENV is "development".

    Parameters:
        origin (str): Origin URL to validate (for example "https://example.com" or "http://localhost:3000").

    Returns:
        True if the origin is allowed, False otherwise.
    """
    # Read environment dynamically to support runtime overrides (e.g., during tests)
    current_env = os.getenv("ENV", "development").lower()

    # Get allowed origins from environment variable or use default
    allowed_origins = [
        origin for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin
    ]

    # If origin is in explicitly allowed list, return True
    if origin in allowed_origins and origin:
        return True

    # Allow HTTP localhost only in development
    if current_env == "development" and re.match(
        r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", origin
    ):
        return True
    # Allow HTTPS localhost in any environment
    if re.match(r"^https://(localhost|127\.0\.0\.1)(:\d+)?$", origin):
        return True
    # Allow Vercel preview deployment URLs (e.g., https://project-git-branch-user.vercel.app)
    if re.match(r"^https://[a-zA-Z0-9\-\.]+\.vercel\.app$", origin):
        return True
    # Allow valid HTTPS URLs with proper domains (ASCII and IDN)
    if re.match(
        r"^https://[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$",
        origin,
    ):
        return True
    # Support IDN (Internationalized Domain Names) — encode host to ASCII and re-validate
    parsed = urlparse(origin)
    if parsed.scheme == "https" and parsed.netloc:
        try:
            ascii_host = parsed.hostname.encode("idna").decode("ascii")
            ascii_origin = f"https://{ascii_host}"
            if parsed.port:
                ascii_origin += f":{parsed.port}"
            if re.match(
                r"^https://[a-zA-Z0-9]"
                r"([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
                r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
                r"\.[a-zA-Z]{2,}$",
                ascii_origin,
            ):
                return True
        except UnicodeError as e:
            # If the hostname cannot be IDNA-encoded, treat the origin as invalid.
            logger.debug(
                "Failed to IDNA-encode hostname for origin %s: %s", origin, e
            )
            return False
    return False
