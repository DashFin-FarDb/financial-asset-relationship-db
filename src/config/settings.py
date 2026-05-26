"""Centralized typed settings layer for selected runtime configuration.

This module provides a typed settings interface for runtime configuration
centralized by Phase 4 work, including environment mode, CORS allowlist input,
auth bootstrap settings, graph cache settings, real-data fetcher settings, and
database URL resolution. It does not yet replace all direct environment reads
across the repository.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field


def _parse_bool_env(value: str | None) -> bool:
    """
    Parse a boolean environment variable value.

    Interprets the value case-insensitively; the values "1", "true", "yes",
    or "on" (ignoring surrounding whitespace) are treated as true.
    """
    # Handle None and empty string
    if value is None or value == "":
        return False

    # Handle boolean passthrough
    if isinstance(value, bool):
        return value

    # Convert everything else to string and parse
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv_env(value: str) -> list[str]:
    """
    Parse a comma-separated environment variable value into a list of strings.
    Splits on commas, trims whitespace, and excludes empty entries.
    """
    return [stripped for item in value.split(",") if (stripped := item.strip())]


class Settings(BaseModel):
    """
    Runtime configuration settings centralized by Phase 4 work.

    Settings are loaded from environment variables and exposed through a typed,
    immutable model. Boolean-like environment variables centralized here are
    parsed into booleans before serialization; for example, ADMIN_DISABLED is
    exposed as admin_disabled: bool rather than as the original raw string.
    """

    model_config = ConfigDict(frozen=True)

    # Environment mode
    env: str = Field(default="development")

    # CORS configuration
    allowed_origins_raw: str = Field(default="")

    # Auth configuration
    secret_key: str | None = Field(default=None)
    admin_username: str | None = Field(default=None)
    admin_password: str | None = Field(default=None)
    admin_email: str | None = Field(default=None)
    admin_full_name: str | None = Field(default=None)
    admin_disabled: bool = Field(default=False)

    # Graph data source configuration
    graph_cache_path: str | None = Field(default=None)
    real_data_cache_path: str | None = Field(default=None)
    use_real_data_fetcher: bool = Field(default=False)

    # Database configuration
    asset_graph_database_url: str | None = Field(default=None)
    database_url: str | None = Field(default=None)
    postgres_url: str | None = Field(default=None)

    # Distributed lock configuration
    rebuild_lock_ttl_seconds: int = Field(default=300, gt=0, description="TTL for rebuild distributed lock in seconds")

    @property
    def allowed_origins(self) -> list[str]:
        """
        Return the configured CORS allowed origins as a list of trimmed, non-empty strings.
        """
        return _parse_csv_env(self.allowed_origins_raw) if self.allowed_origins_raw else []

    @property
    def required_secret_key(self) -> str:
        """
        Return the configured JWT secret key or raise when it is missing.
        """
        if not self.secret_key:
            raise ValueError("SECRET_KEY environment variable must be set before importing api.auth")
        return self.secret_key


def load_settings() -> Settings:
    """
    Load runtime settings from environment variables.

    DATABASE_URL is the canonical database URL. If DATABASE_URL is not set but POSTGRES_URL is,
    POSTGRES_URL is used as a fallback for Vercel Postgres compatibility.

    Returns:
        settings (Settings): Constructed and validated Settings object.
    """
    postgres_url = os.getenv("POSTGRES_URL")

    return Settings(
        env=os.getenv("ENV", "development").strip().lower(),
        allowed_origins_raw=os.getenv("ALLOWED_ORIGINS", ""),
        secret_key=os.getenv("SECRET_KEY"),
        admin_username=os.getenv("ADMIN_USERNAME"),
        admin_password=os.getenv("ADMIN_PASSWORD"),
        admin_email=os.getenv("ADMIN_EMAIL"),
        admin_full_name=os.getenv("ADMIN_FULL_NAME"),
        admin_disabled=_parse_bool_env(os.getenv("ADMIN_DISABLED")),
        graph_cache_path=os.getenv("GRAPH_CACHE_PATH"),
        real_data_cache_path=os.getenv("REAL_DATA_CACHE_PATH"),
        use_real_data_fetcher=_parse_bool_env(os.getenv("USE_REAL_DATA_FETCHER")),
        asset_graph_database_url=os.getenv("ASSET_GRAPH_DATABASE_URL"),
        database_url=os.getenv("DATABASE_URL") or postgres_url,
        postgres_url=postgres_url,
        rebuild_lock_ttl_seconds=int(os.getenv("REBUILD_LOCK_TTL_SECONDS", "300")),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the cached runtime settings instance.

    Settings are loaded once and cached for the lifetime of the process unless
    the cache is explicitly cleared.
    """
    return load_settings()
