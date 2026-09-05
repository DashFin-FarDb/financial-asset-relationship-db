# GNC Phase 3A: offline shadow-boundary and review-memory method

**Candidate, not accepted.** Child [#1817](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1817)
of [#1557](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1557).
Exact base and policy: `165efa4d239737fefad33ca1ecb1db347e6b8414`.
This freezes a proposed method only. It supplies no new evaluator, observation report, model result or live integration.

## Authority and task entry

[Preparation ratification](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1557#issuecomment-5553196960)
was recorded by `mohavro` at `2026-09-05T16:30:22Z`. The existing
[ContractVersion](gnc-phase-3a-shadow-contract.json) requires approving actor and time:
those fields bind this real **preparation** decision, not acceptance of this unwritten-at-ratification contract.
The exact freeze head and normalized contract hash still require separate named-human review and unchanged-head merge.
No preparation field, successful structural test or synthetic source actor grants that acceptance.

Task: prepare the five files in the contract at the exact base, on `codex/gnc-phase3a-freeze`.
All other new paths and every existing file are forbidden. Named read-only seams are the landed
`scripts/gnc/schema.py` canonicalization, ContractVersion, record, finding-fingerprint, evidence and replay
validators; Phase 2 advisory semantics are compatibility references, not an invocation target.
No policy, workflow, provider, dependency, app, database or existing test changes are authorized.
Production remains FastAPI plus Next.js; rebuild, recovery, persistence, lock and operator authority are unchanged.
There is no Supabase/IPv6 dependency and no substitute for the parked database proof.

## The question, and the questions this cannot answer

Can a bounded governance wrapper preserve authority, current-head applicability and unresolved history when supplied
with potentially wrong **fixed hand-authored synthetic** candidates? This is not a study of semantic model usefulness.
It cannot establish precision/recall, general prompt-injection resistance, human authentication, durable storage,
non-equivocation, complete dependency inference, runtime performance, financial savings or operational readiness.

The approach deliberately separates candidate text from structured records. Candidates may invite a human decision;
they may not make it. An exact duplicate link does not resolve its underlying finding. Thread resolution does not
prove a fix. A historical disposition does not acquire current-head applicability through an unchanged filename.
Every later replay must do full assessment: memory links history, never skips current-state checks.
Do not modify accepted Phase 1/2 artifacts to accommodate this experiment.

## Frozen static inventory and identities

There are **63 named cases in 10 question groups**, not 63 representative or independent real reviews.
The separate expected file was authored from these rules and source sequences before any future runtime exists.
Expected lifecycle states and explanations are not embedded in the input corpus. Existing finding
`expected_outcome` is the normative structured fingerprint field, not an oracle label.

- Input: [phase3a-cases.json](../../tests/fixtures/gnc/shadow/phase3a-cases.json),
  canonical SHA-256 `47f70d04ebf58cc60936488893890b58eb3b5b26890588365b39a7d281096fc6`.
- Independent expectation definitions:
  [phase3a-expected.json](../../tests/fixtures/gnc/shadow/phase3a-expected.json),
  canonical SHA-256 `43df6c74d7ebb146ceb734864a764103bcbe9f34175c63e2765626de403fc4f6`.
- Static validation: [test_gnc_shadow_contract.py](../../tests/unit/test_gnc_shadow_contract.py).

Canonical identity means SHA-256 of the landed `canonical_json_bytes` representation, not source whitespace or
platform line endings. The contract hash is SHA-256 of `validate_contract(contract)`, including its normalized
typed rules. This method and both fixture identities are bound by contract rules; the exact freeze commit binds
all five source files. No self-referential commit/hash placeholder is fabricated.

| Question | Explicit contrast families | Critical future guard-removal control |
| --- | --- | --- |
| authority | advisory, self-approval, new rule, waiver request, scope expansion | Promoting candidate requests must break refusal assertions |
| memory | unresolved carry-forward, thread-only, failed/skipped/canceled/unavailable/stale/wrong-target evidence, executed-pass wrong-head-only and wrong-target-only | Removing either exact binding guard must fail its isolated executed-pass contrast against valid resolution |
| resolution | valid, no disposition, no evidence | Always refusing must fail valid resolution; evidence alone cannot close |
| identity | structured exact duplicate, paraphrase, distinct mode, conflict, recurrence | Wording-only collapse must lose a required distinct record and fail |
| waiver | valid, wrong head/contract/scope/finding, expiry, forged actor | Actor-string or stale-binding acceptance must fail; blanket rejection fails valid waiver |
| snapshot | current, superseded head, force-push, rebase, merge-base, contract, policy, evaluator, stale run | Reusing prior assessment must break changed-context assertions |
| context | cross-file change, rename, delete, incomplete inventory, truncation | Filename-only reuse and treating missing inventory as empty must fail |
| input | unknown field, malformed type, four explicit limit probes, inert instruction-like prose | Coercion/truncation/execution or candidate authority must fail |
| history | reordered, duplicated, missing predecessor, divergence, tampered binding/digest, deterministic valid | Skipping sequence/binding/digest checks must fail |
| measurement | complete, empty predictions, empty applicable denominator, abstention, wording variants | Dropping abstentions or counting variants as independent families must fail |

Every concrete case ID, input and expected observation is enumerated in the two JSON files. No contrasts may be
silently dropped, no counts padded to the ceiling, and no oracle changed to match a runtime failure.

## Proposed wire format: data, not an implementation

The input root has exactly `schema_version`, `fixture_kind`, `limits`, `questions`,
`synthetic_policy`, and `cases`. Each case has `case_id`, `question`, and `input`.
The future runtime receives one case input plus the independently hash-checked frozen policy; it never receives
the expected file, expected labels, rationale, or a helper that computes expected decisions.

Each stored fixture input contains explicit `as_of`, ordered `snapshots`, `current_snapshot`, ordered `events`,
`candidates`, `applicable_findings`, and `probe`. The last field belongs only to the fixture adapter:
for every normal and negative-probe case alike, the adapter removes `probe` before the runtime parser sees input.
The runtime wire input therefore has exactly the other six fields and rejects a supplied `probe` as unknown.
No wall-clock, environment, network or repository checkout
is consulted by that future replay. Synthetic object IDs are artificial, not claims of existing Git objects.

Each snapshot explicitly binds `snapshot_id`, `repository`, `target`, `base_sha`, `merge_base_sha`,
`head_sha`, `contract_hash`, `policy_sha`, `evaluator_version`, `analyzed_blobs`,
`context_complete`, `inventory_complete`, `model`, and `prompt`.
Model and prompt are exactly `not-used`. A context digest is derived from the sorted
`[{path, blob_sha}]` mapping using landed canonicalization, never a free-text claim.
Snapshot IDs must be unique and the requested current snapshot must exist.
The last listed snapshot is current; a different selected snapshot is stale and refuses.

Events have `event_id`, integer `sequence`, `predecessor`, `snapshot_id`, `source_class`,
`event_type` and `record`; the only optional event field is `claimed_event_hash`.
Sequence starts at 1, increases by 1, and predecessor is null only at genesis, otherwise the immediately previous
event ID. Source-event identity is SHA-256 of the entire event excluding `claimed_event_hash`.
Any supplied digest must match. IDs must be unique, snapshot references must exist, and events must not move
backward through the supplied snapshot order. No rewriting, deletion, sorting or deduplication of source events
may repair invalid histories. Refusal preserves inspectable original input without deriving an authoritative state.

Finding and evidence records use landed record fields and validation unchanged. A current-view projection may
carry an old unresolved finding forward, but must retain its source head and source event unchanged.
The synthetic rule `synthetic.required` is explicitly mandatory; its one evidence requirement is
`synthetic-check`. The fixed `synthetic_policy` is the experiment's meta-policy, not the preparation contract or
a live repository policy. Snapshot contract/policy hashes are controlled invalidation and applicability inputs:
changing a hash tests whether prior assessment is invalidated and the unchanged experimental rules are reassessed.
It does not supply, evaluate or claim knowledge of unseen changed policy contents. In particular,
`snapshot.contract` and `snapshot.policy` cannot establish correctness under a genuinely different rule set.
Testing genuine policy-semantic changes requires exact policy content and separate scope ratification.

Additional event records:

- `thread`: exactly `finding_id`, boolean `resolved`; origin `synthetic_review_claim`, never remediation.
- `disposition`: exactly `finding_id`, `action` (only resolved here), `actor`, `head_sha`,
  `contract_hash`, `scope`, `evidence_ids`. All bindings must match the current snapshot and finding subject.
- `waiver`: landed Waiver form, explicit `as_of`, exact finding/head/contract/scope and unexpired time.
  Expiry equality is expired, as in landed semantics.
- `finding` and `evidence`: landed Finding and Evidence forms; evidence execution provenance is the
  synthetic `run_ref`, not an external run claimed to exist.

Only `synthetic_authorized_source` with the policy's exact `synthetic-maintainer` actor can represent
a disposition/waiver in this experiment. `synthetic_candidate` and `synthetic_review_claim` cannot.
That source classification is an explicitly supplied test assumption, not a secure real-world authentication design.

Candidates have exactly `candidate_id`, `source_class`, `family_id`, `text`, `proposed_action`,
`finding_id`, boolean `abstains`. Source class is exactly `synthetic_candidate`.
Known proposed actions are advisory, approve, new-rule, waive, expand-scope, duplicate; only advisory is a harmless
request, duplicate needs structured confirmation, and the four authority-changing actions are refused as requests.
All text, including instruction-like text, is inert. No model or command executes it.

All fields use JSON strings, booleans, integers, arrays, objects or null where explicitly permitted; no floats,
coercion, duplicate JSON object keys, unknown keys or ignored extras. Existing sanitization remains authoritative:
no raw patches, logs, transcripts, credentials or executable payloads. Static malformed probes are deliberately
identified cases, not permission for invalid live inputs.

## Resource boundaries and negative probes

Stored files must each fit 256 KiB; at most 64 cases, 8 snapshots and 64 events per case, and 4096 UTF-8 bytes per
permitted text field. Counts use bytes, not characters. No silent truncation.
The stored corpus obeys these bounds. The input's `probe` is normally null. Four negative cases instead specify
exactly `{kind, count}`: events65, snapshots9, text-bytes4097, input-bytes262145.

These are **declarative future boundary probes**, not oversized replay records and not already executed tests.
A separately authorized later test adapter may build exactly those bounded sizes in memory before calling the
runtime parser. It must use unique sequential event/snapshot records, ASCII inert text of the exact byte count,
or legal JSON padded by spaces to the exact input byte size. Test size is verified before invocation.
The production-shaped parser must not accept probe recipes as a runtime bypass; the future test adapter removes
the probe field from every materialized input, including normal cases where it is null. No runtime input requires
or permits that metadata field. The adapter cannot execute arbitrary instructions, repeat without a fixed cap,
make I/O calls, or reinterpret probe failures as pass. Static tests validate the recipes only.

## Decision precedence and required observable result

The later wrapper must emit no lifecycle success after a prior refusal. First validate structural admissibility
and snapshot eligibility (steps 1-4). Then process eligible events strictly in source chronology, applying authority
and evidence checks at each transition. A valid historical resolution is not an early-return result: a later
same-failure event must reopen a recurrence. Finally order current observations as below, with recurrence ahead of
historical resolution; retain historical transitions as provenance rather than treating them as the current state.

1. Encoded byte/resource limits: `input-over-limit`.
2. Known fields/types/canonical values and complete context/inventory: `input-malformed` or `input-incomplete`.
3. Ordered source history, snapshot references, source identity/digest: `history-invalid`.
4. Current snapshot existence/position: `snapshot-inapplicable`.
5. Candidate authority, unknown source authority, waiver applicability: `candidate-authority-refused`,
   `authority-unknown`, `waiver-inapplicable` or `waiver-observed`.
6. Current recurrence after a historically valid resolution: `recurrence-observed` takes priority over
   `resolution-observed`. Both historical resolution and new occurrence remain in the event-transition record.
7. Disposition/evidence applicability: `evidence-unsatisfied`, `remediation-unproven` or `resolution-observed`;
   remaining identity lifecycle includes `exact-link-observed`; distinct failure modes remain
   `distinct-preserved`, conflicting outcomes `conflict-needs-human`, wording-only `duplicate-needs-human`.
8. Changed snapshot/context and removed paths: `path-needs-human` before `changed-context-reassessed`;
   old unresolved source history otherwise yields `unresolved-carried`.
9. Valid remaining inputs: `current-assessed` or `candidate-advisory`; counting cases use `counts-observed`.

The frozen case code names one required **observed contrast**, not a new repository verdict or the entire result.
The future result includes all applicable observation codes, in the above precedence order; the acceptance harness
requires the case's expected code to be present and independently checks projected states and links. It must also
check that no refusal and lifecycle-success observation coexist. The
`history.deterministic` and `snapshot.current` controls explicitly observe full assessment even with a harmless
candidate, while `authority.advisory` observes candidate treatment on the same valid source data. Both observations
must be present for that same input: the runtime does not receive a question or expected-code selector and cannot
alter adjudication by case name. The external harness selects which required observation the case emphasizes.

Expected `states` describe the current view without overwriting source records. `links` preserve exact-duplicate
or recurrence provenance. `source_history=preserve-all` applies even on refusal. `assessment=full` means no
verdict reuse; it does not mean pass or all findings resolved. `assessment=refused` produces empty projected
states, while retaining original input and its identity for inspection.

A future canonical case result must include case/input/policy identities, selected current snapshot identity,
canonical context and ordered event identities, observation codes, projected states and links, raw counts and
refusal/abstention diagnostics. No timestamps or nondeterministic timings enter these canonical bytes.
All source IDs remain accounted for. Repeated evaluation of identical input and policy yields byte-identical bytes;
canonical object-key order is irrelevant, but ordered event sequence is significant.

## Oracle separation, sensitivity and measurements

Static tests check specification structure, bounds, identities, case-to-question coverage and unchanged primitive
compatibility. They do **not** evaluate the future wrapper or prove its 63 expected outcomes.
Expected states were reasoned from authority, temporal ordering and applicability rules, not inferred from test code.
A later independent reviewer must challenge both fixtures and rationale before freeze acceptance.

Future runtime acceptance needs all frozen assertions, independently checked oracle identities and byte determinism.
Removing the expected file or altering it must fail the acceptance harness, while leaving runtime decisions unchanged:
the runtime must neither read nor depend on that file. Altered input/policy identities must make the runtime refuse
before output. Guard-removal tests for the ten rows above must actually fail the relevant assertions; a blanket
refusal implementation must fail valid resolution, waiver and duplicate controls. Static success is not this proof.

Counts preserve candidates (including abstentions), applicable finding opportunities, abstentions and distinct
wording families. Wording variants may raise candidate count, not independent family count. Empty applicable
denominator is undefined, encoded as null for any derived rate, never 0% or100%. Hand-authored applicable IDs are
frozen experimental labels, not independently measured recall opportunities. No accuracy percentage is an acceptance
criterion here; timing, model costs and savings are not measured. Full reassessment is intentionally unoptimized.

Any later model study requires a new proposal: provider/model/prompt identities; privacy and permitted inputs;
independent labels and held-out families; ambiguous-category and missed-finding measurements; denominators,
uncertainty and human review burden; explicit token/spend/retry caps and acceptance thresholds before sampling.
This freeze ratifies none of those choices.

## Validation, stop and next acceptance

Actually run and record focused static tests, compile validation, unchanged Phase 1/2 compatibility tests,
exact-file pre-commit and scoped security checks; verify only the five new files differ from exact base.
Use existing tooling. No dependency installation, whole-application workload, provider probe, CI dispatch or push
is authorized by local preparation. Publication cost authority is separate; ordinary CI is not represented as free.

Stop for base movement, sixth file, changed primitive/authority, external/private inputs, model/provider choice,
new dependency, contradictory review, or oracle answers that require runtime results.
No change to accepted observations is authorized to improve apparent results.
Before acceptance this candidate can be withdrawn; a later rollback is a separately reviewed static-only revert.

Return exact freeze head, canonical contract hash, actual checks and unresolved findings for named-human review.
Only separate exact-head freeze acceptance and unchanged-head merge can open a separately bounded runtime candidate.
Its eventual evidence acceptance and documentation closeout remain distinct decisions.
Parent Phase 3 remains incomplete. There is no enforcement, automatic disposition, merge, promotion or operational
authority here.

References: [ADR0011](../adr/0011-governance-and-compliance-agent.md),
[GNC v1](governance-and-compliance-agent-v1.md),
[Phase2](gnc-phase-2-deterministic-advisory.md),
[task entry](../agent-task-entry.md), [high-risk guardrails](../HIGH_RISK_CHANGE_GUARDRAILS.md).
