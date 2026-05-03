# Graph persistence design

## Status

Design proposal. This document defines the graph persistence boundary for the next implementation phase after hosted preview verification. It intentionally does not introduce migrations, ORM models, repository implementations, runtime startup changes, or API behavior changes.

## Context

The hosted preview gate is complete. Issue #1108 records the verified hosted deployment, the hosted readiness smoke command, the passing smoke result, and manual endpoint evidence for health, detailed health, assets, metrics, and visualization endpoints.

The next production-path need is durable graph persistence. The current service can initialize and serve graph state, but graph truth is not yet represented as first-class durable state in PostgreSQL. Local development and tests must continue to work with SQLite.

The graph persistence boundary must also preserve the existing architectural separation between graph truth and graph layout. Financial relationships are domain data. Coordinates and visualization layout are presentation metadata and must not become the source of truth for relationships.

## Existing schema alignment

This document is a target persistence-boundary design for the next graph persistence phase. It does not replace the current SQLAlchemy persistence layer or existing migration files in this PR.

Future implementation PRs must explicitly reconcile this design with the current schema and ORM models, including `src/data/db_models.py` and `migrations/001_initial.sql`. Where this document uses target names such as `relationships` or `relationship_metadata`, implementation PRs must either:

1. map those concepts onto the existing table/model names, such as `asset_relationships`, without changing behavior; or
2. introduce a migration plan that explains the rename or schema transition, including backfill, compatibility, rollback, and repository/service-layer changes.

Until such an implementation PR is accepted, the existing ORM and migration files remain the operative schema contract.

## Problem statement

FarDb can now be deployed to a hosted preview and can pass hosted readiness checks, but graph data is still treated primarily as runtime-initialized/sample/cache state rather than as durable graph state with explicit persistence semantics.

This creates four production risks:

1. graph state cannot be independently inspected, versioned, or rebuilt from persistent evidence;
2. startup/load behavior is ambiguous when persisted graph state is missing or stale;
3. future schema work may drift between PostgreSQL and SQLite if compatibility is not designed up front;
4. layout or visualization persistence could accidentally become coupled to graph truth if boundaries are not explicit.

## Goals

- Define PostgreSQL as the durable persistence boundary for graph truth in hosted and production environments.
- Preserve SQLite compatibility for local development and automated tests.
- Define tables for assets, relationships, relationship metadata, and optional regulatory events.
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

| Field         | Purpose                                                            | Compatibility note                                                                                                |
| ------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `id`          | Internal primary key                                               | String-compatible primary key to match the current `AssetORM.id`; integer/UUID requires a separate migration PR.  |
| `symbol`      | Stable asset symbol or ticker                                      | Add a unique constraint only if `symbol` is confirmed as the canonical asset lookup key for all persisted assets. |
| `name`        | Display name                                                       | Nullable only if ingestion can legitimately omit it.                                                              |
| `asset_class` | Asset class such as Equity, Fixed Income, Commodity, Currency      | Prefer portable string enum validation in application code before DB-specific enum types.                         |
| `sector`      | Sector classification where applicable                             | Nullable for assets where sector does not apply.                                                                  |
| `issuer`      | Issuer or issuer family where applicable                           | Nullable.                                                                                                         |
| `currency`    | Currency code where applicable                                     | Nullable.                                                                                                         |
| `attributes`  | Source-specific attributes not yet promoted to first-class columns | SQLAlchemy `JSON`-compatible extended attributes; avoid ORM attribute name `metadata`.                            |
| `created_at`  | Insert timestamp                                                   | Must be timezone-aware in application handling.                                                                   |
| `updated_at`  | Last update timestamp                                              | Updated by repository/service layer.                                                                              |

Constraints and indexes:

- Unique index on `symbol` when symbol is canonical.
- Index on `asset_class`.
- Index on `sector` if sector filters remain common.
- Avoid PostgreSQL-only enum definitions unless there is a clear SQLite fallback.

### `relationships`

Stores durable graph edges between assets.

Recommended fields:

| Field               | Purpose                                                                                                           | Compatibility note                                                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                | Internal primary key                                                                                              | Integer or UUID based on repo-wide persistence convention.                                                                             |
| `source_asset_id`   | Source asset foreign key                                                                                          | References `assets.id`.                                                                                                                |
| `target_asset_id`   | Target asset foreign key                                                                                          | References `assets.id`.                                                                                                                |
| `relationship_type` | Domain relationship type, such as same-sector, issuer link, regulatory impact, correlation, or other future types | Validate allowed values in application code initially.                                                                                 |
| `bidirectional`     | Current ORM-compatible direction marker                                                                           | Boolean compatibility baseline for `AssetRelationshipORM.bidirectional`; a later enum-based `direction` field requires a migration PR. |
| `strength`          | Relationship strength                                                                                             | Target name should remain compatible with `AssetRelationshipORM.strength`; use `FLOAT(53)` / double precision.                         |
| `confidence`        | Confidence score separate from strength                                                                           | `FLOAT(53)` / double precision; nullable if not all relationship types have confidence yet.                                            |
| `valid_from`        | Start of validity window                                                                                          | Nullable for timeless/static relationships.                                                                                            |
| `valid_to`          | End of validity window                                                                                            | Nullable for current/open-ended relationships.                                                                                         |
| `source`            | Data/source system that produced the relationship                                                                 | Useful for evidence and rebuild diagnostics.                                                                                           |
| `created_at`        | Insert timestamp                                                                                                  | Repository-managed.                                                                                                                    |
| `updated_at`        | Last update timestamp                                                                                             | Repository-managed.                                                                                                                    |

