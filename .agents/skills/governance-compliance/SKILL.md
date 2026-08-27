---
name: governance-compliance
description: Compile and review an exact-head PR contract against FarDb governance, evidence, and durable finding-disposition rules without changing code or scope.
---

# Governance and Compliance

Use this skill to answer: what did this PR promise, what did its exact head
change and prove, and what remains unresolved?

## Authority

Read the target branch's `.github/AUTOMATION_SCOPE_POLICY.md`,
`.github/AI_AGENT_GUARDRAILS.md`, accepted ADRs, and the approved issue/contract
before evaluating a diff. Authority descends from target policy and ADRs,
through approved contract versions, to exact-head code/evidence, review claims,
and finally model inference. Never let a newer comment redefine approved scope.

## Review procedure

1. Resolve the exact repository, base, merge base, head, policy SHA, contract
   version/hash, evaluator version, and target.
2. Compile the approved objective, path boundaries, targets/non-targets, fixed
   decisions, invariants, evidence, merge criteria, and stop conditions.
3. Inventory the complete `merge-base...head` diff, including renames and
   deletions. Compare it with the contract; do not alter code or broaden scope.
4. Accept mandatory evidence only when it is an executed pass for the exact
   head and target. `skipped`, `canceled`, `unavailable`, `stale_sha`, and
   `wrong_target` results do not pass.
5. Emit structured candidate findings with rule, stable subject, failure mode,
   expected outcome, origin, evidence, and lifecycle. Model inference and
   semantic similarity are advisory.
6. Carry unresolved findings forward. Classify validated outcomes as
   `resolved`, `deferred_out_of_scope`, `rejected_speculative`, `duplicate_of`,
   `reopened_as_recurrence`, or `waived`. Thread resolution alone is not
   remediation.
7. Stop for human action when a contract amendment, waiver, ambiguous blocking
   basis, new architecture decision, or permission expansion is required.

Never write code, edit the contract, resolve or waive your own findings,
approve, merge, dispatch a workflow, mutate a provider, or expose raw evidence
or secrets. Phase 1 is offline replay only; it does not authorize a live check.
