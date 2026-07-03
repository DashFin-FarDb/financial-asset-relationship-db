---
name: ci-workflow-update-and-fix
description: Workflow command scaffold for ci-workflow-update-and-fix in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /ci-workflow-update-and-fix

Use this workflow when working on **ci-workflow-update-and-fix** in `financial-asset-relationship-db`.

## Goal

Update or fix CI/CD workflow YAML files, often in response to PR feedback, security scanner findings, or broken pipelines.

## Common Files

- `.github/workflows/frontend-ci.yml`
- `.github/workflows/release-evidence-verify.yml`
- `.github/workflows/staging-promotion.yml`
- `.github/workflows/production-container.yml`
- `.github/workflows/bandit.yml`
- `.github/workflows/codeql.yml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit one or more files in .github/workflows/ (e.g., frontend-ci.yml, release-evidence-verify.yml, staging-promotion.yml, production-container.yml, etc.)
- Commit with a message referencing fixes, PR feedback, or security findings
- Sometimes co-authored by bots or with 'Potential fix' in the message

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.