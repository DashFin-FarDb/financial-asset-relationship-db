# Release Evidence Pack

**Status:** Active
**Issue:** #1300
**Scope:** Enterprise release evidence mapping for the FastAPI + Next.js production stack.

## Purpose

This evidence pack maps each enterprise release gate to concrete automated evidence, CI or smoke commands, manual
operator artifacts, and remaining work. It is the auditable companion to the
[Enterprise Release Checklist](release-checklist.md).

For the evidence formatting and review rules that keep artifacts from overstating or understating their claim, see
[Operational Evidence Capture Framework](operations/operational-evidence-capture-framework.md).

The manual **Release Evidence Verify** workflow run (`.github/workflows/release-evidence-verify.yml`) is the single
reproducible mechanism for generating the JUnit/readiness artifacts and gate summary used by this pack's evidence
status model.

The document distinguishes:

- **implemented:** runtime or operational capability exists;
- **tested:** targeted tests prove the capability;
- **CI-enforced:** a workflow or required check runs the proof automatically;
- **operator-rehearsed:** an operator has attached hosted logs, workflow runs, or sign-off artefacts.

Do not attach secrets, raw database connection strings, full graph dumps, bearer tokens, private keys, or raw exception
traces to release evidence.

## Evidence Status Legend

- `Satisfied - automated`: covered by committed tests or CI jobs.
- `Satisfied - documented`: covered by authoritative docs or runbooks.
- `Satisfied - manual evidence required`: implementation/docs exist, but release sign-off requires attached operator
  evidence.
- `Partially satisfied`: meaningful evidence exists, with a documented non-blocking gap.
- `Blocked`: release cannot proceed until the listed evidence or remediation is complete.

## Evidence Matrix

| Gate                | Status                               | Automated evidence                                                                                                                                                       | Manual evidence                                                                                                                                             | Release blocker?                                                                   | Remaining work                                                                                                                                                                                       |
| ------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Architecture        | Satisfied - documented               | PR review confirms production code paths remain FastAPI backend and Next.js frontend.                                                                                    | Confirm release artefact and deployment procedure do not depend on `app.py` or Gradio.                                                                      | Yes, if production artefacts depend on Gradio.                                     | None for this gate when release artefacts target `api/` and `frontend/`.                                                                                                                             |
| Durable Persistence | Satisfied - automated                | Repository persistence, lifecycle persistence, hosted startup readiness, and field-fidelity tests.                                                                       | Confirm hosted `ASSET_GRAPH_DATABASE_URL` points to the intended durable graph database boundary.                                                           | Yes, for staging/production promotion.                                             | Attach hosted database configuration evidence without exposing secrets.                                                                                                                              |
| Restart / Reload    | Partially satisfied                  | Lifecycle persisted-startup tests and clean restart-recovery integration test.                                                                                           | Attach restart/redeploy evidence showing persisted startup source after graph persistence.                                                                  | Yes, if restart proof is absent for staging/production.                            | Strict stale-owner restart composition is now covered by the dedicated restart/recovery integration test; attach restart/redeploy evidence showing persisted startup source after graph persistence. |
| Promotion           | Satisfied - manual evidence required | Hosted readiness script and workflow support `--require-persistence`; readiness endpoint exposes persisted startup evidence.                                             | Attach staging/prod smoke output from `scripts/check_hosted_readiness.py <base_url> --require-persistence`, plus bounded `/api/assets?per_page=1` evidence. | Yes.                                                                               | Hosted promotion proof remains manual until actual target-environment logs are attached.                                                                                                             |
| API Contract        | Satisfied - automated                | Density formula/parity tests, pagination `hasMore` tests, `AssetPageResponse` alias tests, rebuild job-list `total` / `hasMore` tests, frontend API contract seam tests. | Confirm frontend build or CI run used for release includes the contract tests.                                                                              | No.                                                                                | None for this gate when the listed contract tests run for the release commit.                                                                                                                        |
| Recovery / Rebuild  | Satisfied - automated                | Distributed lock runtime tests, RecoveryGate unit/integration tests, stale-owner tests, lock refresh flow tests.                                                         | Operator confirms no active rebuild job and valid/expired-safe `graph_rebuild` lock state before promotion.                                                 | Yes, if active rebuild or unsafe lock state exists.                                | None for automated proof; attach operator pre-promotion check.                                                                                                                                       |
| Security            | Satisfied - manual evidence required | Auth/router audit logging tests, security-event tests, protected rebuild endpoint tests, dependency/code/workflow scanner jobs.                                          | Record non-blocking scanner failures with reason, owner, and follow-up issue; confirm no active critical security gate is bypassed.                         | Yes, for unapproved critical/high security failures or undocumented gate bypasses. | Attach security scan summary and exception records where applicable.                                                                                                                                 |
| Governance          | Satisfied - documented               | Governance policy, state-machine authority, release checklist, ADRs, and PR scope guardrails.                                                                            | Named operator ownership for deploy, rollback, restore, and persistence verification.                                                                       | Yes, if owner/sign-off is missing for enterprise release.                          | Attach named release operator and approver sign-off.                                                                                                                                                 |
| Disaster Recovery   | Satisfied - manual evidence required | Backup/restore/DR runbook, ADR 0005, and deployment operating model.                                                                                                     | Restore rehearsal log, selected restore point, database-boundary topology, and post-restore smoke evidence.                                                 | Yes, before final enterprise release sign-off.                                     | DR restore rehearsal remains manual evidence until an actual rehearsal artefact is attached.                                                                                                         |

