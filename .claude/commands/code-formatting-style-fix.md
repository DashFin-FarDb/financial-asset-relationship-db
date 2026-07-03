---
name: code-formatting-style-fix
description: Workflow command scaffold for code-formatting-style-fix in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /code-formatting-style-fix

Use this workflow when working on **code-formatting-style-fix** in `financial-asset-relationship-db`.

## Goal

Apply code formatting and style fixes across one or more files using automated formatters (Autopep8, Black, isort, Prettier, Ruff Formatter, StandardJS).

## Common Files

- `frontend/eslint.config.mjs`
- `docs/ci-required-checks-policy.md`
- `docs/enterprise-readiness-index.md`
- `docs/roadmap/enterprise-readiness-pr-board.md`
- `docs/roadmap/enterprise-readiness-pr-plan.md`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Run code formatters on affected files
- Commit with message starting with 'style: format code with ...'
- Touch files in frontend, docs, or other directories

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.