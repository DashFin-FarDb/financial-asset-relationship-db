# Graph persistence design

## Status

Design proposal. This document defines the graph persistence boundary for the next implementation phase after hosted preview verification. It intentionally does not introduce migrations, ORM models, repository implementations, runtime startup changes, or API behavior changes.

## Context

The hosted preview gate is complete. Issue #1108 records the verified hosted deployment, the hosted readiness smoke command, the passing smoke result, and manual endpoint evidence for health, detailed health, assets, metrics, and visualization endpoints.

The next production-path need is durable graph persistence. The current service can initialize and serve graph state, but graph truth is not yet represented as first-class durable state in PostgreSQL. Local development and tests must continue to work with SQLite.

The graph persistence boundary must also preserve the existing architectural separation between graph truth and graph layout. Financial relationships are domain data. Coordinates and visualization layout are presentation metadata and must not become the source of truth for relationships.

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

| Field         | Purpose                                                            | Compatibility note                                                                         |
| ------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `id`          | Internal primary key                                               | Use integer or UUID only if current DB policy supports both PostgreSQL and SQLite cleanly. |
| `symbol`      | Stable asset symbol or ticker                                      | Unique when symbol is the canonical asset key.                                             |
| `name`        | Display name                                                       | Nullable only if ingestion can legitimately omit it.                                       |
| `asset_class` | Asset class such as Equity, Fixed Income, Commodity, Currency      | Prefer portable string enum validation in application code before DB-specific enum types.  |
| `sector`      | Sector classification where applicable                             | Nullable for assets where sector does not apply.                                           |
| `issuer`      | Issuer or issuer family where applicable                           | Nullable.                                                                                  |
| `currency`    | Currency code where applicable                                     | Nullable.                                                                                  |
| `metadata`    | Source-specific attributes not yet promoted to first-class columns | JSON-compatible text/object with SQLite fallback handling.                                 |
| `created_at`  | Insert timestamp                                                   | Must be timezone-aware in application handling.                                            |
| `updated_at`  | Last update timestamp                                              | Updated by repository/service layer.                                                       |

Constraints and indexes:

- Unique index on `symbol` when symbol is canonical.
- Index on `asset_class`.
- Index on `sector` if sector filters remain common.
- Avoid PostgreSQL-only enum definitions unless there is a clear SQLite fallback.

### `relationships`

Stores durable graph edges between assets.

Recommended fields:

| Field               | Purpose                                                                                                           | Compatibility note                                           |
| ------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `id`                | Internal primary key                                                                                              | Integer or UUID based on repo-wide persistence convention.   |
| `source_asset_id`   | Source asset foreign key                                                                                          | References `assets.id`.                                      |
| `target_asset_id`   | Target asset foreign key                                                                                          | References `assets.id`.                                      |
| `relationship_type` | Domain relationship type, such as same-sector, issuer link, regulatory impact, correlation, or other future types | Validate allowed values in application code initially.       |
| `direction`         | Directionality marker such as directed, undirected, or inferred                                                   | Required so consumers do not infer direction from row order. |
| `weight`            | Relationship strength                                                                                             | Numeric/float compatible with SQLite and PostgreSQL.         |
| `confidence`        | Confidence score separate from strength                                                                           | Nullable if not all relationship types have confidence yet.  |
| `valid_from`        | Start of validity window                                                                                          | Nullable for timeless/static relationships.                  |
| `valid_to`          | End of validity window                                                                                            | Nullable for current/open-ended relationships.               |
| `source`            | Data/source system that produced the relationship                                                                 | Useful for evidence and rebuild diagnostics.                 |
| `created_at`        | Insert timestamp                                                                                                  | Repository-managed.                                          |
| `updated_at`        | Last update timestamp                                                                                             | Repository-managed.                                          |

Constraints and indexes:

- Foreign keys from `source_asset_id` and `target_asset_id` to `assets.id`.
- Composite index on `(source_asset_id, target_asset_id)`.
- Composite index on `(relationship_type, source_asset_id)`.
- Optional uniqueness constraint on `(source_asset_id, target_asset_id, relationship_type, valid_from)` if rebuild semantics require idempotent upserts.
- Application code should canonicalize undirected relationships so `A-B` and `B-A` are not duplicated unintentionally.

### `relationship_metadata`

