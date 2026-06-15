# Reconciliation Engine

Reference for the control-plane primitives in `src/logic/reconciliation_engine.py`
and the rebuild adapter in `src/logic/rebuild_drift_evaluator.py`.

For the discovery / migration rationale, see
[`reconciliation-discovery-map.md`](reconciliation-discovery-map.md).

## Status

Phase 2 integration complete. The Reconciliation Engine is fully integrated into production paths, including RecoveryGate, the rebuild API, and background synchronization loops.

## Intent

`ReconciliationEngine` is a plan-only control-plane primitive. It compares a
desired state with the observed state (via a pluggable `DriftEvaluator`) and
emits a structured `ReconciliationPlan` describing the corrective action.
Execution is delegated; the engine itself never mutates state, never executes a
job, and never writes to persistence.

These constraints are enforced by convention and by the dataclass design —
`ReconciliationPlan` is frozen, and the engine has no DB/lock dependencies of
its own (the evaluator owns those).

## Public surface

All types are importable from `src.logic.reconciliation_engine` unless noted.

| Symbol                  | Kind                                           | Purpose                                                                                      |
| ----------------------- | ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `ActionType`            | Enum                                           | Corrective action: `NOOP`, `ALERT_ONLY`, `RESET_STATE`, `WAIT_FOR_CONVERGENCE`.              |
| `Severity`              | Enum                                           | Drift severity: `NONE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.                                 |
| `ExecutionMode`         | Enum                                           | When the plan may be applied: `IMMEDIATE`, `DEFERRED`, `MANUAL`, `AUTOMATIC`.                |
| `ExecutionSafety`       | Enum                                           | Machine-readable safety intent (see table below).                                            |
| `ReconciliationPlan`    | Frozen dataclass                               | Structured plan output.                                                                      |
| `DriftEvaluator`        | `typing.Protocol`                              | Interface for drift detectors.                                                               |
| `ReconciliationEngine`  | Class                                          | Generates a plan from an evaluator.                                                          |
| `RebuildDriftEvaluator` | Class (in `src.logic.rebuild_drift_evaluator`) | Adapter that bridges `detect_rebuild_inconsistency` and a `DistributedLock` to the protocol. |

### `ReconciliationPlan`

Frozen dataclass with the fields below. Construction validates that
`actions` is a non-empty iterable of `ActionType` values, normalizes the
sequence to a tuple, and enforces `Severity.NONE ⇒ actions == (NOOP,)`.

```python
ReconciliationPlan(
    drift_type=str,                # e.g. "orphaned_running", "lock_lost"
    severity=Severity,
    actions=tuple[ActionType, ...],
    target_state=str,              # human-readable end state
    execution_mode=ExecutionMode,
    safety_state=ExecutionSafety,
    reason=str,
    metadata=dict[str, str | int | float | bool | None],
    created_at=datetime,           # timezone-aware UTC
)
```

### `DriftEvaluator` protocol

```python
class DriftEvaluator(Protocol):
    def evaluate_drift(
        self,
    ) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
        ...
