# Enterprise Readiness Remediation Roadmap

For the broader enterprise-readiness index, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

**Publication date:** 2026-06-25
**Last updated:** 2026-08-18
**Format:** Release evidence / Target-environment proof / Follow-up hardening
**Purpose:** Sequence the remaining work after the PR #1287-#1301 enterprise-readiness reconciliation point

Status legend follows the [Release Evidence Pack](../release-evidence-pack.md): **Satisfied - automated**, **Satisfied - documented**, **Satisfied - manual evidence required**, **Partially satisfied**, and **Blocked**.

## Summary

The repository is no longer in the early enterprise-readiness remediation phase. Observability, rebuild coordination, operator authorization, durable persistence, startup/reload integration, durable promotion checks, API contract cleanup, distributed hosting semantics, governance authority, security/governance documentation, and DR documentation now exist in the repository baseline.
The release evidence pack also exists and governs release-proof capture.

The remaining roadmap is about release execution: attaching target-environment evidence, rehearsing restore, and closing bounded follow-up seams without reopening the architecture.

## Current critical-path programme — CQ-03 PostgreSQL ledger adoption

CQ-03A, CQ-03B-R1/R2, CQ-03C, CQ-03D-00, and CQ-03D-01 are complete at repository scope through merged PRs #1634,
with #1640, #1641, #1643, #1644, and #1646 completing the remaining units. The repository can build the explicit
auth, graph, coordination, and combined profiles on supported PostgreSQL versions and can run a target-bound,
permit-bound, read-only hosted preflight. This is not hosted adoption evidence: no target or permit has been approved
and no hosted preflight has been executed.

| Item                                     | Status                                                                                   | Next evidence required                                                                                                | Non-negotiable boundary                                                                                                                                      |
| ---------------------------------------- | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CQ-03D hosted migration-history adoption | Partially satisfied — D-01 merged and verified at repository scope; target/permit absent | D-02: separately approve one target and protected single-use permit, then obtain a passing hosted read-only preflight | History-only reconciliation; no DDL; no DML beyond one permit-bound history marker; no grant, role, credential, deployment, or provider-configuration change |

The CQ-03D-01 target adapter contract was human-ratified on 2026-08-18 and merged through PR #1646 at verified squash
`790274c1b0dbdb43d4bbbbf35c4565dae36c9fe3`. The command may collect only preflight evidence. CQ-03D-02 must
separately approve one target and a protected single-use permit before a connected hosted preflight. That preflight
does not authorize the later single migration-history marker, which remains a separate decision.

## Release Evidence Now

These items must be completed or explicitly attached before treating a staging or production release as enterprise-ready.

| Item                                                | Status                               | Why now                                                                                                                   | Dependencies                                                                                                                |
| --------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Source-of-truth reconciliation after PR #1287-#1301 | Satisfied - documented               | Canonical docs must reflect the merged implementation and evidence state before the next release objective starts         | Release evidence pack, release checklist, audit, PR board                                                                   |
| Hosted durable promotion evidence                   | Satisfied - manual evidence required | Staging/production promotion requires proof that the hosted runtime loaded durable graph truth, not only bounded health   | `scripts/check_hosted_readiness.py --require-persistence`, target hosted environment, configured `ASSET_GRAPH_DATABASE_URL` |
| Release evidence capture for the release commit     | Satisfied - manual evidence required | The release evidence pack requires CI run links, smoke output, scanner summaries, and named operator sign-off             | Release evidence pack, GitHub Actions, hosted staging/prod target                                                           |
| DR restore rehearsal evidence                       | Satisfied - manual evidence required | DR strategy and runbook exist, but final enterprise release sign-off requires one rehearsed restore artefact              | ADR 0005, backup/restore/DR runbook, staging or scratch restore target                                                      |
| Security scanner and exception summary              | Satisfied - manual evidence required | Security automation exists, but release governance requires scanner output and approved exceptions for the release commit | Security workflows, governance policy, release approver                                                                     |

## Target-Environment Proof Next

These items turn repository-level readiness into operational confidence.

