# PR Scope Guardrails

This document exists to reduce review churn, agent drift, and accidental scope expansion.

## Default rule

One PR should carry one primary decision.

Examples:
- dependency alignment
- validator follow-up
- framework upgrade
- lint/style cleanup
- documentation-only update

A PR may touch several files, but those files should support the same decision.

## Scope classes

### 1. Dependency alignment
Purpose:
- make dependency files agree with an already-chosen model

Typical files:
- `requirements.txt`
- `requirements-dev.txt`
- `pyproject.toml`
- `.github/workflows/dependency-check.yml`
- `tests/integration/test_requirements*.py`
- relevant docs

Not in scope:
- framework upgrades
- unrelated lint cleanup
- unrelated refactors

### 2. Validator / workflow follow-up
Purpose:
- make tests and CI reflect an already-decided policy

Typical files:
- `.github/workflows/*`
- `tests/integration/*`
- docs describing install or validation paths

Not in scope:
- changing the dependency model itself unless the PR explicitly says so

### 3. Framework or security upgrade
Purpose:
- intentionally change a major or security-sensitive package version

Typical files:
- `requirements.txt`
- `pyproject.toml`
- code, tests, and docs needed to prove compatibility

Not in scope:
- opportunistic cleanup of unrelated validators unless required for the upgrade

### 4. Cleanup-only PR
Purpose:
- formatting, comments, docs, or minor refactors with no policy change

Not in scope:
- dependency policy changes
- validator semantics changes

## Size guidance

These are guardrails, not hard limits.

### Preferred
- fewer than 8 changed files
- fewer than 300 lines of effective logic change
- one reviewable concern per PR

### Caution zone
- 8 to 15 files changed
- mixed code + policy + validator changes
- PR description longer than the actual code rationale

### Stop and split
Split the PR if any of the following become true:
- the PR changes both a dependency decision and a framework version decision
- the PR changes source files and also rewrites multiple validators to make the change pass
- the PR description needs a long "also" section
- reviewers are arguing about what the PR is actually supposed to do

## Anti-drift rules for AI-assisted changes

Before changing files, restate the intended model in plain language.

For dependency work, the model must answer:
- what file is authoritative?
- which files mirror it?
- which files validate it?

If that cannot be answered in three sentences, the change is not ready.

### AI agent rules
- do not let the newest review comment replace the source-of-truth policy
- do not broaden scope to "fix nearby issues" unless explicitly instructed
- if a validator disagrees with the documented policy, prefer fixing the validator
- if a PR needs a second architectural decision, stop and open a follow-up PR instead

## Required PR description sections

Every non-trivial PR should state:
- what decision this PR makes
- what it explicitly does not do
- why the touched files belong in the same PR
- what commands were run locally

## Reviewer checklist

Reviewers should ask:
- is this one decision or several?
- are any files only present because the scope drifted?
- is the PR solving the root issue or only the current failing validator?
- does the PR description overstate what has been proven?

If the answer is unclear, request a split before merge.
