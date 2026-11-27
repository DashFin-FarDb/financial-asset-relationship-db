# Enterprise Readiness Index

**Publication date:** 2026-07-15
**Last reconciled:** 2026-11-27 (post-hardening, operational drills, PG18 scale baseline, ADR-0012, operator sign-off, observability/OTLP/Loki/Tempo integration, RBAC role hierarchy, Dependabot 0-alert remediation, and `hardening_tier` P1–P3 workflow wiring; `main@02be2e729`)
**Purpose:** Single entry point for enterprise-readiness audit, roadmap, PR plan, release criteria, and release evidence

## What To Read

| Document                                                      | Purpose                                                                                                                    |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `docs/audits/enterprise-readiness-audit.md`                   | Full audit of what is implemented, evidence-backed, manually gated, and still deferred                                     |
| `docs/roadmap/enterprise-readiness-roadmap.md`                | High-level release-execution roadmap after the PR #1287-#1301 reconciliation point                                         |
| `docs/roadmap/enterprise-readiness-completion-checklist.md`   | Completion-criteria checklist and non-negotiable boundaries for the 14 remaining roadmap items                             |
| `docs/roadmap/enterprise-readiness-pr-plan.md`                | PR-by-PR execution plan with validation commands                                                                           |
| `docs/roadmap/enterprise-readiness-pr-board.md`               | Operational PR board with status and exit criteria                                                                         |
| `docs/release-checklist.md`                                   | Release gates and enterprise exit criteria                                                                                 |
| `docs/release-evidence-pack.md`                               | Gate-by-gate release evidence matrix, targeted commands, manual artefacts, and blocker rules                               |
| `docs/operations/operational-evidence-capture-framework.md`   | Canonical evidence grammar for classifying, redacting, and reviewing operational proof artifacts                           |
| `docs/testing/operational-drill-and-scale-validation-pack.md` | Operational drill matrix and bounded scale-validation guidance for observability, SLO, dashboard, alert, and runbook proof |
| `docs/governance/state-machine-and-operating-authority.md`    | Current operational authority for rebuild/recovery state machines, invariants, ownership, and exception paths              |
| `docs/adr/0007-database-authorization-boundary.md`            | Accepted hosted database authorization boundary and bounded verification contract                                          |
| `docs/runbooks/database-authorization-closure.md`             | Operator setup and remediation path for ADR 0007 / H-P0-04 (staging Satisfied — `db_authz: PASS` + `run-30002002715`)      |
| `docs/adr/0006-release-and-deployment-automation.md`          | Release and Deployment automation strategy, GitHub Actions constraints                                                     |
| `docs/adr/0005-backup-restore-dr-strategy.md`                 | Backup, restore, DR strategy, data classification, RPO, and RTO                                                            |
| `docs/adr/0012-multi-region-and-advanced-hosting-strategy.md` | Accepted Active-Passive multi-region / advanced hosting strategy and failover protocol                                     |
| `docs/runbooks/backup-restore-dr.md`                          | Operator procedures for backup verification, restore execution, and post-restore checks                                    |
| `docs/compound/INDEX.md`                                      | Additive architecture-expert compounded memory index (provisional vs landed)                                               |
| `docs/strategy/fardb-project-continuity.md`                   | Cross-session continuity ledger for decisions, commitments, milestones, and agent handoffs                                 |

## Executive Summary

The repository has moved from enterprise-readiness remediation into release-evidence execution.
The merged PR #1287-#1301 sequence means the durable persistence path, startup/reload integration,
durable promotion checker, API contract cleanup, recovery/governance hardening, failure-mode
validation, security/governance documentation, DR documentation, and release evidence pack are now
part of the repository baseline.

