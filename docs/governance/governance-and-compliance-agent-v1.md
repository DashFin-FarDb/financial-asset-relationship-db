# Governance and Compliance agent v1 contract

This document is normative for GNC Phase 1. It defines offline record
semantics; it does not authorize a workflow, GitHub write, live evaluator,
provider integration, or merge gate.

## 1. Authority and operating boundary

GNC evaluates one exact PR head against one approved contract version. Inputs
are ordered: target policy and accepted ADRs; approved contract; approved
amendments; exact-head code and executed evidence; review claims; model
inference. Lower authority cannot silently amend higher authority.

GNC reads but does not alter code, scope, reviews, checks, settings, rulesets,
or providers. Its state is separate from architecture-compound and any
code-writing agent. A future semantic model receives bounded, redacted input
and no write tools.

## 2. Canonical data and contract versions

Records are JSON-compatible data. Canonical bytes are UTF-8 JSON with keys
sorted, compact separators, and no floating-point values. SHA-256 over those
bytes binds a record independent of source whitespace or mapping insertion
order.

A `ContractVersion` includes its stable ID and version; parent issue;
objective; base and policy SHA; risk; allowed and forbidden paths; typed rules;
required evidence; merge criteria; stop conditions; approving actor and time.
The approval time is a timezone-aware ISO 8601 timestamp. Surrounding
whitespace is removed during normalization; the timestamp text is otherwise
preserved as supplied.
Version 2 or later also binds the previous contract hash and an amendment
rationale. Editing prose does not mutate a frozen version.

The record validator accepts a `contract_version` envelope containing a
`contract`. It normalizes the contract and returns its canonical SHA-256 as
`contract_hash`. The other supported record types are `review_run`, `evidence`,
`finding`, and `waiver`; each record type discriminator must be a string.

Git object identifiers for bases, heads, policies, and analyzed blobs accept
lowercase 40-character SHA-1 or 64-character SHA-256 object IDs. Canonical GNC
hashes, including contract, previous-contract, and context hashes, remain
strictly lowercase 64-character SHA-256 values.

Rule types are:

- `mandatory_invariant`: deterministically blocking when approved;
- `fixed_decision`: deterministically blocking when approved;
- `preferred_pattern`: advisory;
- `example`: non-blocking.

## 3. Review runs and invalidation

A `ReviewRun` binds run ID, head and merge-base SHA, contract and policy hash,
`context_digest`, evaluator version, target, mode, analyzed blob hashes, and
verdict. `context_digest` is the canonical SHA-256 hash of the ordered set of
cross-file inputs relevant to the run: each item contains its repository path
and blob SHA. The validator canonicalizes those repository paths, sorts items
by path, recomputes the digest from `[{"path": ..., "blob_sha": ...}]`, and
rejects a supplied digest that does not match. A cached file verdict is
reusable only when its blob, contract, policy, evaluator, and context digest
are unchanged.

Force-push, rebase, merge-base movement, policy or contract amendment,
evaluator change, truncation, or a high-risk shared-contract change requires a
full review. Whole-PR allowlist, rename/delete, cross-file, evidence, and
unresolved-finding checks always rerun. Only the latest head may receive a
verdict.

## 4. Checklist and evidence

Each checklist requirement has a stable ID, current state, evidence references,
and last evaluated head. `Evidence` binds requirement, head, target, execution
state, result, and run reference. Contract `required_evidence` entries and
`Evidence.requirement_id` use the same lowercase stable-identifier syntax.
Replay review-run entries carry `record_type=review_run`, matching standalone
operational records.
Replay evidence entries carry `record_type=evidence`, matching standalone
operational records.

Within a replay, the run policy must equal the contract policy and every
evidence requirement must be required by that contract. Executed, skipped,
canceled, and unavailable evidence binds the run's exact head and target.
`stale_sha` differs only by head; `wrong_target` differs only by target. The
required evidence `run_ref` identifies its external execution provenance; it is
not the GNC review-run ID. Each evidence `run_ref` must have an exact
`execution:<run_ref>` entry in the replay's frozen `source_refs`. The `run.*`
namespace is reserved for GNC review-run IDs and is invalid for evidence
provenance.

