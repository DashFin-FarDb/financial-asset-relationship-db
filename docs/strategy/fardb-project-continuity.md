# FarDB Project Continuity Ledger

**Repository:** `DashFin-FarDb/financial-asset-relationship-db`
**Established:** 2026-07-21
**Repository evidence cutoff:** `main` at `74c5451acbb462b2a5923eaac1d600f780824e07`
**Continuity status:** Initial ledger landed; reconciled to post–H-P1-02 `main`

This ledger preserves durable project decisions, plans, milestones, and handoffs across ChatGPT, Codex, and
repository work. It is an index of authoritative evidence, not a replacement for detailed specifications, issues,
pull requests, ADRs, runbooks, or release evidence packs.

## Reading guide

- **Verified** means supported by current repository evidence at the stated cutoff.
- **Implemented** means delivery is evidenced but its full completion criteria or live operating proof are not yet
  independently confirmed.
- **Agreed** and **Planned** describe intent, not delivered code.
- Live release, provider, security, and deployment observations expire; recapture them for the exact artefact being
  promoted.
- When this ledger conflicts with current verified evidence, current evidence wins and this ledger must be corrected.

## Current project state

FarDB has progressed from an October 2025 financial relationship-graph prototype into a platform with durable graph
persistence, bounded FastAPI and Next.js product interfaces, a database-backed rebuild and recovery control plane,
and evidence-led release mechanisms.

The production architecture is FastAPI plus Next.js. Gradio remains a non-production research and demonstration
surface. SQLite is retained for local development and tests; hosted durable graph truth uses PostgreSQL. Product,
graph, and coordination state are logically separated, while shared hosted boundaries require explicit evidence and
approval.

Repository-level enterprise-readiness implementation is substantially complete, and RC1 has an approved evidence
record for its identified June 2026 release commit. That evidence does not automatically approve later commits. The
current release posture remains artefact-specific and requires fresh hosted, security, operator, authorization, and
recovery evidence.

At the evidence cutoff:

