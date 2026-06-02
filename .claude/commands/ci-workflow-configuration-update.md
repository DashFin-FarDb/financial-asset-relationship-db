---
name: ci-workflow-configuration-update
description: Workflow command scaffold for ci-workflow-configuration-update in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /ci-workflow-configuration-update

Use this workflow when working on **ci-workflow-configuration-update** in `financial-asset-relationship-db`.

## Goal

Updating, fixing, or adding CI workflow YAML files for automation, security scans, or labeling. Often involves .github/workflows/\*.yml and related config files.

## Common Files

- `.github/workflows/snyk-security.yml`
- `.github/workflows/zscaler-iac-scan.yml`
- `.github/workflows/snyk-container.yml`
- `.github/workflows/snyk-infrastructure.yml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or add one or more YAML files under .github/workflows/ or .github/
- Commit with a message referencing the workflow or config change
- Optionally, repeat to fix syntax, add conditions, or handle errors

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.
