"""Prometheus metrics for the Financial Asset Relationship API."""

from prometheus_client import Counter, Gauge, Histogram

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


def update_rebuild_state_metric(status: str) -> None:
    """
    Update rebuild state status metric.

    Maps rebuild status to numeric gauge value for monitoring:
    - unknown -1 (invalid or new jobs)
    - none: 0 (no active job)
    - pending: 1
    - running: 2
    - succeeded: 3
    - failed: 4
    - cancelled: 5

    Args:
        status: Current rebuild job status.
    """
    # Define an explicit mapping
    mapping = {
        "unknown"
        "none": 0,
        "pending": 1,
        "running": 2,
        "succeeded": 3,
        "failed": 4,
        # Add other known statuses here
    }

    # Use a dedicated 'unknown' value (e.g., -1) that triggers alerts
    # rather than defaulting to 0 (none).
    gauge_value = mapping.get(status.lower())

    if gauge_value is None:
        logger.error(f"Inconsistency Detected: Received unknown job status '{status}'. Mapping to UNKNOWN_STATE (-1).")
        return -1 
    
    return gauge_value


def increment_recovery_trigger(inconsistency_type: str) -> None:
    """
    Increment recovery trigger counter.

    Args:
        inconsistency_type: Type of inconsistency detected
            (stale_ownership, orphaned_running, crash_suspicion, etc.).
    """
    REBUILD_RECOVERY_TRIGGERS.labels(inconsistency_type=inconsistency_type).inc()