Stores evidence/provenance and extensible relationship attributes without forcing every future signal into the `relationships` table.

Recommended fields:

| Field             | Purpose                        | Compatibility note                                                                                           |
| ----------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| `id`              | Internal primary key           | Same key policy as other tables.                                                                             |
| `relationship_id` | Relationship foreign key       | References `relationships.id`.                                                                               |
| `metadata_key`    | Metadata/evidence key          | Portable text.                                                                                               |
| `metadata_value`  | JSON-compatible metadata value | Store as JSON/JSONB in PostgreSQL only if SQLite fallback is abstracted; otherwise use serialized JSON text. |
| `evidence_source` | Source of the evidence         | Nullable when inherited from relationship source.                                                            |
| `created_at`      | Insert timestamp               | Repository-managed.                                                                                          |

Design rule:

Relationship metadata may describe why a relationship exists, how it was calculated, and which evidence contributed to it. It must not store layout coordinates as graph truth.

### `regulatory_events` optional

Stores durable event data if regulatory events remain part of graph construction.

Recommended fields:

| Field          | Purpose                                     | Compatibility note                       |
| -------------- | ------------------------------------------- | ---------------------------------------- |
| `id`           | Internal primary key                        | Same key policy as other tables.         |
| `event_key`    | Stable external or derived event identifier | Unique if available.                     |
| `event_type`   | Regulatory event classification             | Portable string.                         |
| `title`        | Human-readable event label                  | Required where available.                |
| `description`  | Event detail                                | Nullable.                                |
| `event_date`   | Date or timestamp of event                  | Portable datetime/date handling.         |
| `jurisdiction` | Jurisdiction or regulator region            | Nullable.                                |
| `source`       | Source system or URL label                  | Do not store secrets.                    |
| `metadata`     | JSON-compatible extended event attributes   | Same JSON compatibility policy as above. |
| `created_at`   | Insert timestamp                            | Repository-managed.                      |
| `updated_at`   | Last update timestamp                       | Repository-managed.                      |

Optional join table:

`regulatory_event_impacts` may be introduced later if event-to-asset or event-to-relationship impact needs first-class querying.

Recommended fields:

- `id`
- `regulatory_event_id`
- `asset_id`
- `relationship_id`, nullable
- `impact_type`
- `impact_score`
- `confidence`
- `metadata`
- `created_at`

### `graph_builds` or `graph_snapshots` optional

Tracks graph rebuild/load state without making visualization layout the graph source of truth.

Recommended fields:

| Field                | Purpose                                                  | Compatibility note                                  |
| -------------------- | -------------------------------------------------------- | --------------------------------------------------- |
| `id`                 | Internal primary key                                     | Same key policy as other tables.                    |
| `graph_version`      | Application graph schema/semantic version                | Portable text.                                      |
| `graph_hash`         | Hash of assets, relationships, and evidence inputs       | Used for stale detection.                           |
| `build_reason`       | Initial build, rebuild, refresh, import, test seed, etc. | Portable text.                                      |
| `data_mode`          | Runtime data mode that produced the graph                | Mirrors explicit runtime contract when implemented. |
| `asset_count`        | Asset count at build time                                | Integer.                                            |
| `relationship_count` | Relationship count at build time                         | Integer.                                            |
| `status`             | succeeded, failed, partial, invalidated                  | Portable string.                                    |
| `started_at`         | Build start timestamp                                    | Repository-managed.                                 |
| `completed_at`       | Build completion timestamp                               | Nullable until finished.                            |
| `metadata`           | Non-secret build diagnostics                             | JSON-compatible.                                    |

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
2. Check for a latest valid graph build/snapshot record.
3. If a valid persisted graph exists and no explicit refresh is requested, load assets, relationships, and metadata from persistence.
4. If persisted graph state is missing, stale, invalid, or explicitly refreshed, rebuild graph state from the configured source path.
5. After successful rebuild, persist assets, relationships, relationship metadata, optional regulatory events, and graph build metadata in one controlled transaction boundary where feasible.
6. If persistence write fails after a rebuild, surface the degraded state explicitly rather than silently treating the runtime graph as durable.

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
- Use JSON fields only through a compatibility layer. If necessary, store JSON as text in SQLite and JSON/JSONB in PostgreSQL behind the ORM model or repository layer.
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
