---
name: python-test-file-edit-workflow
description: Workflow command scaffold for python-test-file-edit-workflow in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /python-test-file-edit-workflow

Use this workflow when working on **python-test-file-edit-workflow** in `financial-asset-relationship-db`.

## Goal

Iterative editing and improvement of a specific Python test file, often for bugfixes, refactoring, or test isolation. Typically involves multiple small commits to the same file in short succession.

## Common Files

- `tests/unit/test_api.py`
- `tests/unit/test_api_main.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit a test file in tests/unit/ (e.g., test_api.py or test_api_main.py)
- Commit with a message referencing the fix, refactor, or improvement
- Optionally, repeat with further small edits (e.g., docstrings, fixture changes, pre-commit fixes)

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.
