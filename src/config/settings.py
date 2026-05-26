"""Centralized typed settings layer for selected runtime configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ... (_parse_bool_env and _parse_csv_env remain unchanged) ...

class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    # ... (other fields remain unchanged) ...

    # Distributed lock configuration
    # Allow int | str | None to capture empty strings from os.getenv
    rebuild_lock_ttl_seconds: int = Field(default=300, gt=0)

    @field_validator("rebuild_lock_ttl_seconds", mode="before")
    @classmethod
    def parse_ttl(cls, value: Any) -> Any:
        """Coerce empty strings or None to the default."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return 300
        return value

    # ... (rest of the class) ...

def load_settings() -> Settings:
    """Load runtime settings, passing raw env values to Pydantic for robust coercion."""
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
        # PASS RAW ENV VALUE TO PYDANTIC:
        rebuild_lock_ttl_seconds=os.getenv("REBUILD_LOCK_TTL_SECONDS"),
    )

# ... (get_settings remains unchanged) ...
