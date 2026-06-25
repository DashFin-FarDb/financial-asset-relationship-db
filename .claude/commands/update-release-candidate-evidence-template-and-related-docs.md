---
name: update-release-candidate-evidence-template-and-related-docs
description: Workflow command scaffold for update-release-candidate-evidence-template-and-related-docs in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /update-release-candidate-evidence-template-and-related-docs

Use this workflow when working on **update-release-candidate-evidence-template-and-related-docs** in `financial-asset-relationship-db`.

## Goal

Keeps the release candidate evidence template and associated deployment documentation up to date.

## Common Files

- `.github/ISSUE_TEMPLATE/release_candidate_evidence.md`
- `docs/staging-deployment-operating-baseline.md`
- `docs/release-checklist.md`
- `docs/release-evidence-pack.md`
- `docs/enterprise-deployment-operating-model.md`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit .github/ISSUE_TEMPLATE/release_candidate_evidence.md to reflect new requirements or clarifications.
- Update related documentation files in docs/ (such as staging deployment baselines or release checklists) to stay consistent with the template changes.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.