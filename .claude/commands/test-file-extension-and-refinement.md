---
name: test-file-extension-and-refinement
description: Workflow command scaffold for test-file-extension-and-refinement in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /test-file-extension-and-refinement

Use this workflow when working on **test-file-extension-and-refinement** in `financial-asset-relationship-db`.

## Goal

Adds or refines tests in an existing test file to improve coverage, clarify assertions, or match updated logic, without changing the main script.

## Common Files

- `tests/unit/test_check_hosted_readiness.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit tests/unit/test_check_hosted_readiness.py to add new test cases or clarify existing ones
- Commit only the test file changes

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.