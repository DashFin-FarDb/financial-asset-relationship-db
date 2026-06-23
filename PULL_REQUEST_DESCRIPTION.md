# PR: Unify ReconciliationPlan Consumption in RecoveryGate

## Architectural Alignment

- Backend: FastAPI production path. This PR changes startup/background recovery control-plane behavior used by the FastAPI application lifecycle.
- Frontend: Next.js production path is unaffected.
- Gradio: non-production demo/testing path is unaffected.

This PR does not change the declared production architecture. It keeps the work in the FastAPI backend and Python recovery/control-plane code, consistent with `.github/AUTOMATION_SCOPE_POLICY.md` and `docs/adr/0001-production-architecture.md`.

## Primary Objective

Make `RecoveryGate` the single execution boundary that consumes `ReconciliationPlan` objects and decides whether execution may proceed, must wait, must alert/block, or may perform bounded reset recovery.

The main safety objective is to remove split-brain recovery decision paths where the periodic reconciliation loop generated/interpreted a plan and then asked `RecoveryGate` to independently re-plan before mutating state.

## Scope

### In Scope

- Add `RecoveryGate.consume_reconciliation_plan(plan, cancellation_event=None)` as the canonical plan-consumption method.
- Refactor `RecoveryGate.ensure_safe_to_execute()` to generate one plan and delegate consumption to `consume_reconciliation_plan()`.
- Add explicit `RecoveryGate` constructor options:
  - `enable_automatic_recovery`
  - `record_drift_metric`
- Ensure `get_reconciliation_plan()` constructs `ReconciliationEngine` with the same automatic-recovery and drift-metric configuration that the consuming gate will enforce.
- Refactor `src/logic/reconciliation_loop.py` so the periodic loop:
  - creates session/lock dependencies,
  - constructs a `RecoveryGate`,
  - asks that gate for one plan,
  - consumes that same plan once,
  - does not independently inspect or execute `ActionType.RESET_STATE`.
- Preserve startup fail-closed behavior:
  - `RecoveryGate.enable_automatic_recovery` defaults to `False`.
  - startup reconciliation passes `enable_automatic_recovery=False`.
  - periodic reconciliation passes `enable_automatic_recovery=True`.
- Propagate `settings.rebuild_lock_ttl_seconds` from `api/app_factory.py` into `periodic_reconciliation_loop()`.
- Enforce the distributed-lock TTL safety ceiling for reconciliation recovery:
  - app-factory background task wiring bounds configured TTL to `1..300`.
  - reconciliation-loop lock construction bounds TTL to `1..300`.
  - `RecoveryGate.lock_ttl_seconds` bounds TTL to `1..300`.
- Preserve the plan drift type when lock reacquisition times out instead of hard-coding `orphaned_running`.
- Treat expected `ExecutionBlockedError` safety blocks in the periodic loop as non-transient blocked states, not infrastructure failures that trigger exponential backoff.
- Release only locks reacquired by `RecoveryGate`, and continue logging release failures without crashing the reconciliation loop.
- Add/extend tests for:
  - plan consumption paths,
  - wait/alert/evaluation-failed/deferred reset non-mutation behavior,
  - automatic reset delegation,
  - post-reset re-evaluation,
  - cancellation before reset mutation,
  - reacquired-lock release,
  - lock release failure logging,
  - configured and bounded lock TTL propagation,
  - no duplicate plan generation in the periodic loop,
  - drift metric forwarding,
  - runtime-not-ready skip behavior,
  - expected blocked states not entering transient-error backoff.

### Out of Scope

- Graph persistence semantics.
- SQLite persistence compatibility changes.
- Rebuild job schema changes.
- Hosted readiness probes or deployment smoke-check behavior.
- Auth model changes.
- API response contract cleanup outside reconciliation/recovery behavior.
- Frontend/Next.js visualizer changes.
- Gradio/demo behavior changes.
- New schedulers, workers, or background executors.
- Dependency changes.

### Files Expected to Change

- `src/logic/recovery_gate.py`
  - Adds explicit plan consumption, automatic-recovery configuration, TTL bounding, reset authorization checks, post-reset re-evaluation, and drift-aware lock reacquisition errors.
- `src/logic/reconciliation_loop.py`
  - Removes duplicate plan interpretation from the loop, delegates consumption to `RecoveryGate`, bounds lock TTL, releases reacquired locks, and treats expected recovery-gate blocks as non-transient.
- `api/app_factory.py`
  - Passes bounded `rebuild_lock_ttl_seconds` into the periodic reconciliation loop.
- `tests/conftest.py`
  - Adds shared `make_reconciliation_plan` test fixture used by recovery-gate and reconciliation-loop tests.
- `tests/unit/test_recovery_gate.py`
  - Adds plan-consumption, reset, cancellation, TTL, and lock-reacquisition regression coverage.
- `tests/unit/test_reconciliation_loop.py`
  - Adds dedicated periodic reconciliation-loop unit coverage.
- `tests/unit/test_app_factory.py`
  - Adds background task TTL propagation/capping coverage and fixes the loop test trace wrapper to return an awaitable.
- `tests/unit/test_recovery_gate_startup.py`
  - Updates startup recovery-gate expectations to preserve fail-closed defaults and automatic-recovery explicitness.
