"""Rate limiting configuration for the Financial Asset Relationship Database API."""

# pylint: disable=import-error
from slowapi import Limiter  # type: ignore[import-not-found]
from slowapi.util import get_remote_address  # type: ignore[import-not-found]

# pylint: enable=import-error

# Shared rate limiter instance used across the application
limiter = Limiter(key_func=get_remote_address)
