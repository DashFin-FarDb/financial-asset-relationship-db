---
name: unit-test-file-iteration
description: Workflow command scaffold for unit-test-file-iteration in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /unit-test-file-iteration

Use this workflow when working on **unit-test-file-iteration** in `financial-asset-relationship-db`.

## Goal

Iteratively updating, fixing, and auto-formatting a specific unit test file (e.g., tests/unit/test_api.py) in response to code changes, review suggestions, or pre-commit hooks.

## Common Files

- `tests/unit/test_api.py`
- `tests/unit/test_api_main.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit the target unit test file to fix or improve tests.
- Apply code review suggestions from collaborators or bots.
- Run pre-commit hooks or CI auto-fixes to enforce formatting and linting.
- Repeat as needed until tests and formatting are satisfactory.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.
