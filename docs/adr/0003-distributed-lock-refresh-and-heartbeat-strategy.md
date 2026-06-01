# ADR 0003: Distributed Lock Refresh and Heartbeat Strategy

## Status

Accepted

## Date

2026-04-17

## Context

The Financial Asset Relationship Database's graph rebuild operation is a long-running, resource-intensive process that must guarantee exclusive access to the persistence store. When distributed across multiple instances (e.g., in a horizontally scaled deployment), we need to prevent "split-brain" scenarios where multiple workers simultaneously attempt to rebuild and persist graph state.

### Problem: Lock Expiration During Long Operations

Distributed locks backed by database TTL (time-to-live) naturally expire after a fixed duration. For rebuild operations that may take longer than the TTL, the lock could expire mid-operation, allowing another instance to acquire it and create data corruption.

### Problem: Silent Lock Loss Detection

Even with lock refresh, transient database connectivity issues could prevent a worker from refreshing its lock. The worker must detect lock loss promptly to abort the operation before committing incomplete or conflicting state.

### Problem: Liveness Tracking

Operators need visibility into whether a rebuild worker is still actively progressing or has stalled/crashed. A heartbeat mechanism provides this operational insight.

## Decision

We implement a **heartbeat keeper thread** that periodically refreshes both the distributed lock and rebuild job heartbeat timestamp at an interval of `TTL/3`. A dedicated background thread ensures that lock refresh and heartbeat updates occur independently of the main rebuild operation, preventing heartbeats from being blocked by long-running synchronous CPU-bound graph processing stages.

### Key Design Elements

#### 1. Heartbeat Refresh Interval

