---
name: eslint-config-update
description: Workflow command scaffold for eslint-config-update in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /eslint-config-update

Use this workflow when working on **eslint-config-update** in `financial-asset-relationship-db`.

## Goal

Update, migrate, or fix the ESLint configuration for the frontend, including switching config formats, resolving plugin issues, or fixing lint errors.

## Common Files

- `frontend/eslint.config.mjs`
- `frontend/.eslintrc.json`
- `frontend/.eslintignore`
- `frontend/package.json`
- `frontend/package-lock.json`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit frontend/eslint.config.mjs (sometimes also .eslintrc.json, .eslintignore)
- Update frontend/package.json and/or package-lock.json if dependencies change
- Commit with message referencing ESLint, config, or lint errors

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.