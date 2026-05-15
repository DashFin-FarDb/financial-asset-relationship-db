"""Prometheus metrics for the Financial Asset Relationship API."""

import logging

from prometheus_client import Counter, Gauge, Histogram

from src.data.db_models import RebuildJobStatus

logger = logging.getLogger(__name__)

# Rebuild metrics
REBUILD_REQUESTS = Counter(
    "graph_rebuild_requests_total",
    "Total number of graph rebuild requests received.",
)

REBUILD_SUCCESS = Counter(
    "graph_rebuild_success_total",
    "Total number of successful graph rebuilds.",
    ["source"],
)

REBUILD_FAILURE = Counter(
    "graph_rebuild_failure_total",
    "Total number of failed graph rebuilds.",
    ["category"],
)

REBUILD_DURATION = Histogram(
    "graph_rebuild_duration_seconds",
    "Time spent rebuilding the graph.",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)

# Graph state metrics
GRAPH_ASSETS = Gauge(
    "graph_assets_count",
    "Current number of assets in the graph.",
)

GRAPH_RELATIONSHIPS = Gauge(
    "graph_relationships_count",
    "Current number of relationships in the graph.",
)

# Stage 5C.1: Recovery state metrics
REBUILD_STATE_STATUS = Gauge(
    "graph_rebuild_state_status",
    "Current rebuild state status (0=none, 1=pending, 2=running, 3=succeeded, 4=failed, 5=cancelled).",
)

REBUILD_RECOVERY_TRIGGERS = Counter(
    "graph_rebuild_recovery_trigger_total",
    "Total number of rebuild recovery triggers detected.",
    ["inconsistency_type"],
)


def update_graph_metrics(asset_count: int, relationship_count: int) -> None:
    """Update gauge metrics for the current graph state."""
    GRAPH_ASSETS.set(asset_count)
    GRAPH_RELATIONSHIPS.set(relationship_count)


def update_rebuild_state_metric(status: str | RebuildJobStatus | None) -> None:
    """
    Update rebuild state status metric.

    Maps rebuild status to numeric gauge value for monitoring:
    - none/unknown: 0 (no active job or unknown status)
    - pending: 1
    - running: 2
    - succeeded: 3
    - failed: 4
    - cancelled: 5

    Args:
        status: Current rebuild job status (string, enum, or None).
    """
    # Normalize status to string for mapping
    if status is None:
        status_str = "none"
    elif isinstance(status, RebuildJobStatus):
        status_str = status.value
    else:
        status_str = str(status)

    # Define an explicit mapping using enum values for type safety
    mapping = {
        "none": 0,
        RebuildJobStatus.PENDING.value: 1,
        RebuildJobStatus.RUNNING.value: 2,
        RebuildJobStatus.SUCCEEDED.value: 3,
        RebuildJobStatus.FAILED.value: 4,
        RebuildJobStatus.CANCELLED.value: 5,
    }

    gauge_value = mapping.get(status_str.lower())

    if gauge_value is None:
        logger.error(
            f"Inconsistency Detected: Received unknown job status '{status_str}'. "
            f"Mapping to none (0)."
        )
        gauge_value = 0

    REBUILD_STATE_STATUS.set(gauge_value)


def increment_recovery_trigger(inconsistency_type: str) -> None:
    """
    Increment recovery trigger counter.

    Args:
        inconsistency_type: Type of inconsistency detected
            (stale_ownership, orphaned_running, crash_suspicion, etc.).
    """
    REBUILD_RECOVERY_TRIGGERS.labels(inconsistency_type=inconsistency_type).inc()
