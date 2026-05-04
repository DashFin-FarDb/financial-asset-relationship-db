# Graph persistence design

## Status

Design proposal. This document defines the graph persistence boundary for the next implementation phase after hosted preview verification. It intentionally does not introduce migrations, ORM models, repository implementations, runtime startup changes, or API behavior changes.

## Context

The hosted preview gate is complete. Issue #1108 records the verified hosted deployment, the hosted readiness smoke command, the passing smoke result, and manual endpoint evidence for health, detailed health, assets, metrics, and visualization endpoints.

The next production-path need is authoritative graph persistence. The repository already has SQLAlchemy persistence primitives and migration history for assets and asset relationships, but the hosted/runtime graph lifecycle is not yet explicitly wired to load from and save to that persistence layer as the authoritative graph source. Local development and tests must continue to work with SQLite.

The graph persistence boundary must also preserve the existing architectural separation between graph truth and graph layout. Financial relationships are domain data. Coordinates and visualization layout are presentation metadata and must not become the source of truth for relationships.

## Existing schema alignment

This document is a target persistence-boundary design for the next graph persistence phase. It does not replace the current SQLAlchemy persistence layer or existing migration files in this PR.

Future implementation PRs must explicitly reconcile this design with the current schema and ORM models, including `src/data/db_models.py` and `migrations/001_initial.sql`. Where this document uses target names such as `relationships` or `relationship_metadata`, implementation PRs must either:

1. map those concepts onto the existing table/model names, such as `asset_relationships`, without changing behavior; or
2. introduce a migration plan that explains the rename or schema transition, including backfill, compatibility, rollback, and repository/service-layer changes.

Until such an implementation PR is accepted, the existing ORM and migration files remain the operative schema contract.

## Problem statement

FarDb can now be deployed to a hosted preview and can pass hosted readiness checks, but runtime graph state is still treated primarily as initialized/sample/cache state rather than as state loaded from and saved to an explicit authoritative persistence lifecycle.

This creates four production risks:

1. graph state cannot be independently inspected, versioned, or rebuilt from persistent evidence;
2. startup/load behavior is ambiguous when persisted graph state is missing or stale;
3. future schema work may drift between PostgreSQL and SQLite if compatibility is not designed up front;
4. layout or visualization persistence could accidentally become coupled to graph truth if boundaries are not explicit.

## Goals

- Define PostgreSQL as the durable persistence boundary for graph truth in hosted and production environments.
- Preserve SQLite compatibility for local development and automated tests.
- Define tables for assets, relationships, relationship metadata, and optional regulatory events.
- Define persistence boundaries for assets, relationships, relationship metadata, and optional regulatory events while preserving the current domain/schema contract unless a later migration PR explicitly changes it.
- Define optional graph build/snapshot tracking for rebuild/load decisions.
- Define repository boundaries that future implementation PRs can add without changing this design's scope.
- Keep graph truth separate from layout and visualization coordinates.
- Define load/rebuild semantics for missing, stale, invalid, and explicitly refreshed graph state.

## Non-goals

- No Alembic setup or migration files in this PR.
- No SQLAlchemy model implementation in this PR.
- No repository implementation in this PR.
- No runtime graph save/load path in this PR.
- No startup integration in this PR.
- No layout persistence implementation in this PR.
- No new hosted-readiness behavior in this PR.

## Persistence model

### `assets`

Stores durable asset identity and asset attributes needed to reconstruct graph nodes.

Recommended fields:

This list is a target persistence boundary, not an exhaustive replacement for the current asset contract. Implementation PRs must include every field required to reconstruct `src.models.financial_models.Asset` and supported subclasses from the operative ORM/migration contract. Current required fields such as `price`, and current optional or class-specific fields such as `market_cap`, must not be dropped merely because they are not central to graph topology.

