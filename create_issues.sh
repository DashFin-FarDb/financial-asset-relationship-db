#!/bin/bash

gh issue create --title "PR 2 — Startup Load / Save Integration" --body "**Primary objective:** Make persisted graph truth participate in startup and rebuild lifecycle.

**Scope**
- load durable graph state during startup when present and valid;
- persist rebuilt graph state through the new repository boundary;
- record startup source / fallback behavior in observability;
- ensure restart semantics are visible and deterministic."

gh issue create --title "PR 3 — Durable Promotion Gate Extension" --body "**Primary objective:** Require durable graph evidence for staging/production promotion.

**Scope**
- extend hosted readiness checks to prove persisted graph load;
- add durable promotion criteria to deployment docs and smoke checks;
- ensure bounded health does not imply durable graph truth."

gh issue create --title "PR 4 — API Contract Cleanup" --body "**Primary objective:** Remove ambiguity from externally consumed API contracts.

**Scope**
- normalize density semantics end-to-end;
- formalize visualization payload types;
- decide pagination contract for assets and align frontend/backend behavior;
- update affected tests and types together."

gh issue create --title "PR 5 — Recovery-Plane Completion" --body "**Primary objective:** Finish the remaining control-plane integration around reconciliation and recovery.

**Scope**
- integrate reconciliation plan consumption into \`RecoveryGate\`;
- add or refine periodic reconciliation behavior if still warranted;
- tighten recovery-path tests and invariants."

gh issue create --title "PR 6 — Distributed Hosting Semantics Spec" --body "**Primary objective:** Define and document multi-instance behavior for rebuild, restart, and lock ownership.

**Scope**
- specify single-writer / multi-reader assumptions;
- document split-brain handling and stale-owner mutation rules;
- define restart/redeploy interaction with in-flight rebuilds;
- map operational expectations into testable invariants."

gh issue create --title "PR 7 — Failure-Mode and Scale Validation" --body "**Primary objective:** Prove the system behaves correctly under restart, crash, and larger-graph conditions.

**Scope**
- add crash / restart / stale-owner tests;
- add representative-scale persistence and rebuild checks;
- record baseline timings for load and rebuild paths."

gh issue create --title "PR 8 — Security and Governance Hardening" --body "**Primary objective:** Convert security and governance from broad coverage into enforceable operating policy.

**Scope**
- define release provenance and artifact-integrity expectations;
- formalize secret rotation / leak response expectations;
- add authorization-failure or sensitive-event audit logging where needed;
- clarify approval / exception workflows."

gh issue create --title "PR 9 — Backup, Restore, and DR Runbook" --body "**Primary objective:** Close the remaining enterprise recovery gap.

**Scope**
- define backup schedule and retention;
- define restore procedure and verification;
- document RPO / RTO assumptions;
- define operator ownership and escalation."
