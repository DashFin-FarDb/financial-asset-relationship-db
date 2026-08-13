# Agent task entry route

**Purpose:** Start repository work from one short route to current authority, code, tests, and evidence.
**Scope:** Navigation and task control only. This page is not a second roadmap, ledger, ADR, or release record.

## 1. Establish the exact task

Do not infer current priority from this repository, an old conversation, generated memory, or an open PR. Obtain a
task brief that names the current work-programme ID or issue and complete every field below before editing:

```text
Exact base ref and requested branch/PR:
Primary objective and work-programme ID:
Decision and authority sources:
Allowed files:
Forbidden files:
Named code seams:
Focused tests and validation commands:
Linked issue, PR, and evidence:
Fixed decisions and non-targets:
Stop conditions:
Completion evidence:
```

If the brief is absent, contradictory, or does not bound a high-risk task, stop and obtain a corrected brief. Follow
the additional low-autonomy contract in [AI Agent Guardrails](../.github/AI_AGENT_GUARDRAILS.md) for database,
authentication, deployment, CI, security, persistence, migration, and recovery work.

## 2. Apply authority in order

When sources conflict, current evidence wins. Use this order:

1. The exact task brief and current priority decision supplied for this work item.
2. Merged code, tests, migrations, workflows, exact-SHA evidence, and current provider observations.
3. Accepted [ADRs](adr/0001-production-architecture.md), contracts, operating authorities, and runbooks.
4. The [project continuity ledger](strategy/fardb-project-continuity.md), reconciled against current `main` and open
   work before use.
5. Dated strategy snapshots, plans, generated compound material, and historical memory as context only.

The repository's durable authorities include:

- [Production architecture](adr/0001-production-architecture.md)
- [Database authorization boundary](adr/0007-database-authorization-boundary.md)
- [GRAC v1 contract](governance/governed-relationship-assertion-contract-v1.md)
- [State machine and operating authority](governance/state-machine-and-operating-authority.md)
- [Enterprise readiness index](enterprise-readiness-index.md)
- [GRAC v1 exact-SHA staging sign-off](governance/grac-v1-exact-sha-evidence-signoff.md)

The external programme workspace may select priority, but it does not prove delivery. If it is unavailable, require
the task brief to reproduce the selected work-item ID, decision, scope, and completion condition; do not guess them.

## 3. Verify before changing files

1. Record the current branch and commit, requested ref, associated PR, and difference from `main`.
2. Confirm that no later merge, open PR, or provider evidence has already closed or invalidated the task.
3. Open only the named code seams and focused tests first.
4. State allowed and forbidden files, fixed decisions, stop conditions, and completion evidence.
5. Challenge any claim whose evidence is stale, contradictory, or insufficient. Record the contrary evidence and a
   testable adjudication path instead of manufacturing agreement.

Stop rather than widening scope when a new architecture decision, credential/authority boundary, destructive action,
protected disclosure, contradictory source, dependency change, or unlisted file becomes necessary.

## 4. Close with evidence

One PR should implement one bounded decision. Its description must identify the work-programme ID, exact base,
scope and exclusions, validation actually run, operational evidence where required, documentation impact, and merge
criteria. A task is not done until the intended PR is merged, required post-merge/provider checks pass, and the
priority authority plus continuity handoff are reconciled.

## Historical and generated material

- [`docs/strategy/current-state.md`](strategy/current-state.md) is a dated historical snapshot.
- [`.elastic-copilot/memory/`](../.elastic-copilot/memory/README.md) is retained legacy memory, not active
  instruction.
- [`docs/compound/`](compound/INDEX.md) is generated navigational memory and must not override source evidence or
  accepted authority.