- `tests/integration/test_recovery_gate_integration.py`
  - Adjusts integration coverage to match explicit automatic-recovery construction.
- `PULL_REQUEST_DESCRIPTION.md`
  - Keeps the checked-in PR description aligned with the live GitHub PR body and repo guardrails.

## Behavior and Compatibility Notes

- `RecoveryGate.ensure_safe_to_execute()` remains public and backward-compatible for existing callers.
- `RecoveryGate.evaluate_state()` remains public and backward-compatible.
- `ExecutionBlockedError` continues exposing `action` and `inconsistency_type`.
- Block messages continue including `(action=..., inconsistency=...)` tags where compatibility-sensitive callers/tests expect them.
- Startup remains conservative: automatic reset recovery is not enabled by default.
- Periodic reconciliation remains the only automatic recovery path in this PR and only runs once the runtime lifecycle is `READY`.
- Bounded reset recovery still requires:
  - automatic or immediate execution mode,
  - `RESET_REQUIRED` safety state,
  - no cancellation signal,
  - a valid or successfully reacquired distributed lock,
  - stale/orphaned active rebuild state before mutation.

## Review Feedback Addressed

- Capped configured reconciliation lock TTL values before they reach `DistributedLock` or stale-heartbeat comparisons.
- Fixed the test trace wrapper that previously returned a synchronous result where the loop expected an awaitable.
- Preserved plan drift type for lock reacquisition timeout errors.
- Added a module-level `pytestmark = pytest.mark.unit` to the new reconciliation-loop unit tests.
- Reduced duplicated wait/alert block handling in `RecoveryGate`.
- Bundled repeated reconciliation-loop test dependencies to reduce test fixture argument count.
- Added regression coverage for expected blocked states so they do not trigger transient-error backoff.

## Delayed, Deferred, or Not Acted On

- No in-scope implementation items are intentionally deferred.
- CodeScene-style duplication findings in tests may still reappear depending on the analyzer threshold; this PR reduced the highest-signal duplication/argument-count issues without obscuring scenario-specific test intent.
- Existing repository/default-branch vulnerability notices are not addressed here because this PR does not change dependencies.
- Full-file `tests/unit/test_app_factory.py` was not used as final validation because the existing lifespan/background-task teardown path timed out locally under the managed sandbox. The three app-factory tests affected by this PR were run directly and passed.
- Review threads were not manually resolved through GitHub by this change; they are expected to be re-evaluated by reviewers/bots after the pushed commits.

## Validation Commands

Executed successfully:

```bash
pytest tests/unit/test_recovery_gate.py tests/unit/test_reconciliation_loop.py -q
pytest tests/unit/test_app_factory.py::test_periodic_reconciliation_loop_triggers_recovery tests/unit/test_app_factory.py::test_start_background_tasks_propagates_rebuild_lock_ttl_seconds tests/unit/test_app_factory.py::test_start_background_tasks_caps_rebuild_lock_ttl_seconds -q
pre-commit run --files api/app_factory.py src/logic/reconciliation_loop.py src/logic/recovery_gate.py tests/unit/test_app_factory.py tests/unit/test_reconciliation_loop.py tests/unit/test_recovery_gate.py
```

Additional syntax/format checks were also run during implementation:

```bash
python -m compileall src/logic/recovery_gate.py src/logic/reconciliation_loop.py api/app_factory.py tests/unit/test_recovery_gate.py tests/unit/test_reconciliation_loop.py tests/unit/test_app_factory.py
python -m black --workers 1 src/logic/recovery_gate.py src/logic/reconciliation_loop.py api/app_factory.py tests/unit/test_recovery_gate.py tests/unit/test_reconciliation_loop.py tests/unit/test_app_factory.py
python -m flake8 --jobs=1 src/logic/recovery_gate.py src/logic/reconciliation_loop.py api/app_factory.py tests/unit/test_recovery_gate.py tests/unit/test_reconciliation_loop.py tests/unit/test_app_factory.py
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective.
- [x] This PR makes one primary decision only: converge `ReconciliationPlan` consumption into `RecoveryGate`.
- [x] In-scope and out-of-scope boundaries are explicitly documented.
- [x] Changes align with production architecture (`FastAPI` backend + `Next.js` frontend).
- [x] Gradio/demo paths are not treated as production architecture.
- [x] Runtime dependency source of truth remains unchanged.
- [x] Compatibility surface is preserved or explicitly documented.
- [x] Focused validation commands pass locally.
- [x] Review-feedback fixes are documented.
- [x] Deferred or not-acted-on items are explicitly recorded.

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only.
- [x] I have explicitly listed what is out of scope.
- [x] This is not a docs/policy/architecture-only PR.
- [x] I have verified the branch, base branch, and referenced issue/PR context.
- [x] I have checked this PR against the production architecture (`FastAPI` backend + `Next.js` frontend).
- [x] I have checked this PR against `.github/AUTOMATION_SCOPE_POLICY.md`.

### Testing Best Practices

- [x] Tests verify observable behavior such as raised actions, state decisions, function calls, and interval/backoff effects.
- [x] Tests avoid coupling to exact log message strings.
- [x] New tests do not add fixed timing sleeps for assertions.
- [x] Recovery/control-plane tests use mocks or existing fixtures to avoid leaking database/lock resources.
