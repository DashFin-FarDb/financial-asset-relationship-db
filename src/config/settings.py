"""Centralized typed settings layer for runtime environment configuration.

This module provides a single source of truth for all runtime configuration,
replacing direct os.getenv calls throughout the application.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _parse_bool_env(value: Optional[str]) -> bool:
    """
    Parse a boolean environment variable value.

    Interprets the value case-insensitively; the values "1", "true", "yes",
    or "on" (ignoring surrounding whitespace) are treated as true.

    Parameters:
        value (Optional[str]): Environment variable value to parse.

    Returns:
        bool: True if the value matches an accepted truthy value, False otherwise.
    """
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv_env(value: str) -> list[str]:
    """
    Parse a comma-separated environment variable value into a list of strings.

    Splits on commas, trims whitespace, and excludes empty entries.

    Parameters:
        value (str): Comma-separated string to parse.

    Returns:
        list[str]: A list of trimmed non-empty strings.
    """
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseModel):
    """
    Runtime configuration settings for the application.

    All settings are loaded from environment variables and cached at module load.
    This provides a typed, validated interface to runtime configuration.
    """

    model_config = ConfigDict(frozen=True)

    # Environment mode
    env: str = Field(default="development")

    # CORS configuration
    allowed_origins_raw: str = Field(default="")

    # Graph data source configuration
    graph_cache_path: Optional[str] = Field(default=None)
    real_data_cache_path: Optional[str] = Field(default=None)
    use_real_data_fetcher: bool = Field(default=False)

    # Database configuration
    asset_graph_database_url: Optional[str] = Field(default=None)

    @property
    def allowed_origins(self) -> list[str]:
        """
        Parse and return the allowed CORS origins as a list.

        Returns:
            list[str]: Parsed list of allowed origin strings.
        """
        if not self.allowed_origins_raw:
            return []
        return _parse_csv_env(self.allowed_origins_raw)


def load_settings() -> Settings:
    """
    Load runtime settings from environment variables.

    This function reads environment variables and constructs a Settings object.
    It is called by get_settings() which provides caching.

    Returns:
        Settings: Loaded and validated settings object.
    """
    return Settings(
        env=os.getenv("ENV", "development").lower(),
        allowed_origins_raw=os.getenv("ALLOWED_ORIGINS", ""),
        graph_cache_path=os.getenv("GRAPH_CACHE_PATH"),
        real_data_cache_path=os.getenv("REAL_DATA_CACHE_PATH"),
        use_real_data_fetcher=_parse_bool_env(os.getenv("USE_REAL_DATA_FETCHER")),
        asset_graph_database_url=os.getenv("ASSET_GRAPH_DATABASE_URL"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the cached runtime settings instance.

    Settings are loaded once and cached for the lifetime of the application.
    This ensures consistent configuration across all modules.

    Returns:
        Settings: The singleton settings instance.
    """
    return load_settings()
