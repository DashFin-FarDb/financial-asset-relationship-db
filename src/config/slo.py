"""Service Level Objective (SLO) configuration settings.

This module provides a typed settings interface for runtime SLO thresholds,
loading values from the environment with sensible defaults.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field


class SLOSettings(BaseModel):
    """Configuration model for SLO thresholds."""

    model_config = ConfigDict(frozen=True)

    slo_api_latency_p99_seconds: float = Field(default=2.0)
    slo_api_latency_p50_seconds: float = Field(default=0.1)
    slo_rebuild_duration_max_seconds: int = Field(default=300)
    slo_error_rate_threshold: float = Field(default=0.01)
    slo_availability_threshold: float = Field(default=0.999)


def get_slo_settings() -> SLOSettings:
    """Load SLO settings from environment variables."""
    return SLOSettings(
        slo_api_latency_p99_seconds=float(os.environ.get("SLO_API_LATENCY_P99_SECONDS", 2.0)),
        slo_api_latency_p50_seconds=float(os.environ.get("SLO_API_LATENCY_P50_SECONDS", 0.1)),
        slo_rebuild_duration_max_seconds=int(os.environ.get("SLO_REBUILD_DURATION_MAX_SECONDS", 300)),
        slo_error_rate_threshold=float(os.environ.get("SLO_ERROR_RATE_THRESHOLD", 0.01)),
        slo_availability_threshold=float(os.environ.get("SLO_AVAILABILITY_THRESHOLD", 0.999)),
    )