| Field         | Purpose                                                                                                                    | Compatibility note                                                                                                                                          |
| ------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`          | Internal primary key                                                                                                       | String-compatible primary key to match the current `AssetORM.id`; integer/UUID requires a separate migration PR.                                            |
| `symbol`      | Stable asset symbol or ticker                                                                                              | Add a unique constraint only if `symbol` is confirmed as the canonical asset lookup key for all persisted assets.                                           |
| `name`        | Display name                                                                                                               | Nullable only if ingestion can legitimately omit it.                                                                                                        |
| `asset_class` | Asset class from the current `AssetClass` domain enum, including Equity, Fixed Income, Commodity, Currency, and Derivative | Prefer portable string enum validation in application code before DB-specific enum types.                                                                   |
| `price`       | Current asset price/value required by the domain model                                                                     | Preserve current non-null ORM/domain behavior unless a migration PR explicitly changes it.                                                                  |
| `market_cap`  | Market capitalization where applicable                                                                                     | Preserve current ORM/domain behavior; nullable or class-specific only if the current model permits it.                                                      |
| `sector`      | Sector classification where applicable                                                                                     | Preserve current non-null ORM/migration behavior unless a migration PR explicitly relaxes it.                                                               |
| `issuer_id`   | Issuer identifier where applicable                                                                                         | Aligns with current `AssetORM.issuer_id` / `Bond.issuer_id`; nullable only if current ORM/migration behavior permits it, or after an explicit migration PR. |
| `currency`    | Currency code where applicable                                                                                             | Preserve current non-null ORM/migration behavior unless a migration PR explicitly relaxes it.                                                               |
| `attributes`  | Source-specific attributes not yet promoted to first-class columns                                                         | SQLAlchemy `JSON`-compatible extended attributes; avoid ORM attribute name `metadata`.                                                                      |
| `created_at`  | Insert timestamp                                                                                                           | Must be timezone-aware in application handling.                                                                                                             |
| `updated_at`  | Last update timestamp                                                                                                      | Updated by repository/service layer.                                                                                                                        |

Nullability and domain/schema compatibility: current ORM, migration, and domain-model constraints remain authoritative until a schema PR changes them. Implementation PRs must preserve existing required/non-null behavior in `AssetORM` and `migrations/001_initial.sql` for fields such as `price`, `sector`, or `currency` unless an explicit migration plan is approved. Any relaxation for asset classes where a field does not apply must include backfill or default handling, a SQLite compatibility check, and corresponding repository/service-layer validation updates.

Constraints and indexes:

- Unique index on `symbol` when symbol is canonical.
- Index on `asset_class`.
- Index on `sector` if sector filters remain common.
- Preserve current indexes and constraints needed by the existing ORM/domain contract unless a migration PR explicitly changes them.
- Avoid PostgreSQL-only enum definitions unless there is a clear SQLite fallback.

### `relationships`

Stores durable graph edges between assets.

Recommended fields:

| Field               | Purpose                                                                                                           | Compatibility note                                                                                                                                                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                | Internal primary key                                                                                              | Preserve the current relationship-table key strategy. The existing schema may use an autoincrement integer for relationship rows while asset/event IDs remain string-compatible; unifying key policy requires a separate migration PR. |
| `source_asset_id`   | Source asset foreign key                                                                                          | References `assets.id`.                                                                                                                                                                                                                |
| `target_asset_id`   | Target asset foreign key                                                                                          | References `assets.id`.                                                                                                                                                                                                                |
| `relationship_type` | Domain relationship type, such as same-sector, issuer link, regulatory impact, correlation, or other future types | Validate allowed values in application code initially.                                                                                                                                                                                 |
| `bidirectional`     | Current ORM-compatible direction marker                                                                           | Boolean compatibility baseline for `AssetRelationshipORM.bidirectional`; a later enum-based `direction` field requires a migration PR.                                                                                                 |
| `strength`          | Relationship strength                                                                                             | Target name should remain compatible with `AssetRelationshipORM.strength`; use `FLOAT(53)` / double precision.                                                                                                                         |
| `confidence`        | Confidence score separate from strength                                                                           | `FLOAT(53)` / double precision; nullable if not all relationship types have confidence yet.                                                                                                                                            |
| `valid_from`        | Start of validity window                                                                                          | Nullable for timeless/static relationships.                                                                                                                                                                                            |
| `valid_to`          | End of validity window                                                                                            | Nullable for current/open-ended relationships.                                                                                                                                                                                         |
| `source`            | Data/source system that produced the relationship                                                                 | Useful for evidence and rebuild diagnostics.                                                                                                                                                                                           |
| `created_at`        | Insert timestamp                                                                                                  | Repository-managed.                                                                                                                                                                                                                    |
| `updated_at`        | Last update timestamp                                                                                             | Repository-managed.                                                                                                                                                                                                                    |

Constraints and indexes:

- Foreign keys from `source_asset_id` and `target_asset_id` to `assets.id`.
- Composite index on `(source_asset_id, target_asset_id)`.
- Composite index on `(relationship_type, source_asset_id)`.
- Compatibility baseline: preserve the current uniqueness semantics on `(source_asset_id, target_asset_id, relationship_type)` unless a migration PR explicitly introduces validity-windowed relationship history.
- If validity-windowed history is added later, avoid nullable fields inside idempotency constraints; use a non-null normalized validity key or a partial/generated-index strategy with PostgreSQL and SQLite behavior documented.
- Compatibility baseline: preserve current runtime semantics for bidirectional relationships. If the runtime stores reciprocal directed edges, persistence should not collapse them to one row unless the implementation PR also updates query paths, indexing, and reconstruction semantics.
- SQLite compatibility note: these composite indexes are portable B-tree indexes. Foreign-key enforcement in SQLite requires `PRAGMA foreign_keys = ON`; implementation PRs must ensure the SQLAlchemy engine or connection setup enables this so test behavior matches PostgreSQL as closely as possible.

### `relationship_metadata`

Stores evidence/provenance and extensible relationship attributes without forcing every future signal into the `relationships` table.

Recommended fields:

| Field             | Purpose                        | Compatibility note                                                                                                       |
| ----------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `id`              | Internal primary key           | String-compatible internal key unless a later migration establishes a repo-wide surrogate-key policy.                    |
| `relationship_id` | Relationship foreign key       | References `relationships.id`.                                                                                           |
| `metadata_key`    | Metadata/evidence key          | Portable text.                                                                                                           |
| `metadata_value`  | JSON-compatible metadata value | Use SQLAlchemy `JSON` as the portable abstraction; repository callers must not depend on PostgreSQL-only JSONB behavior. |
| `evidence_source` | Source of the evidence         | Nullable when inherited from relationship source.                                                                        |
| `created_at`      | Insert timestamp               | Repository-managed.                                                                                                      |

Design rule:

Relationship metadata may describe why a relationship exists, how it was calculated, and which evidence contributed to it. It must not store layout coordinates as graph truth.

### `regulatory_events` optional

Stores durable event data if regulatory events remain part of graph construction.

Compatibility baseline: if the current ORM models regulatory events as asset-scoped rows, implementation PRs should preserve that behavior initially. A normalized shared-event model, where one regulatory event links to many assets or relationships through `regulatory_event_impacts`, requires a dedicated schema/migration PR.

The recommended fields below describe the future normalized/shared-event target model. The initial compatibility-preserving implementation must either map the target concepts onto the current `RegulatoryEventORM` shape or include a dedicated migration plan. Current schema names such as `date` must not be silently replaced by target names such as `event_date` without backfill, compatibility, and rollback planning.

Recommended fields:

| Field          | Purpose                                     | Compatibility note                                                                                                                                                                                                               |
| -------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`           | Internal primary key                        | String-compatible internal key unless a later migration establishes a repo-wide surrogate-key policy.                                                                                                                            |
| `asset_id`     | Associated asset foreign key                | Required for the initial asset-scoped compatibility implementation; references `assets.id`.                                                                                                                                      |
| `event_key`    | Stable external or derived event identifier | Required and unique only for the normalized shared-event model; optional external identifier for asset-scoped compatibility mode.                                                                                                |
| `event_type`   | Regulatory event classification             | Portable string.                                                                                                                                                                                                                 |
| `title`        | Human-readable event label                  | Target field only; not currently present in `RegulatoryEventORM` or `migrations/001_initial.sql`.                                                                                                                                |
| `description`  | Event detail                                | Future target model may allow nulls, but the current operative schema/ORM requires NOT NULL; any relaxation of `description` or similar required fields needs a dedicated migration, backfill, compatibility, and rollback plan. |
| `event_date`   | Date or timestamp of event                  | Portable datetime/date handling; target name for the current `date` field.                                                                                                                                                       |
| `impact_score` | Event impact score                          | Preserve current non-null behavior; range -1.0 to 1.0.                                                                                                                                                                           |
| `jurisdiction` | Jurisdiction or regulator region            | Target field only; not currently present in `RegulatoryEventORM` or `migrations/001_initial.sql`.                                                                                                                                |
| `source`       | Source system or URL label                  | Target field only; not currently present in `RegulatoryEventORM` or `migrations/001_initial.sql`; do not store secrets.                                                                                                          |
| `attributes`   | JSON-compatible extended event attributes   | Target field only; not currently present in `RegulatoryEventORM` or `migrations/001_initial.sql`; avoid ORM attribute name `metadata`.                                                                                           |
| `created_at`   | Insert timestamp                            | Repository-managed.                                                                                                                                                                                                              |
| `updated_at`   | Last update timestamp                       | Repository-managed.                                                                                                                                                                                                              |

