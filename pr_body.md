## Architectural Alignment

<!-- Describe how this PR aligns with the production architecture. -->

- Backend: FastAPI (production path)
- Frontend: Next.js (production path)
- Gradio: non-production (demo/testing only)

This PR strictly aligns with the Next.js frontend production path.

## Primary Objective

Update frontend components and tests to align with the backend pagination and metrics refactor. Closes #1274

## Scope

### In Scope

- Fix mocked metrics shapes in test utilities
- Refactor test assertions for synchronous and async component behavior
- Match test cases to the updated paginated fields `limit` and `offset`
- Align metrics test expectations to `density` instead of legacy density fields

### Out of Scope

- Backend endpoints modifications
- Changes outside of frontend components and tests

### Files Expected to Change

- `frontend/__tests__/integration/component-integration.test.tsx`
- `frontend/__tests__/lib/api.test.ts`
- `frontend/__tests__/lib/api-axios-compatibility.test.ts`
- `frontend/__tests__/lib/api-upgrade-integration.test.ts`
- `frontend/__tests__/components/AssetList.test.tsx`
- `frontend/__tests__/test-utils.ts`

## Validation Commands

```bash
cd frontend && npm test
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective
- [x] Validation commands pass locally or in CI
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
