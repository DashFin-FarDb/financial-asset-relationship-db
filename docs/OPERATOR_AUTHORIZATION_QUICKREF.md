# Operator Rebuild Authorization — Quick Reference

**Component Status**: ✅ DEPLOYMENT-READY

## What This Component Does

Ensures only designated **operator users** can execute destructive graph rebuild operations:

- `POST /api/graph/rebuild` — Rebuild and persist graph
- `GET /api/graph/rebuild/jobs/{job_id}` — View rebuild job details
- `GET /api/graph/rebuild/jobs` — List rebuild jobs
- `POST /api/graph/rebuild/jobs/{job_id}/cancel` — Request cancellation of a rebuild job

## Authorization Flow

```text
Request
  └─► get_current_active_user()  [JWT auth + active check]
        └─► get_current_rebuild_operator_user()  [operator username check]
              ├─► ADMIN_USERNAME not set → 503 Service Unavailable
              ├─► username != ADMIN_USERNAME → 403 Forbidden
              └─► match → 200 OK (endpoint executes)
```

## Configuration

```bash
# Required environment variables
ADMIN_USERNAME=operator_username  # Designated operator
ADMIN_PASSWORD=secure_password    # Operator credential
```

## Quick Verification

```bash
# As operator (should succeed)
curl -X POST https://your-app.com/api/graph/rebuild \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
# Expected: 200 OK

# As non-operator (should fail)
curl -X POST https://your-app.com/api/graph/rebuild \
  -H "Authorization: Bearer $USER_TOKEN"
# Expected: 403 Forbidden
```

## Implementation Details

**Location**: `api/auth.py:428-451`

**Protected by**: `get_current_rebuild_operator_user()` dependency

**Error Codes**:

- `401` — Not authenticated
- `403` — Authenticated but not operator
- `503` — Operator not configured

## Test Coverage

✅ All authorization paths tested:

- `test_rebuild_returns_403_for_active_non_operator_user`
- `test_rebuild_allows_active_authorized_operator_user`
- `test_rebuild_jobs_endpoints_return_403_for_non_operator`
- `test_rebuild_endpoints_require_authentication`

## Security Assessment

✅ **No vulnerabilities identified**
✅ Bounded error messages (no secret leakage)
✅ Centralized configuration
✅ Audit logging for successful rebuild operations
⚠️ Authorization failures (403) not currently logged

## Deployment Readiness

| Criteria                | Status |
| ----------------------- | ------ |
| Implementation complete | ✅     |
| Tests passing           | ✅     |
| Security reviewed       | ✅     |
| Documentation exists    | ✅     |
| Ready for production    | ✅     |

## See Also

- **Full Audit**: `docs/audits/OPERATOR_REBUILD_AUTHORIZATION_AUDIT.md`
- **Enterprise Operating Model**: `docs/enterprise-deployment-operating-model.md`
- **Graph Persistence Design**: `docs/graph-persistence-design.md`

---

**Last Updated**: 2026-05-23
**Component Version**: Merged in PR #1143
