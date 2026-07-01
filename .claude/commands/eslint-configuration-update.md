---
name: eslint-configuration-update
description: Workflow command scaffold for eslint-configuration-update in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /eslint-configuration-update

Use this workflow when working on **eslint-configuration-update** in `financial-asset-relationship-db`.

## Goal

Update or migrate ESLint configuration, including switching config formats, updating config files, and related package changes.

## Common Files

- `frontend/.eslintrc.json`
- `frontend/eslint.config.mjs`
- `frontend/.eslintignore`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/__tests__/config/eslint-upgrade-validation.test.ts`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or replace ESLint configuration files (e.g., .eslintrc.json, eslint.config.mjs).
- Update package.json and package-lock.json to reflect ESLint or related dependency changes.
- Optionally, update .eslintignore or remove obsolete test files related to ESLint.
- Commit changes with a message indicating ESLint config update or migration.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.