Current compatibility mapping:

| Current concept / column                                                                                                      | Target concept                                                       | Implementation rule                                                                                                                                                                                                                                                |
| ----------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `RegulatoryEventORM.id`                                                                                                       | `regulatory_events.id`                                               | Preserve as the internal key unless a migration PR changes key policy.                                                                                                                                                                                             |
| asset-scoped `asset_id` relationship                                                                                          | `regulatory_events.asset_id`                                         | Keep the current direct asset-scoped shape for the first compatibility implementation, or migrate to the join table in a dedicated schema PR.                                                                                                                      |
| `date`                                                                                                                        | `event_date`                                                         | Treat `event_date` as a target normalized name; preserve `date` until a migration/backfill PR renames or remaps it.                                                                                                                                                |
| `event_type`, `description`, `impact_score` — fields present in current `RegulatoryEventORM` and `migrations/001_initial.sql` | `event_type`, `description`, `impact_score` (target names unchanged) | These columns exist today and map directly; no migration or backfill required for the initial compatibility implementation.                                                                                                                                        |
| `title`, `jurisdiction`, `source`, `attributes` — **not present** in the current ORM or migration                             | `title`, `jurisdiction`, `source`, `attributes` (new target fields)  | These fields do not exist in `RegulatoryEventORM` or `migrations/001_initial.sql` today. Adding any of them requires a dedicated schema/migration PR with column defaults, nullability rules, backfill plan, rollback plan, and SQLite compatibility verification. |

