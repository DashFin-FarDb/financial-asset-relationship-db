# Lesson Note: Automation Scope Drift Recovery

## Purpose

This note captures both sides of a recent repository incident:

1. the **bad lesson** — how automation and partial edits can corrupt repository documents
2. the **good lesson** — how to recover safely without compounding damage

It is intended to become reusable knowledge for contributors, reviewers, agents, and scanners.

## Incident Summary

During PR #1023, a documentation branch intended to establish production architecture and control-plane guardrails experienced two related failures:

- a bad commit replaced `README.md` with a placeholder string
- a follow-up automated formatting step then operated on the already-broken file instead of recognizing the invalid intermediate state

A similar risk later appeared in `ARCHITECTURE.md`, where a partial documentation edit left the file truncated.

## The Bad Lesson

### Failure Pattern

This is the failure pattern the repository now needs to actively prevent:

1. a file enters an invalid intermediate state
2. an automated tool reacts only to the local state of the file
3. the tool applies formatting or consistency edits without contextual understanding
4. the active PR is widened or damaged further

### Why This Is Dangerous

This failure mode is especially dangerous because it can appear superficially helpful:

- formatting still runs
- linting still runs
- bot activity looks productive
- review threads get noisier while the actual document gets less trustworthy

The result is compounded corruption, not recovery.

### Repository Interpretation

This is exactly what `/.github/AUTOMATION_SCOPE_POLICY.md` is meant to prevent.

The core rule remains:

**Automation may review scope, but it may not redefine scope.**

When a file enters an invalid state, the correct action is escalation, not automatic widening.

## The Good Lesson

### Correct Recovery Pattern

The correct recovery approach is:

1. identify the damaged file precisely
2. determine whether the file is safe for incremental patching
3. if the file is not safe, restore the full file from a known-good source
4. re-apply only the intended, scoped edits
5. validate that the restored file is complete and structurally coherent

### What “Safe Recovery” Looks Like

#### Case 1: README corruption

`README.md` was not incrementally patched from the corrupted placeholder state.

Instead, it was restored from a known-good commit and then re-checked. This avoided layering more automated changes on top of an already-invalid file.

#### Case 2: ARCHITECTURE.md truncation

`ARCHITECTURE.md` was recognized as unsafe to patch in place because the file was already truncated.

The correct recovery was:

- restore the complete file from `main`
- re-apply only the PR-1-safe changes:
  - production-path declaration
  - Python runtime alignment
  - architectural flow clarification showing:
    - `Next.js → FastAPI → Core Logic`
    - `Gradio → Core Logic (direct)`

This is the preferred pattern for damaged structural docs.

## Recovery Decision Rule

Use this rule before editing a possibly damaged file:

### Incremental patching is acceptable when:

- the file is complete
- the file is internally coherent
- the change is local and bounded
- there is no sign of truncation, placeholder overwrite, or structural loss

### Full restore is required when:

- the file has been truncated
- placeholder text replaced real content
- prior automation acted on an already-invalid state
- you cannot trust the surrounding context enough to patch safely

## Repository Policy Implications

This incident reinforces several repository rules:

### 1. Active PRs are bounded units of intent

A docs PR must not turn into a repair playground for unrelated formatting or scanner behavior.

### 2. Control-plane documents deserve extra caution

Files such as:

- `README.md`
- `ARCHITECTURE.md`
- `DEPLOYMENT.md`
- ADRs
- PR templates
- automation policy files

should be treated as structural assets. Partial corruption in these files is more harmful than a normal typo.

### 3. Broken intermediate state should trigger escalation

When automation detects anomalies, the preferred actions are:

- comment
- open a separate narrow follow-up PR
- open an issue

not silent mutation of the active branch.

## Preferred Maintainer Response

When this class of incident occurs, maintainers should:

1. stop further automated widening of the PR if possible
2. identify the first bad commit or bad file state
3. restore from a known-good source
4. re-apply intended changes in one controlled pass
5. capture the lesson in repository knowledge so the same failure pattern becomes less likely

## Short Version

### Bad lesson

Do not let automation keep editing a broken file just because the diff is still technically editable.

### Good lesson

When a structural document is damaged, restore first, then re-apply scoped intent.

## Related Documents

- [Automation Scope Policy](../../.github/AUTOMATION_SCOPE_POLICY.md)
- [Repository Control Plane](../REPOSITORY_CONTROL_PLANE.md)
- [PR Scope Guardrails](../PR_SCOPE_GUARDRAILS.md)
- [ADR 0001: Production Architecture](../adr/0001-production-architecture.md)
