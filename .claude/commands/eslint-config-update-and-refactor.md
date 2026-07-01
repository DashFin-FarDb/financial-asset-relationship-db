---
name: eslint-config-update-and-refactor
description: Workflow command scaffold for eslint-config-update-and-refactor in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /eslint-config-update-and-refactor

Use this workflow when working on **eslint-config-update-and-refactor** in `financial-asset-relationship-db`.

## Goal

Update or refactor ESLint configuration, including migration to new config formats, adding/removing compatibility layers, and updating related package dependencies.

## Common Files

- `frontend/.eslintrc.json`
- `frontend/.eslintignore`
- `frontend/eslint.config.mjs`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/__tests__/config/eslint-upgrade-validation.test.ts`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or replace frontend/.eslintrc.json and/or frontend/.eslintignore
- Add or modify frontend/eslint.config.mjs
- Update frontend/package.json and frontend/package-lock.json to reflect new ESLint dependencies
- Optionally remove or add compatibility layers (e.g., FlatCompat)
- Remove or update related test files if necessary

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.