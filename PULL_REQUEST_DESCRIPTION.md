# PR: Distributed Hosting Semantics Spec

## Summary

Defines FarDb distributed hosting semantics for multi-instance backend
deployments.

This PR documents the system as single-writer / multi-reader:

- one rebuild writer per graph persistence boundary;
- multiple backend instances may serve reads;
- rebuild mutation requires lock ownership;
- stale-owner recovery is allowed only under RecoveryGate-approved conditions;
- suspected split-brain fails closed and requires operator intervention.

## Scope

### In Scope

- Add ADR 0004 for distributed hosting semantics.
- Define the authority model for durable graph truth, runtime graph snapshots,
  and the rebuild control plane.
- Document single-writer / multi-reader behavior for multi-instance backend
  deployments.
- Map lock ownership, heartbeat/liveness, stale-owner recovery, split-brain,
  restart, and redeploy semantics.
- Update the enterprise deployment operating model with rebuild ownership
  rules.
- Update reconciliation documentation so plan generation remains distinct from
  write authorization.
- Add testable invariants for PR 7 failure-mode validation.
- Update roadmap and audit docs to reflect PR 6 documentation completion.

### Out of Scope

- No production code changes.
- No schema changes.
- No frontend changes.
- No new rebuild endpoint.
- No new distributed scheduler or coordinator.
- No multi-region support claim.
- No Redis, queue, or external coordinator introduction.
- No backup/restore runbook; that belongs to PR 9.
- No failure-injection tests; that belongs to PR 7.

### Files Expected to Change

- `docs/adr/0004-distributed-hosting-semantics.md`
- `docs/testing/distributed-hosting-invariants.md`
- `docs/enterprise-deployment-operating-model.md`
- `docs/reconciliation-engine.md`
- `docs/reconciliation-discovery-map.md`
- `docs/roadmap/enterprise-readiness-pr-board.md`
- `docs/roadmap/enterprise-readiness-pr-plan.md`
- `docs/audits/enterprise-readiness-audit.md`
- `PULL_REQUEST_DESCRIPTION.md`

## Behavior and Compatibility Notes

- Backend scale-out is specified for read serving only.
- Scale-out does not increase rebuild writer concurrency.
- Durable graph truth in `ASSET_GRAPH_DATABASE_URL` is authoritative in
  staging and production.
- Runtime graph state is an in-memory snapshot/cache, not the source of truth.
- Unknown ownership, lock loss, persistence unavailability, fresh competing
  owners, and suspected split-brain all fail closed for mutation.
- PR 7 remains responsible for proving these semantics with failure-mode and
  scale validation.

## Delayed, Deferred, or Not Acted On

- No production code, schema, frontend, scheduler, queue, or coordinator change
  is included.
- No multi-region behavior is claimed.
- Backup/restore remains deferred to PR 9.
- Failure-injection implementation and scale validation remain deferred to PR 7.
- The invariant table is a future test target, not a claim that those tests
  already exist.

## Validation

Executed successfully:

```bash
python -m compileall src api
```

Documentation consistency checks were also performed against ADR 0002, ADR
0003, the enterprise operating model, reconciliation docs, roadmap, and audit
notes.

## Merge Criteria

- [x] ADR 0004 exists and defines single-writer / multi-reader semantics.
- [x] Split-brain handling is explicit and fail-closed.
- [x] Stale-owner mutation rules are explicit and narrow.
- [x] Restart/redeploy behavior with in-flight rebuilds is documented.
- [x] Operational expectations are reflected in the enterprise deployment
      operating model.
- [x] Every operational rule maps to at least one future testable invariant.
- [x] Docs do not claim multi-region, multi-writer, queue-based, or
      scheduler-based behavior.
- [x] Docs distinguish current guarantees from PR 7 validation work.
- [x] No production code, schema, or frontend change is introduced.

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only.
- [x] I have explicitly listed what is out of scope.
- [x] This is a docs/spec PR.
- [x] I have verified the branch, base branch, and referenced roadmap context.
- [x] I have checked this PR against the production architecture
      (`FastAPI` backend + `Next.js` frontend).
- [x] I have checked this PR against `.github/AUTOMATION_SCOPE_POLICY.md`.

### Documentation Review

- [x] ADR 0004 aligns with ADR 0002 and ADR 0003.
- [x] Enterprise operating model includes distributed hosting semantics.
- [x] Reconciliation docs keep `ReconciliationEngine` plan-only.
- [x] Testable invariants map directly to PR 7.
