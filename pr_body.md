## Architectural Alignment

<!-- Describe how this PR aligns with the production architecture. -->

- Backend: FastAPI (production path)
- Frontend: Next.js (production path)
- Gradio: non-production (demo/testing only)

No runtime architecture behavior is changed; this is a repository-state correction.

## Primary Objective

Remove the accidental gitlink at `financial-asset-relationship-db` so checkout/cleanup operations no longer carry submodule-like index state.

## Scope

### In Scope

- Delete the tracked gitlink entry (`mode 160000`) for `financial-asset-relationship-db`
- Normalize repository tree/index state to a standard single-repo layout
- Keep all runtime code and API/frontend behavior unchanged

### Out of Scope

- Any backend or frontend functional changes
- Dependency, CI workflow, or infrastructure refactors
- Test-suite refactoring or behavior updates

### Files Expected to Change

- `financial-asset-relationship-db` (gitlink entry removed from index/tree)
- No source files under `api/`, `src/`, or `frontend/`
- No docs/policy/template files

## Validation Commands

```bash
git ls-files --stage | awk '$1==160000 {print}'
git status --short
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective
- [ ] Validation commands pass locally or in CI
- [x] Changes align with production architecture (FastAPI + Next.js)

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only (see Primary Objective)
- [x] I have explicitly listed what is out of scope
- [x] If this is a docs/policy/architecture-only PR, I have not mixed those changes with unrelated code changes
- [x] If this is a docs/policy/architecture-only PR, no runtime behavior changes are included
- [x] I have verified the branch, base branch, and referenced PR/commit/ref context before concluding merge status or PR necessity
- [x] I have checked this PR against the production architecture (`FastAPI` backend + `Next.js` frontend)
- [x] I have checked this PR against `.github/AUTOMATION_SCOPE_POLICY.md`

### Testing Best Practices

- [x] Tests verify observable behavior (events, state changes, return values) rather than coupling to implementation details
- [x] Tests avoid coupling to exact log message strings (verify log level instead of message text)
- [x] Tests use polling loops with `time.monotonic()` deadlines instead of fixed `time.sleep()` for timing-dependent assertions
- [x] Tests properly clean up resources (database connections, threads, temp files) in finally blocks

---

**Related Documentation**:

- [PR Scope Guardrails](../docs/PR_SCOPE_GUARDRAILS.md)
- [Automation Scope Policy](./AUTOMATION_SCOPE_POLICY.md)
