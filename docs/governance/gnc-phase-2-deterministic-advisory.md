# GNC Phase 2 deterministic advisory

**Authority:** issue #1739, ratified 2026-08-27 at base
`9cbb4493cc5f1701c6c7789c9cc076fba57d82ca`
**Phase 1 prerequisite:** issue #1558 and merged PR #1673
**Status:** implementation contract; live completion still requires the controlled-draft proof described below

## Purpose and authority boundary

Phase 2 adds one deterministic answer for each supported pull-request event targeting `main`:

> What did this PR promise, what did its exact head change and prove, and what deterministic gaps remain?

The answer is an Actions job summary plus one normalized artifact. `pass`, `block`, and `needs-human` are report
states only. The workflow is not a required check and cannot approve, waive, review, comment, label, resolve, merge,
commit, deploy, or alter a repository or provider setting.

This phase does not add semantic/model review, enforcement, programme governance, a dependency, a database, or a
provider integration. It does not change GRAC, application runtime, staging, Supabase, IPv6, Vercel, Sentry,
Grafana, Alloy, Prometheus, rulesets, branch protection, bypass, or auto-merge behavior.

## Contract enrollment

Every PR targeting `main` is evaluated. Its body must contain exactly one JSON object between these exact markers:

```text
<!-- gnc-contract:start -->
{ ... one Phase 1 ContractVersion JSON object ... }
<!-- gnc-contract:end -->
```

The object is normalized by the landed Phase 1 `validate_contract` function and hashed with its canonical SHA-256
function. The `base_sha` binds the merge base. The `policy_sha` binds the exact target commit from which the trusted
schema and evaluator are loaded. The allowlist is both the maximum and expected changed scope: every changed path
must fall under an allowed component, and every allowed component must appear in the complete changed-path inventory.
Renames bind both the old and new path; removals remain part of the inventory.

Missing, duplicated, malformed, oversized, unapproved, edited, stale, or mismatched input returns `needs-human` and
never a pass. Contract amendments increment `version`, include the Phase 1 lineage fields, and receive a new approval;
editing a PR body does not reuse an old approval.

## Human approval record

Approval is a new top-level comment on the contract's `parent_issue`, authored by `mohavro`. The comment is exact,
contains no prose or code fence, and uses this form:

```text
<!-- gnc-approval:v1 -->
{"actor":"mohavro","contract_hash":"<canonical-sha256>","contract_version":<integer>,"head_sha":"<exact-pr-head>","policy_sha":"<exact-policy-sha>"}
```

The evaluator accepts exactly one matching record and requires the GitHub comment author to equal `actor`, the actor
to be authorized, and `created_at` to equal `updated_at`. The contract's own `approved_by` field is schema data, not
approval proof. An amendment or force-push uses a new comment; the earlier comment remains immutable audit history.

## Trusted execution and metadata

The workflow uses `pull_request_target` for `opened`, `reopened`, `edited`, `synchronize`, and `ready_for_review`. It
checks out only `github.event.pull_request.base.sha`, with persisted credentials disabled, and executes only the
evaluator present at that trusted SHA. It never checks out, imports, sources, or executes the PR head.

Permissions are explicit reads for Actions, checks, contents, issues, pull requests, and statuses. The automatically
issued read-only `github.token` is used only for bounded GitHub metadata calls; there is no repository secret input.
Forks follow the same path and receive no PR-head execution or secret access.

The adapter may read only:

- the triggering event and current/final PR identity;
- complete paginated changed-file metadata, without patches;
- the merge base and existence of the landed Phase 1 schema at the exact policy SHA;
- top-level parent-issue comments needed for approval proof;
- review state and unresolved-thread metadata, without review bodies;
- exact-head check-run, commit-status, Actions-run, and named-review metadata.

It never reads a raw patch, review transcript, log body, artifact body, executable PR content, or external provider.
All pages must be proven complete. API, identity, pagination, rate-limit, bound, or shape ambiguity fails safely to
`needs-human`.

## Deterministic evaluation

Evaluation order is contract and bounds, exact refs, approval, changed paths, required evidence, and review metadata.
The final state has fail-safe precedence:

1. any `needs-human` finding produces `needs-human`;
2. otherwise any deterministic blocker produces `block`;
3. otherwise the result is `pass` (possibly with advisory-only observations).

Required-evidence identifiers match a stable lowercase identifier derived from a GitHub check, status, or Actions run
name. `named-human-review` is supplied only by an exact-head review from `mohavro`. Success/neutral is passing;
failure/error is blocking; pending, skipped, cancelled, unavailable, stale-head, wrong-target, unknown state, missing
evidence, and an unapproved evidence source need human attention.

An unresolved thread attached to a `CHANGES_REQUESTED` review is a deterministic blocker. Other unresolved,
non-outdated threads are advisory-only observations. Raw thread content is never ingested. The evaluator re-fetches PR
identity after all other metadata and suppresses a result if the head, target SHA, or target changed. PR-scoped
concurrency cancels superseded runs.

The normalized artifact is canonical JSON with no timestamp or run-specific field, so the same snapshot emits
byte-identical output. Findings and evidence are sorted. Secret-like values, control characters, workflow-command
sequences, forbidden fields, and overlong text are sanitized before output.

## Fixed bounds

| Input or output | Bound |
| --- | ---: |
| PR body | 128 KiB |
| Extracted contract JSON | 64 KiB |
| Changed-file records | 500 |
| One normalized path | 512 UTF-8 bytes |
| Aggregate normalized path data | 256 KiB |
| Reviews plus review threads | 1,000 records |
| Check, status, Actions, and normalized evidence records | 1,000 records |
| Human-readable job summary | 64 KiB |
| Normalized artifact | 1 MiB |
| Artifact retention | 30 days |

An exceeded or truncated bound produces a sanitized `needs-human` result. A trusted runtime failure remains a visible
failed workflow when no bounded artifact can be produced; it is never converted into a passing advisory.

## Validation and merge evidence

The implementation PR must contain only the seven paths in
[`gnc-phase-2-contract.json`](gnc-phase-2-contract.json). Before merge, record at the final exact head:

- focused Phase 1 and Phase 2 tests;
- Python compile validation;
- exact-file pre-commit results;
- static workflow event, permission, pinning, checkout, secret, and output assertions;
- secret/security scanning and all exact-head repository checks;
- resolution or explicit disposition of every substantive review thread;
- one new immutable approval comment on issue #1739; and
- a separate explicit maintainer merge decision with auto-merge disabled.

## Post-merge controlled-draft proof

Issue #1739 remains open after the implementation merge. Create one harmless controlled draft PR targeting `main`
with a minimal approved contract and no provider/runtime effect. At exact draft head, verify:

1. a supported event starts the workflow using the exact base evaluator;
2. the job and artifact report the latest head, canonical contract, approval, refs, paths, and evidence consistently;
3. rerunning an identical snapshot yields byte-identical normalized JSON;
4. a superseded head is cancelled or reports stale and never publishes a current pass;
5. the check remains non-required and creates no comment, review, label, commit, merge, deployment, settings, or
   provider mutation; and
6. cleanup/closure of the controlled draft is a separate human action recorded on #1739.

Only after that exact-SHA evidence is recorded may #1739 and the Phase 2 line in parent issue #1557 be marked complete.

## Rollback

Revert the Phase 2 merge commit, or disable/remove only `.github/workflows/gnc-advisory.yml` through a separately
reviewed rollback PR. No provider, database, secret, deployment, ruleset, or external-state rollback is part of this
phase because Phase 2 has no authority to alter those surfaces.
