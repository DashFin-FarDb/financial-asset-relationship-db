# Graph persistence lifecycle seam

## Purpose

This note identifies the smallest safe seam for integrating durable graph
persistence into the FastAPI application lifecycle after #1114 and #1119.

It does not implement persistence loading or saving.

## Current baseline

### Repository contract

#1114 added repository helpers for graph snapshot persistence:

- `AssetGraphRepository.save_graph()`
- `AssetGraphRepository.load_graph()`

#1119 added graph persistence round-trip contract tests that verify
graph -> database -> graph behavior for assets, relationships, and regulatory
events.

### Runtime boundary

The repository can persist and reconstruct graph truth, but the FastAPI runtime
still initializes its in-memory graph through the existing lifecycle path.

This document maps that lifecycle path and identifies where future
`load_graph()` integration should be considered.

## Current lifecycle map

### Application startup

`api/app_factory.py` owns FastAPI application construction and lifespan
registration.

Current startup behavior:

1. FastAPI starts.
2. `lifespan()` calls `get_graph()`.
3. If graph initialization succeeds, startup logs
   `Application startup complete - graph initialized`.
4. If graph initialization fails, startup logs the exception and re-raises,
   aborting startup.

This is the current startup hook to document. This PR does not change it.

### Graph singleton lifecycle

`api/graph_lifecycle.py` owns the actual graph singleton lifecycle:

- `graph_state.graph`
- `graph_state.graph_factory`
- `graph_lock`
- `get_graph()`
- `set_graph()`
- `set_graph_factory()`
- `reset_graph()`
- `_initialize_graph()`

`get_graph()` lazily initializes `graph_state.graph` under `graph_lock`.

Current `_initialize_graph()` source order:

1. Use `graph_state.graph_factory` when present.
2. Otherwise, if `graph_cache_path` is configured (env:
   `GRAPH_CACHE_PATH`), initialize from that path (and this branch may still
   enable `RealDataFetcher` network behavior when `use_real_data_fetcher` is
   true (env: `USE_REAL_DATA_FETCHER`)).
3. Otherwise, if `graph_cache_path` is not configured (env:
   `GRAPH_CACHE_PATH`), use `use_real_data_fetcher` (env:
   `USE_REAL_DATA_FETCHER`) with `real_data_cache_path` (env:
   `REAL_DATA_CACHE_PATH`) when enabled.
4. Otherwise, fall back to `create_sample_database()`.

This is the key integration seam for future `AssetGraphRepository.load_graph()`
work.

### Backward compatibility layer

`api/main.py` remains the public compatibility entrypoint.

Important compatibility behavior:

- It re-exports lifecycle helpers for older callers and tests.
- It initializes a module-level `graph = _get_graph()` reference for older
  callers and tests.
- `api.main.set_graph()` updates lifecycle state and the module-level `graph`
  reference.
- `api.main.reset_graph()` resets lifecycle state and clears the module-level
  `graph` reference so the next access falls through to lifecycle
  initialization.

Future integration must preserve this compatibility layer.

### Router access path

Routers generally access graph state through helper imports.

`api/router_helpers.py` first checks `api.main.graph` for compatibility, then
falls through to `api.graph_lifecycle.get_graph()`.

Future startup or lifecycle changes must not leave `api.main.graph` stale or
inconsistent with the lifecycle graph.

## Persistence integration seam

The future load integration should be considered at
`api.graph_lifecycle._initialize_graph()` or in a small helper called by
`_initialize_graph()`.

Recommended future seam:

```text
api.graph_lifecycle._initialize_graph()
    -> if explicit graph factory exists: preserve current behavior
    -> else attempt persisted graph load if graph persistence is configured
       and persisted graph rows exist
    -> else preserve existing graph_cache_path / real-data / sample fallback
       order
```

Alternative seam:

```text
api.app_factory.lifespan()
    -> call a persistence-aware initialization helper before get_graph()
```

Rejected for now:

- router-level persistence loading;
- endpoint-level lazy persistence loading;
- automatic `save_graph()` during startup;
- persistence in `api.main` compatibility wrappers.

## Settings boundary

`src/config/settings.py` already exposes database-related settings:

- `asset_graph_database_url`
- `database_url`
- `postgres_url`

It also exposes graph source settings:

- `graph_cache_path`
- `real_data_cache_path`
- `use_real_data_fetcher`

Rebuild coordination settings:

- `rebuild_lock_ttl_seconds` (env: `REBUILD_LOCK_TTL_SECONDS`, default `300`, validated `> 0`)
- Propagated to `GraphLifecycleSettings` in `api/graph_lifecycle_providers.py` for graph admin rebuild orchestration (distributed lock TTL and heartbeat interval)

`src/data/database.py` currently resolves the asset graph SQLAlchemy engine from
`settings.asset_graph_database_url`, falling back to `sqlite:///./asset_graph.db`
when unset.

This seam note does not choose the final runtime setting for graph persistence.
The next implementation PR must explicitly decide whether startup graph
persistence is governed by `asset_graph_database_url` (env:
`ASSET_GRAPH_DATABASE_URL`), `database_url` (env: `DATABASE_URL`),
`postgres_url` (env: `POSTGRES_URL`), a new explicit setting, or current
repository/session-factory defaults.

