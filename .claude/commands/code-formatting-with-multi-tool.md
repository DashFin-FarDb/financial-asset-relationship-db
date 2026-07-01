---
name: code-formatting-with-multi-tool
description: Workflow command scaffold for code-formatting-with-multi-tool in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /code-formatting-with-multi-tool

Use this workflow when working on **code-formatting-with-multi-tool** in `financial-asset-relationship-db`.

## Goal

Apply code formatting across the codebase using multiple formatters (Autopep8, Black, isort, Prettier, Ruff Formatter, StandardJS) to enforce style consistency.

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
- Commit changes to files with style fixes

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.