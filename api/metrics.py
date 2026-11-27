"""Prometheus metrics for the Financial Asset Relationship API."""

import logging
import time

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

# Reconciliation and Drift metrics
RECONCILIATION_DRIFT_TOTAL = Counter(
    "reconciliation_drift_total",
    "Total number of reconciliation drift evaluations.",
    ["drift_type", "severity", "execution_mode"],
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

# Rebuild and State metrics
REBUILD_DURATION = Histogram(
    "graph_rebuild_duration_seconds",
    "Time spent rebuilding the graph.",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)

GRAPH_REBUILD_STATE_TRANSITION_TOTAL = Counter(
    "graph_rebuild_state_transition_total", "Total number of rebuild job state transitions.", ["from_state", "to_state"]
)

GRAPH_REBUILD_ADMISSION_TOTAL = Counter(
    "graph_rebuild_admission_total",
    "Total rebuild requests admitted or rejected by fail-fast admission.",
    ["result"],
)

GRAPH_REBUILD_CANCELLED_TOTAL = Counter("graph_rebuild_cancelled_total", "Total number of cancelled graph rebuilds.")

REBUILD_LOCK_ACQUISITION_TOTAL = Counter(
    "rebuild_lock_acquisition_total", "Total number of rebuild lock acquisitions.", ["status"]
)

# Reconciliation Metrics
RECONCILIATION_DURATION = Histogram(
    "reconciliation_duration_seconds",
    "Time spent reconciling the graph state.",
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, float("inf")),
)

# Application Lifecycle Metrics
APPLICATION_STARTUP_DURATION = Histogram(
    "application_startup_duration_seconds",
    "Time spent during application startup.",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, float("inf")),
)

APPLICATION_STARTUP_SUCCESS_TOTAL = Counter(
    "application_startup_success_total", "Total number of successful application startups."
)

