# Mergify Automation

This document describes the Mergify configuration in `.mergify.yml` and how it
automates pull-request workflows in this repository.

---

## Overview

[Mergify](https://mergify.com) is a GitHub-native automation service that acts on
pull requests based on declarative rules. The configuration in `.mergify.yml` covers
five areas:

1. **PR size labels** — automatically tag every PR with a t-shirt size so reviewers
   can gauge review effort at a glance.
2. **Content labels** — tag PRs that touch security tooling, CI, documentation, or
   dependency files.
3. **Review automation** — request reviews from the right people and dismiss stale
   approvals when new commits arrive.
4. **Auto-merge** — merge patch updates from trusted bots (Dependabot, Snyk) after
   CI passes, without requiring manual approval.
5. **Stale PR management** — flag PRs that have been inactive for 14 days and
   automatically un-flag them when activity resumes.

---

## PR Size Labels

Every PR is labelled with a t-shirt size based on the total number of modified lines
(additions + deletions). Labels are **toggled** so they update automatically if a PR
grows or shrinks between tiers during review.

| Label      | Condition             | Typical scope                          |
| ---------- | --------------------- | -------------------------------------- |
| `size/XS`  | `< 10` modified lines | Single-line fix, typo, comment         |
| `size/S`   | `10 – 49` lines       | Small bug fix, minor feature tweak     |
| `size/M`   | `50 – 99` lines       | Medium feature or refactor             |
| `size/L`   | `100 – 499` lines     | Large feature or multi-file change     |
| `size/XL`  | `500 – 999` lines     | Major feature or significant refactor  |
| `size/XXL` | `>= 1000` lines       | Large-scale change; consider splitting |

> **Tip:** Aim to keep PRs at `size/M` or smaller to reduce review latency.

---

## Content Labels

In addition to size labels, PRs are tagged based on which files they modify.
Unlike size labels, content labels use `add` (they are not removed when files change).

| Label           | Triggered by                                                     |
| --------------- | ---------------------------------------------------------------- |
| `security`      | Snyk/Bandit/CodeQL/Semgrep workflow files, `.safety-policy.json` |
| `ci`            | Any file under `.github/workflows/`                              |
| `documentation` | Files matching `**/*.md` or under `docs/`                        |
| `dependencies`  | `requirements*.txt`, `pyproject.toml`, `frontend/package.json`   |

A single PR can receive multiple content labels (e.g., a PR that updates a workflow
and its documentation gets both `ci` and `documentation`).

---

## Review Automation

### Request review from maintainer

When a non-draft PR is opened or moved out of draft by a non-bot author **and no
reviewer has been assigned yet**, Mergify automatically requests a review from
`@mohavro`.

Conditions that suppress the request:

- PR is in draft state
- Author is `dependabot[bot]` or `snyk-bot`
- At least one reviewer is already assigned

### Dismiss stale reviews on new commits

When new commits are pushed to a PR targeting `main`, any existing approvals are
automatically dismissed. This ensures that reviewers explicitly re-approve after
seeing the latest changes.

---

## Auto-merge

Auto-merge rules are intentionally narrow to prevent accidental merges.

### Dependabot patch updates

Automatically squash-merged when **all** of the following are true:

- Author is `dependabot[bot]`
- PR has the `dependencies` label
- No more than 5 files are changed
- CI check `Test Python 3.12` is passing

### Snyk security fixes

Automatically squash-merged when **all** of the following are true:

- Author is `snyk-bot`
- PR has the `security` label
- CI check `Test Python 3.12` is passing

> **Safety note:** Both auto-merge rules require a passing CI run. A failing
> `Test Python 3.12` job blocks the merge regardless of the author or labels.

---

## Stale PR Management

### Mark stale (14-day threshold)

A PR is marked `stale` when:

- It is not a draft
- It is not already closed
- It has had no activity for **14 days**

When marked stale, Mergify:

1. Adds the `stale` label.
2. Posts a comment explaining the status and how to keep the PR open.

### Remove stale label

The `stale` label is automatically removed when the PR receives any activity
(new commit, comment, label change) within the following day.

---

## Adding New Rules

To add a new rule to `.mergify.yml`:

1. Open `.mergify.yml` in the repository root.
2. Add a new entry to the `pull_request_rules` list with `name`, `conditions`,
   and `actions` keys.
3. Follow the existing naming conventions:
   - Size rules: `"T-shirt size: <SIZE> (<range>)"`
   - Content rules: `"Label <category> changes"`
   - Auto-merge rules: `"Auto-merge <bot> <type> updates"`
4. Run the validation tests locally before pushing:

   ```bash
   python3 -c "import yaml; yaml.safe_load(open('.mergify.yml'))"
   pytest tests/unit/test_mergify_config.py -v
   pytest tests/integration/test_mergify_workflow.py -v
   ```

5. Open a PR to `main`. Mergify will validate the new config automatically on
   push via the [Mergify config checker](https://docs.mergify.com/configuration/file-format/).
