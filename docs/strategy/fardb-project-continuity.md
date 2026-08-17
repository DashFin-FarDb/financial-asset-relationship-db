# FarDB Project Continuity Ledger

**Repository:** `DashFin-FarDb/financial-asset-relationship-db`
**Established:** 2026-07-21
**Repository evidence cutoff:** `main` at `76f1194f1f9b83cb9ed8f0bb0083824ededbe0ae`
**Continuity status:** CQ-03B-R1 ratified on 2026-08-17; ADR 0010 records the adjudication and R2 is next after merge

This ledger preserves durable project decisions, plans, milestones, and handoffs across ChatGPT, Codex, and
repository work. It is an index of authoritative evidence, not a replacement for detailed specifications, issues,
pull requests, ADRs, runbooks, or release evidence packs.

## Reading guide

- **Verified** means supported by current repository evidence at the stated cutoff.
- **Implemented** means delivery is evidenced but its full completion criteria or live operating proof are not yet
  independently confirmed.
- **Satisfied** means the commitment's stated completion test is met by current cited evidence for its declared scope;
  provider rollout or production qualification remains separate unless the entry explicitly includes it.
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

- PR [#1608](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1608) merged from final reviewed
  head `743ce9254ca0fdb20805a789e4082c2891053109` as GitHub-verified squash
  `1a49cee56255ec4f50495fa9bdd80ddd3f8f6763` on `main`.
- The final exact-head CI run passed PostgreSQL 16 GRAC/authority, PostgreSQL 15 compatibility, Python 3.10–3.12,
  and security jobs. The PostgreSQL 16 job executed the membership and authority regressions rather than skipping
  them.
- PR #1598 records named human sign-off and exact-SHA staging evidence for candidate
  `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`.
- GRAC runtime capability is `CURRENT` only for the evidenced staging slice
  `financial.bond.issuer_reference@1::financial_graph_current_view`. Production certification, capacity, and
  broader generality remain `NEXT`.
- CQ-01/CQ-02 are closed at repository and exact-head CI scope.
- QH-01 is closed at repository/configuration scope through merged PR #1632 and verified squash
  `5b2685c5ff0635cfd586798cbe2df33a33145216`. Later generated knowledge-branch pushes were canceled at Vercel's
  verified-commit gate, so they do not independently prove that `ignoreCommand` executed. A signed or otherwise
  eligible controlled probe remains an operational evidence item, not a repository blocker.
- The non-authoritative DeepSource timeout/configuration contexts were explicitly accepted as non-blocking; #1631
  closed as not planned without source repair or threshold weakening.
- CQ-03A completed through merged PR #1634 and accepted ADR 0009 under GitHub #1633 and Linear DAS-62. The later
  CQ-03B receipt/dependency conflict was ratified as CQ-03B-R1 on 2026-08-17 and is recorded by ADR 0010: exact
  provider statements remain immutable evidence, clean builds use new forward-dated component baselines, targets
  select explicit auth, graph, coordination, or combined profiles, and hosted-history adoption remains blocked until
  CQ-03D. The controlling commitment is FPC-2026-08-13-01. Provider rollout, production
  promotion and recovery evidence remain artefact-specific; production scale, repeated immutable promotion, and
  domain-neutral reuse remain unproven.

Primary authorities:

- [Enterprise Readiness Index](../enterprise-readiness-index.md)
- [Agent Task Entry Route](../agent-task-entry.md)
- [Historical Current State of FarDB](current-state.md)
- [Claims and Truth Policy](claims-and-truth-policy.md)
- [Release Evidence Pack](../release-evidence-pack.md)
- [State Machine and Operating Authority](../governance/state-machine-and-operating-authority.md)
- [PostgreSQL migration ledger and drift contract](../adr/0009-postgresql-migration-ledger-and-drift-contract.md)
- [Historical receipt evidence and target-ledger profiles](../adr/0010-historical-receipt-evidence-and-target-ledger-profiles.md)
- [Governed Relationship Assertion Contract v1](../governance/governed-relationship-assertion-contract-v1.md)
- [GRAC v1 exact-SHA staging evidence and sign-off](../governance/grac-v1-exact-sha-evidence-signoff.md)
- [The Big Read](the-big-read.md)

## Active commitments

### FPC-2026-08-13-01 — Establish one profile-scoped PostgreSQL migration authority and drift gate

- **Type:** Database architecture / production qualification blocker
- **Status:** Agreed — ADR 0009 accepted; CQ-03B-R1 ratified on 2026-08-17 and recorded by ADR 0010; R2 next after
  this record merges
- **Decision or objective:** Keep one repository-owned PostgreSQL schema authority while composing immutable auth,
  graph, and coordination component ledgers through one target-profile manifest. Preserve exact provider
  `statements[]` as lineage evidence, build clean targets from new forward-dated baselines, and retain ADR 0009's
  fail-closed drift and verify-only runtime contracts.
- **Rationale and constraints:** Read-only evidence confirms six provider receipt identities, but later receipts
  depend on objects not created by the earlier recorded chain. Reusing historical timestamps for reviewed SQL would
  manufacture provenance; replaying the recorded chain would not build clean state. Distinct database capabilities
  also must not receive a universal schema. No hosted schema, migration history, credential, provider link state, or
  production target may change in CQ-03B/C.
- **Repository scope:** ADR 0009 as amended by ADR 0010, GitHub #1633, Linear DAS-62, and the Notion work programme.
  Canonical SQL belongs under `supabase/ledgers/<component>/migrations/`; `supabase/ledger-profiles.json` is the sole
  composition authority. `fresh-v1` and non-executable `hosted-legacy-v1` lineage records explain truthful target
  history without creating a second schema authority.
- **Dependencies or blockers:** CQ-03B-R2 may start only after the R1 record merges. It must prove PostgreSQL 15/16
  profile rebuilds, deterministic combined ordering, identity/hash immutability, target/profile conflict rejection,
  and negative hosted-write barriers. CQ-03D retains separate human approval and a single-use permit bound to exact
  SHA, profile, target fingerprint, digest, and one timestamp.
- **Evidence and provenance:** merged CQ-03A PR #1634 and squash
  `2dd9f64136eb653284b0f5330a16ee99f6b0b491`; merged clarification PR #1636 and exact current
  `main@76f1194f1f9b83cb9ed8f0bb0083824ededbe0ae`; read-only provider receipt and current Supabase CLI-documentation
  review; explicit human ratification on 2026-08-17; GitHub #1633; Linear DAS-62.
- **Next action and completion test:** After this continuity record and ADR 0010 merge, execute CQ-03B-R2 against the
  ratified decision as one bounded implementation unit. R2 closes only when every clean target profile and combined
  union rebuild on PostgreSQL 15/16 and hosted-write attempts fail before CQ-03D. CQ-03C adds profile-aware deliberate
  drift failures;
  CQ-03D remains separately approved.
- **Last updated:** 2026-08-17

### FPC-2026-08-09-01 — Separate migration and runtime database authority

- **Type:** Security / production qualification blocker
- **Status:** Satisfied — repository implementation and exact-head PostgreSQL 15/16 evidence; provider rollout and
  production qualification remain separate
- **Decision or objective:** Make database mutation and credential bootstrap an explicit operator action, then require
  verify-only startup under restricted runtime credentials that exclude `ADMIN_PASSWORD` and schema-migration
  authority.
- **Rationale and constraints:** ADR 0007 requires distinct application and migration authority. Preserve the custom
  synchronous migration path and SQLite compatibility; do not introduce Alembic, provider-led schema authority,
  dependency changes, or implicit startup repair.
- **Repository scope:** `scripts/migrate_database.py`, startup and database compatibility verification, runtime
  settings, production/container gates, launchers, focused tests, migration-authority runbooks, and the canonical
  operating-authority record merged through PR #1608.
- **Dependencies or blockers:** Repository closure is no longer blocked. Any target-environment rollout still requires
  the documented superuser-owned capability-role bootstrap, explicit operator migration, restricted login binding,
  and fresh target-specific startup, authorization, promotion, rollback, and recovery evidence. Repository code does
  not create provider credentials or mutate provider configuration.
- **Evidence and provenance:** User ratification on 2026-08-09; merged
  [PR #1608](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1608), final reviewed head
  `743ce9254ca0fdb20805a789e4082c2891053109`, and GitHub-verified squash
  [`1a49cee56255ec4f50495fa9bdd80ddd3f8f6763`](https://github.com/DashFin-FarDb/financial-asset-relationship-db/commit/1a49cee56255ec4f50495fa9bdd80ddd3f8f6763).
  [Final CI](https://github.com/DashFin-FarDb/financial-asset-relationship-db/actions/runs/31684943008) passed the
  PostgreSQL 16 GRAC/authority and PostgreSQL 15 compatibility jobs, Python 3.10–3.12, and security jobs. The merged
  implementation supplies explicit operator migration, superuser-owned capability bootstrap, password-free
  verify-only runtime startup, restricted capability roles, exact privilege/ownership checks, and production Compose
  migration packaging.
- **Post-merge review reference:** Detailed scanner and review-thread dispositions remain in
  [PR #1608](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1608)'s review record. Issue
  [#1623](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1623) tracks the only durable
  follow-up: a bounded P2 server-side statement-timeout improvement for normal PostgreSQL request connections.
- **Next action and completion test:** Treat CQ-01/CQ-02 as satisfied and follow FPC-2026-08-13-01: begin CQ-03B
  within accepted ADR 0009. Preserve CQ-03D's separate human approval before provider history mutation. Qualify
  provider rollout and production
  promotion
  separately against the exact artefact being deployed. Issue #1623 may proceed as one small P2 PR without displacing
  the CQ-03 programme.
- **Last updated:** 2026-08-13

### FPC-2026-07-21-01 — Close the hosted database authorization gate

- **Type:** Security / release blocker
- **Status:** Satisfied — staging (`db_authz: PASS|run-30002002715`; #1525 / #1528)
- **Decision or objective:** Enforce and prove the deny-by-default hosted PostgreSQL authorization boundary defined
  by ADR 0007.
- **Rationale and constraints:** Database reachability, durability, and application authentication do not prove
  least-privilege database authorization. Changes must be staged, rollback-tested, and kept out of public evidence at
  object-level detail.
- **Repository scope:** `docs/adr/0007-database-authorization-boundary.md`,
  `scripts/check_database_authorization.py`, provider configuration, restricted closure evidence, release record.
  Workflow wiring exists in `release-evidence-verify.yml`, `staging-promotion.yml`, and `production-promotion.yml`
  (H-P0-04 Satisfied for staging). Assert-path `hardening_tier=P0` fails closed when DB authz is skipped; staging,
  production, and release-evidence authz steps fail closed when any required boundary secret is missing
  (asset-graph, auth/app or postgres fallback, and coordination). Operator setup path:
  `docs/runbooks/database-authorization-closure.md`,
  `docs/evidence-records/templates/db-authz-*.md`,
  `.github/ISSUE_TEMPLATE/database_authorization_closure.md`.
- **Dependencies or blockers:** Production twin still needs its own SHA-bound authz PASS when that artefact is
  promoted. Restricted worksheet remains offline.
- **Evidence and provenance:** ADR 0007 is accepted and the bounded checker was merged through PR #1482. Fail-closed
  Assert-path wiring landed through PR #1506. The operator closure setup path (runbook, worksheets, issue template,
  per-boundary schema secrets) landed through PR #1520 (`e121b54d` on `main`). Deny-by-default migrations landed
  through PR #1526 (`8f95fad1` on `main`). Staging closure tracker [#1525](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1525)
  captured a P0 `release-evidence-verify` pass at `29991d03` with public marker
  `db_authz: PASS|run-30002002715` ([run 30002002715](https://github.com/DashFin-FarDb/financial-asset-relationship-db/actions/runs/30002002715));
  committed redacted record in PR #1528 (`docs/evidence-records/hp004-db-authz-pass-29991d03.md`). Restricted exit
  criteria, fixed-search-path review, credential/rollback review, and named sign-off completed 2026-07-24.
- **Next action and completion test:** Treat staging H-P0-04 / FPC-2026-07-21-01 as Satisfied. For production, repeat
  the SHA-bound `db_authz: PASS|<opaque-ref>` attachment against the production Environment before claiming that
  target closed.
- **Last updated:** 2026-07-24

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
  requirements for later releases. Hardening automation through H-P1-02 and H-P1-03 (PR #1510) is on `main`.
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
- **Status:** Verified — bounded exact-SHA staging slice `CURRENT`; broader capability remains `NEXT`
- **Decision or objective:** Decide and document the lifecycle that distinguishes propositions, evidence, assertions,
  determinations, projections, corrections, supersession, authority, purpose, and time.
- **Rationale and constraints:** This is the differentiating semantic core. It may be represented as current only
  inside a verified evidence boundary; plausible foundations do not justify transferring or broadening that claim.
- **Repository scope:** ADR 0008, frozen contract v1, conformance, schema, lifecycle, projection, publication, APIs,
  UI, staging proof, exact-SHA evidence, and continuity/strategy links delivered through #1532–#1540 and PR #1598.
- **Dependencies or blockers:** The bounded staging slice is proved. Production certification, capacity, a second
  predicate, and broader-domain generality remain separate gates.
- **Evidence and provenance:** User decision 2026-07-25; original contract baseline `5e457537`; reviewed implementation
  baseline `0a72dfee`; ADR 0008 Accepted; the #1532–#1540 delivery sequence completed; PR #1598 records exact-SHA
  staging evidence and sign-off for `financial.bond.issuer_reference@1::financial_graph_current_view` at
  `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`.
- **Next action and completion test:** Preserve the bounded staging claim while closing the runtime/migration-authority
  boundary and later qualifying a new exact production candidate. Do not transfer the staging approval to another
  SHA, predicate, environment, or broader capability.
- **Last updated:** 2026-08-08

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

### FARDB-GRAC-V1 — Governed Relationship Assertion Contract v1

- **Type:** Architecture and product milestone
- **Status:** Verified — bounded staging slice
- **Decision:** Make append-only governed assertions the authoritative source
  for relationship provenance, evidence, authority, time, confidence,
  lifecycle and supersession; retain the graph as a deterministic projection.
- **First proof:** `financial.bond.issuer_reference@1` complete financial
  vertical slice.
- **Constraints:** Main repository only; FastAPI + Next.js production path;
  SQLite/PostgreSQL parity; existing rebuild control plane owns publication;
  no raw evidence blobs, multi-domain expansion or graph-database migration.
- **Evidence:** User decision dated 2026-07-25; original contract baseline
  `5e45753705c10c2c4f50e0e9bc4d07b823d752ab`; reviewed implementation baseline
  `0a72dfee67aae4ef7cc44041347474a6a6e234cd`; tracker epic #1530 / children #1531–#1540; completed delivery
  sequence and exact-SHA sign-off in PR #1598; ADR 0008 Accepted; frozen contract
  [governed-relationship-assertion-contract-v1.md](../governance/governed-relationship-assertion-contract-v1.md).
- **Evidence boundary:** The
  [exact-SHA sign-off record](../governance/grac-v1-exact-sha-evidence-signoff.md) proves only
  `financial.bond.issuer_reference@1::financial_graph_current_view` in the recorded staging scope at `16d0a69c`.
- **Next action:** Close runtime/migration authority before a new exact production qualification candidate is selected.
- **Completion test:** A new candidate preserves the evidenced GRAC invariants while satisfying the separate
  production authority, recovery, dependency, quality, and promotion gates.
- **Last updated:** 2026-08-08

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
  - PR #1510 — H-P1-03 post-recovery readiness re-smoke (`21f54a42`)
- **Evidence and provenance:** Merged history on `main`; evidence pack / board rows for H-P1-01 and H-P1-02 marked
  Satisfied - automated. H-P1-03 merged via PR #1510. H-P0-04 is Satisfied for staging: redacted PASS, restricted exit
  criteria, and named sign-off recorded (#1525 / PR #1528 / PR #1529; `db_authz: PASS|run-30002002715`).
- **Last updated:** 2026-07-25

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

1. **Database authorization closure:** Staging H-P0-04 / FPC-2026-07-21-01 is Satisfied
   (`db_authz: PASS|run-30002002715` / #1525 / #1528). Production still needs its own SHA-bound authz PASS when that
   artefact is under promotion.
2. **Current-release identity:** RC1 is approved for its June 2026 SHA. No later SHA inherits that approval. Select the
   next immutable candidate before claiming a current enterprise release.
3. **Documentation freshness:** The [Enterprise Readiness Index](../enterprise-readiness-index.md) dated 2026-07-15
   predates PR #1482 and the 2026-07-20 through 2026-07-21 hardening sequence. Reconcile its implementation inventory
   when the next release record is prepared.
4. **Tracker vs ledger:** Active commitments in this ledger may outlive or precede open GitHub issues/PRs. Empty or
   sparse trackers are not evidence that release gates are satisfied.
5. **GRAC claim boundary:** ADR 0008 and the frozen contract define semantics. The
   [exact-SHA sign-off](../governance/grac-v1-exact-sha-evidence-signoff.md) supersedes earlier all-`NEXT` wording only
   for `financial.bond.issuer_reference@1::financial_graph_current_view` in the recorded staging scope. Production,
   capacity, second-predicate, and broader-domain claims remain `NEXT`.

## Agent-ready handoff

### Current verified state

- Production path: FastAPI plus Next.js; Gradio non-production.
- Hosted durability: PostgreSQL; SQLite retained locally.
- Durable graph load, startup provenance, promotion checking, recovery control plane, API contracts, governance, DR
  documentation, and release-evidence mechanisms exist in the repository.
- RC1 has candidate-specific approved hosted and restore evidence.
- `main` is `76f1194f1f9b83cb9ed8f0bb0083824ededbe0ae` at this cutoff.
- CQ-01/CQ-02 are closed through merged PR #1608 with exact PostgreSQL 15/16 authority evidence. QH-01 is closed
  through merged PR #1632. Provider rollout and production qualification remain separate evidence obligations.
- CQ-03 is the active critical-path programme. CQ-03A is complete through accepted ADR 0009 and merged PR #1634;
  CQ-03B-R1 is human-ratified and recorded by ADR 0010. Follow FPC-2026-08-13-01 and GitHub #1633 for R2 after the
  R1 record merges. Provider history adoption remains separately authorized.
- GRAC v1 is `CURRENT` only for the exact-SHA staging slice recorded by PR #1598; broader claims remain `NEXT`.

### Governing constraints

- One PR equals one decision.
- Verify branch, ref, PR, and merge state before reviewing or changing work.
- Durable persistence gates restart, promotion, and DR.
- Bounded health is not durable graph truth.
- Ambiguous mutation and recovery authority fails closed.
- Current claims require dated evidence; future strategy must remain labelled.
- Never expose credentials, live topology, raw provider findings, or restricted authorization evidence.

### Next highest-value action

Review and merge the CQ-03B-R1 ADR 0010 record under active commitment **FPC-2026-08-13-01**. Then begin R2's bounded
component-ledger, target-profile, and forward-baseline materialization without provider mutation. Do not replay or
reconstruct SQL under historical timestamps, run `supabase db pull` against hosted state, retain provider link state,
or select `hosted-legacy-v1` as adopted before CQ-03D.
Issue #1623 remains a small P2 follow-up and does not displace the CQ-03 programme. Release repeatability
(**FPC-2026-07-21-02**) remains active.

### Completion test

One declared PostgreSQL authority can build fresh auth, graph, coordination, and explicitly combined profiles from
new forward migrations, explain approved legacy history without replaying it, and detect profile-specific unrecorded
drift. CI and readiness fail clearly on drift or an unknown profile/lineage while the restricted application role
remains verify-only and cannot acquire migration, ownership, grant-management, history-adoption, or implicit
credential-bootstrap authority.

## Backfill coverage and gaps

### Sources reviewed

- Repository `main` through `76f1194f1f9b83cb9ed8f0bb0083824ededbe0ae` on 2026-08-17.
- Repository agent instructions and production-architecture declaration.
- Enterprise-readiness index, audit, roadmap, PR board, validation-gap audit, release checklist, release evidence pack,
  hosted staging baseline, operational evidence framework, drill and scale-validation documents, and risk register.
- ADRs and governance authorities referenced by those indices, including ADRs 0001, 0002, 0005, 0006, and 0007.
- RC1 committed evidence record and its repository companion issue record.
- Current-state strategy, claims taxonomy, and Big Read chronology.
- Merged hardening PRs #1506, #1508, #1509, and #1510 (H-P1-03).
- Merged GRAC foundation PRs #1541, #1542, #1549, #1550, and #1552.
- Merged CQ-01/CQ-02 PR #1608, its final exact-head CI, and post-merge review-thread disposition.
- Merged QH-01 PR #1632 and Linear DAS-63; closed external-quality record #1631; active CQ-03 programme record #1633,
  merged CQ-03A PR #1634, accepted ADR 0009, merged clarification PR #1636, ratified ADR 0010, and Linear DAS-62.
- Read-only Supabase aggregate inventory and migration history captured on 2026-08-13 and revalidated at bounded
  identity/status scope on 2026-08-17; current Supabase CLI workflow documentation reviewed; no provider mutation.
- Available ChatGPT continuity context covering the enterprise-readiness program, PR #1096 onward, RC1 evidence work,
  hosted startup incidents, audit completion, and agreed future-work discussions.

### Confidence limits

- Earlier conversation context was used to locate and organize decisions, not to prove implementation.
- The ledger does not reproduce every PR, issue, review comment, CI run, or conversation.
- Supabase schema and migration history were inspected read-only at aggregate scope; no schema, history, role,
  credential, project, deployment, Vercel, scanner, or authorization mutation was performed.
- Restricted provider payload content was used only for bounded classification and adjudication; it was not copied
  into this public ledger. Exact protected evidence remains outside the repository.
- RC1 evidence is accepted as a committed candidate-specific record; its live artifacts were not recaptured.
- Dates for grouped implementation phases are representative ledger anchors; individual PR merge dates remain
  authoritative in GitHub.

### Maintenance rule

Update this ledger whenever a FarDB discussion produces an agreed plan, architecture or governance decision, audit
conclusion, roadmap change, material blocker, milestone, handoff, or completion claim. Reconcile existing entries
instead of appending duplicates, and require repository or target-environment evidence before advancing an item to
`Implemented` or `Verified`.