Optional join table:

The current ORM/schema already includes an event-to-asset join-table concept via `regulatory_event_assets` in `src/data/db_models.py` and `migrations/001_initial.sql`. Future implementation PRs must treat `regulatory_event_impacts` as a possible evolution or expansion of that existing pattern, not as a brand-new event↔asset association concept.

`regulatory_event_impacts` may be introduced later if event-to-asset or event-to-relationship impact needs first-class querying. Where only event↔asset association is required, implementation should prefer mapping onto the existing `regulatory_event_assets` shape unless a dedicated migration PR justifies the new table and documents compatibility, backfill, and rollback behavior.

Recommended fields:

- `id`
- `regulatory_event_id`
- `asset_id`
- `relationship_id` (nullable)
- `impact_type`
- `impact_score`
- `confidence`
- `attributes`
- `created_at`

### `graph_builds` optional

Tracks graph rebuild/load state without making visualization layout the graph source of truth. If future implementation or migration planning prefers the term `graph_snapshots`, treat it as an alias/mapping for this same optional tracking table rather than as a distinct concept.

Recommended fields:

| Field                | Purpose                                                          | Compatibility note                                                                                        |
| -------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `id`                 | Internal primary key                                             | String-compatible internal key unless a later migration establishes a repo-wide surrogate-key policy.     |
| `graph_version`      | Application graph schema/semantic version                        | Portable text.                                                                                            |
| `graph_hash`         | Deterministic hash of assets, relationships, and evidence inputs | Used for stale detection; inputs must be sorted by stable keys and serialized canonically before hashing. |
| `build_reason`       | Initial build, rebuild, refresh, import, test seed, etc.         | Portable text.                                                                                            |
| `data_mode`          | Runtime data mode that produced the graph                        | Mirrors explicit runtime contract when implemented.                                                       |
| `asset_count`        | Asset count at build time                                        | Integer.                                                                                                  |
| `relationship_count` | Relationship count at build time                                 | Integer.                                                                                                  |
| `status`             | succeeded, failed, in_progress, partial, invalidated             | Portable string.                                                                                          |
| `started_at`         | Build start timestamp                                            | Repository-managed.                                                                                       |
| `completed_at`       | Build completion timestamp                                       | Nullable until finished.                                                                                  |
| `build_attributes`   | Non-secret build diagnostics                                     | SQLAlchemy `JSON`-compatible extended attributes.                                                         |