Only `state=executed`, `result=pass`, exact-head, exact-target evidence
satisfies a mandatory item. `skipped`, `canceled`, `unavailable`, `stale_sha`,
and `wrong_target` cannot pass. Structural, SQLite, local, or documentation
evidence cannot satisfy a PostgreSQL, restart, concurrency, hosted, or
behavioral requirement unless the approved contract explicitly says it can.
A replay verdict of `pass` is valid only when every contract
`required_evidence` entry has at least one satisfying evidence record.

## 5. Findings, duplicates, and recurrence

A `Finding` binds rule, stable subject, failure mode, expected outcome, origin,
state, and head. Its fingerprint hashes those stable semantic fields, not
reviewer wording. Lifecycle states are `open`, `resolved`,
`deferred_out_of_scope`, `rejected_speculative`, `duplicate_of`, `waived`, and
`reopened_as_recurrence`.
Replay finding entries carry `record_type=finding`, matching standalone
operational records.

Deduplication first checks exact fingerprints, then may retrieve lexical or
semantic candidates, then requires deterministic structured comparison or
human confirmation. `duplicate_of` requires a target finding. A repeated
failure after resolution is recurrence, not a duplicate. Resolving a GitHub
thread is not proof of remediation.

Model-origin claims, preferred patterns, probable duplicates, speculative
improvements, and architectural alternatives stay advisory until confirmed.
A `human_confirmed` blocking basis binds a non-empty `confirmed_by` actor. A
`deterministic_rule` blocking basis binds `blocking_rule_id`, which must equal
the finding's `rule_id`; the approved contract determines whether that rule is
blocking-eligible. Every replay finding binds the review run's exact head and
an existing contract rule; any blocking basis requires a
`mandatory_invariant` or `fixed_decision`. A basis label without that linkage
is invalid. Linkage fields are mutually exclusive and are invalid without their
matching basis. Out-of-scope findings record a rationale and follow-up issue or
human decision.

## 6. Waivers

A `Waiver` binds waiver and finding IDs, authorized actor, reason, exact scope,
head SHA, contract hash, and expiry. A waiver for another head, contract, scope,
or expired period is invalid. GNC cannot issue, approve, or extend its own
waiver. Waiver validation requires an explicit timezone-aware `as_of` timestamp;
it never depends on the evaluator's wall clock.

## 7. Threat model and sanitization

PR text, comments, diffs, filenames, logs, reports, and artifacts are untrusted
and can contain prompt injection or secrets. A future implementation must bound
inputs, redact secrets, pin policy/model/evaluator versions, reject stale runs,
and never execute PR code with privileged `pull_request_target` or
`workflow_run` credentials.

Phase 1 replay fixtures store sanitized facts and source references only. The
canonical validator in `scripts/gnc/schema.py` case-folds object keys and
rejects these exact names: `credential`, `credentials`, `diff`,
`evidence_body`, `patch`, `password`, `private_key`, `raw_evidence`,
`review_transcript`, `script`, `secret`, and `token`. String values are scanned
case-insensitively for PEM private-key headers and common token prefixes
`github_pat_`, `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `sk_live_`, and
`xox*-`. The schema validator is authoritative so fixture producers cannot
redefine this list or pattern. Fixtures are data, not commands.

## 8. Phase boundaries and merge policy

Phase 1 ends when the schema, canonical hashes, finding fingerprints, evidence
rules, lifecycle constraints, skill, and six historical replay cases validate
deterministically. It does not publish a check or interact with a live PR.

Later phases require new approved contracts. Blocking enforcement additionally
requires measured shadow-mode accuracy, a live ruleset/bypass audit, protected
GNC paths, a last-known-good evaluator for self-changes, and named human review.
No auto-merge is authorized.