Boundary hardening follow-ups are tracked as stable IDs **H-P0-\*** … **H-P3-\*** in
[Release Evidence Pack — Hardening backlog](release-evidence-pack.md#hardening-backlog-p0p3)
and mirrored on the [enterprise-readiness PR board](roadmap/enterprise-readiness-pr-board.md#hardening-backlog-p0p3).
RC dispatch defaults to `hardening_tier=P0` (strict hosted readiness). Soft rehearsal uses `hardening_tier=none`.
Cumulative tiers `P1`, `P2`, and `P3` are wired in `.github/workflows/release-evidence-verify.yml` (PR #2010) and validated by `tests/unit/test_hardening_tier_workflow.py`.

Staging H-P0-04 is Satisfied by the SHA-bound record `db_authz: PASS|run-30002002715`, and strict stale-owner
restart composition is Satisfied - automated. Neither result is inherited by a later hosted target or release SHA.

The remaining work is no longer primarily architectural. It is concentrated in live release evidence and bounded follow-up hardening:

- fresh SHA-bound database authorization evidence when a production artefact is selected for promotion;
- hosted promotion evidence showing durable graph truth in the target environment (coordinated via
  `.github/workflows/release-evidence-verify.yml` and attached target-environment outputs);
- DR restore rehearsal evidence against the documented backup/restore process;
- release-commit security scanner review and named operator sign-off (captured/reviewed via
  `.github/workflows/release-evidence-verify.yml` plus scanner workflows);
- the operational evidence-capture framework and drill pack for classifying operational proof;
- the operational drill and scale-validation pack for observability and runbook proof;
- production-scale validation and evidence-capture discipline for operational drills that stays bounded outside normal CI.

The DR documentation gap is closed at the strategy and runbook level through [ADR 0005](adr/0005-backup-restore-dr-strategy.md) and the [backup/restore/DR runbook](runbooks/backup-restore-dr.md). Final enterprise release readiness still requires operators to rehearse restore at least once and record the evidence in the release process.

### Dated evidence update — 2026-11-19

PR [#1925](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1925) (merged 2026-11-19, `966133f97`) adds
advisory local
scale and functionality observations plus an operator-reported host-attested PostgreSQL 16.14 disposable ledger-profile
proof. These results improve coverage of the project’s persistence and analysis behavior but do not establish a
production-scale asset-graph workload or hosted staging. The PostgreSQL run’s exact source SHA and manifest SHA were
not captured. See the
[production-scale checklist item](roadmap/enterprise-readiness-completion-checklist.md#12-production-scale-validation)
for the evidence boundary and remaining criteria.

### Dated evidence update — 2026-11-27

Between PRs #1965 and #1990 (through `main@de676fc64`), the following non-Actions readiness milestones landed:

- **H-P1–H-P3 hardening backlog (PRs #1965–#1975):** All 11 hardening IDs implemented and merged (`H-P1-04`, `H-P2-01`–`H-P2-05`, `H-P3-01`–`H-P3-05`), and the `H-P2-03` single-running-job partial unique index was applied live to hosted Supabase with SHA-bound verification (`docs/evidence-records/hp203-single-running-index-migration-48a36108.md`, PR #1976). Only `hardening_tier` P1–P3 workflow wiring remains open under `#1917`.
- **Operational drills (PR #1982, closing #1919):** All 5 representative operational drills executed and passed (`docs/testing/operational-drill-execution-records.md`).
- **Production-scale validation (PR #1983, closing #1918):** Deterministic `SCALE10K` (10,000 assets / 50,000 directed relationships) PostgreSQL 18.6 baseline recorded (`docs/evidence-records/production-scale-pg18-baseline-2026-11-27.md`).
- **Multi-region / advanced hosting strategy (PR #1984, closing #1920):** Accepted Active-Passive single-writer topology in `docs/adr/0012-multi-region-and-advanced-hosting-strategy.md`.
- **Operator sign-off (PR #1985, closing #1914):** SHA-bound operator sign-off recorded in `docs/evidence-records/operator-signoff-bf624469-2026-11-27.md`.
- **Documentation hygiene (PRs #1986–#1992):** Archived 118 historical root/`docs/` files locally with SHA-256 manifests and refreshed core developer, readiness, strategy, and agent docs.
- **Security, resilience, concurrency & performance (PRs #1993–#2000, #2008, #2011):** Added JWT key rotation (`JWT_KEY_ID`, `JWT_PREVIOUS_SECRET_KEYS`) and `jti` revocation (`POST /api/auth/logout`), shared rate-limit store precedence and fail-closed guard (`RATE_LIMIT_STORAGE_URI`, `REQUIRE_SHARED_RATE_LIMIT_STORE`), Playwright E2E smoke suite (`npm run test:e2e`), resilient ingestion adapter (`src/data/ingestion_resilience.py`), atomic monotonic fencing CAS, rebuild `Idempotency-Key` support, PostgreSQL chunked bulk upsert fast path, 0-alert Dependabot remediation (`filelock==4.2.1`, `minimatch==11.0.9`), and application RBAC role hierarchy (`resolve_user_roles`, `require_roles`, JWT `roles` claim, assertion proposer guard).
- **Full-stack observability, readiness & release automation (PRs #1995, #2001–#2007, #2009–#2010):** Wired Grafana dashboard auto-provisioning (`api-overview.json`, `rebuild-operations.json`, `slo-compliance.json`, `graph-postgres-bridge.json`), Prometheus/Alertmanager routing, Grafana datasource plugins (`vercel`, `netlify`, `sentry`), Graph↔DB boundary metrics (`fardb_graph_persistence_configured`, `graph_projection_last_published_timestamp_seconds`, `graph_db_persistence_duration_seconds`), optional OTLP tracing (`src/observability/tracing.py`) and JSON log file output (`LOG_FILE_PATH`), strict `GET /api/ready` readiness probe, security/resilience Prometheus metrics, production Docker `/api/ready` healthcheck and env passthroughs (`Dockerfile.api`, `docker-compose.production.yml`), and cumulative `hardening_tier` P1–P3 workflow wiring (`#1917`).

All remaining open enterprise-readiness issues (`#1909`, `#1912`, `#1913`, `#1915`, `#1923`) now depend solely on GitHub Actions billing restoration for live workflow dispatch.

## Roadmap Status Snapshot

Status legend follows the [Release Evidence Pack](release-evidence-pack.md): **Satisfied - automated**, **Satisfied - documented**, **Satisfied - manual evidence required**, **Partially satisfied**, and **Blocked**.

| Status                               | Current items                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Satisfied - automated                | PR 1 durable graph persistence; PR 2 startup load/save integration; PR 4 core density, asset pagination, and frontend/backend contract seams; PR 5 RecoveryGate/reconciliation control-plane path; PR 7 CI-bounded failure-mode and representative-scale validation; strict stale-owner restart composition; H-P1–H-P3 hardening implementations (#1965–#1975) and cumulative `hardening_tier` P1–P3 workflow wiring (#2010); full observability/readiness/RBAC/Dependabot hardening (#1993–#2011) |
| Satisfied - documented               | PR 6 distributed hosting semantics; PR C governance/state-machine authority; production architecture, deployment operating model, and ADR 0012 multi-region strategy; all 5 operational drills (#1982); PG18 `SCALE10K` baseline (#1983); SHA-bound operator sign-off (#1985)                                                                             |
| Satisfied - manual evidence required | PR 3 hosted durable promotion proof for the target environment; fresh SHA-bound production database authorization evidence when that target is promoted; PR 8 security scanner summary, exception review, and release sign-off; PR 9 restore rehearsal and post-restore smoke evidence                                                                  |
| Partially satisfied                  | Hosted platform rollout of optional production controls (shared Redis rate-limit store, Grafana Cloud alerting rule upload, and GitHub Environment reviewer/branch-protection settings under `H-P1-04` / `H-P3-05`; repository code and `hardening_tier` P1–P3 workflow wiring are complete) |
| Blocked                              | Remaining live workflow evidence dispatches (`#1909`, `#1912`, `#1913`, `#1915`, `#1923`) — including hosted promotion evidence, target-specific database authorization evidence where applicable, release-commit security scanner review, and DR restore rehearsal via `.github/workflows/release-evidence-verify.yml` and `post-recovery-readiness.yml` — are blocked on GitHub Actions billing restoration. |

## Recommended Reading Order

1. `docs/release-evidence-pack.md`
2. `docs/release-checklist.md`
3. `docs/audits/enterprise-readiness-audit.md`
4. `docs/roadmap/enterprise-readiness-roadmap.md`
5. `docs/roadmap/enterprise-readiness-pr-board.md`
6. `docs/roadmap/enterprise-readiness-pr-plan.md`
7. `docs/governance/state-machine-and-operating-authority.md`
8. `docs/adr/0007-database-authorization-boundary.md`
9. `docs/adr/0005-backup-restore-dr-strategy.md`
10. `docs/runbooks/backup-restore-dr.md`

## Operational Rule

If a change touches production behavior, deployment, security, persistence, recovery, or release promotion, it should be mapped back to the release evidence pack and the canonical state-machine authority before implementation begins.

Repository tests and documentation may satisfy implementation evidence, but staging and production promotion require target-environment evidence. A bounded health response alone must not be treated as durable graph truth.

## Related Entry Points

- [README.md](../README.md) — main repository entry point and production setup overview
- [docs/strategy/README.md](./strategy/README.md) — product strategy and claim taxonomy; subordinate to this
  release-status authority
- [docs/release-evidence-pack.md](./release-evidence-pack.md) — auditable release evidence matrix
- [docs/operations/operational-evidence-capture-framework.md](./operations/operational-evidence-capture-framework.md) — canonical evidence grammar for claims, redaction, and review
- [docs/testing/operational-drill-and-scale-validation-pack.md](./testing/operational-drill-and-scale-validation-pack.md) — operator-facing drill matrix and bounded scale-validation guidance
- [docs/governance/state-machine-and-operating-authority.md](./governance/state-machine-and-operating-authority.md) — current authority for rebuild/recovery/persistence state-machine governance
- [docs/adr/0007-database-authorization-boundary.md](./adr/0007-database-authorization-boundary.md) — accepted hosted database authorization boundary and bounded checker contract
- [docs/runbooks/database-authorization-closure.md](./runbooks/database-authorization-closure.md) — operator remediation sequence, Environment secret readiness, and redacted PASS attachment path
- [docs/adr/0002-hosted-deployment-and-persistence.md](./adr/0002-hosted-deployment-and-persistence.md) — hosted persistence decision
- [docs/adr/0006-release-and-deployment-automation.md](./adr/0006-release-and-deployment-automation.md) — release and deployment automation strategy
- [docs/adr/0005-backup-restore-dr-strategy.md](./adr/0005-backup-restore-dr-strategy.md) — backup, restore, and DR strategy
- [docs/runbooks/backup-restore-dr.md](./runbooks/backup-restore-dr.md) — backup and restore operating procedure
- [docs/roadmap/enterprise-readiness-completion-checklist.md](./roadmap/enterprise-readiness-completion-checklist.md) — per-item completion criteria, boundaries, and single-decision PR mapping for the remaining roadmap items
- [docs/enterprise-deployment-operating-model.md](./enterprise-deployment-operating-model.md) — promotion, rollback, and DR operating model