```

Implementations return the drift type, severity, and a metadata dict. The
engine treats `ValueError` from the evaluator as a fatal invariant violation and
re-raises; any other exception is converted into a `CRITICAL` /
`ALERT_ONLY` / `MANUAL` plan with `safety_state =
ExecutionSafety.EVALUATION_FAILED`.

### `ReconciliationEngine`

```python
engine = ReconciliationEngine(
    evaluator=evaluator,
    enable_automatic_execution=False,
)
plan = engine.generate_reconciliation_plan()
```

`enable_automatic_execution` controls only the execution mode of HIGH-severity `RESET_STATE` plans.
When `False` (the default), HIGH-severity `RESET_STATE` plans are marked `DEFERRED` instead of `AUTOMATIC`.
This applies to every drift type that routes through `_create_reset_plan` (`orphaned_running`; `stale_ownership` when the lock is invalid; `crash_suspicion` when the lock is invalid).
It does not affect `NOOP`, `WAIT_FOR_CONVERGENCE`, or `ALERT_ONLY` plans.

### `ReconciliationEngine.run_rebuild()`

To execute a checkpointed graph rebuild from the provided assets and events, call:

```python
graph = engine.run_rebuild(
    assets=assets,
    regulatory_events=regulatory_events,
    on_checkpoint=on_checkpoint,
    initial_checkpoint=initial_checkpoint,
    cancel_event=cancel_event,
)
```

**Parameters:**

- `assets` (`Iterable[Asset]`): An iterable collection of asset domain objects to add to the graph.
- `regulatory_events` (`Iterable[RegulatoryEvent]`): An iterable collection of regulatory event domain objects to apply.
- `on_checkpoint` (`Callable[[dict[str, Any]], None] | None`): An optional callback function invoked periodically (every 50 assets processed) to record/persist rebuild progress checkpoints.
- `initial_checkpoint` (`dict[str, Any] | None`): An optional state dictionary used to resume a partial rebuild.
- `cancel_event` (`threading.Event | None`): An optional threading event monitored during the execution loops to signal early cancellation of the rebuild job.

**Raises:**

- `RebuildCancelledError`: If `cancel_event` is set during execution.

## Drift → plan decision matrix

The mapping in `ReconciliationEngine._drift_to_plan` /
`_map_drift_type_to_plan` is deterministic. Keys used:

- `lock_is_valid` is read from evaluator metadata and normalised via
  `_parse_lock_is_valid` (accepts `bool`, numeric, or the strings
  `"1" / "true" / "yes" / "y" / "t"` case-insensitive).
- `severity == NONE` short-circuits regardless of drift type.
- `severity == CRITICAL` short-circuits to `ALERT_ONLY` / `MANUAL` with
  `safety_state` chosen by drift type.

| Severity                  | Drift type                | `lock_is_valid` | Actions                | Execution mode | Safety state                                  |
| ------------------------- | ------------------------- | --------------- | ---------------------- | -------------- | --------------------------------------------- |
| `NONE`                    | any                       | `True`          | `NOOP`                 | `AUTOMATIC`    | `CONVERGED`                                   |
| `NONE`                    | any                       | `False`         | `NOOP`                 | `DEFERRED`     | `WAIT_REQUIRED`                               |
| `CRITICAL`                | `lock_lost`               | any             | `ALERT_ONLY`           | `MANUAL`       | `INTEGRITY_COMPROMISED`                       |
| `CRITICAL`                | `persistence_unavailable` | any             | `ALERT_ONLY`           | `MANUAL`       | `OBSERVABILITY_FAILURE`                       |
| `CRITICAL`                | `zombie_executor`         | any             | `ALERT_ONLY`           | `MANUAL`       | `UNSAFE_SPLIT_BRAIN`                          |
| `CRITICAL`                | `orphaned_running`        | `True`          | `ALERT_ONLY`           | `MANUAL`       | `UNSAFE_SPLIT_BRAIN`                          |
| `CRITICAL`                | `orphaned_running`        | `False`         | `ALERT_ONLY`           | `MANUAL`       | `MANUAL_INVESTIGATION`                        |
| `CRITICAL`                | other / evaluator failure | any             | `ALERT_ONLY`           | `MANUAL`       | `MANUAL_INVESTIGATION` or `EVALUATION_FAILED` |
| `HIGH` / `MEDIUM` / `LOW` | `orphaned_running`        | any             | `RESET_STATE`          | see note¹      | `RESET_REQUIRED`                              |
| any non-NONE              | `stale_ownership`         | `True`          | `WAIT_FOR_CONVERGENCE` | `DEFERRED`     | `WAIT_REQUIRED`                               |
| any non-NONE              | `stale_ownership`         | `False`         | `RESET_STATE`          | see note¹      | `RESET_REQUIRED`                              |
| any non-NONE              | `crash_suspicion`         | `True`          | `WAIT_FOR_CONVERGENCE` | `DEFERRED`     | `WAIT_REQUIRED`                               |
| any non-NONE              | `crash_suspicion`         | `False`         | `RESET_STATE`          | see note¹      | `RESET_REQUIRED`                              |
| any non-NONE              | `zombie_executor`         | any             | `ALERT_ONLY`           | `MANUAL`       | `UNSAFE_SPLIT_BRAIN`                          |
| any non-NONE              | unknown drift type        | any             | `ALERT_ONLY`           | `MANUAL`       | `MANUAL_INVESTIGATION`                        |

¹ For `RESET_STATE` plans the execution mode is chosen by
`_create_reset_plan`: `HIGH` → `AUTOMATIC` if
`enable_automatic_execution=True`, otherwise `DEFERRED`; `MEDIUM` / `LOW` →
`DEFERRED`; anything else → `MANUAL`.

## `RebuildDriftEvaluator`

`src/logic/rebuild_drift_evaluator.py` adapts the existing rebuild-coordination
machinery (`src/logic/rebuild_failure_detection.detect_rebuild_inconsistency` + `src/data/distributed_lock.DistributedLock`) to the `DriftEvaluator` protocol.

```python
from src.data.distributed_lock import DistributedLock
from src.logic.rebuild_drift_evaluator import RebuildDriftEvaluator
from src.logic.reconciliation_engine import ReconciliationEngine