- `main` resolves to `74c5451acbb462b2a5923eaac1d600f780824e07` (includes H-P0 foundation gates PR #1506,
  H-P1-01 PR #1508, and H-P1-02 PR #1509).
- Open PR #1510 lands H-P1-03 (`post-recovery-readiness.yml`); treat it as in-flight until merged.
- Database authorization remains release-blocking until the target environment passes ADR 0007's automated and
  manual exit criteria with restricted evidence and a public redacted result (H-P0-04 Partially satisfied).
- Production-scale capacity, repeated immutable promotion, and domain-neutral reuse remain unproven.

Primary authorities:

- [Enterprise Readiness Index](../enterprise-readiness-index.md)
- [Current State of FarDB](current-state.md)
- [Claims and Truth Policy](claims-and-truth-policy.md)
- [Release Evidence Pack](../release-evidence-pack.md)
- [State Machine and Operating Authority](../governance/state-machine-and-operating-authority.md)
- [The Big Read](the-big-read.md)

## Active commitments

### FPC-2026-07-21-01 — Close the hosted database authorization gate

- **Type:** Security / release blocker
- **Status:** Blocked
- **Decision or objective:** Enforce and prove the deny-by-default hosted PostgreSQL authorization boundary defined
  by ADR 0007.
- **Rationale and constraints:** Database reachability, durability, and application authentication do not prove
  least-privilege database authorization. Changes must be staged, rollback-tested, and kept out of public evidence at
  object-level detail.
- **Repository scope:** `docs/adr/0007-database-authorization-boundary.md`,
  `scripts/check_database_authorization.py`, provider configuration, restricted closure evidence, release record.
  Workflow wiring exists in `release-evidence-verify.yml`, `staging-promotion.yml`, and `production-promotion.yml`
  (H-P0-04 Partially satisfied). Assert-path `hardening_tier=P0` fails closed when DB authz is skipped; staging,
  production, and release-evidence authz steps fail closed when any required boundary secret is missing
  (asset-graph, auth/app or postgres fallback, and coordination). Operator setup path:
  `docs/runbooks/database-authorization-closure.md`,
  `docs/evidence-records/templates/db-authz-*.md`,
  `.github/ISSUE_TEMPLATE/database_authorization_closure.md`.
- **Dependencies or blockers:** Live inventory; least-privilege role and policy design; negative tests; application,
  recovery, and restore regression proof; provider advisers; credential review; operator approval; Environment secrets
  for staging/production promotion paths.
- **Evidence and provenance:** ADR 0007 is accepted and the bounded checker was merged through PR #1482. Fail-closed
  Assert-path wiring landed through PR #1518. The ADR explicitly says that it does not mutate the live database or
  close the gate without target-environment evidence.
- **Next action and completion test:** Open a `[DB AUTHZ]` closure issue from the template, complete the restricted
  worksheet offline, configure GitHub Environment secrets, execute ADR 0007's remediation sequence against staging,
  dispatch staging-promotion (or release-evidence with `hardening_tier=P0`), and attach a redacted
  `db_authz: PASS|<opaque-workflow-run-or-artifact-id>` showing every exit criterion is satisfied or a named,
  time-bounded exception is approved.
- **Last updated:** 2026-07-22

### FPC-2026-07-21-02 — Prove release repeatability for the exact artefact

- **Type:** Release / operations
- **Status:** Planned
- **Decision or objective:** Bind hosted promotion, scanner, operator, rollback, and restore evidence to the exact
  immutable release artefact under consideration.
- **Rationale and constraints:** RC1 proves an identified earlier candidate, not every later commit. Repository CI and
  bounded health do not prove hosted durable graph truth.
- **Repository scope:** `docs/release-evidence-pack.md`, `docs/release-checklist.md`,
  `.github/workflows/release-evidence-verify.yml`, hosted-readiness tooling and evidence records;
  `staging-promotion.yml` / `production-promotion.yml` (H-P1-02); post-recovery re-smoke (H-P1-03 / PR #1510).
- **Dependencies or blockers:** Selected release SHA; target environment; database authorization closure; named
  operators; fresh hosted and restore outputs.
- **Evidence and provenance:** The current-state strategy and enterprise-readiness index both preserve fresh-evidence
  requirements for later releases. Hardening automation through H-P1-02 is on `main`; H-P1-03 is open as PR #1510.
- **Next action and completion test:** Promote the same immutable artefact through the governed path and obtain a
  complete evidence ledger with durable persisted startup, scanner review, operator sign-off, rollback, and restore
  proof.
- **Last updated:** 2026-07-21

### FPC-2026-07-21-03 — Establish a measured capacity and resilience envelope

- **Type:** Roadmap
- **Status:** Planned
- **Decision or objective:** Define the workload, failure, latency, memory, connection, rebuild, lock, and cost envelope
  FarDB can support before making production-scale claims.
- **Rationale and constraints:** Representative CI fixtures exist, but the repository does not prove million-node or
  million-edge operation, sustained production load, dense-view limits, or realistic concurrency and cost.
- **Repository scope:** `docs/testing/operational-drill-and-scale-validation-pack.md`, observability assets, staging
  datasets, benchmark and fault harnesses.
- **Dependencies or blockers:** Stable staging dataset; performance budget; observability dashboards; named operators;
  release-safe test boundaries.
- **Evidence and provenance:** Verified as an open proof in the current-state strategy, enterprise roadmap, validation
  audit, and Big Read.
- **Next action and completion test:** Approve representative workload tiers, run bounded production-shaped tests
  outside normal CI, and record reproducible p50/p95/p99, rebuild, persistence, lock, memory, connection, and cost
  results with explicit limits.
- **Last updated:** 2026-07-21

### FPC-2026-07-21-04 — Ratify the governed relationship-assertion contract

- **Type:** Product architecture
- **Status:** Planned
- **Decision or objective:** Decide and document the lifecycle that distinguishes propositions, evidence, assertions,
  determinations, projections, corrections, supersession, authority, purpose, and time.
- **Rationale and constraints:** This is the proposed differentiating semantic core. It must not be represented as a
  current capability merely because the existing graph and governance foundations make it plausible.
- **Repository scope:** Strategy documents, future ADR or specification, canonical domain model, conformance tests and
  later domain adapters.
- **Dependencies or blockers:** Domain admission criteria; bitemporal and evidence-custody decisions; expert review;
  database authorization and release proof.
- **Evidence and provenance:** Classified as `NEXT` or `RESEARCH` by the accepted claims taxonomy and current-state
  strategy; not implemented as a complete governed lifecycle.
- **Next action and completion test:** Ratify a narrow contract through one decision-scoped ADR/specification and prove
  it first in the financial domain with lifecycle and invariant tests.
- **Last updated:** 2026-07-21

### FPC-2026-07-21-05 — Prove domain generality without weakening the core

- **Type:** Product roadmap
- **Status:** Deferred
- **Decision or objective:** Demonstrate a second expert-led domain through a versioned adapter or domain pack without
  changing the canonical core for domain-specific convenience.
- **Rationale and constraints:** Medical research, supply chains, patents, workforce, benefits, banking liabilities,
  and generic relationship analysis are potential applications, not current product claims.
- **Dependencies or blockers:** Governed assertion contract; domain-admission test; conformance fixtures; privacy and
  authorization model; design partner and expert review.
- **Evidence and provenance:** Strategy documents classify cross-domain reuse as a future proof and explicitly reject
  current claims of a complete multi-domain suite or industry standard.
- **Next action and completion test:** After the assertion contract is ratified, select one bounded reference domain and
  show measurable expert workflow value with no unplanned canonical-core changes.
- **Last updated:** 2026-07-21

## Decision and delivery record

### FPC-2025-10-26-01 — Financial relationship prototype becomes a versioned project

- **Type:** Milestone
- **Status:** Verified
- **Decision or objective:** Establish the financial asset relationship database as a repository-backed engineering
  project following the October 2025 working prototype.
- **Evidence and provenance:** Repository history and the milestone chronology in `docs/strategy/the-big-read.md` record
  the initial commit on 2025-10-26, followed by 2D/3D visualization and formulaic-analysis work and early Vercel,
  Next.js, and FastAPI integration.
- **Last updated:** 2026-07-21

### FPC-2026-04-17-01 — FastAPI and Next.js declared the production architecture

- **Type:** Architecture decision
- **Status:** Verified
- **Decision or objective:** Treat FastAPI plus Next.js as the production product path and Gradio as non-production.
- **Rationale and constraints:** Prevent prototype and demonstration surfaces from acquiring production authority or
  diverting enterprise-readiness work.
- **Evidence and provenance:** [ADR 0001](../adr/0001-production-architecture.md), accepted 2026-04-17; reinforced by
  `AGENTS.md` and repository automation policy.
- **Last updated:** 2026-07-21

### FPC-2026-04-30-01 — PostgreSQL selected for hosted durability

- **Type:** Architecture decision
- **Status:** Verified
- **Decision or objective:** Use PostgreSQL for hosted durable state while preserving SQLite compatibility for local
  development and tests.
- **Rationale and constraints:** Hosted graph truth cannot depend on process memory or an ephemeral filesystem.
- **Evidence and provenance:** [ADR 0002](../adr/0002-hosted-deployment-and-persistence.md), adopted 2026-04-30.
- **Last updated:** 2026-07-21

### FPC-2026-05-01-01 — Hosted readiness and durable graph round-trip foundations

- **Type:** Milestone
- **Status:** Verified
- **Decision or objective:** Separate liveness from readiness, add hosted smoke checking, support PostgreSQL URL
  handling, and prove graph save/load fidelity including stale-row removal and legacy relationship expansion.
- **Repository scope:** PRs #1096, #1100, #1103, #1107, #1108, #1114, and #1119.
- **Evidence and provenance:** [Enterprise Readiness Index](../enterprise-readiness-index.md),
  [roadmap](../roadmap/enterprise-readiness-roadmap.md),
  [audit](../audits/enterprise-readiness-audit.md), repository tests, and merged history.
- **Last updated:** 2026-07-21

### FPC-2026-05-15-01 — Rebuild and recovery control plane made explicit

- **Type:** Architecture / milestone
- **Status:** Verified
- **Decision or objective:** Move rebuild operations behind authenticated operator authority, persisted job state,
  structured audit events, metrics, failure detection, recovery gating, and deterministic reconciliation plans.
- **Repository scope:** PRs #1141, #1144, #1155, #1157, #1161, #1167, #1169, and #1193.
- **Rationale and constraints:** Ambiguous mutation and recovery authority must fail closed; stale workers cannot retain
  write authority.
- **Evidence and provenance:** Current code and tests, the state-machine authority, enterprise audit, and Big Read
  chronology.
- **Last updated:** 2026-07-21

### FPC-2026-06-15-01 — Distributed cancellation and stale-writer integrity hardened

- **Type:** Milestone
- **Status:** Verified
- **Decision or objective:** Require `execution_id` ownership for rebuild mutations, cancellation checks in processing
  loops, lock-loss fencing, heartbeats, and fail-closed recovery behavior.
- **Repository scope:** Stage 5C work through PR #1255 and supporting integration tests.
- **Evidence and provenance:** `AGENTS.md`, state-machine authority, current implementation and validation audit.
- **Last updated:** 2026-07-21

### FPC-2026-06-25-01 — Enterprise-readiness remediation sequence reconciled

- **Type:** Audit / milestone
- **Status:** Verified
- **Decision or objective:** Close the highest-value repository implementation gaps without reopening architecture:
  persistence, startup/reload, promotion proof, API contracts, recovery, distributed hosting, failure-mode validation,
  security/governance documentation, DR documentation, and release evidence.
- **Repository scope:** PRs #1287 through #1301 and their canonical audit, roadmap, board, checklist, and evidence pack.
- **Rationale and constraints:** Durable persistence gates restart, promotion, and DR; one PR equals one decision.
- **Evidence and provenance:** [Enterprise Readiness Index](../enterprise-readiness-index.md),
  [audit](../audits/enterprise-readiness-audit.md),
  [roadmap](../roadmap/enterprise-readiness-roadmap.md),
  [PR board](../roadmap/enterprise-readiness-pr-board.md), and merged implementation.
- **Last updated:** 2026-07-21

### FPC-2026-06-27-01 — Release evidence became a canonical operating discipline

- **Type:** Governance / milestone
- **Status:** Verified
- **Decision or objective:** Map each release gate to exact automated evidence, target-environment proof, manual
  artifacts, redaction rules, operator ownership, and blocker semantics.
- **Repository scope:** Issues and follow-ups #1302 through #1318; operational evidence framework; hosted-readiness
  guide; release-candidate and drill templates; DR and scale-validation packs.
- **Evidence and provenance:** Committed documents and evidence templates linked from the enterprise-readiness index.
- **Last updated:** 2026-07-21

### FPC-2026-06-29-01 — Hosted startup fallback and degraded boot behavior corrected

- **Type:** Architecture / incident follow-up
- **Status:** Verified
- **Decision or objective:** Resolve hosted graph persistence consistently, allow narrowly scoped degraded boot for the
  hosted fallback boundary, and preserve strict fail-fast behavior for local or explicitly dedicated persistence.
- **Rationale and constraints:** Liveness recovery must not be mistaken for persisted graph truth; the strict promotion
  gate remains separate.
- **Repository scope:** PR #1337 for hosted graph URL resolution and PR #1339 for hosted degraded startup behavior.
- **Evidence and provenance:** Merged PR descriptions, implementation, and regression tests.
- **Last updated:** 2026-07-21

### FPC-2026-06-29-02 — RC1 durable release evidence approved

- **Type:** Release milestone
- **Status:** Verified
- **Decision or objective:** Capture an auditable release record for RC1 / Objective 2 follow-up.
- **Evidence and provenance:** [RC1 evidence record](../evidence-records/rc1-objective-2-follow-up.md) identifies release
  commit `c54323552e44032c79f99d377b0881a1ddaf6368`, reports CI success, persisted hosted startup with 19 assets and
  73 relationships, scanner review, named operators, and a passed restore rehearsal. The record marks the candidate
  approved.
- **Constraints:** This is candidate-specific evidence, not approval of later commits or a production-scale
  certificate.
- **Last updated:** 2026-07-21

### FPC-2026-07-15-01 — Claim taxonomy adopted

- **Type:** Governance / strategy decision
- **Status:** Verified
- **Decision or objective:** Classify material claims as `CURRENT`, `NEXT`, `RESEARCH`, `ASPIRATION`, or `EXCLUDED`,
  and tie current claims to dated evidence.
- **Rationale and constraints:** Prevent strategy, research, or future domain potential from being represented as
  implemented capability.
- **Evidence and provenance:** PR #1477 merged on 2026-07-15; `docs/strategy/claims-and-truth-policy.md`, current-state
  strategy, and Big Read use the taxonomy.
- **Last updated:** 2026-07-21

### FPC-2026-07-19-01 — Hosted database authorization contract accepted

- **Type:** Security architecture decision
- **Status:** Implemented
- **Decision or objective:** Make FastAPI the only product ingress to canonical database state; revoke unintended
  untrusted provider-role authority; separate application, migration, recovery, and administrative authority; and
  verify the boundary with bounded tooling and restricted evidence.
- **Evidence and provenance:** [ADR 0007](../adr/0007-database-authorization-boundary.md) and
  `scripts/check_database_authorization.py`, merged through PR #1482 on 2026-07-19.
- **Constraints:** The contract and checker are implemented, but live target-environment closure is not verified by the
  public repository evidence reviewed for this ledger.
- **Next action and completion test:** See FPC-2026-07-21-01.
- **Last updated:** 2026-07-21

### FPC-2026-07-20-01 — Dependency and CI guardrails repaired after automated updates

- **Type:** Maintenance milestone
- **Status:** Verified
- **Decision or objective:** Preserve reproducible frontend installs and CI validation after automated dependency
  updates.
- **Evidence and provenance:** Main includes PRs #1492, #1493, #1497, #1499, #1504, and #1505, covering workflow lint
  and pin guards, the TypeScript 5.9 / ESLint 9 compatibility baseline, Super-Linter Checkov/actionlint handling,
  follow-up lifecycle documentation, native libc lockfile filters, and post-restore constraint verification.
- **Constraints:** These repairs preserve the baseline; they do not change the strategic release gates.
- **Last updated:** 2026-07-21

### FPC-2026-07-21-06 — Hardening P0 foundation and P1 promotion automation landed

- **Type:** Milestone
- **Status:** Verified
- **Decision or objective:** Automate hardening backlog P0 foundation gates and the first P1 promotion proofs without
  claiming live authorization or DR rehearsal closure.
- **Repository scope:**
  - PR #1506 — P0 foundation gates (`cabb8222` lineage on `main`)
  - PR #1508 — H-P1-01 `--assets-smoke` with `--require-persistence` (`5c507f6c`)
  - PR #1509 — H-P1-02 `production-promotion.yml` twin (`74c5451a`)
- **Evidence and provenance:** Merged history on `main`; evidence pack / board rows for H-P1-01 and H-P1-02 marked
  Satisfied - automated. H-P0-04 remains Partially satisfied pending target-environment redacted PASS.
- **In flight:** PR #1510 — H-P1-03 post-recovery readiness re-smoke dispatch recipe + artifacts.
- **Last updated:** 2026-07-21

## Deferred work

| Item                                       | Status   | Reactivation condition                                                                  |
| ------------------------------------------ | -------- | --------------------------------------------------------------------------------------- |
| Multi-region or advanced hosting topology  | Deferred | Single-region durable release and restore behavior is repeatable, measured, and costed. |
| Specialist graph engine                    | Deferred | A measured workload crosses an agreed PostgreSQL or in-memory projection threshold.     |
| Multi-tenancy and jurisdictional isolation | Deferred | A bounded product/domain requirement and authorization model are approved.              |
| Federated evidence verification            | Deferred | Assertion contract, evidence custody, and partner requirements are proven.              |
| Offline or crisis operational profile      | Deferred | Separate safety case, product need, and certification envelope exist.                   |
| Formal standards claim                     | Deferred | At least two domains and an external conformance implementation demonstrate adoption.   |
| Residual frontend mock typing cleanup      | Deferred | Convert opportunistically when the affected tests are next edited.                      |

## Open questions and conflicts

1. **Database authorization closure:** The accepted ADR and checker establish the contract, and promotion/RC workflows
   can invoke the checker, but public repository evidence does not establish that live remediation, negative tests,
   rollback, credential review, and provider-adviser checks all passed. Treat the gate as blocked until target
   evidence says otherwise (FPC-2026-07-21-01 / H-P0-04).
2. **Current-release identity:** RC1 is approved for its June 2026 SHA. No later SHA inherits that approval. Select the
   next immutable candidate before claiming a current enterprise release.
3. **Documentation freshness:** The [Enterprise Readiness Index](../enterprise-readiness-index.md) dated 2026-07-15
   predates PR #1482 and the 2026-07-20 through 2026-07-21 hardening sequence. Reconcile its implementation inventory
   when the next release record is prepared.
4. **Tracker vs ledger:** Active commitments in this ledger may outlive or precede open GitHub issues/PRs. Empty or
   sparse trackers are not evidence that release gates are satisfied.
5. **Product category decision:** The governed assertion model is a recommended next decision, not yet an accepted ADR
   or current platform capability.

## Agent-ready handoff

### Current verified state

- Production path: FastAPI plus Next.js; Gradio non-production.
- Hosted durability: PostgreSQL; SQLite retained locally.
- Durable graph load, startup provenance, promotion checking, recovery control plane, API contracts, governance, DR
  documentation, and release-evidence mechanisms exist in the repository.
- RC1 has candidate-specific approved hosted and restore evidence.
- `main` is `74c5451acbb462b2a5923eaac1d600f780824e07` at this cutoff (H-P0 foundation, H-P1-01, H-P1-02 merged).
- PR #1510 (H-P1-03 post-recovery re-smoke) is open at ledger update time.

### Governing constraints

- One PR equals one decision.
- Verify branch, ref, PR, and merge state before reviewing or changing work.
- Durable persistence gates restart, promotion, and DR.
- Bounded health is not durable graph truth.
- Ambiguous mutation and recovery authority fails closed.
- Current claims require dated evidence; future strategy must remain labelled.
- Never expose credentials, live topology, raw provider findings, or restricted authorization evidence.

### Next highest-value action

Close FPC-2026-07-21-01 using the repository operator path
([database-authorization-closure runbook](../runbooks/database-authorization-closure.md)): configure Environment
secrets, complete the restricted worksheet offline, remediate staging, dispatch the fail-closed authz workflow, and
attach a public redacted `db_authz: PASS|<opaque-ref>`. This remains the nearest release blocker. Repository
Assert-path fail-closed wiring for skipped DB authz does not substitute for a live redacted
`db_authz: PASS|<opaque-ref>`.

### Completion test

The authorization checker passes every configured hosted boundary; manual privileged-function review, negative access
tests, rollback, application/recovery/restore regression checks, provider advisers, credential review, and redacted
operator sign-off are complete; and no unresolved high-severity access-control finding remains without a named,
time-bounded exception.

## Backfill coverage and gaps

### Sources reviewed

- Repository `main` through `74c5451acbb462b2a5923eaac1d600f780824e07` on 2026-07-21.
- Repository agent instructions and production-architecture declaration.
- Enterprise-readiness index, audit, roadmap, PR board, validation-gap audit, release checklist, release evidence pack,
  hosted staging baseline, operational evidence framework, drill and scale-validation documents, and risk register.
- ADRs and governance authorities referenced by those indices, including ADRs 0001, 0002, 0005, 0006, and 0007.
- RC1 committed evidence record and its repository companion issue record.
- Current-state strategy, claims taxonomy, and Big Read chronology.
- Merged hardening PRs #1506, #1508, #1509 and open PR #1510.
- Available ChatGPT continuity context covering the enterprise-readiness program, PR #1096 onward, RC1 evidence work,
  hosted startup incidents, audit completion, and agreed future-work discussions.

### Confidence limits

- Earlier conversation context was used to locate and organize decisions, not to prove implementation.
- The ledger does not reproduce every PR, issue, review comment, CI run, or conversation.
- Live Supabase, Vercel, scanner, and authorization state was not independently re-executed for this update.
- Restricted security and provider evidence was intentionally not accessed or recorded.
- RC1 evidence is accepted as a committed candidate-specific record; its live artifacts were not recaptured.
- Dates for grouped implementation phases are representative ledger anchors; individual PR merge dates remain
  authoritative in GitHub.

### Maintenance rule

Update this ledger whenever a FarDB discussion produces an agreed plan, architecture or governance decision, audit
conclusion, roadmap change, material blocker, milestone, handoff, or completion claim. Reconcile existing entries
instead of appending duplicates, and require repository or target-environment evidence before advancing an item to
`Implemented` or `Verified`.