APPLICATION_STARTUP_FAILURE_TOTAL = Counter(
    "application_startup_failure_total", "Total number of failed application startups."
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

# Graph <-> Relational DB boundary metrics
GRAPH_PERSISTENCE_CONFIGURED = Gauge(
    "fardb_graph_persistence_configured",
    "Whether durable graph persistence is configured (1=configured, 0=not configured).",
)

GRAPH_PROJECTION_LAST_PUBLISHED_TIMESTAMP = Gauge(
    "graph_projection_last_published_timestamp_seconds",
    "Unix timestamp of the last graph projection published or synchronized into runtime memory.",
)

GRAPH_DB_PERSISTENCE_DURATION_SECONDS = Histogram(
    "graph_db_persistence_duration_seconds",
    "Time spent persisting a graph snapshot into the relational database.",
    ["dialect"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, float("inf")),
)

_KNOWN_DB_DIALECTS = frozenset({"postgresql", "sqlite"})

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

# Stage 5C.3B: Checkpoint metrics
REBUILD_CHECKPOINTS_TOTAL = Counter(
    "rebuild_checkpoints_total",
    "Total number of rebuild checkpoints written to database.",
    ["status"],  # success | failure
)

HEARTBEAT_LAST_SUCCESS_TIMESTAMP = Gauge(
    "rebuild_heartbeat_last_success_timestamp",
    "Unix timestamp of last successful heartbeat.",
)

# HTTP request metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed.",
    ["method", "route", "status_group"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "route", "status_group"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "http_requests_in_flight",
    "Number of HTTP requests currently being processed.",
)

# Phase 3: SLO metrics
SLO_COMPLIANCE_STATUS = Gauge(
    "slo_compliance_status",
    "SLO Compliance Status (1=compliant, 0=breached)",
    ["slo_name"],
)

# Security, Rate-Limiting, Idempotency & Ingestion Resilience metrics
AUTH_LOGIN_TOTAL = Counter(
    "auth_login_total",
    "Total authentication login attempts by outcome.",
    ["outcome"],  # success | failure
)

AUTH_TOKEN_REVOCATIONS_TOTAL = Counter(
    "auth_token_revocations_total",
    "Total JWT access tokens revoked.",
)

RATE_LIMIT_STORE_BACKEND_INFO = Gauge(
    "rate_limit_store_backend_info",
    "Active rate-limit storage backend classification (1=active).",
    ["backend"],
)

HTTP_RATE_LIMIT_EXCEEDED_TOTAL = Counter(
    "http_rate_limit_exceeded_total",
    "Total HTTP 429 rate-limit rejections by route template.",
    ["route"],
)

REBUILD_IDEMPOTENCY_TOTAL = Counter(
    "rebuild_idempotency_total",
    "Total Idempotency-Key evaluations by outcome.",
    ["outcome"],  # hit | miss | conflict
)

INGESTION_RESILIENCE_EVENTS_TOTAL = Counter(
    "ingestion_resilience_events_total",
    "Total data ingestion resilience events by provider and outcome.",
    ["provider", "outcome"],  # success | retry | circuit_open | failure
)

_KNOWN_RATE_LIMIT_BACKENDS = frozenset({"memory", "redis", "memcached", "mongodb"})
_KNOWN_IDEMPOTENCY_OUTCOMES = frozenset({"hit", "miss", "conflict"})
_KNOWN_LOGIN_OUTCOMES = frozenset({"success", "failure"})
_KNOWN_INGESTION_OUTCOMES = frozenset({"success", "retry", "circuit_open", "failure"})


def update_graph_metrics(asset_count: int, relationship_count: int) -> None:
    """Update gauge metrics for the current graph state and publication timestamp."""
    GRAPH_ASSETS.set(asset_count)
    GRAPH_RELATIONSHIPS.set(relationship_count)
    record_graph_projection_published()


def update_graph_persistence_configured(configured: bool) -> None:
    """Record whether durable graph persistence is configured (1 or 0)."""
    GRAPH_PERSISTENCE_CONFIGURED.set(1 if configured else 0)


def record_graph_projection_published(timestamp_seconds: float | None = None) -> None:
    """Record the Unix timestamp of the latest published or synced graph projection."""
    GRAPH_PROJECTION_LAST_PUBLISHED_TIMESTAMP.set(
        time.time() if timestamp_seconds is None else float(timestamp_seconds)
    )


def observe_graph_db_persistence_duration(duration_seconds: float, dialect: str | None) -> None:
    """Record relational database persistence duration with bounded dialect label."""
    normalized = (dialect or "").strip().lower()
    label = normalized if normalized in _KNOWN_DB_DIALECTS else "other"
    GRAPH_DB_PERSISTENCE_DURATION_SECONDS.labels(dialect=label).observe(max(0.0, float(duration_seconds)))


def record_auth_login(outcome: str) -> None:
    """Record an authentication login attempt with bounded outcome label."""
    label = outcome if outcome in _KNOWN_LOGIN_OUTCOMES else "failure"
    AUTH_LOGIN_TOTAL.labels(outcome=label).inc()


def record_auth_token_revocation() -> None:
    """Record a JWT access token revocation."""
    AUTH_TOKEN_REVOCATIONS_TOTAL.inc()


def record_rate_limit_backend(backend: str | None) -> None:
    """Expose the active rate-limit storage backend as a binary info gauge."""
    normalized = (backend or "").strip().lower()
    active_label = normalized if normalized in _KNOWN_RATE_LIMIT_BACKENDS else "other"
    for candidate in (*sorted(_KNOWN_RATE_LIMIT_BACKENDS), "other"):
        RATE_LIMIT_STORE_BACKEND_INFO.labels(backend=candidate).set(1 if candidate == active_label else 0)


def record_rate_limit_exceeded(route: str) -> None:
    """Record an HTTP 429 rate-limit rejection for a resolved route template."""
    HTTP_RATE_LIMIT_EXCEEDED_TOTAL.labels(route=route or "unknown").inc()


def record_rebuild_idempotency(outcome: str) -> None:
    """Record an Idempotency-Key evaluation outcome (hit, miss, or conflict)."""
    label = outcome if outcome in _KNOWN_IDEMPOTENCY_OUTCOMES else "conflict"
    REBUILD_IDEMPOTENCY_TOTAL.labels(outcome=label).inc()


def record_ingestion_resilience_event(provider: str, outcome: str) -> None:
    """Record a data ingestion resilience outcome for a provider."""
    safe_provider = (provider or "unknown").strip().lower()[:32] or "unknown"
    label = outcome if outcome in _KNOWN_INGESTION_OUTCOMES else "failure"
    INGESTION_RESILIENCE_EVENTS_TOTAL.labels(provider=safe_provider, outcome=label).inc()


def update_slo_compliance_status(slo_name: str, is_compliant: bool) -> None:
    """Update the SLO compliance status gauge for a specific SLO."""
    SLO_COMPLIANCE_STATUS.labels(slo_name=slo_name).set(1 if is_compliant else 0)


def update_rebuild_state_metric(status: str | RebuildJobStatus | None) -> None:
    """
    Set the rebuild-state gauge to the numeric value corresponding to a rebuild job status.

    Normalizes the provided status (None, RebuildJobStatus, or other) to a lowercase string

    and maps it to the following numeric values:

    unknown → -1, none → 0, pending → 1, running → 2, succeeded → 3, failed → 4, cancelled → 5.

    If the status is not recognized and is not the literal "unknown",

    emits a structured error event and maps to -1.

    Parameters:
        status (str | RebuildJobStatus | None): Current rebuild job status to map;
        may be None, an enum member, or any string.
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
                    f"Inconsistency detected: received unknown job status '{status}'. Mapping to UNKNOWN_STATE (-1)."
                ),
                metadata={"status": str(status)},
            ),
        )

    REBUILD_STATE_STATUS.set(gauge_value)


def increment_recovery_trigger(inconsistency_type: str) -> None:
    """
    Record a detected recovery trigger by incrementing the counter for the given inconsistency type.

    Parameters:
        inconsistency_type (str): Identifier for the detected inconsistency
        (e.g. "stale_ownership", "orphaned_running", "crash_suspicion").
    """
    REBUILD_RECOVERY_TRIGGERS.labels(inconsistency_type=inconsistency_type).inc()


def record_drift_metric(drift_type: str, severity: str, execution_mode: str) -> None:
    """
    Record a detected reconciliation drift by incrementing its counter.

    Parameters:
        drift_type (str): The classification of the detected drift.
        severity (str): The severity level of the drift.
        execution_mode (str): The planned execution mode.
    """
    RECONCILIATION_DRIFT_TOTAL.labels(drift_type=drift_type, severity=severity, execution_mode=execution_mode).inc()


def record_rebuild_state_transition(from_state: str, to_state: str) -> None:
    """
    Record a state transition for a rebuild job.

    Parameters:
        from_state (str): The original state.
        to_state (str): The new state.
    """
    GRAPH_REBUILD_STATE_TRANSITION_TOTAL.labels(from_state=from_state, to_state=to_state).inc()


def record_rebuild_cancelled() -> None:
    """Record that a rebuild job was successfully cancelled."""
    GRAPH_REBUILD_CANCELLED_TOTAL.inc()


def record_rebuild_lock_acquisition(status: str) -> None:
    """
    Record a rebuild lock acquisition attempt.

    Parameters:
        status (str): The outcome of the acquisition (e.g. 'acquired', 'timeout', 'error').
    """
    REBUILD_LOCK_ACQUISITION_TOTAL.labels(status=status).inc()


def _initialize_from_active_job(active_job) -> None:
    """
    Initialize the rebuild-state metric from an active rebuild job.

    Sets the REBUILD_STATE_STATUS gauge based on active_job.status and emits an informational observability event
    ("metrics_rebuild_state_initialized_active") that includes the job's status and job_id.

    Parameters:
        active_job: An object with attributes `status` (a `RebuildJobStatus` or string-like) and `job_id`.
    """
    status_value = (
        active_job.status.value if isinstance(active_job.status, RebuildJobStatus) else str(active_job.status)
    )
    update_rebuild_state_metric(active_job.status)
    log_event(
        logger,
        logging.INFO,
        ObservabilityEvent(
            event="metrics_rebuild_state_initialized_active",
            message=(f"Initialized rebuild state metric from active job: {status_value} (job_id={active_job.job_id})"),
            metadata={"status": status_value, "job_id": active_job.job_id},
        ),
    )


def _initialize_from_latest_job(latest_job) -> None:
    """
    Set the rebuild-state gauge using the provided latest terminal rebuild job.

    Emits an informational observability event that records the job's normalized status and `job_id`.

    Parameters:
        latest_job: The latest persisted rebuild job whose `status` (a `RebuildJobStatus` or string) is used
            to set the metric; `latest_job.job_id` is included in the emitted event.
    """
    status_value = (
        latest_job.status.value if isinstance(latest_job.status, RebuildJobStatus) else str(latest_job.status)
    )
    update_rebuild_state_metric(latest_job.status)
    log_event(
        logger,
        logging.INFO,
        ObservabilityEvent(
            event="metrics_rebuild_state_initialized_latest",
            message=(f"Initialized rebuild state metric from latest job: {status_value} (job_id={latest_job.job_id})"),
            metadata={"status": status_value, "job_id": latest_job.job_id},
        ),
    )


def initialize_rebuild_state_metric_from_db(
    session_factory,
) -> None:
    """
    Set the rebuild-state Prometheus gauge from the authoritative persisted DB state at startup.

    Reads the currently active rebuild job and, if present, initializes the gauge from that job;

    otherwise uses the latest persisted rebuild job to preserve terminal states.

    If no rebuild jobs exist the gauge is set to "none". On errors while reading the DB the gauge is set to "unknown".

    Parameters:
        session_factory: Callable that returns a SQLAlchemy session used to query rebuild job state.
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
