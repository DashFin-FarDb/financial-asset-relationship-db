# ADR 0010: Historical receipt evidence and target-ledger profiles

## Status

**Accepted — ratified on 2026-08-17; effective as repository authority when this record merges.**

This ADR is the CQ-03B-R1 adjudication requested after receipt recovery exposed dependency and target-boundary
conflicts in [ADR 0009](0009-postgresql-migration-ledger-and-drift-contract.md). It amends only ADR 0009's
historical-replay, flat-ledger, and pre-CQ-03D provider-inspection clauses. ADR 0009 remains authoritative for
repository ownership, imperative forward-only migrations, verify-only runtime behavior, drift categories, rollback
policy, and the separate CQ-03D approval boundary.

## Date

2026-08-17

## Decision owner and ratifier

- Decision owner: FarDB maintainers
- Human ratifier: Mohamed Abdel-Aziz Mohamed
- Control records: [GitHub #1633](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1633)
  and [Linear DAS-62](https://linear.app/dashfin/issue/DAS-62/cq-03-establish-postgresql-migration-ledger-and-drift-gate)
- Exact setup baseline: `main@76f1194f1f9b83cb9ed8f0bb0083824ededbe0ae`
- Model and reasoning: GPT-5.6 Sol / max

## Context

Read-only recovery of the six provider migration records established two facts that ADR 0009 did not resolve:

1. the provider preserves an ordered `statements[]` payload for each receipt, but that payload is not proof of the
   original migration file's comments, whitespace, transaction wrapper, or filename bytes; and
2. later receipts refer to application objects that their earlier provider-recorded history does not create.

The recovered receipts therefore prove what the provider recorded and applied, but they are not a valid clean-build
programme. Replaying reviewed substitutes under the old timestamps would manufacture history, while replaying the
recorded statements alone would fail to establish their dependencies.

The runtime also exposes distinct PostgreSQL capabilities for authentication, graph, and coordination state. Giving
every target a universal schema would erase the separation required by ADR 0007. Maintaining independent schema
definitions outside the migration authority would instead create a second authority.

Finally, current Supabase documentation states that `supabase db pull` can insert a baseline row into
`supabase_migrations.schema_migrations`. A command commonly described as a pull therefore cannot be treated as
read-only during CQ-03B.

## Decision

### 1. Historical receipts are immutable evidence, not clean-build migrations

For every provider receipt, preserve the exact provider-recorded payload as an ordered evidence envelope:

- provider timestamp and recorded name;
- statement ordinal and the exact UTF-8 content of every `statements[]` element;
- statement count, capture time, capture mechanism, and an opaque target fingerprint; and
- a deterministic SHA-256 digest over the ordered, length-delimited statement values.

The digest input is `fardb-provider-statements-v1` followed by a zero byte, the statement count as an unsigned
64-bit big-endian integer, then for each statement its UTF-8 byte length as an unsigned 64-bit big-endian integer and
its raw bytes. The domain prefix and integer encoding make the evidence digest reproducible and unambiguous.

Every SHA-256 digest persisted or transmitted under this ADR—including evidence, manifest, normalized-catalog, and
target-fingerprint values wherever recorded in evidence, manifests, or adoption permits—is serialized as exactly 64
lowercase hexadecimal ASCII characters with no prefix or separators. Raw bytes, uppercase hexadecimal, and alternate
encodings are invalid persisted representations.

The statement values must not be reformatted, reparsed, reordered, combined, split, or normalized before hashing.
This preserves exact provider evidence without claiming that the provider retained the original SQL file bytes.

Evidence classification is content-sensitive. Exact payloads that pass public review may be committed only in a
non-executable evidence location. The provider membership receipt and any payload containing restricted identities,
topology, credentials, or operator-only details remain in the protected evidence store; the public repository records
only timestamp, purpose, statement count, classification, digest, and bounded provenance.

Historical timestamp markers may appear only in the non-executable `hosted-legacy-v1` lineage record. They are never
staged into an executable migration directory and cannot satisfy a clean-build dependency.

A reviewed replay-safe reconstruction is allowed only as a new canonical migration with a new forward UTC timestamp.
It must cite the source receipt digests and review record. It must never reuse or backdate a provider timestamp, and it
must not be described as the exact historical SQL.

### 2. New forward baselines establish dependencies without inventing history

CQ-03B-R2 creates a forward-dated canonical baseline for each schema component. Each baseline contains the complete,
reviewed, dependency-ordered state required for that component on an empty supported PostgreSQL database. Later
canonical migrations may depend on those baselines; historical receipt markers may not.

The baseline is executed on fresh targets. An existing hosted target does not execute it merely because its catalog
already contains equivalent objects. CQ-03D may mark one baseline timestamp at a time as applied only after the
profile-aware catalog, runtime-compatibility, and authorization checks prove exact equality and the adoption permit
names that timestamp. Any actual schema delta stops adoption and requires a new forward migration and review.

This makes the repository authoritative without backdating a migration, replaying an invalid dependency chain, or
retaining ORM creation, imperative repair helpers, generated dumps, or declarative schema files as a second schema
authority.

### 3. One repository authority contains separate immutable component ledgers

The repository authority is partitioned into these component ledgers:

- `auth` — authentication and application-user persistence;
- `graph` — financial graph and governed relationship persistence; and
- `coordination` — rebuild, recovery, lease, and coordination persistence.

CQ-03B-R2 materializes the canonical SQL under `supabase/ledgers/<component>/migrations/` and one reviewed profile
manifest at `supabase/ledger-profiles.json`. Those paths are the only PostgreSQL schema authority. A generated or
temporary Supabase CLI workspace is an execution projection of the selected source files, not a committed schema
representation.

Migration timestamps are globally unique and strictly increasing across all component ledgers. The profile manifest
records component dependencies and their deterministic order. A migration contains no target-selection SQL and no
conditional branch based on whether an object happens to exist.

The manifest defines four build profiles:

- `auth` selects only the auth component;
- `graph` selects only the graph component;
- `coordination` selects only the coordination component; and
- `combined` selects the deterministic union of auth, graph, and coordination for an explicitly approved shared
  physical database.

Each target binding names exactly one build profile and one lineage profile:

- `fresh-v1` expects no provider receipts before the canonical forward baseline; or
- `hosted-legacy-v1` allowlists the six immutable provider receipt identities and evidence digests without making
  their SQL executable.

The hosted lineage is history metadata, not schema authority. It exists so a fresh target and a previously hosted
target can converge on the same canonical schema while retaining truthful, different execution histories.

Distinct auth, graph, and coordination targets receive only their named component profile. A shared physical target
receives `combined` exactly once. If two configured URLs resolve to the same opaque target fingerprint while naming
different profiles, execution fails unless the operator explicitly selected `combined`; the runner must not infer or
silently expand a profile.

Target identity uses SHA-256 algorithm version `fardb-target-fingerprint-v1`. The canonical inputs supplied by the
approved target adapter are its adapter ID, an immutable authority-namespace ID, and an immutable database ID. Each
input is Unicode-normalized to NFC and encoded as UTF-8 with case preserved; leading or trailing whitespace, control
characters, missing values, and values that cannot be proven immutable are invalid. The digest input is the ASCII
algorithm-version prefix, a zero byte, then each canonical input in the stated order prefixed by its unsigned 64-bit
big-endian byte length. A DSN, hostname, port, mutable project or database name, and catalog contents are not identity
inputs. Raw identifiers remain protected; only their lowercase-hex fingerprint leaves protected evidence.

The algorithm version is stored with the fingerprint in evidence and manifests; changing it is a reviewed contract
change. Missing or ambiguous inputs, an observed collision between distinct protected canonical inputs, or any other
inability to prove target identity produces `TARGET_IDENTITY_INDETERMINATE` and a non-zero result before profile
selection or SQL execution. The runner must not infer or expand a profile to recover from that result. Explicit
same-target/profile conflicts remain rejected as described above.

#### CQ-03D-01 production target adapter

The human ratifier approved the bounded CQ-03D-01 production adapter contract on 2026-08-18. The adapter ID is
`supabase-postgresql-routing-v1`. Its immutable authority-namespace ID is the protected Supabase project reference,
and its immutable database ID is the live positive `pg_database.oid` for the connected database. The adapter accepts
only a documented Supabase direct route or port-5432 session-pooler route with `sslmode=verify-full` and an explicit
trust-root path. Transaction-pooler routing, unknown hosts, caller-supplied PostgreSQL `options`, weak TLS, or an
unavailable trust root fails closed.

Before any drift or parity check, the adapter starts a read-only transaction on the inspection DSN and every required
runtime DSN, reads the current database OID from `pg_catalog.pg_database`, compares the resulting canonical identity
and fingerprint with the protected binding, and rolls the transaction back. Missing, unavailable, or mismatched
proof is `TARGET_IDENTITY_INDETERMINATE`. Raw project references, OIDs, DSNs, login names, SQL, and provider output
remain protected and do not enter public evidence.

CQ-03D-01 evaluates `hosted-legacy-v1` as a strict ordered adoption prefix: the actual history must equal all six
reviewed hosted receipts plus any earlier canonical profile markers, and the permit must name exactly the next
canonical marker. Its only Supabase subprocess is pinned version `2.114.0` `migration list` against a disposable
projection containing that one marker and an explicit permit-bound `--db-url`. CQ-03D-01 does not run
`db push --dry-run`, repair history, apply DDL or DML, consume the permit, deploy, or mutate provider configuration.

This ratification authorizes repository implementation and review of that read-only preflight contract. It does not
approve a hosted target, issue a permit, authorize a connected preflight, or authorize the later history action.

Changing a target's profile, component membership, lineage, dependency order, or manifest digest is a reviewed
contract change. It cannot be selected from SQL, inferred from the current catalog, or adopted merely because a
provider target happens to contain additional objects.

### 4. CQ-03B/C cannot acquire hosted-history adoption authority

CQ-03B and CQ-03C use a dedicated provider inspection credential that is technically unable to write managed
schemas or `supabase_migrations`. Sessions are read-only, and public evidence records only the opaque target
fingerprint and bounded aggregates.

Before CQ-03D approval, all of the following are forbidden against a hosted target:

- `supabase db pull`, because the current workflow can update remote migration history;
- `supabase migration repair` and `supabase db push`;
- `supabase db reset --linked`;
- `supabase db reset --db-url <connection-string>`;
- provider migration APIs, dashboard SQL, or SQL statements that write DDL, DML, grants, roles, or migration history;
- retained or committed Supabase link state, including a provider project reference; and
- use of an owner, migration, service, or other credential with provider write authority.

Any necessary CLI inspection runs only in a disposable, explicitly selected work directory and leaves no link state
behind. Receipt recovery uses bounded read-only provider queries or APIs and stores evidence outside the executable
ledger.

CQ-03B-R2 must add a fail-closed command barrier and negative tests for every forbidden operation, including both
hosted reset variants. A documentation warning alone is insufficient.

CQ-03D is a separate manual workflow. It requires a signed or equivalently protected, single-use adoption permit
that binds all of the following:

- the exact reviewed repository SHA;
- build-profile ID and manifest digest;
- lineage-profile ID and opaque target fingerprint;
- one allowlisted canonical migration timestamp;
- the passing CQ-03B/C evidence and normalized catalog digests; and
- the ratifier, approval time, and expiry.

The workflow rechecks every binding before one history-only mutation, then reruns history, catalog, compatibility,
and authorization checks. A changed SHA, target, profile, timestamp, digest, privilege boundary, incomplete check, or
schema delta invalidates the permit. CQ-03D never applies DDL; if DDL is needed, it stops and returns to a new
forward-migration decision.

### 5. Drift is evaluated against the target's explicit profile and lineage

ADR 0009's status and failure-category contract remains unchanged, but its expected state is profile-scoped:

- `LEDGER_HISTORY_MISMATCH` compares canonical migration identities plus the selected lineage allowlist;
- `PROVIDER_SCHEMA_DRIFT` compares the normalized catalog with the selected build profile's expected digest; and
- `RUNTIME_COMPATIBILITY_MISMATCH` evaluates only the capabilities required by that target profile.

An unknown profile, unapproved lineage, extra component, aliased target with conflicting profiles, or changed profile
manifest produces `EVALUATION_INCOMPLETE` and a non-zero exit. Before CQ-03D, selecting `hosted-legacy-v1` as an
adopted lineage is itself incomplete because no adoption permit exists.

## CQ-03B-R2 bounded handoff

CQ-03B-R2 is the next implementation unit after this record merges. It may materialize the component ledger layout,
profile manifest and validator, forward baselines, disposable execution projection, operator-command hand-off,
focused tests, and synchronized runbook/continuity text.

It must prove clean, profile-specific builds on PostgreSQL 15 and 16; deterministic `combined` union ordering;
globally unique identities and hashes; rejection of target/profile alias conflicts; and negative hosted-write
barriers. The provider catalog and history remain unchanged.

CQ-03B-R2 stops if a recovered dependency cannot be assigned to exactly one component, a cross-component dependency
cycle appears, exact evidence cannot be preserved within its classification boundary, a clean profile needs
target-conditional SQL, or any provider mutation or CQ-03D permit is required.

CQ-03C then makes the existing drift contract profile-aware and supplies its negative fixtures. CQ-03D remains the
only phase that may adopt hosted history, one explicitly permitted timestamp at a time.

## Alternatives considered

### Replay exact `statements[]` under the historical timestamps

Rejected. The payload is valuable evidence, but the observed chain does not establish every dependency and is not
proof of the original file bytes.

### Put reviewed reconstructions under the historical timestamps

Rejected. That would manufacture provenance and make a reconstruction indistinguishable from applied history.

### Give every PostgreSQL target the same universal schema

Rejected. It broadens privileges and persistence surfaces across boundaries that ADR 0007 deliberately separates.

### Keep one independent migration tree per target

Rejected. Repeated SQL would drift and create multiple schema authorities. Component ledgers plus one profile
manifest preserve one authority while allowing explicit target composition.

### Use the hosted catalog or declarative schema files as a baseline authority

Rejected. The hosted catalog is mutable evidence, and a committed declarative mirror would be a second schema
representation during adoption.

## Consequences

Positive consequences:

- historical evidence remains truthful without becoming an invalid replay chain;
- clean targets receive complete dependencies through forward-only migrations;
- auth, graph, coordination, and explicitly combined targets have deterministic least-scope schemas;
- fresh and legacy-hosted histories can differ without claiming different desired schemas; and
- CQ-03B/C cannot accidentally cross the CQ-03D provider-mutation boundary.

Costs and risks:

- the executor must build and verify a disposable profile projection for the Supabase CLI;
- profile and lineage manifests become security-sensitive control inputs and require immutable hashing;
- existing hosted adoption needs target-specific equality evidence and one-timestamp permits; and
- a component-boundary mistake must fail closed instead of being hidden by conditional SQL.

## Ratification record

The named human ratifier answered **Ratified** on 2026-08-17 after reviewing the normative commitments in
[Decision 1](#1-historical-receipts-are-immutable-evidence-not-clean-build-migrations),
[Decision 2](#2-new-forward-baselines-establish-dependencies-without-inventing-history),
[Decision 3](#3-one-repository-authority-contains-separate-immutable-component-ledgers),
[Decision 4](#4-cq-03bc-cannot-acquire-hosted-history-adoption-authority), and
[Decision 5](#5-drift-is-evaluated-against-the-targets-explicit-profile-and-lineage). Those numbered sections are the
single source of truth for receipt fidelity, forward baselines, target-ledger composition, the CQ-03D barrier, and
profile-aware drift behavior; this record does not restate their commitments.

**Decision:** Accepted
**Ratifier:** Mohamed Abdel-Aziz Mohamed
**Decision date:** 2026-08-17
