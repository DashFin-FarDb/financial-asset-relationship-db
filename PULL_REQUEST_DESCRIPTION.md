# PR: Security and Governance Hardening

## Primary Objective

Formalize repository security/governance policy and add technical audit/provenance controls for authentication events,
Loki security-event aggregation, and Docker SBOM release artifacts.

This PR addresses issue #1278 in three separated commits:

1. policy documentation;
2. auth and authorization audit logging;
3. artifact integrity and SBOM workflow enforcement.

## Scope

### In Scope

- Replace advisory security guidance with repository-owned security policy covering vulnerability disclosure, secret
  management, incident response, artifact provenance, and SBOM availability.
- Add `docs/GOVERNANCE.md` for approval requirements, security-sensitive changes, release procedure, artifact integrity,
  CI gate exceptions, and automation boundaries.
- Emit structured security audit events for login success/failure, expired/invalid tokens, disabled users, and rebuild
  operator authorization denials.
- Add Loki recording rules for auth failures and access denials.
- Add Docker image SBOM generation and upload for non-PR Docker publish runs using SHA-pinned actions.
- Add focused unit tests for audit logging and Loki recording rules.
- Update roadmap/audit docs to reflect PR 8 progress.

### Out of Scope

- No authentication model redesign.
- No new roles or permissions.
- No new alert thresholds.
- No secret manager integration.
- No SLSA compliance claim.
- No public disclosure automation.
- No changes to rebuild authorization semantics beyond audit logging.
- No changes to release publishing triggers beyond SBOM generation.

### Files Expected to Change

- `SECURITY.md`
- `docs/GOVERNANCE.md`
- `api/auth.py`
- `api/routers/auth.py`
- `monitoring/alerts/loki-recording.yml`
- `.github/workflows/docker-publish.yml`
- `tests/unit/test_auth_security_events.py`
- `tests/unit/test_auth_router_audit_logging.py`
- `tests/unit/test_loki_recording_rules.py`
- `docs/audits/enterprise-readiness-audit.md`
- `docs/roadmap/enterprise-readiness-pr-board.md`
- `docs/roadmap/enterprise-readiness-pr-plan.md`
- `PULL_REQUEST_DESCRIPTION.md`

## Behavior and Compatibility Notes

- Security audit events use existing `ObservabilityEvent` structured logging.
- Audit metadata is bounded to request/context identifiers, endpoint, IP address, username fields, and reason/policy
  labels.
- Passwords, bearer tokens, raw JWT payloads, and full Authorization headers are not logged.
- Loki additions are recording rules only; no alert thresholds are introduced.
- Docker SBOM generation runs outside pull requests, matching existing publish/signing boundaries.
- SBOM and upload steps use full commit SHA-pinned GitHub Actions.

## Delayed, Deferred, or Not Acted On

- SBOM publication as an OCI artifact is documented as future work.
- SLSA provenance attestations are documented as a future target, not a current compliance claim.
- Secret-manager integration and automated public disclosure workflows are not introduced.

## Validation Commands

Executed successfully:

```bash
pytest tests/unit/test_auth_security_events.py -q
pytest tests/unit/test_auth_router_audit_logging.py -q
pytest tests/unit/test_loki_recording_rules.py -q
pytest tests/unit/test_api_auth.py tests/unit/test_api_auth_comprehensive.py tests/unit/test_auth.py -q
pytest tests/integration/test_workflow_security_advanced.py -q
pytest tests/unit/test_workflow_yaml_files.py -q
python -m compileall api src tests
pre-commit run --files SECURITY.md docs/GOVERNANCE.md api/auth.py api/routers/auth.py monitoring/alerts/loki-recording.yml .github/workflows/docker-publish.yml tests/unit/test_auth_security_events.py tests/unit/test_auth_router_audit_logging.py tests/unit/test_loki_recording_rules.py
```

Attempted locally but not completed because an existing Starlette `TestClient` middleware test timed out before returning
a first result in this environment:

```bash
pytest tests/unit/api -q
```

Attempted locally but not completed because the existing async rebuild persistence suite timed out before returning a
first test result in this environment:

```bash
pytest tests/integration/test_graph_rebuild_persistence.py -q --timeout=10 --timeout-method=thread
```

## Merge Criteria

- [x] `SECURITY.md` contains VDP, secret management, incident response, artifact provenance, and SBOM policy.
- [x] `docs/GOVERNANCE.md` defines approval, release, exception, and automation-boundary rules.
- [x] Authentication success/failure emits structured `ObservabilityEvent` logs.
- [x] Expired/invalid tokens emit structured security events before raising.
- [x] Disabled-user and rebuild-operator denials emit structured warning-level events before raising.
- [x] Sensitive values are not logged.
- [x] Loki recording rules aggregate auth failures and access denials.
- [x] Docker publish workflow generates an SPDX SBOM outside PRs.
- [x] SBOM upload uses SHA-pinned GitHub Actions.
- [x] Tests prove audit events are emitted and sensitive fields are not logged.
- [x] No claims are made for controls not implemented in this PR.

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only.
- [x] I have explicitly listed what is out of scope.
- [x] I have verified the branch, base branch, and referenced issue #1278.
- [x] I have checked this PR against the production architecture (`FastAPI` backend + `Next.js` frontend).
