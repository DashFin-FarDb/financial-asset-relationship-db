## Architectural Alignment

<!-- Describe how this PR aligns with the production architecture. -->

- Backend: FastAPI (production path)
- Frontend: Next.js (production path)
- Gradio: non-production (demo/testing only)

<!-- Confirm that no changes contradict the defined production architecture. -->

## Primary Objective

<!-- State the single primary objective or scope decision this PR makes. -->
<!-- This section must be completed in line with .github/AUTOMATION_SCOPE_POLICY.md. -->

## Scope

### In Scope

<!-- List what this PR does. Be specific and comprehensive. -->

-
-
-

### Out of Scope

<!-- List what this PR explicitly does NOT do. This prevents scope creep and clarifies boundaries. -->

-
-
-

### Files Expected to Change

<!-- List all files you expect to modify and explain why they belong in the same PR -->

-
-
-

## Validation Commands

<!-- List the specific commands to verify these changes -->

```bash
# Add validation commands here
```

## Merge Criteria

- [ ] Scope is tightly aligned to the Primary Objective
- [ ] Validation commands pass locally or in CI
- [ ] Changes align with production architecture (FastAPI + Next.js)

## Checklist

### Scope Compliance

- [ ] This PR makes one primary decision only (see Primary Objective)
- [ ] I have explicitly listed what is out of scope
- [ ] If this is a docs/policy/architecture-only PR, I have not mixed those changes with unrelated code changes
- [ ] If this is a docs/policy/architecture-only PR, no runtime behavior changes are included
- [ ] I have verified the branch, base branch, and referenced PR/commit/ref context before concluding merge status or PR necessity
- [ ] I have checked this PR against the production architecture (`FastAPI` backend + `Next.js` frontend)
- [ ] I have checked this PR against `.github/AUTOMATION_SCOPE_POLICY.md`

---

**Related Documentation**:

- [PR Scope Guardrails](docs/PR_SCOPE_GUARDRAILS.md)
- [Automation Scope Policy](.github/AUTOMATION_SCOPE_POLICY.md)
