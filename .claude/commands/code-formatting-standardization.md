---
name: code-formatting-standardization
description: Workflow command scaffold for code-formatting-standardization in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /code-formatting-standardization

Use this workflow when working on **code-formatting-standardization** in `financial-asset-relationship-db`.

## Goal

Apply automated code formatting to maintain consistent code style using tools like Prettier, Black, Autopep8, isort, Ruff Formatter, and StandardJS.

## Common Files

- `frontend/eslint.config.mjs`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Run code formatters (e.g., Prettier, Black, etc.) on relevant files.
- Commit formatted files with a message referencing the tools used and the issue or PR.
- Repeat as needed after significant code changes.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.
