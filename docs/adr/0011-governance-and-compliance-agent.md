# ADR 0011: Governance and Compliance agent

## Status

**Accepted for Phase 1 specification and offline replay only.**

## Date

2026-08-22

## Authority

- Parent programme: GitHub issue #1557
- Phase contract: `gnc.phase1@v1`, defined by the linked
  [normative contract](../governance/governance-and-compliance-agent-v1.md)
- Execution authorization: issue #1558 at base
  `8b755727bfb1b52c9b0ef09ef12e03bbf3b06084`, including amendment
  `gnc.phase1.amendment-1` for the ADR 0011 path

## Context

FarDb policy describes automation scope, but a PR's promises, exact-head
evidence, review dispositions, and waivers are not one frozen executable
contract. Review comments can arrive incrementally, evidence can belong to a
stale SHA or wrong target, and structurally valid output can overstate runtime
proof. Adding another autonomous fixer would amplify those failure modes.

## Decision

Adopt a separate Governance and Compliance (GNC) capability whose permanent
question is: what did this PR promise, what has the exact head changed and
proved, and what remains unresolved?

GNC is read-only over repository content, PR metadata, reviews, policy, and
evidence. Phase 1 supplies only schemas, policy, skill instructions, and a
sanitized offline replay corpus. It performs no network call, subprocess,
repository write, live check, comment, ruleset change, or provider mutation.

Authority descends from target-branch policy and accepted ADRs, through a
human-approved contract and amendments, to exact-head code/evidence, review
claims, and finally model inference. A newer comment does not redefine scope.

Contract rules are typed. `mandatory_invariant` and `fixed_decision` may be
deterministic blockers. `preferred_pattern` is advisory and `example` never
blocks. Model analysis and semantic similarity produce candidates only; they
cannot dismiss, waive, or block without a deterministic rule or human
confirmation.

Operational state is separate from architecture-compound. Compound may supply
read-only landed context and later receive sanitized, human-approved lessons,
but its observation ledger is not GNC authority.

## Evidence and disposition

Evidence is bound to the exact head SHA and target. Only an executed pass for
that binding satisfies a mandatory requirement. Skipped, canceled,
unavailable, `stale_sha`, and `wrong_target` states do not pass.

Findings have stable semantic fingerprints and durable dispositions. Thread
resolution does not resolve the underlying finding. Similarity produces a
duplicate candidate; `duplicate_of` requires a target, while recurrence is a
distinct lifecycle state. Waivers bind an authorized actor, reason, scope,
contract, head, and expiry.

## Trust and human override

PR prose, comments, patches, filenames, test output, and artifacts are
untrusted inputs. Replay fixtures contain sanitized facts and source
references, never secrets, credentials, raw evidence bodies, review
transcripts, patches, or executable payloads. GNC cannot self-approve,
self-waive, alter its policy, write code, or merge. Human override remains
explicit and auditable; GNC is not a ruleset bypass actor.

## Staged delivery

1. Phase 1: specification, schemas, and offline replay.
2. Phase 2: deterministic, non-blocking exact-head advisory.
3. Phase 3: semantic shadow mode with human disposition.
4. Phase 4: limited deterministic enforcement after a ruleset/bypass audit.
5. Phase 5: cross-PR programme governance and sanitized lesson export.

Every phase requires its own current-base issue, exact file allowlist, tests,
rollback, stop conditions, human review, and PR. No phase may infer authority
from this ADR to implement a later phase.

## Consequences

PR scope and evidence can be evaluated deterministically without granting an
agent write authority. The cost is an additional versioned contract and
finding ledger, plus explicit human decisions for amendments, waivers, and
ambiguous semantic findings. Phase 1 has no production or provider effect and
is rolled back by reverting its PR.