Design rule:

A graph build/snapshot record may identify which graph version is current and whether persisted graph state is valid. It should not replace normalized `assets` and `relationships` as the durable graph truth unless a later architecture decision explicitly chooses snapshot-only persistence.

## Repository boundary

Future implementation should expose graph persistence through repository interfaces. The codebase already has `AssetGraphRepository` in `src/data/repository.py`; implementation PRs should build on, split, or rename that existing repository rather than introduce a competing persistence layer. The API and graph services should not issue ad hoc queries directly.

The repository names below describe target responsibilities, not a requirement to create entirely new modules. A future implementation PR may keep `AssetGraphRepository` as the façade and delegate internally to asset, relationship, regulatory-event, and graph-build helpers, or it may split the existing repository into narrower classes if that reduces coupling without changing behavior.

Separation of concerns between repositories:

`AssetRepository` is responsible for asset-row lifecycle: upsert, retrieval by id or symbol, bulk load for graph reconstruction, and application-level field validation. It must not write relationship or regulatory-event rows.

`RelationshipRepository` is responsible for relationship rows and associated metadata/evidence: idempotent upsert, type- and asset-filtered queries, bulk replacement for full graph rebuilds, and any approved canonicalization of undirected edges. It must not write asset attributes beyond foreign-key identifiers.

A future `GraphSnapshotRepository` or `GraphBuildRepository` coordinates atomic publication of a complete graph build by recording build state, delegating asset and relationship writes, and marking the build `succeeded` only after required integrity checks pass.

### `AssetRepository`

Responsibilities:

- upsert assets by canonical key;
- fetch assets by symbol/id;
- list assets with filters needed by current API behavior;
- provide bulk load operations for graph reconstruction;
- enforce application-level validation that must remain portable across PostgreSQL and SQLite.

### `RelationshipRepository`

Responsibilities:

- upsert relationships idempotently;
- load relationships by asset, type, and graph build/snapshot where applicable;
- persist relationship evidence/metadata;
- enforce undirected-edge canonicalization where applicable;
- support bulk replacement for full graph rebuilds.

### `RegulatoryEventRepository` optional

Responsibilities:

- upsert regulatory events by stable event key;
- persist event-to-asset or event-to-relationship impacts if modeled;
- expose event inputs used by graph rebuild logic.

### `GraphSnapshotRepository` or `GraphBuildRepository`

Responsibilities:

- record graph build attempts and outcomes;
- store graph version/hash/timestamps;
- identify the latest valid persisted graph;
- mark stale or invalid graph builds;
- support explicit refresh/rebuild workflows later.

## Load and rebuild semantics

Startup and refresh behavior should eventually follow a deterministic policy.

1. Validate persistence configuration.
2. Check for the latest valid graph build/snapshot record.
3. If a valid persisted graph exists and no explicit refresh is requested, load assets, relationships, and metadata from persistence.
4. If persisted graph state is missing, stale, invalid, or explicitly refreshed, rebuild graph state from the configured source path.
5. After successful rebuild, persist assets, relationships, relationship metadata, optional regulatory events, and graph build metadata with atomic publish semantics. Small graphs may use one controlled transaction boundary. Larger graphs should use a staging/swap or build-version pointer pattern so partially written graph state is never published as latest valid state.
6. If persistence write fails after a rebuild, surface the degraded state explicitly rather than silently treating the runtime graph as durable.

Performance expectations for implementation PRs:

The first persistence implementation should record basic timings in the PR description for:

- loading persisted assets and relationships into the in-memory graph;
- full rebuild duration through the graph-build publish step;
- final consistency/integrity check duration.

These timings can be measured against the current sample dataset initially. Automated benchmarks and performance gates should be deferred to a dedicated performance PR.

Atomicity and publication rules:

- A rebuild must create or mark a graph build/snapshot as `in_progress` before writes begin.
- Loaders must only read a graph build/snapshot marked `succeeded` and selected as the latest valid build.
- Assets, relationships, relationship attributes, optional regulatory events, and graph build metadata must be written before the build is marked `succeeded`.
- Marking a build `succeeded`, or moving a `latest_valid` pointer to that build, must be the final publish step.
- A build must not become latest valid unless foreign-key integrity checks pass for required graph truth tables.
- On write failure, the build must be rolled back where possible or marked `failed`; partial writes must not be considered durable graph state.
- Concurrent rebuild attempts should be serialized by application-level locking (e.g., file-based locks for SQLite or distributed locks for hosted environments) or a single-writer application policy. Database advisory locking can be used as an optimization where available.

Staleness should be based on explicit signals rather than incidental process state:

- graph semantic version mismatch;
- graph hash mismatch;
- source data timestamp newer than persisted graph build;
- explicit operator refresh;
- failed or partial previous build;
- missing required tables or schema version mismatch after migrations exist.

## Source of truth rules

- The domain graph is the source of truth for assets and relationships.
- The database stores durable assets, relationships, evidence, and graph build metadata.
- Visualization payloads are derived views over graph truth.
- Layout coordinates are not evidence of relationships.
- Relationship computation must not read coordinates or layout metadata as financial input.
- Future layout persistence, if added, must use separate layout-specific tables keyed by graph hash/version and must remain optional for graph reconstruction.

## SQLite compatibility

SQLite remains supported for local development and tests. Implementation PRs should preserve this by default.

Compatibility rules:

- Prefer portable column types for the initial schema: text, integer, float/numeric, datetime represented through SQLAlchemy-compatible types.
- Avoid PostgreSQL enum types until there is an explicit abstraction or migration strategy.
- Use SQLAlchemy `JSON` as the default portable JSON abstraction. Repository callers must not depend on PostgreSQL-only JSONB operators unless a later PR adds dialect-specific handling and SQLite fallback behavior.
- Keep foreign keys and uniqueness constraints compatible with SQLite test behavior.
- Do not require PostgreSQL-only upsert syntax directly in repository callers.
- Keep local tests able to initialize an in-memory or temporary SQLite database.

## Future implementation PR split

The implementation should remain narrow and ordered.

1. Schema/repository PR: add models, repositories, and tests for persistence operations.
2. Save/load PR: persist and reconstruct graph state through repository interfaces.
3. Startup integration PR: wire persisted graph load/rebuild semantics into application startup.
4. Test expansion PR: add integration tests for PostgreSQL-like behavior where available and SQLite compatibility.
5. Hosted-readiness extension PR if needed: extend smoke/readiness checks only after persistence behavior is implemented.

Migration validation requirements for implementation PRs:

Each PR that changes schema or introduces a migration step must include:

- **Backfill plan**: describe how existing rows are transformed. If no target-environment rows exist, state that explicitly as a precondition rather than assuming clean-slate deployment.
- **Rollback plan**: provide a down-migration or explicit rollback procedure. PRs that cannot provide lossless rollback must document the data-loss risk and require explicit sign-off.
- **Compatibility verification**: record evidence that the migration ran on SQLite and, where available, PostgreSQL-compatible staging.
- **Column-type change procedure**: for type changes such as string-to-UUID or text-to-enum, use a two-phase plan: add/backfill the new column first, then remove the old column in a later migration step. Single-step destructive renames are not permitted without explicit data-loss acknowledgment.

## Validation for this PR

This PR is design-only. Validation is review-based:

- confirm the document defines PostgreSQL graph persistence boundaries;
- confirm SQLite compatibility is explicitly preserved;
- confirm graph truth and layout metadata are separated;
- confirm runtime implementation is deferred to later PRs;
- confirm no production deployment behavior changes are introduced.