Current RC1 / Objective 2 follow-up live record: [issue #1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330). The committed companion record is [docs/evidence-records/rc1-objective-2-follow-up.md](evidence-records/rc1-objective-2-follow-up.md). The live record has been fully verified, executed, and approved for its objective-scope items; several release gates (DR, Promotion, Security) still require manual evidence per their respective blocking rules.

## Gate Evidence Details

### 1. Architecture Gate

Required proof:

- Production scope remains FastAPI backend in `api/` and Next.js frontend in `frontend/`.
- Gradio `app.py` remains demo/internal testing only and is not part of production release artefacts.

Evidence sources:

- [ADR 0001: Production Architecture](adr/0001-production-architecture.md)
- [Automation Scope Policy](../.github/AUTOMATION_SCOPE_POLICY.md)
- [Enterprise Deployment Operating Model](enterprise-deployment-operating-model.md)

Manual release attachment:

- Release artefact or deployment manifest summary showing the production entrypoints.
- Reviewer note confirming no production dependency on `app.py`.

### 2. Durable Persistence Gate

Required proof:

- Durable graph truth can be persisted and reloaded through repository abstractions.
- Startup can load persisted graph state.
- Persistence preserves required asset, relationship, and event fields.
- SQLite compatibility remains intact for local/test execution.

Targeted commands:

```bash
pytest tests/unit/test_repository_graph_persistence.py -q
pytest tests/unit/test_graph_lifecycle_persistence.py -q
pytest tests/unit/test_repository_graph_persistence_fields.py -q
pytest tests/unit/test_graph_lifecycle_persistence_fields.py -q
pytest tests/integration/test_hosted_graph_startup_readiness.py -q
```

Manual release attachment:

- Confirmation that `ASSET_GRAPH_DATABASE_URL` is configured for the target environment.
- Redacted provider/database boundary evidence proving the graph persistence store is durable.

Workflow evidence:

- `.github/workflows/release-evidence-verify.yml` (`Run Gate Tests (Durable Persistence)` step and `release-evidence`
  artifact).

### 3. Restart / Reload Gate

Required proof:

- Restart after persistence does not silently fall back to an unverified graph state.
- Startup evidence identifies persisted, cache, sample, or rebuild source.
- Clean restart/recovery composition is exercised with the real lifecycle and persistence seams.

Targeted commands:

```bash
pytest tests/unit/test_graph_lifecycle_persistence.py -q
pytest tests/integration/test_restart_recovery_clean_path.py -q
pytest tests/integration/test_distributed_hosting_failure_modes.py -q
```

Caveat:

- The exact strict stale-owner restart/recovery composition now has deterministic CI coverage; hosted restart/redeploy
  evidence remains a separate release artifact.

Manual release attachment:

- Restart/redeploy log or smoke output showing `graph.persistence_loaded == true` and
  `graph.startup_source == "persisted"` after persistence is written.

Workflow evidence:

- `.github/workflows/release-evidence-verify.yml` (`Run Gate Tests (Restart/Reload)` step and `release-evidence`
  artifact).

### 4. Promotion Gate

Required proof:

- Hosted readiness proves durable graph evidence, not only bounded health.
- Promotion includes an explicit durable graph-persistence smoke procedure.

Targeted commands:

```bash
python scripts/check_hosted_readiness.py <base_url> --require-persistence
curl -fsS "<base_url>/api/health/detailed"
curl -fsS "<base_url>/api/assets?per_page=1"
```

Workflow evidence:

- `.github/workflows/release-evidence-verify.yml` (`Check Hosted Readiness` step with `--json` and optional
  `--require-persistence`, plus gate summary output).
- `.github/workflows/hosted-readiness.yml` run for the target environment when configured.

Manual release attachment:

- Staging/prod smoke output with secrets redacted.
- Expected persisted graph counts or approved sentinel baseline evidence.
- See the [Hosted Readiness Evidence Guide](operations/hosted-readiness-evidence-guide.md) for the canonical capture,
  classification, and redaction rules.
- For staging, attach the provider, boundary, Vercel mapping, and preview durability evidence required by the
  [Staging Deployment Operating Baseline](staging-deployment-operating-baseline.md).

Blocking rule:

- Hosted promotion proof remains manual evidence. Do not mark this gate complete from repository tests alone.

### 5. API Contract Gate

Required proof:

- Density semantics are consistent across backend and frontend.
- Asset pagination reports `hasMore` correctly.
- Backend response aliases match frontend contract expectations.

Targeted commands:

```bash
pytest tests/unit/test_api_density_contract.py -q
pytest tests/unit/test_api_asset_pagination_values.py -q
pytest tests/integration/test_api_pagination_contract.py -q
pytest tests/unit/test_asset_page_response_alias.py -q
cd frontend && npm test -- api-contract-seams.test.ts
```

Rebuild job-list contract:

- `RebuildJobListResponse.count` is the number of jobs returned in the current page.
- `RebuildJobListResponse.total` is the number of jobs matching the active `status` filter before `limit` / `offset`.
- `RebuildJobListResponse.has_more` is true when another page exists after the current response.
- The endpoint keeps the default cap of 100 jobs and supports bounded `limit`, `offset`, and `status` query parameters.

Manual release attachment:

- CI run or local validation summary showing backend and frontend API contract checks executed for the release commit.

Workflow evidence:

- `.github/workflows/release-evidence-verify.yml` (`Run Gate Tests (API Contract)` step and `release-evidence`
  artifact).

### 6. Recovery / Rebuild Gate

Required proof:

- Distributed lock loss, stale-owner handling, and RecoveryGate decisions fail closed.
- Rebuild cancellation, lock-loss, and reset/block paths are tested.
- No stale owner can mutate rebuild state after restart or lock loss.

Targeted commands:

```bash
pytest tests/unit/test_distributed_lock_runtime.py -q
pytest tests/unit/test_recovery_gate.py -q
pytest tests/unit/test_recovery_gate_startup.py -q
pytest tests/integration/test_recovery_gate_integration.py -q
pytest tests/integration/test_lock_refresh_flow.py -q
```

Note:

- `tests/integration/test_distributed_hosting_failure_modes.py` is exercised in the Restart / Reload gate to avoid
  duplicate runtime and duplicate failure signaling across gates.

Workflow evidence:

- `.github/workflows/release-evidence-verify.yml` (`Run Gate Tests (Recovery/Rebuild)` step and `release-evidence`
  artifact).
- `.github/workflows/ci-gate-spec.yaml` coordination safety gate run, where enabled.

Manual release attachment:

- Operator note confirming no in-flight rebuild job, no unsafe active lock holder, and no suspected split-brain before
  promotion.

### 7. Security Gate

Required proof:

- Authentication success/failure and authorization denials emit bounded structured audit events.
- Destructive rebuild endpoints remain operator-protected.
- Dependency, code, container, and workflow scan jobs are reviewed.

Targeted commands:

```bash
pytest tests/unit/test_auth_router_audit_logging.py -q
pytest tests/unit/test_auth_security_events.py -q
pytest tests/integration/test_graph_admin_router.py -q
```

Workflow evidence:

- `.github/workflows/release-evidence-verify.yml` (`Run Gate Tests (Security)` step and `release-evidence`
  artifact).
- Relevant GitHub security workflows, including CodeQL, Bandit, Bearer, Semgrep, Snyk, Trivy, dependency review, and
  workflow scanners where configured for the release branch.

Manual release attachment:

- Scanner summary with non-blocking failures documented by reason, owner, and follow-up issue.
- Any CI/security exception request and explicit maintainer approval, per [Governance Policy](../docs/GOVERNANCE.md).

### 8. Governance Gate

Required proof:

- Current operational authority, release checklist, and governance rules are documented.
- Exception handling and operator authority are explicit.
- Release-bound PRs follow scope guardrails.

Evidence sources:

- [State Machine and Operating Authority](../docs/governance/state-machine-and-operating-authority.md)
- [Governance Policy](../docs/GOVERNANCE.md)
- [Enterprise Release Checklist](../docs/release-checklist.md)
- [Enterprise Deployment Operating Model](../docs/enterprise-deployment-operating-model.md)
- [Automation Scope Policy](../.github/AUTOMATION_SCOPE_POLICY.md)

Manual release attachment:

- Named deploy operator, promotion approver, rollback owner, restore operator, and persistence-verification owner.
- Any exception request with affected gate, risk, expiry/follow-up, and maintainer approval.

### 9. Disaster Recovery Gate

Required proof:

- Backup/restore procedure exists.
- RPO/RTO are defined.
- Rollback is distinguished from data restore.
- Restore has been rehearsed at least once before final enterprise release sign-off.

Evidence sources:

- [Backup, Restore, and DR Runbook](runbooks/backup-restore-dr.md)
- [ADR 0005: Backup, Restore, and Disaster Recovery Strategy](adr/0005-backup-restore-dr-strategy.md)
- [Enterprise Deployment Operating Model](enterprise-deployment-operating-model.md#disaster-recovery)

Manual release attachment:

- Restore rehearsal log.
- Selected restore point.
- Effective database-boundary topology: Auth DB, Coordination DB, Asset Graph DB.
- Scratch restore verification results.
- Post-restore hosted readiness smoke output.
- RPO/RTO observations and decision recorded using the
  [restore rehearsal evidence record](runbooks/backup-restore-dr.md#restore-rehearsal-evidence-record).

Blocking rule:

- DR restore rehearsal remains manual evidence. Do not mark this gate complete until an actual rehearsal artefact is
  attached.

## Release Evidence Attachment Checklist

Open one release-candidate evidence issue per release candidate using the
[Release candidate evidence capture template](../.github/ISSUE_TEMPLATE/release_candidate_evidence.md). The issue is
the operational record for hosted evidence, scanner review, operator sign-off, and DR rehearsal proof. For capture and
classification details, operators should use the [Hosted Readiness Evidence Guide](operations/hosted-readiness-evidence-guide.md).

Before enterprise release sign-off, attach or link:

- CI run for the release commit.
- Hosted readiness run with `--require-persistence`.
- `/api/health/detailed` output with secrets redacted.
- `/api/assets?per_page=1` smoke output or approved sentinel evidence.
- Security scanner summary and approved exception records, if any.
- Operator sign-off for deploy, promotion, rollback, restore, and persistence verification.
- DR restore rehearsal log and post-restore smoke evidence.
- Live RC evidence record that collates the attached artifacts and the current gate state.
