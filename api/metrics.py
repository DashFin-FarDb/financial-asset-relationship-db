"""Prometheus metrics for the Financial Asset Relationship API."""

import logging

from prometheus_client import Counter, Gauge, Histogram

from src.data.db_models import RebuildJobStatus
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

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
    "Current rebuild state status (-1=unknown, 0=none, 1=pending, 2=running, 3=succeeded, 4=failed, 5=cancelled).",
)

REBUILD_RECOVERY_TRIGGERS = Counter(
    "graph_rebuild_recovery_trigger_total",
    "Total number of rebuild recovery triggers detected.",
    ["inconsistency_type"],
)

# Stage 5C.2: Lock refresh and heartbeat metrics
LOCK_REFRESH_TOTAL = Counter(
    "rebuild_lock_refresh_total",
    "Total lock refresh attempts during rebuild.",
    ["status"],  # success | failure
)

LOCK_REFRESH_DURATION = Histogram(
    "rebuild_lock_refresh_duration_seconds",
    "Time taken to refresh distributed lock.",
    buckets=(0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
)

HEARTBEAT_UPDATE_TOTAL = Counter(
    "rebuild_heartbeat_update_total",
    "Total heartbeat database updates.",
    ["status"],  # success | failure
)

HEARTBEAT_LAST_SUCCESS_TIMESTAMP = Gauge(
    "rebuild_heartbeat_last_success_timestamp",
    "Unix timestamp of last successful heartbeat.",
)


def update_graph_metrics(asset_count: int, relationship_count: int) -> None:
    """Update gauge metrics for the current graph state."""
    GRAPH_ASSETS.set(asset_count)
    GRAPH_RELATIONSHIPS.set(relationship_count)


def update_rebuild_state_metric(status: str | RebuildJobStatus | None) -> None:
    """
    Update rebuild state status metric.

    Maps rebuild status to numeric gauge value for monitoring:
    - unknown: -1
    - none: 0
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
        "unknown": -1,
        "none": 0,
        "pending": 1,
        "running": 2,
        "succeeded": 3,
        "failed": 4,
        "cancelled": 5,
    }

    normalized_status = status_str.lower()
    gauge_value = mapping.get(normalized_status, -1)

    if gauge_value == -1 and normalized_status != "unknown":
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="metrics_rebuild_status_mapping_error",
                message=(
                    f"Inconsistency detected: received unknown job status '{status}'. " "Mapping to UNKNOWN_STATE (-1)."
                ),
                metadata={"status": str(status)},
            ),
        )

    REBUILD_STATE_STATUS.set(gauge_value)


def increment_recovery_trigger(inconsistency_type: str) -> None:
    """
    Increment recovery trigger counter.

    Args:
        inconsistency_type: Type of inconsistency detected
            (stale_ownership, orphaned_running, crash_suspicion, etc.).
    """
    REBUILD_RECOVERY_TRIGGERS.labels(inconsistency_type=inconsistency_type).inc()


def _initialize_from_active_job(active_job) -> None:
    """Initialize rebuild state metric from an active RUNNING job."""
    status_value = (
        active_job.status.value if isinstance(active_job.status, RebuildJobStatus) else str(active_job.status)
    )
    update_rebuild_state_metric(active_job.status)
    log_event(
        logger,
        logging.INFO,
        ObservabilityEvent(
            event="metrics_rebuild_state_initialized_active",
            message=(
                f"Initialized rebuild state metric from active job: {status_value} "
                f"(job_id={active_job.job_id})"
            ),
            metadata={"status": status_value, "job_id": active_job.job_id},
        ),
    )


def _initialize_from_latest_job(latest_job) -> None:
    """Initialize rebuild state metric from the latest (terminal) job."""
    status_value = (
        latest_job.status.value if isinstance(latest_job.status, RebuildJobStatus) else str(latest_job.status)
    )
    update_rebuild_state_metric(latest_job.status)
    log_event(
        logger,
        logging.INFO,
        ObservabilityEvent(
            event="metrics_rebuild_state_initialized_latest",
            message=(
                f"Initialized rebuild state metric from latest job: {status_value} "
                f"(job_id={latest_job.job_id})"
            ),
            metadata={"status": status_value, "job_id": latest_job.job_id},
        ),
    )


def initialize_rebuild_state_metric_from_db(
    session_factory,
) -> None:
    """
    Initialize rebuild state metric from authoritative DB state on startup.

    This ensures the Prometheus gauge reflects the actual persisted rebuild
    state after process restarts, including terminal states (succeeded/failed),
    rather than showing default/stale values that could hide crashed jobs.

    Args:
        session_factory: Callable that returns a SQLAlchemy session.
    """
    from src.data.repository import AssetGraphRepository

    session = None
    try:
        session = session_factory()
        repo = AssetGraphRepository(session)

        # First check for active RUNNING job
        active_job = repo.get_active_rebuild_state()

        if active_job is not None:
            _initialize_from_active_job(active_job)
        else:
            # No active job - check latest job to preserve terminal state
            latest_job = repo.get_latest_rebuild_job()
            if latest_job is not None:
                _initialize_from_latest_job(latest_job)
            else:
                # No rebuild jobs at all - set to "none"
                update_rebuild_state_metric(None)
                log_event(
                    logger,
                    logging.DEBUG,
                    ObservabilityEvent(
                        event="metrics_rebuild_state_initialized_none",
                        message="Initialized rebuild state metric: none (no rebuild jobs)",
                    ),
                )
    except ValueError as exc:
        # Multiple running jobs — business-logic inconsistency, no credentials at risk
        # S8572: Using logger.warning with bounded format to prevent credential leakage
        # (repository convention from PR #1161 - DB errors can embed DSN in tracebacks)
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="metrics_rebuild_state_initialization_blocked",
                message=f"Cannot initialize rebuild state metric: {type(exc).__name__}. Setting to unknown.",
                metadata={"error": type(exc).__name__},
            ),
        )
        update_rebuild_state_metric("unknown")
    except Exception as exc:  # noqa: BLE001
        # DB read failure — SQLAlchemy errors can embed DSN/credentials in tracebacks
        # S8572: Using logger.warning with bounded format to prevent credential leakage
        # (repository convention from PR #1161 - avoids stack traces with DB connection details)
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="metrics_rebuild_state_initialization_failed",
                message=f"Failed to initialize rebuild state metric from DB: {type(exc).__name__}. Setting to unknown.",
                metadata={"error": type(exc).__name__},
            ),
        )
        update_rebuild_state_metric("unknown")
    finally:
        if session is not None:
            session.close()
