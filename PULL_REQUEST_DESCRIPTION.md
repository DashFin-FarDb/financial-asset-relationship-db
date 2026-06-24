# PR: Failure-Mode and Scale Validation

## Primary Objective

Prove the distributed graph rebuild hosting semantics under controlled restart, crash, stale-owner, lock-loss, and
representative-scale conditions without changing the architecture.

This PR is a test-and-evidence PR. It validates the single-writer / multi-reader operating model documented in PR 6
using focused integration tests and deterministic graph fixtures.

## Scope

### In Scope

- Add integration coverage for fresh-owner protection, stale-owner reset after lock reacquisition, and restart during a
  live foreign rebuild owner.
- Add rebuild pipeline failure tests for crash-before-persist, post-persist metadata failure, and lock-loss fail-closed
  behavior.
- Add a deterministic representative graph factory for scale validation.
- Add representative-scale persistence round-trip checks for 250/1,000 and 1,000/5,000 graph snapshots.
- Add bounded timing tripwires for persisted startup load and rebuild persistence paths.
- Document tested invariants and non-SLO timing evidence.
- Update roadmap and audit docs to reflect PR 7 validation progress.

### Out of Scope

- No architecture changes.
- No production schema changes.
- No frontend changes.
- No new rebuild endpoint.
- No new distributed scheduler, queue, or coordinator.
- No multi-region support claim.
- No production benchmark framework or strict performance SLO.
- No DR/backup runbook; that remains PR 9 scope.

### Files Expected to Change

- `tests/helpers/graph_scale_factory.py`
- `tests/integration/test_distributed_hosting_failure_modes.py`
- `tests/integration/test_graph_persistence_scale_validation.py`
- `docs/testing/failure-mode-and-scale-validation.md`
- `docs/roadmap/enterprise-readiness-pr-board.md`
- `docs/roadmap/enterprise-readiness-pr-plan.md`
- `docs/audits/enterprise-readiness-audit.md`
- `PULL_REQUEST_DESCRIPTION.md`

## Behavior and Compatibility Notes

- The validation uses SQLite-backed integration fixtures to preserve the roadmap’s SQLite compatibility rule.
- The scale graph helper is deterministic and avoids duplicate directed relationship keys so persisted counts are exact.
- The startup scale timing test exercises the lifecycle persisted-load path directly; existing hosted readiness tests
  continue to cover the FastAPI health/readiness surface.
- Timing assertions are generous regression tripwires, not production SLOs.
- No API response shape, persistence schema, lock semantics, or RecoveryGate behavior is changed.

## Delayed, Deferred, or Not Acted On

- Production-scale benchmarking remains out of scope.
- Multi-region, multi-writer, queue, scheduler, and external coordinator behavior remains unsupported.
- DR/backup/restore procedures remain deferred to PR 9.
- Larger stress tests for memory growth and lock refresh under production-like load remain future validation work.

## Validation Commands

Executed successfully:

```bash
pytest tests/integration/test_graph_persistence_scale_validation.py -q
pytest tests/integration/test_distributed_hosting_failure_modes.py -q
pytest tests/unit/test_recovery_gate.py -q
python -m compileall src api tests
pre-commit run --files tests/helpers/__init__.py tests/helpers/graph_scale_factory.py tests/integration/test_distributed_hosting_failure_modes.py tests/integration/test_graph_persistence_scale_validation.py docs/testing/failure-mode-and-scale-validation.md docs/roadmap/enterprise-readiness-pr-board.md docs/roadmap/enterprise-readiness-pr-plan.md docs/audits/enterprise-readiness-audit.md PULL_REQUEST_DESCRIPTION.md
```

Attempted locally but not completed because the existing suites hung before producing a first test result in this
environment:

```bash
pytest tests/integration/test_graph_rebuild_persistence.py -q
pytest tests/integration/test_hosted_graph_startup_readiness.py -q
```

## Merge Criteria

- [x] Fresh foreign rebuild owners are not reset.
- [x] Stale owners are reset only through valid RecoveryGate lock ownership.
- [x] Restart during a live rebuild does not steal fresh ownership.
- [x] Crash before persistence fails the job without writing partial durable graph truth.
- [x] Post-persist metadata failure leaves durable graph truth loadable and consistent.
- [x] Lock loss aborts before persistence or success marking.
- [x] Representative-scale save/load round trip preserves exact counts and selected edge strengths.
- [x] Representative persisted startup load and rebuild persist paths have bounded timing tripwires.
- [x] Baseline evidence is documented without introducing production SLO claims.
- [x] No architecture, schema, frontend, or API-contract changes are introduced.

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only.
- [x] I have explicitly listed what is out of scope.
- [x] This is a test-and-evidence PR.
- [x] I have verified the branch, base branch, and referenced roadmap context.
- [x] I have checked this PR against the production architecture (`FastAPI` backend + `Next.js` frontend).

### Documentation Review

- [x] Failure-mode evidence maps back to ADR 0004 distributed hosting semantics.
- [x] Scale validation is documented as representative and non-SLO.
- [x] Roadmap and audit docs distinguish current proof from deferred production-scale validation.
