# GNC Phase 3A refusal scope — static clarification candidate

## Authority, identity and task boundary

Programme: [#1817](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1817),
parent [#1557](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1557).
Exact preparation base: `8a606184279f65031698ead26c2b39d9ef8135cf`.
Preparation branch: `codex/gnc-phase3a-refusal-scope-clarification`.

The maintainer approved the proposed distinction and preparation in the working
conversation on 2026-09-06:

> approve the proposed GNC refusal-scope distinction and preparation of the separate two-file static clarification candidate from main 8a606184279f65031698ead26c2b39d9ef8135cf; preserve all accepted files and the runtime checkpoint unchanged; this does not authorize runtime changes, publication, CI spend, acceptance or merge

This records preparation authority, **not exact-head acceptance of this candidate**.
It does not retroactively amend the accepted method or authorize runtime changes.
Publication, CI spend, acceptance and merge remain withheld.

The immutable parent is [the Phase 3A method](gnc-phase-3a-shadow-method.md) at
accepted freeze source head `dc1571c3a6d6f20a4f7fb0d3addb62c525c04cb8`.
Its normalized [contract](gnc-phase-3a-shadow-contract.json) identity remains
`45d08e008b5bb7af1bdefd41051cd5a012f7c3f79d511a799c11c49a92d36fe9`.
The input and expected canonical SHA-256 identities remain respectively
`47f70d04ebf58cc60936488893890b58eb3b5b26890588365b39a7d281096fc6` and
`3d8b79a812e023fad51cf1ebfec8b83384b11a66edcbef6a6e401782f46b9205`.
All five parent files remain byte-identical.

This addendum has a separate raw SHA-256 identity, independently pinned in its
static test. The old contract hash identifies only the old freeze, not this
addendum. Any later acceptance must bind the exact addendum source head and its
raw content hash together with the parent identity. No self-referential head or
hash is fabricated in this document; preparation does not approve a future hash.

Only these two new files are allowed:

1. `docs/governance/gnc-phase-3a-refusal-scope-addendum.md`.
2. `tests/unit/test_gnc_shadow_refusal_scope_contract.py`.

All existing files and all other new paths are forbidden. Named read-only seams
are the parent method, machine contract, both frozen inventories, their static
test and unchanged `scripts/gnc/schema.py` canonicalization/contract validation.
No runtime import, replay, new compound fixture, report or evidence generation
belongs to this static candidate. The runtime checkpoint
`fce67057b0bad08a8e5c2d3902296f0a75670c08` and its failing combined-case assertion
remain unchanged on `codex/gnc-phase3a-runtime`.

## Why this clarification exists

The parent method refuses unauthorized candidates **as requests**, but also
prohibits refusal and lifecycle-success observations from coexisting. Combining
the frozen valid-resolution control with a candidate's unauthorized approval
request exposes the ambiguity: rejecting that request and independently
recognizing the valid resolution satisfy the former wording but fail a literal
global reading of the latter. The original 63 cases do not combine these two
contrasts. Their successful execution does not settle the interpretation.

The proposed distinction prevents a candidate from acquiring either approval
power or veto power. It is not a retrospective claim that the runtime passed,
nor permission to remove its failing assertion before separate authority exists.

## Normative clarification proposed for exact-head acceptance

### Assessment-level refusal

Assessment-level refusal and request-level rejection are distinct. An
assessment-level refusal produces no successful lifecycle adjudication: its
projected states and links are empty and its source history remains preserved.
It yields no successful projected transitions. Preserving original source
records is not adjudicating a successful lifecycle result.

Structural validation, resource bounds, chronology and current-snapshot
eligibility retain their existing fail-closed precedence. Malformed fields,
unknown fields, incomplete context/inventory, invalid history, exceeded limits
and an ineligible snapshot cannot be excused by otherwise valid evidence or by
describing the input as an untrusted request. Policy identity remains a required
boundary; an invalid policy is not made admissible by this clarification.

### Request-level rejection

Within a structurally admissible, current-snapshot-eligible assessment,
`candidate-authority-refused` records rejection only of a syntactically valid
synthetic candidate's request to approve, create a rule, waive or expand scope.
Such a request cannot create, alter, substitute for, or veto authority.

Request-level rejection does not invalidate a separate lifecycle transition
justified entirely by the existing method's applicable authorized records and
required evidence. The rejection diagnostic may coexist with the observation
of that independently justified transition. Removing the rejected candidate
request must not change the projected lifecycle states, links or transitions;
candidate diagnostics and raw candidate counts may differ.

This distinction does not relax structural validation, resource bounds,
chronology, current-snapshot eligibility, exact bindings, evidence requirements
or source/actor checks. Invalid candidate structure still causes the applicable
assessment-level refusal. An unauthorized request alone can never resolve,
waive, approve or otherwise close a finding.

Only the request-level meaning of `candidate-authority-refused` is clarified.
This does not reclassify `authority-unknown`, `waiver-inapplicable`, or any other
failure category. No general rule that all rejected events are harmless follows.
Synthetic source authority remains a declared test assumption, not authentication.

## Contrast matrix and later proof obligations

| Independent records and assessment | Unauthorized candidate request | Required distinction |
| --- | --- | --- |
| Valid resolution with every existing evidence/authority check satisfied | approve / new-rule / waive / expand-scope | Reject request; preserve independently justified resolution |
| No authorized disposition or no required evidence | Any of those four requests | Reject request; finding stays open |
| Executed-pass evidence with wrong head only or wrong target only | Any of those four requests | Reject request; insufficient evidence cannot resolve |
| Valid independent waiver, exact duplicate link or recurrence under existing rules | Any of those four requests | Reject request; neither create nor veto the independently justified result |
| Forged actor/source or inapplicable disposition | Any of those four requests | Preserve existing refusal/applicability rules; no new authority |
| Malformed or unknown fields, incomplete context, over-limit input, invalid history or ineligible snapshot | Any request, even beside otherwise valid resolution records | Refuse assessment; no successful projected states, links or transitions |

This matrix is a prospective specification, not newly executed evidence and not
a replacement for the frozen oracle. A separately authorized runtime candidate
must define new compound contrasts independently of its observed outputs while
retaining every original input/expected definition and all 63 assertions.

Later non-interference checks must compare the same independently justified
baseline with and without each rejected request. States, links and transitions
must agree; diagnostics and counts need not. Positive controls must defeat an
always-refuse implementation. Guard-removal controls must detect both accidental
candidate approval and accidental candidate veto. Separate negative controls
must remove or forge authority/evidence, and combine otherwise valid resolution
with structural failures; no favorable record may bypass assessment refusal.

No new runtime test is executed by this candidate. Any later replacement of the
blanket non-coexistence assertion must be explicitly authorized, explain its
relationship to this accepted distinction and preserve the original failing
checkpoint. Skipping it, marking it expected-failure or silently deleting it is
not a substitute for that governed change.

## Validation, stops and subsequent decisions

Planned local static validation:

```text
python -m pytest tests/unit/test_gnc_shadow_refusal_scope_contract.py tests/unit/test_gnc_shadow_contract.py tests/unit/test_gnc_schema.py tests/unit/test_gnc_advisory.py --confcutdir=tests/unit -q
python -m py_compile tests/unit/test_gnc_shadow_refusal_scope_contract.py
python -m pre_commit run --files docs/governance/gnc-phase-3a-refusal-scope-addendum.md tests/unit/test_gnc_shadow_refusal_scope_contract.py
git diff --check
```

Also perform a scoped security scan, exact two-new-path inventory and raw parent
preservation checks. Record actual results against the local candidate head
separately: these planned commands and static checks are not runtime evidence.
Static text/identity checks detect drift; they do not prove semantic correctness,
adequate coverage or human acceptance. Exact-head review remains mandatory.

Stop for base movement, a third file, changed parent identity, new dependency,
new semantic/authority question or a need to execute/change runtime. Publication
and CI spend require separate authority. This addendum becomes applicable only
after its separate exact-head acceptance and unchanged-head merge; a renewed
bounded runtime brief is still required before resuming runtime changes.
Keep #1817 and #1557 open. Acceptance of this addendum is not runtime acceptance.

## Non-targets and non-claims

No Phase 1/2, GRAC, database, persistence, recovery, operator authority, API,
frontend, dependency, workflow, scanner-setting or production architecture change.
FastAPI plus Next.js remains production; this is a synthetic offline GNC method
clarification. Canonical rebuild/state-machine/operating-authority interpretation
is unchanged. No other project or private research material is imported.

No authentication, security effectiveness, availability/denial-of-service
resistance, general injection resistance, real-world model quality, performance,
savings, operational readiness, integration, enforcement, production use or GRAC
write/replacement authority is established. This is prospective clarification,
not a retrofit of accepted results or proof that a runtime defect is repaired.