Until that implementation PR makes the decision, references to these settings in
this document are descriptive, not prescriptive.

## Key design questions for the next PR

The implementation PR must answer these before coding:

1. **Which setting governs graph persistence?**
   - `DATABASE_URL`
   - `ASSET_GRAPH_DATABASE_URL`
   - `POSTGRES_URL`
   - a new explicit setting
   - current repository/session-factory defaults
2. **What counts as an existing persisted graph?**
   - at least one asset row;
   - any relationship row;
   - any regulatory event row;
   - any graph-owned table row.
3. **What happens when persistence is configured but empty?**
4. **What happens when persistence is configured but unreachable or the
   schema is missing?**
5. **Should the startup path automatically call `init_db()` if persistence
   is enabled?**
6. **How does persisted graph loading interact with:**
   - `GRAPH_CACHE_PATH`;
   - `USE_REAL_DATA_FETCHER`;
   - sample fallback;
   - `set_graph_factory()` tests;
   - `reset_graph()`;
   - `api.main.graph` compatibility.
7. **How do we ensure startup load never triggers destructive
   `save_graph()` snapshot replacement?**
8. **How is the database session managed during the one-off startup load?**
   - Should startup loading create a short-lived session from the existing
     session factory?
   - Where is that session closed?
   - How are startup-load session failures reported without leaking database
     connection details?

## Save behavior boundary

`save_graph()` has destructive snapshot semantics.

Therefore, startup load and save/rebuild integration must remain separate PRs.

Future startup loading must not:

- overwrite persisted graph truth;
- regenerate sample data and immediately persist it;
- trigger `save_graph()` during requests to read-only endpoints;
- persist layout or visualization state;
- silently change reset or reinitialize semantics.

## Recommended next implementation PR

Title:

```text
Load persisted graph during application startup
```

Expected behavior:

- If graph persistence is configured and persisted graph rows exist, load graph
  truth through `AssetGraphRepository.load_graph()`.
- If no persisted graph exists, preserve current initialization behavior.
- Preserve `graph_state.graph_factory` precedence.
- Preserve `reset_graph()` semantics.
- Preserve `api.main.graph` compatibility.

## Test plan for the next PR

The startup-load implementation PR should include tests for:

### Existing factory behavior

- `set_graph_factory()` still takes precedence.
- No repository load is attempted when a factory is set.

### Empty persistence fallback

- A configured empty database does not produce an empty accidental production
  graph unless explicitly selected.
- The existing fallback path remains unchanged.

### Persisted graph startup load

- Persisted assets are loaded.
- Persisted relationships are loaded.
- Persisted regulatory events are loaded.

### Directed relationship contract

- Explicit reverse strengths survive startup loading.

### Legacy compatibility

- `bidirectional=True` rows expand only when no explicit reverse row exists.

### Reset semantics

- `reset_graph()` clears cached state and settings cache as before.
- The next `get_graph()` reinitializes using the selected source.

### Compatibility reference

- `api.main.graph` and lifecycle graph do not diverge after startup, load, or
  reset.

### Failure handling

- Configured unreachable database behavior is explicit and tested.

### Startup session management

- Startup graph loading uses a bounded, short-lived database session.
- The session is closed after load success or failure.
- Session creation/load failures follow the selected startup failure policy.

## Non-goals

This seam note does not implement:

- repository loading during startup;
- repository saving;
- reset or reinitialize persistence behavior;
- hosted readiness checks;
- migrations;
- API route changes;
- frontend changes;
- layout persistence;
- scanner configuration changes;
- Master Production Readiness Checklist - FarDb #1028 changes.

## Follow-up sequence

1. Implement startup persisted graph loading.
2. Define explicit save/rebuild trigger semantics.
3. Extend hosted readiness to prove persisted graph loading.
4. Defer migrations until schema evolution becomes a concrete blocker.
5. Defer layout persistence until graph-truth lifecycle behavior is stable.

## Appendix: Current implementation anchors

These snippets are included only as audit anchors for the next implementation
PR. They are not a second source of truth for runtime behavior; implementation
work must still verify the live source before changing code.

### `api/app_factory.py` startup hook

```python
@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    try:
        get_graph()
        logger.info("Application startup complete - graph initialized")
    except Exception:
        logger.exception("Failed to initialize graph during startup")
        raise

    yield

    logger.info("Application shutdown")
```

### `api/graph_lifecycle.py` initialization order

```python
def _initialize_graph() -> AssetRelationshipGraph:
    if graph_state.graph_factory is not None:
        return graph_state.graph_factory()

    settings = get_settings()
    cache_path = settings.graph_cache_path
    use_real_data = settings.use_real_data_fetcher

    if cache_path:
        fetcher = RealDataFetcher(
            cache_path=cache_path,
            enable_network=use_real_data,
        )
        return fetcher.create_real_database()

    if use_real_data:
        real_data_cache_path = settings.real_data_cache_path
        fetcher = RealDataFetcher(
            cache_path=real_data_cache_path,
            enable_network=True,
        )
        return fetcher.create_real_database()

    return create_sample_database()
```

### Relevant settings names

- `asset_graph_database_url`
- `database_url`
- `postgres_url`
- `graph_cache_path`
- `real_data_cache_path`
- `use_real_data_fetcher`