evaluator = RebuildDriftEvaluator(
    session_factory=SessionLocal,        # callable returning a SQLAlchemy Session
    lock=DistributedLock(...),
    runtime_has_active_executor=False,   # supplied by caller from runtime state
    lock_ttl_seconds=300,
)
engine = ReconciliationEngine(evaluator)
plan = engine.generate_reconciliation_plan()
```

Behavioural notes (verified against the implementation of
RebuildDriftEvaluator.evaluate_drift):

- Lock state is checked first via `lock.check_state()`. A `LockState.LOST`
  result short-circuits to `("lock_lost", CRITICAL, …)` and the rebuild job is
  not queried.
- `SQLAlchemyError` and `OSError` from the session factory or repository are
  caught and reported as `("persistence_unavailable", CRITICAL, …)`. Other
  database exceptions (including `ValueError` for multi-RUNNING integrity
  violations) propagate unchanged so the engine treats them as fatal.
- Severity classification (`_classify_severity`) preserves the existing
  RecoveryGate downgrade: `ORPHANED_RUNNING` with a valid lock is `CRITICAL`,
  **except** when the job's `active_worker_id` differs from
  `lock.holder_id` _and_ `last_heartbeat_at` is older than
  `lock_ttl_seconds` (or unparseable / missing), in which case it is downgraded
  to `HIGH` so RecoveryGate's resettable path stays reachable.
- Heartbeat parsing accepts `datetime`, ISO-8601 strings (including a
  trailing `Z`), and `None`; unparseable / missing values are treated as
  stale.
- Naive datetimes are assumed to be UTC. If your DB stores naive non-UTC
  timestamps the staleness check will misclassify them — store
  timezone-aware UTC or convert before persisting.

## Constraints and pitfalls

- **No execution.** Callers must apply the plan themselves — typically by
  delegating to `RecoveryGate` or a future job-execution layer. Treat
  `execution_mode` as advice, not authority.
- **`actions` is normalised to a tuple.** Passing a list works, but the stored
  value is a tuple; passing a raw `str`/`bytes` is rejected even though
  `ActionType` is a `str` subclass.
- **`Severity.NONE` requires `actions == (NOOP,)`** — `ReconciliationPlan`
  raises `ValueError` otherwise.
- **Evaluator metadata is copied** into the plan (shallow copy in
  `_drift_to_plan`). Don't rely on mutating the dict after the plan is
  produced.
- **`ValueError` from `evaluate_drift` is fatal.** The engine re-raises it so
  invariant violations (e.g. multiple RUNNING jobs detected by the repository)
  surface to the caller instead of being masked by an `EVALUATION_FAILED`
  plan.
- **Logging is at `INFO` for plans and `DEBUG` for raw drift evaluations.**
  Evaluator failures are logged at `EXCEPTION` (full traceback) with the error
  type and message before the failure plan is returned.

## Related modules

- `src/logic/rebuild_failure_detection.py` — raw drift detection
  (`InconsistencyType`, `detect_rebuild_inconsistency`).
- `src/logic/rebuild_recovery.py` — legacy `determine_recovery_action` mapping
  that the engine generalises.
- `src/logic/recovery_gate.py` — current execution boundary that consumes
  recovery actions; Phase 2 will let it consume `ReconciliationPlan` instead.
- `src/data/distributed_lock.py` — lock primitive used by
  `RebuildDriftEvaluator`.