Constraints and indexes:

- Foreign keys from `source_asset_id` and `target_asset_id` to `assets.id`.
- Composite index on `(source_asset_id, target_asset_id)`.
- Composite index on `(relationship_type, source_asset_id)`.
- Compatibility baseline: preserve the current uniqueness semantics on `(source_asset_id, target_asset_id, relationship_type)` unless a migration PR explicitly introduces validity-windowed relationship history.
- If validity-windowed history is added later, avoid nullable fields inside idempotency constraints; use a non-null normalized validity key or a partial/generated-index strategy with PostgreSQL and SQLite behavior documented.
- Compatibility baseline: preserve current runtime semantics for bidirectional relationships. If the runtime stores reciprocal directed edges, persistence should not collapse them to one row unless the implementation PR also updates query paths, indexing, and reconstruction semantics.

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

Recommended fields:

| Field          | Purpose                                     | Compatibility note                                                                                                                |
| -------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `id`           | Internal primary key                        | String-compatible internal key unless a later migration establishes a repo-wide surrogate-key policy.                             |
| `event_key`    | Stable external or derived event identifier | Required and unique only for the normalized shared-event model; optional external identifier for asset-scoped compatibility mode. |
| `event_type`   | Regulatory event classification             | Portable string.                                                                                                                  |
| `title`        | Human-readable event label                  | Required where available.                                                                                                         |
| `description`  | Event detail                                | Nullable.                                                                                                                         |
| `event_date`   | Date or timestamp of event                  | Portable datetime/date handling.                                                                                                  |
| `jurisdiction` | Jurisdiction or regulator region            | Nullable.                                                                                                                         |
| `source`       | Source system or URL label                  | Do not store secrets.                                                                                                             |
| `attributes`   | JSON-compatible extended event attributes   | SQLAlchemy `JSON`-compatible extended attributes; avoid ORM attribute name `metadata`.                                            |
| `created_at`   | Insert timestamp                            | Repository-managed.                                                                                                               |
| `updated_at`   | Last update timestamp                       | Repository-managed.                                                                                                               |

Optional join table:

`regulatory_event_impacts` may be introduced later if event-to-asset or event-to-relationship impact needs first-class querying.

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

### `graph_builds` or `graph_snapshots` optional

Tracks graph rebuild/load state without making visualization layout the graph source of truth.

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
| `status`             | succeeded, failed, partial, invalidated                          | Portable string.                                                                                          |
| `started_at`         | Build start timestamp                                            | Repository-managed.                                                                                       |
| `completed_at`       | Build completion timestamp                                       | Nullable until finished.                                                                                  |
| `build_attributes`   | Non-secret build diagnostics                                     | SQLAlchemy `JSON`-compatible extended attributes.                                                         |

Design rule:

A graph build/snapshot record may identify which graph version is current and whether persisted graph state is valid. It should not replace normalized `assets` and `relationships` as the durable graph truth unless a later architecture decision explicitly chooses snapshot-only persistence.

## Repository boundary

Future implementation should introduce repositories behind a persistence interface. The API and graph services should not issue ad hoc queries directly.

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

Atomicity and publication rules:

- A rebuild must create or mark a graph build/snapshot as `in_progress` before writes begin.
- Loaders must only read a graph build/snapshot marked `succeeded` and selected as the latest valid build.
- Assets, relationships, relationship attributes, optional regulatory events, and graph build metadata must be written before the build is marked `succeeded`.
- Marking a build `succeeded`, or moving a `latest_valid` pointer to that build, must be the final publish step.
- A build must not become latest valid unless foreign-key integrity checks pass for required graph truth tables.
- On write failure, the build must be rolled back where possible or marked `failed`; partial writes must not be considered durable graph state.
- Concurrent rebuild attempts should be serialized by repository-level locking, database advisory locking where available, or a single-writer application policy.

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

## Validation for this PR

This PR is design-only. Validation is review-based:

- confirm the document defines PostgreSQL graph persistence boundaries;
- confirm SQLite compatibility is explicitly preserved;
- confirm graph truth and layout metadata are separated;
- confirm runtime implementation is deferred to later PRs;
- confirm no production deployment behavior changes are introduced.
