# ADR 0009: Repository-owned PostgreSQL migration ledger and drift contract

## Status

**Accepted — ratified through reviewed PR #1634.**

This ADR records the accepted CQ-03 migration and drift boundary. It authorizes the repository-only CQ-03B and
CQ-03C implementation phases within this contract. It does not authorize Supabase migration-history changes, hosted
schema changes, credential changes, production promotion, or CQ-03D history adoption without its separate approval.

## Date

2026-08-13

## Decision owner and ratifier

- Decision owner: FarDB maintainers
- Human ratifier: Mohamed Abdel-Aziz Mohamed
- Control records: [GitHub #1633](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1633)
  and [Linear DAS-62](https://linear.app/dashfin/issue/DAS-62/cq-03-establish-postgresql-migration-ledger-and-drift-gate)
- Setup baseline: `main@5b2685c5ff0635cfd586798cbe2df33a33145216`
- Model and reasoning: GPT-5.6 Sol / max

## Context

CQ-01/CQ-02 separated runtime and migration authority and made FastAPI startup verify-only. They deliberately did
not choose a durable PostgreSQL migration ledger or reconcile historical provider state.

Read-only evidence captured on 2026-08-13 shows the scale of the reconciliation problem without publishing live
object identities:

- the hosted PostgreSQL service is healthy and currently reports PostgreSQL 17;
- the exposed `public` schema contains 22 tables, all with RLS enabled;
- the aggregate catalog contains 197 columns, 65 constraints, 71 indices, 45 policies, 21 user triggers, and
  2 functions;
- the provider migration history contains six timestamped records;
- the repository currently mixes SQLite-oriented SQL files, two PostgreSQL authorization SQL files,
  SQLAlchemy `create_all`, imperative PostgreSQL repair helpers, and provider-recorded migrations.

Those mechanisms are useful historical inputs, but together they are not one replayable PostgreSQL authority.
A clean database cannot currently be shown to converge from one declared ledger, and equal migration-history
timestamps do not by themselves prove equal schema state.

The runtime boundary from ADR 0007 remains fixed: normal FastAPI request handling must not receive DDL, ownership,
role creation, grant management, migration-history repair, or credential-bootstrap authority.

## Decision

### 1. One repository authority

Adopt immutable, timestamped PostgreSQL SQL migrations under `supabase/migrations/` as the sole PostgreSQL schema
ledger.

The repository files are authoritative. The provider table
`supabase_migrations.schema_migrations` is an execution receipt and synchronization surface, not an independent
design authority. Dashboard edits, SQL-editor edits, ORM metadata, runtime compatibility checks, generated dumps,
and a provider's current catalog do not become migrations until reviewed SQL is committed to this ledger.

Use the standard 14-digit UTC timestamp plus a descriptive snake_case name:

```text
supabase/migrations/YYYYMMDDHHMMSS_descriptive_name.sql
```

Only the timestamp determines migration identity and execution order. The descriptive filename stem is immutable
manifest metadata after application: it does not affect identity or ordering, but renaming it changes provenance and
therefore fails the immutable-file check. Physical directory, API, and diff-display order are irrelevant.

### 2. Imperative migrations first

Use imperative SQL migrations for adoption and the initial CQ-03 implementation.

Do not introduce a parallel declarative `supabase/schemas/` representation during baseline adoption. Supabase's
existing-project workflow treats the pulled migration as the baseline; maintaining declarative schemas at the same
time would create a second representation before the historical ledger is stable.

A later ADR may adopt declarative schema authoring if it proves a net benefit after the ledger, rebuild, and drift
gate are working.

### 3. Supabase tooling is operator/CI tooling

Use the Supabase CLI to fetch provider-recorded migration files, compare local and remote history, build a fresh
local Supabase database, preview remote application, and perform an explicitly approved history repair.

It is an operator and CI dependency only. It must not enter the FastAPI runtime dependency set or run during
application startup.

The controlling commands and their intended roles are:

- `supabase migration fetch` — read provider-recorded migration files into a temporary review workspace;
- `supabase migration list` — compare repository timestamps with provider receipts;
- `supabase db pull` — generate a candidate reconciliation migration from read-only hosted state;
- `supabase db reset` — destructively rebuild only a disposable local database from the ledger;
- `supabase db push --dry-run` — prove that an approved target has no unexpected pending SQL;
- `supabase migration repair --status applied <timestamp>` — history-only adoption after separate human approval.

The last command mutates provider migration history and is forbidden in the design PR and all unapproved
implementation work.

References:

- [Supabase local development workflow](https://supabase.com/docs/guides/local-development/cli-workflows)
- [Supabase database migrations](https://supabase.com/docs/guides/deployment/database-migrations)
- [Supabase migration fetch](https://supabase.com/docs/reference/cli/supabase-migration-fetch)
- [Supabase migration repair](https://supabase.com/docs/reference/cli/supabase-migration-repair)

### 4. Existing migration mechanisms become explicit compatibility boundaries

The target state is:

- `supabase/migrations/` owns PostgreSQL schema evolution.
- The root `migrations/` files and `src/data/migrations.py` remain a SQLite compatibility track until a separately
  characterized replacement is safe. They cannot be cited as PostgreSQL history.
- `Base.metadata.create_all` and imperative PostgreSQL repair helpers cease being production PostgreSQL mutation
  authority after the ledger is implemented.
- `scripts/migrate_database.py` remains transitional during CQ-03. Its final responsibility must be narrowed so it
  cannot create or repair PostgreSQL schema outside the ledger. Credential provisioning and capability verification
  may remain explicit operator steps, but they cannot silently restore DDL authority.
- `scripts/bootstrap_database_capability_roles.sql` remains a separately authorized cluster bootstrap because
  PostgreSQL role creation is cluster-scoped and provider-sensitive. Its fixed `NOLOGIN` capability roles are
  verified by ADR 0007 tooling; login creation, membership, passwords, and provider configuration remain outside
  the schema ledger.
- FastAPI startup and readiness remain read-only consumers of ledger and compatibility state.

There may be more than one executor for disposable testing, but there is only one ordered set of PostgreSQL
migration files and one migration identity model.

## Baseline adoption protocol

Adoption must be a separate, reviewed implementation and operator sequence.

The PR mapping and migration-command hand-off are normative:

- CQ-03A ratifies this ADR and changes no migration behavior.
- CQ-03B performs Phase A and Phase B steps 1–3. It keeps `python -m scripts.migrate_database` and the production
  Compose `migrate` service as stable operator entrypoints, but atomically replaces their PostgreSQL schema-mutation
  internals with delegation to the pinned Supabase CLI ledger executor over `supabase/migrations/`. For PostgreSQL,
  the command must no longer call `init_db`, `initialize_schema`, `Base.metadata.create_all`, or imperative schema
  repair helpers. After ledger application it may perform only separately authorized non-schema duties: read-only
  compatibility and capability verification plus explicit credential-data provisioning. Cluster capability-role
  bootstrap remains the preceding, separately authorized operator step.
- CQ-03B leaves the command's SQLite behavior on the root `migrations/` compatibility track. It updates the operator
  image, Compose service, CI, tests, and migration runbook in the same PR, so no existing invocation loses an
  applicable migration mechanism before its replacement is packaged and proven.
- CQ-03C performs Phase B steps 4–7, and CQ-03D performs Phase C.

Until CQ-03B merges, the current command remains the explicit transitional operator path documented by CQ-01/CQ-02;
it is not evidence of ledger closure. This mapping keeps ledger materialization, drift-gate implementation, and
hosted-history adoption as separate decisions while preventing a second PostgreSQL schema authority.

### Phase A — capture without mutation (CQ-03B)

1. Freeze schema-changing work for the bounded capture window.
2. Record the exact repository SHA and read-only provider migration timestamps.
3. Run `supabase migration fetch` in a temporary workspace to recover the six provider-recorded files.
4. Compare recovered SQL with repository history and merged PR evidence.
5. Run `supabase db pull` to generate a candidate reconciliation migration, but decline any prompt to update remote
   migration history.
6. Remove provider noise and generated statements outside the managed scope only through explicit review.
7. Do not copy data, credentials, row counts, live role names, connection details, or restricted authorization
   evidence into the repository.

The six observed provider receipts retain their exact timestamp identities as six immutable ledger entries in
`supabase/migrations/`. CQ-03B must recover and review the SQL for each receipt; it must not collapse them into one
synthetic baseline. Five receipts contain replayable schema or capability-role SQL. The remaining receipt records a
separately authorized provider login-membership handoff whose role identities and credential topology are restricted
operator material. Its public ledger file preserves the exact timestamp, approved purpose, transaction policy, and
bounded receipt provenance, but contains no executable membership statement, login identity, OID, DSN, or credential.
This is a sanitized external-action receipt, not placeholder schema SQL: the provider membership remains outside the
schema ledger, is not run by `db reset`, and is verified only through the existing restricted runtime-authority checks.

Schema state not explained by the replayable receipts belongs in a later, reviewed reconciliation migration. The
existing six receipts need no history repair; only that new reconciliation timestamp can become the separately
approved Phase C history-only adoption candidate. If any replayable receipt SQL cannot be recovered or proven, or the
restricted membership receipt cannot be reconciled by bounded operator evidence, CQ-03B stops and returns to human
decision.

### Phase B — prove the repository ledger and drift gate (CQ-03B/C)

1. Replay the complete proposed ledger into a disposable local Supabase database.
2. Replay the application-owned portable subset against supported plain PostgreSQL versions used by CI.
3. Run all existing schema-compatibility and ADR 0007 negative-authority tests.
4. Produce a versioned normalized catalog snapshot and digest.
5. Compare that digest with a fresh read-only hosted digest under the exclusions below.
6. Require `supabase migration list` to explain every local/remote timestamp.
7. Introduce one deliberate history mismatch and one deliberate schema mutation in disposable databases and prove
   that the correct drift categories fail.

### Phase C — adopt the hosted history (CQ-03D)

This phase requires a new human approval after Phase B evidence is attached.

1. Reconfirm the target project and exact repository SHA.
2. Confirm that the reconciliation migration makes no schema change against the hosted target.
3. Mark only that reviewed reconciliation timestamp as applied with `supabase migration repair`.
4. Re-run migration-list parity, normalized drift, compatibility, and authorization verification.
5. Require `supabase db push --dry-run` to report no unexpected pending migration.
6. Stop immediately unless every required gate reports `PASS`; any drift category, `EVALUATION_INCOMPLETE`, changed
   catalog digest, migration timestamp, privilege boundary, or target identity blocks history adoption.

History repair is not schema repair. It is permitted only when read-only evidence proves that the hosted schema
already equals the reviewed ledger state.

## Migration identity and immutability

- Timestamp identities are unique, strictly increasing, and generated in UTC.
- An applied migration is immutable. Correct it with a later forward migration.
- CI records SHA-256 for every migration file in a repository manifest.
- Renaming an applied file, changing its timestamp or descriptive stem, deleting it, or editing its bytes fails
  manifest CI. "Reordering" means changing timestamp values or introducing a timestamp that violates the ledger's
  strictly increasing UTC order; filesystem enumeration and display order do not matter.
- A migration header states its control issue, managed schemas, transaction policy, lock expectation, data/backfill
  behavior, rollback or restore path, and whether a provider capability is required.
- SQL must be deterministic and must not interpolate secrets or environment-specific object identities.
- Seed/demo data, live data copies, login roles, role memberships, OIDs, passwords, and connection details never enter
  executable ledger SQL.
- A sanitized external-action receipt may preserve an already-recorded provider timestamp only when the action is
  outside repository schema authority, its executable statement would disclose restricted operator identities, the
  public file is explicitly non-executable, and restricted verification proves the intended end state. Such a receipt
  cannot satisfy a schema migration, create a role, grant membership, or authorize provider mutation.

## Forward and rollback policy

PostgreSQL migrations are forward-only.

- A compatible defect is corrected by a later migration.
- An application rollback is allowed only when the previous application remains compatible with the migrated schema.
- Destructive or irreversible changes require backup/restore evidence and an explicit operator pause gate.
- An emergency schema rollback uses the approved restore procedure; it does not edit an applied migration or return
  DDL authority to runtime.
- SQLite compatibility may use backend-specific mechanics, but it must preserve equivalent application invariants
  and must not claim byte-for-byte PostgreSQL parity.

## Managed drift contract

### Included schemas and object classes

The first contract manages application-owned objects in `public`:

- tables, partitioned tables, columns, generated/identity behavior, types, nullability, and normalized defaults;
- primary, foreign-key, unique, exclusion, and check constraints;
- indices, expressions, predicates, uniqueness, and access method;
- sequences and application-owned sequence relationships;
- views and materialized views;
- application-owned functions by identity, language, volatility, security mode, safe configuration, and normalized
  definition digest;
- user triggers and normalized trigger definitions;
- RLS enable/force flags and policies;
- application-owned grants and default privileges relevant to ADR 0007;
- application-owned enum, domain, and composite types;
- explicitly declared extensions required by application objects.

### Exclusions

The `fardb-pg-scope-v1` classifier is total and deterministic. It enumerates every `public` object in the included
object classes before applying a classification:

- **Application-owned:** the exact object identity is produced by replaying `supabase/migrations/` or is declared in
  the versioned application-owned scope manifest with its controlling migration. Columns and other subordinate
  catalog entries inherit their parent only when they have no independent identity; independently addressable
  functions, sequences, policies, triggers, types, indices, and grants are classified separately.
- **Provider-owned:** the exact object identity appears in the versioned provider-owned `public` allowlist with a
  provider owner and exclusion rationale. Ownership is never inferred from a role, name prefix, extension, or current
  absence from the repository ledger.
- **Unknown:** the identity matches neither list, matches both, or has an unclassified independently addressable
  dependency. Unknown objects produce the public reason code `OUTSIDE_MANAGED_SCOPE` and
  `EVALUATION_INCOMPLETE`; they are never silently excluded or treated as provider-owned.

The collector normalizes every application-owned object into the catalog digest. Provider-owned objects are excluded
from that catalog digest only by exact allowlist identity, but their identities, rationales, and bounded count are
covered by the managed-scope manifest digest. The public traversal reports bounded application-owned,
provider-owned, and unknown counts, so their sum accounts for every enumerated `public` object.

The provider-owned non-`public` schema inventory observed at the 2026-08-13 baseline is `auth`, `extensions`,
`graphql`, `graphql_public`, `net`, `pgbouncer`, `pgmq`, `realtime`, `storage`, `supabase_functions`,
`supabase_migrations`, and `vault`. PostgreSQL system, temporary, and TOAST namespaces are classified by catalog
namespace type rather than an open-ended name wildcard. A newly observed non-`public` schema produces
`OUTSIDE_MANAGED_SCOPE` and `EVALUATION_INCOMPLETE`; excluding it requires an owner, rationale, and reviewed
scope-version change. This inclusion/exclusion inventory is independently versioned as `fardb-pg-scope-v1`.

The first contract also excludes:

- provider-maintained extensions and objects only when their exact identities appear in the versioned provider-owned
  allowlist; absence from the application ledger alone is never sufficient for exclusion;
- physical storage details, OIDs, statistics, planner estimates, row counts, data, comments generated by the provider,
  and ephemeral sequence values;
- login roles, passwords, connection settings, network controls, project configuration, and secret custody;
- cluster capability-role creation and provider login membership, which remain separately verified by ADR 0007;
- ownership or grants that the provider necessarily manages and that are explicitly allowlisted with rationale.

Every exclusion is named and versioned. A wildcard exclusion without a documented provider owner is not acceptable.

### Normalization profile

Define `fardb-pg-catalog-v1` as a versioned catalog normalization profile. The effective drift-contract identity is
`fardb-pg-catalog-v1+fardb-pg-scope-v1`; changing either component requires review and a new expected digest:

- obtain definitions through PostgreSQL catalog and `pg_get_*def` functions;
- sort schemas, identities, columns, role sets, policy commands, and ACL items deterministically;
- discard OIDs and physical/statistical fields;
- canonicalize equivalent built-in type spellings;
- normalize whitespace only after PostgreSQL has parsed and deparsed expressions;
- distinguish absent values from explicit defaults;
- hash the canonical UTF-8 JSON representation with SHA-256.

Changing the normalization profile is a reviewed contract change and cannot silently rewrite a passing digest.

### Failure categories

The gate publishes one top-level status per target evaluation:

- `PASS` — every required check ran and no drift category or scope-classification reason was detected; exit zero.
- `DRIFT_DETECTED` — at least one of the three primary drift categories below was detected; exit non-zero.
- `EVALUATION_INCOMPLETE` — no primary drift category is safely publishable because a required check is
  `NOT_EVALUATED` or a scope-classification reason such as `OUTSIDE_MANAGED_SCOPE` prevents a complete comparison;
  exit non-zero. It is a fail-closed evaluation status, not a fourth drift category.

When status is `DRIFT_DETECTED`, the gate publishes exactly one primary category:

1. `LEDGER_HISTORY_MISMATCH` — expected timestamp or immutable file receipt is missing, extra, reordered, or changed.
2. `PROVIDER_SCHEMA_DRIFT` — migration history agrees but the normalized managed catalog differs.
3. `RUNTIME_COMPATIBILITY_MISMATCH` — the target may match the ledger but fails the existing application-required
   compatibility or ADR 0007 capability contract.

Evaluation order and primary-category precedence are `LEDGER_HISTORY_MISMATCH` → `PROVIDER_SCHEMA_DRIFT` →
`RUNTIME_COMPATIBILITY_MISMATCH`. The gate runs every read-only check that remains safe, records every detected
category in a restricted artifact, and selects the first detected category by that order. A category is publishable
as primary only when every required check at the same or higher precedence completed. If any such check is
`NOT_EVALUATED`, status is `EVALUATION_INCOMPLETE`, public `primary_category` is null, and any detected
lower-priority category remains bounded restricted evidence with reason code
`HIGHER_PRIORITY_CHECK_NOT_EVALUATED`; it cannot mask the unknown higher-priority state. Required checks strictly
downstream of a publishable primary may remain `NOT_EVALUATED` in diagnostics without replacing
`DRIFT_DETECTED`. If no category is detected and any required check is `NOT_EVALUATED`, the result is likewise
`EVALUATION_INCOMPLETE`, never `PASS`. Single-failure, combined-failure, unavailable-higher-priority, and
incomplete-evaluation fixtures must prove these rules.

Public output includes `status`, nullable `primary_category`, bounded reason codes, target class,
normalization-profile version, managed-scope version, required-check totals, evaluated and `NOT_EVALUATED` counts,
application-owned/provider-owned/unknown counts, and expected/actual digests when available. Live object names, data,
URLs, raw database errors, and role identities stay in a restricted diagnostic artifact. Disposable CI fixtures may
name repository-owned objects in test assertions.

Every Phase C history-adoption step requires `PASS`. `EVALUATION_INCOMPLETE` stops adoption even when no drift
category has been proven.

## Verification and completion evidence

CQ-03 implementation is complete only when all of the following are attached to the exact reviewed SHA:

- a fresh local Supabase rebuild from the repository ledger;
- the supported PostgreSQL-version matrix for the application-owned portable subset;
- migration-history parity and immutable-file checks;
- a deliberate missing-migration fixture producing `LEDGER_HISTORY_MISMATCH`;
- a deliberate unrecorded DDL fixture producing `PROVIDER_SCHEMA_DRIFT`;
- a deliberate required-invariant fixture producing `RUNTIME_COMPATIBILITY_MISMATCH`;
- a deliberately unavailable required check, including an unavailable higher-priority check with a detected
  lower-priority mismatch, and an unknown `public` object each producing `EVALUATION_INCOMPLETE` with the applicable
  bounded reason code, null public primary category, and non-zero exit;
- proof that startup/readiness performs no DDL or migration-history mutation;
- negative tests proving restricted runtime cannot create, alter, drop, own, grant, repair history, or bootstrap
  credentials;
- a reviewed adoption record showing that any hosted history repair was history-only and separately approved;
- updated runbook, continuity ledger, roadmap, GitHub issue, Linear issue, and Notion execution authority.

A local rebuild alone does not close CQ-03. A hosted inspection alone does not close CQ-03.

## Implementation sequence after ratification

One PR remains one decision:

1. **CQ-03A — ratify this ADR.** Documentation and evidence inventory only; no provider mutation.
2. **CQ-03B — materialize the ledger.** Recover history, add reviewed reconciliation SQL, and prove fresh rebuilds
   without changing hosted state.
3. **CQ-03C — add the drift gate.** Versioned catalog normalizer, immutable migration manifest, negative fixtures,
   CI/readiness integration, and sanitized diagnostics.
4. **CQ-03D — adopt hosted history.** Separate operator approval, history-only reconciliation, read-only equality
   verification, and evidence attachment.

If a phase cannot preserve the verify-only runtime boundary, it stops and returns to human decision.

## Alternatives considered

### Keep ORM creation and imperative repairs as PostgreSQL authority

Rejected. They describe current desired fragments but do not provide immutable ordered history, remote receipt parity,
or a reproducible drift boundary.

### Adopt Alembic now

Deferred. Alembic is capable, but it adds a new framework and a second revision/history model beside the provider's
existing timestamp history. It may be reconsidered only with a separate migration and provider-interoperability case.

### Adopt declarative schema files immediately

Deferred. For this existing project, a pulled imperative baseline is the safer first authority. Declarative schemas
would add a second representation during the most sensitive reconciliation phase.

### Treat the hosted catalog as authority

Rejected. A mutable provider state cannot explain intent, review, ordering, or whether an unrecorded change is
legitimate.

## Consequences

Positive consequences:

- one reviewable PostgreSQL history can rebuild clean state;
- hosted receipts, CI, and repository files use one timestamp identity;
- drift categories separate history, catalog, and application compatibility failures;
- runtime remains verify-only;
- provider adoption is explicit and reversible through evidence/restore procedures rather than implicit repair.

Costs and risks:

- historical SQL must be recovered and reviewed carefully;
- the operator and CI images need a pinned Supabase CLI;
- SQLite remains a separate compatibility implementation;
- the normalized catalog profile must be versioned and tested across PostgreSQL releases;
- a one-time, separately approved hosted history repair is likely required.

## Ratification record

CQ-03A ratification completed when the named human ratifier authorized ready-state review and merge, all
substantive review and authoritative CI gates cleared, and PR #1634 merged as squash
`2dd9f64136eb653284b0f5330a16ee99f6b0b491` on 2026-08-13. CQ-03B/C may proceed within this ADR; CQ-03D still
requires the separate history-adoption approval defined above.

- [x] Approve `supabase/migrations/` as the sole repository PostgreSQL ledger.
- [x] Approve imperative timestamped SQL for initial adoption.
- [x] Approve Supabase CLI as pinned operator/CI tooling only.
- [x] Approve the atomic `scripts.migrate_database` PostgreSQL ledger hand-off while preserving its SQLite path and
      existing operator, CI, Compose, test, and runbook entrypoints.
- [x] Approve `fardb-pg-scope-v1`, its total ownership classifier, named exclusions, unknown-object non-pass rule,
      and the `fardb-pg-catalog-v1` normalization contract.
- [x] Approve the three failure categories, `EVALUATION_INCOMPLETE` status, exit behavior, and sanitized evidence
      boundary.
- [x] Approve forward-only migrations and restore-based destructive rollback.
- [x] Approve a later, separately authorized history-only provider adoption step.
- [x] Confirm that SQLite compatibility remains separate and cannot claim PostgreSQL authority.

**Decision:** Accepted
**Ratifier:** Mohamed Abdel-Aziz Mohamed
**Decision date:** 2026-08-13
**GitHub evidence link:** [PR #1634](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1634)
