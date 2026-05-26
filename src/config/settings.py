"""Centralized typed settings layer for selected runtime configuration.

This module provides a typed settings interface for runtime configuration
centralized by Phase 4 work, including environment mode, CORS allowlist input,
auth bootstrap settings, graph cache settings, real-data fetcher settings, and
database URL resolution.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


def _parse_bool_env(value: str | None) -> bool:
    """
    Parse a boolean environment variable value.
    Interprets the value case-insensitively; "1", "true", "yes", or "on" are True.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and not value.strip():
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv_env(value: str) -> list[str]:
    """Parse a comma-separated environment variable value into a list of strings."""
    return [s for s in (item.strip() for item in value.split(",")) if s]


class Settings(BaseModel):
    """Runtime configuration settings."""

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
    # Allow int | str | None to capture empty strings from os.getenv
    rebuild_lock_ttl_seconds: int = Field(default=300, gt=0)

    @field_validator("rebuild_lock_ttl_seconds", mode="before")
    @classmethod
    def parse_ttl(cls, value: Any, info: ValidationInfo) -> Any:
        """Coerce empty strings or None to the field default."""
        if value is None or (isinstance(value, str) and not value.strip()):
            field_name = info.field_name
            field_info = cls.model_fields.get(field_name)
            default = getattr(field_info, "default", 300)
            return default
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                raise ValueError(f"Invalid integer for environment variable {info.field_name.upper()}: {value!r}")
        # For non-string, non-None inputs, return value unchanged
        return value

    @property
    def allowed_origins(self) -> list[str]:
        """Return CORS allowed origins as a list."""
        return _parse_csv_env(self.allowed_origins_raw) if self.allowed_origins_raw else []

    @property
    def required_secret_key(self) -> str:
        """Return the JWT secret key or raise if missing."""
        if not self.secret_key:
            raise ValueError("SECRET_KEY environment variable must be set")
        return self.secret_key


def load_settings() -> Settings:
    """Load runtime settings, delegating type coercion to Pydantic."""
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
        # Passed as raw string to Pydantic for validation and coercion
        rebuild_lock_ttl_seconds=os.getenv("REBUILD_LOCK_TTL_SECONDS"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the cached runtime settings instance."""
    return load_settings()
