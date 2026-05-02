---
name: script-feature-update-and-test-sync
description: Workflow command scaffold for script-feature-update-and-test-sync in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /script-feature-update-and-test-sync

Use this workflow when working on **script-feature-update-and-test-sync** in `financial-asset-relationship-db`.

## Goal

Implements or updates a Python script in scripts/, and synchronously adds or updates corresponding unit tests in tests/unit/ to ensure coverage and correctness.

## Common Files

- `scripts/check_hosted_readiness.py`
- `tests/unit/test_check_hosted_readiness.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or add feature to scripts/check_hosted_readiness.py
- Add or update tests in tests/unit/test_check_hosted_readiness.py to cover the new or changed logic
- Commit both script and test changes together

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.
