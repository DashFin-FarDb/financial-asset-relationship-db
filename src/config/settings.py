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
    """Parse a boolean environment variable value.

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

    # Logging configuration
    log_level: str = Field(default="INFO")

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
    coordination_database_url: str | None = Field(default=None)
    postgres_url: str | None = Field(default=None)
    # Distributed lock configuration
    # Allow int | str | None to capture empty strings from os.getenv
    rebuild_lock_ttl_seconds: int = Field(
        default=300,
        gt=0,
        description="TTL for rebuild distributed lock in seconds",
    )

    # SLO Configuration
    slo_api_latency_avg_seconds: float = Field(default=0.1, ge=0.0)
    slo_rebuild_duration_max_seconds: int = Field(default=300, ge=0)
    slo_error_rate_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    slo_evaluation_interval_seconds: float = Field(default=60.0, ge=1.0)

    @field_validator(
        "rebuild_lock_ttl_seconds",
        "slo_api_latency_avg_seconds",
        "slo_rebuild_duration_max_seconds",
        "slo_error_rate_threshold",
        "slo_evaluation_interval_seconds",
        mode="before",
    )
    @classmethod
    def parse_env_vars(cls, value: Any, info: ValidationInfo) -> Any:
        """Coerce empty strings or None to the field default."""
        field_name = info.field_name or "rebuild_lock_ttl_seconds"
        if value is None or (isinstance(value, str) and not value.strip()):
            field_info = cls.model_fields.get(field_name)
            default = getattr(field_info, "default", 300)
            return default
        if field_name in ("rebuild_lock_ttl_seconds", "slo_rebuild_duration_max_seconds") and isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                raise ValueError(f"Invalid integer for environment variable {field_name.upper()}: {value!r}") from None
        # For other fields or non-string inputs, Pydantic will handle the type coercion
        return value

    @field_validator("slo_rebuild_duration_max_seconds")
    @classmethod
    def validate_rebuild_threshold(cls, value: int) -> int:
        """Validate that the rebuild threshold matches a histogram bucket boundary."""
        # Canonical buckets defined in api/metrics.py
        allowed_buckets = {1, 5, 10, 30, 60, 120, 300}
        if value not in allowed_buckets:
            raise ValueError(
                f"SLO_REBUILD_DURATION_MAX_SECONDS ({value}) must match a histogram bucket boundary. "
                f"Allowed values: {sorted(allowed_buckets)}"
            )
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
    """
    Load runtime settings from environment variables and return a configured Settings instance.

    Reads environment variables (for example: ENV, LOG_LEVEL, SECRET_KEY, DATABASE_URL,
    POSTGRES_URL, COORDINATION_DATABASE_URL, ALLOWED_ORIGINS, REBUILD_LOCK_TTL_SECONDS)
    and maps them to Settings fields, delegating type coercion and validation to Pydantic.
    REBUILD_LOCK_TTL_SECONDS is passed unchanged for field-level parsing. DATABASE_URL
    falls back to POSTGRES_URL when unset; COORDINATION_DATABASE_URL falls back to
    DATABASE_URL then POSTGRES_URL.

    Returns:
        Settings: A Settings instance populated from the current environment.
    """
    postgres_url = os.getenv("POSTGRES_URL")

    return Settings(
        env=os.getenv("ENV", "development").strip().lower(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
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
        coordination_database_url=os.getenv("COORDINATION_DATABASE_URL") or os.getenv("DATABASE_URL") or postgres_url,
        postgres_url=postgres_url,
        # Passed as raw string to Pydantic for validation and coercion
        rebuild_lock_ttl_seconds=os.getenv("REBUILD_LOCK_TTL_SECONDS"),  # type: ignore[arg-type]
        slo_api_latency_avg_seconds=os.getenv("SLO_API_LATENCY_AVG_SECONDS"),  # type: ignore[arg-type]
        slo_rebuild_duration_max_seconds=os.getenv("SLO_REBUILD_DURATION_MAX_SECONDS"),  # type: ignore[arg-type]
        slo_error_rate_threshold=os.getenv("SLO_ERROR_RATE_THRESHOLD"),  # type: ignore[arg-type]
        slo_evaluation_interval_seconds=os.getenv("SLO_EVALUATION_INTERVAL_SECONDS"),  # type: ignore[arg-type]
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the cached runtime settings instance."""
    return load_settings()