**Refresh interval = max(1, lock_ttl_seconds // 3)**

- Default lock TTL: 300 seconds
- Default refresh interval: 100 seconds
- Ensures at least 2 refresh opportunities before expiration
- Provides early detection of connectivity issues

#### 2. Dual Refresh: Lock + Database Heartbeat

On each interval, the heartbeat keeper:

1. Refreshes the distributed lock TTL via `DistributedLock.refresh()`
2. Updates the `RebuildJobORM.last_heartbeat_at` timestamp
3. Records the worker ID in `RebuildJobORM.active_worker_id`

Both operations must succeed; failure of either signals the lock_lost event.

#### 3. Lock Refresh Retry Logic

The `DistributedLock.refresh()` method implements transient error retry:

- **Retries on**: `SQLAlchemyError`, `OSError` (database/network blips)
- **Does not retry on**: Lock conflict (held by another holder)
- **Default**: 2 retries with 0.5s delay
- **Returns**: `True` on success, `False` on failure (conflict or exhausted retries)

This handles brief network hiccups without failing the entire rebuild.

#### 4. Lock Loss Signal

The heartbeat keeper sets a `threading.Event` (lock_lost) when:

- Lock refresh returns `False` (conflict or persistent error)
- Heartbeat database update fails (connectivity loss)
- Any unexpected exception during refresh cycle

The main rebuild thread checks this event at critical checkpoints:

- Before building the graph
- Before persisting to database
- Before committing the transaction
- Before marking job as succeeded

If lock_lost is set, the rebuild aborts with `_DistributedLockLostError`.

### Configuration

**Environment Variable**: `REBUILD_LOCK_TTL_SECONDS` (default: 300)

Typed setting in `src/config/settings.py`:

```python
rebuild_lock_ttl_seconds: int = Field(default=300, gt=0)
```

Propagated to `GraphLifecycleSettings` and consumed by `graph_admin.py` rebuild orchestration.

## Consequences

### Positive

1. **Prevents Lock Expiration**: Long-running rebuilds maintain their lock for the operation duration
2. **Early Conflict Detection**: Loses the lock within one refresh interval if another holder takes over
3. **Transient Error Resilience**: Brief network blips don't cause unnecessary rebuild failures
4. **Operational Visibility**: Heartbeat timestamps enable monitoring and detection of stalled workers
5. **Typed Configuration**: Pydantic validation ensures lock TTL is always a positive integer
6. **Fail-Safe Design**: Lock loss triggers immediate abort, preventing split-brain data corruption

### Negative

1. **Thread Complexity**: Background heartbeat thread adds concurrency complexity (managed via `threading.Event` and daemon threads)
2. **Database Load**: Periodic refresh operations add ~2 queries per 100 seconds during rebuilds
3. **Delayed Detection**: Lock loss detected at next checkpoint (up to 100 seconds for long rebuild stages)
4. **Configuration Coupling**: Lock TTL now affects both lock duration and refresh interval timing

### Neutral

1. **Lock Refresh Overhead**: Minimal CPU/memory impact (single background thread, simple refresh logic)
2. **No Network Coordination**: Uses database-backed state only (no Redis/external coordinator required)

## Implementation

### Core Files

#### `src/data/distributed_lock.py`

- `DistributedLock.refresh()` method with retry logic (lines 234-314)
- Retries transient errors (`SQLAlchemyError`, `OSError`)
- No retry on lock conflicts (returns `False` immediately)

#### `api/routers/graph_admin.py`

- `_heartbeat_keeper()` function (lines 602-654)
  - Background thread refreshing lock and heartbeat
  - Sets `lock_lost` event on any failure
- `_orchestrate_heartbeat()` context manager (lines 702-736)
  - Manages heartbeat thread lifecycle
  - Calculates refresh interval as `max(1, lock_ttl // 3)`
- Rebuild pipeline checks `lock_lost` at critical checkpoints

#### `src/config/settings.py`

- `Settings.rebuild_lock_ttl_seconds` field (default 300, validated >0)
- Environment variable binding: `REBUILD_LOCK_TTL_SECONDS`

#### `api/graph_lifecycle_providers.py`

- `GraphLifecycleSettings.rebuild_lock_ttl_seconds` field
- Mapped from base `Settings` in `get_graph_lifecycle_settings()`

### Testing

#### Unit Tests

- `tests/unit/test_repository_distributed_lock.py::TestDistributedLockRetryLogic`
  - `test_refresh_retries_on_transient_db_error`: Validates retry behavior
  - `test_refresh_does_not_retry_on_lock_conflict`: Validates conflict handling
  - `test_refresh_exhausts_retries_on_persistent_error`: Validates retry exhaustion

- `tests/unit/test_settings.py` (new tests recommended):
  - Test default `rebuild_lock_ttl_seconds=300`
  - Test environment variable override
  - Test validation rejects ≤0 values

#### Integration Tests

- `tests/integration/test_lock_refresh_flow.py` (existing)
  - Validates end-to-end lock refresh during rebuild

## Operational Runbook

### Symptoms of Lock Loss

- **Log**: `"Heartbeat keeper lost distributed lock for job {job_id}"`
- **Metric**: `heartbeat_update_total{status="failure"}` increase
- **Job Status**: Rebuild job marked as `failed` with category `distributed_lock_lost`
- **HTTP Response**: `503 Service Unavailable` with code `distributed_lock_lost_during_rebuild`

### Recovery Steps

1. **Check for Concurrent Rebuilds**: Review rebuild job history for overlapping execution
2. **Verify Database Connectivity**: Check database availability and network stability
3. **Review Lock TTL**: Ensure `REBUILD_LOCK_TTL_SECONDS` is appropriate for rebuild duration (default 300s)
4. **Retry Rebuild**: Operator can retry the rebuild request; the system enforces exclusive access
5. **Monitor Heartbeats**: Query `last_heartbeat_at` on running jobs to verify liveness

## References

- [src/data/distributed_lock.py](../../src/data/distributed_lock.py): Lock refresh implementation
- [api/routers/graph_admin.py](../../api/routers/graph_admin.py): Heartbeat keeper and rebuild orchestration
- [src/config/settings.py](../../src/config/settings.py): Typed lock TTL configuration
- [ADR 0002: Hosted Deployment and Persistence](./0002-hosted-deployment-and-persistence.md): Related persistence guarantees

## Authors

- Claude (AI Agent)
- DashFin-FarDb Organization

## Review and Approval

This ADR documents the lock refresh and heartbeat coordination design implemented as part of Phase 3 improvements to rebuild reliability.