| Item                                     | Status                               | Why next                                                                                                                         | Dependencies                                                                                   |
| ---------------------------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Staging deployment operating baseline    | Partially satisfied                  | The operating model defines the topology, but staging needs explicit provider, database-boundary, secret, and promotion evidence | Vercel project/environment mapping, durable app DB, durable graph DB, optional coordination DB |
| Durable graph smoke procedure execution  | Satisfied - manual evidence required | The procedure is documented; the next step is attaching redacted hosted output for the target environment                        | Rebuild or approved persisted baseline, backend restart/redeploy, readiness checker            |
| Restore rehearsal and post-restore smoke | Satisfied - manual evidence required | The DR gate remains open until restore is executed and verified at least once                                                    | Selected restore point, scratch target, post-restore readiness smoke                           |
| Operator ownership sign-off              | Satisfied - manual evidence required | Deploy, promotion, rollback, restore, and persistence-verification owners must be named for release                              | Enterprise deployment operating model, release evidence pack                                   |

## Follow-up Hardening Later

These items are valid but should not be bundled into the release-evidence reconciliation PR.

| Item                                        | Status                 | Why later                                                                                                                                                                                        | Dependencies                                                         |
| ------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| `RebuildJobListResponse` truncation signal  | Satisfied - automated  | Rebuild job-list responses expose `total` and `hasMore`; tests cover default cap, explicit pagination, and status-filtered truncation semantics                                                  | None                                                                 |
| Strict stale-owner restart composition test | Satisfied - automated  | The dedicated restart/recovery integration test now covers owner death, lock expiry, RecoveryGate reset, persisted restart load, and stale-owner fencing                                         | Existing restart/recovery helpers, distributed lock test fixtures    |
| Production-scale validation                 | Partially satisfied    | Representative CI fixtures exist, but production-scale rebuild, lock refresh, memory, and persistence-load evidence should run outside normal CI                                                 | Stable staging dataset, performance budget, observability dashboards |
| Continuous operational drills               | Satisfied - documented | The operational drill pack defines representative incident drills, metrics, dashboard panels, alert surfaces, and runbook responses; the execution-record register captures actual run artifacts | Observability stack, runbooks, named operators                       |
| Multi-region / advanced hosting strategy    | Partially satisfied    | Too early until single-region durable staging/prod evidence and restore rehearsal are complete                                                                                                   | Release evidence, DR evidence, cost and provider model               |

## Key Dependencies

- The durable graph persistence, startup integration, and promotion gate path is implemented; hosted release proof still requires target-environment evidence.
- The release evidence pack is now the controlling release-proof document for the nine gates.
- Contract cleanup now includes `RebuildJobListResponse` truncation semantics through `total` and `has_more`.
- Failure-mode validation should continue, but production-scale evidence should not block this docs-only reconciliation unless the release scope explicitly makes it mandatory.
- The operational drill pack now documents the representative incident matrix; the execution-record register captures live drill evidence as a separate follow-up artifact rather than a new CI surface.
- Governance changes must keep `docs/governance/state-machine-and-operating-authority.md` aligned as the current authority.

## Risks

- If hosted promotion evidence is not attached, repository tests may be mistaken for target-environment durable graph proof.
- If restore rehearsal slips, the DR gate remains manual-documentation complete but operationally unproven.
- If stale status language remains in canonical docs, future PRs will plan against obsolete roadmap assumptions.
- If follow-up contract or scale work is bundled into release evidence capture, the repository may reintroduce broad, multi-decision PRs.

## Proposed Delivery Order

1. CQ-03D-02 separately approved target, protected single-use permit, and passing hosted read-only preflight.
2. If separately ratified, exactly one permit-bound migration-history marker and its post-action evidence.
3. RC1 release evidence capture issue.
4. Staging deployment operating baseline.
5. Hosted durable promotion smoke with `--require-persistence`.
6. DR restore rehearsal and post-restore smoke evidence.
7. Production-scale validation and operational drill execution.
8. Multi-region / advanced hosting strategy.
