---
name: code-formatting-auto-fix
description: Workflow command scaffold for code-formatting-auto-fix in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /code-formatting-auto-fix

Use this workflow when working on **code-formatting-auto-fix** in `financial-asset-relationship-db`.

## Goal

Automatically formats codebase to conform to style guidelines using tools like Autopep8, Black, isort, Prettier, Ruff Formatter, and StandardJS.

## Common Files

- `tests/integration/test_lock_refresh_flow.py`
- `api/slo_evaluator.py`
- `src/config/settings.py`
- `src/data/repository.py`
- `api/graph_lifecycle_providers.py`
- `src/data/db_models.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Run code formatting tools (Autopep8, Black, isort, Prettier, Ruff Formatter, StandardJS)
- Apply formatting fixes to affected files
- Commit the changes with a standardized commit message

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.
