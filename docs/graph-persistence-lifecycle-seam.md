# Graph persistence lifecycle seam

## Purpose

This note identifies the smallest safe seam for integrating durable graph persistence into the FastAPI application lifecycle after #1114 and #1119.

It does not implement persistence loading or saving.

## Current baseline

### Repository contract

- #1114 added `AssetGraphRepository.save_graph()` and `AssetGraphRepository.load_graph()`.
- #1119 added graph → DB → graph round-trip contract tests.

### Runtime boundary

The repository can persist and reconstruct graph truth, but the FastAPI runtime still initializes its in-memory graph through the existing lifecycle path.

## Current lifecycle map

### Application startup

`api/app_factory.py` defines the FastAPI lifespan handler.

Current behavior:

1. FastAPI starts.
2. `lifespan()` calls `get_graph()`.
3. If graph initialization succeeds, startup completes.
4. If graph initialization fails, startup aborts.

### Graph singleton lifecycle

`api/graph_lifecycle.py` owns:

- `graph_state.graph`
- `graph_state.graph_factory`
- `graph_lock`
- `get_graph()`
- `set_graph()`
- `set_graph_factory()`
- `reset_graph()`
- `_initialize_graph()`

Current initialization order:

1. Use `graph_state.graph_factory` when present.
2. Use `GRAPH_CACHE_PATH` through `RealDataFetcher` when configured.
3. Use `USE_REAL_DATA_FETCHER` and `REAL_DATA_CACHE_PATH` when enabled.
4. Fall back to `create_sample_database()`.

### Backward compatibility layer

`api/main.py` remains the public compatibility entrypoint.

Important compatibility behavior:

- `api.main.graph` is initialized for older tests/callers.
- `api.main.set_graph()` updates lifecycle state and the module-level graph reference.
- `api.main.reset_graph()` resets lifecycle state and clears the module-level graph reference.

### Router access path

Routers generally access graph state through helper imports.

`api/router_helpers.py` first checks `api.main.graph` for compatibility and then falls through to `api.graph_lifecycle.get_graph()`.

Future lifecycle changes must not leave these paths inconsistent.

## Persistence integration seam

The future load integration should be considered at `_initialize_graph()` or in a small helper called by `_initialize_graph()`.

### Recommended future seam

```text
api.graph_lifecycle._initialize_graph()
    → if explicit graph factory exists: preserve current behavior
    → else attempt persisted graph load if graph persistence is configured and persisted graph rows exist
    → else preserve existing graph_cache_path / real-data / sample fallback order
```

### Alternative seam

```text
api.app_factory.lifespan()
    → call a persistence-aware initialization helper before get_graph()
```

### Rejected for now

- router-level persistence loading;
- endpoint-level lazy persistence loading;
- automatic `save_graph()` during startup;
- persistence in `api.main` compatibility wrappers.

## Key design questions for next PR

The implementation PR must answer these before coding:

1. **Which setting governs graph persistence?**
   - `DATABASE_URL`
   - `ASSET_GRAPH_DATABASE_URL`
   - a new explicit setting
   - current repository/session factory defaults

2. **What counts as an existing persisted graph?**
   - at least one asset row;
   - any relationship row;
   - any regulatory event row;
   - any graph-owned table row.

3. **What happens when persistence is configured but empty?**

4. **What happens when persistence is configured but unreachable?**

5. **How does persisted graph loading interact with:**
   - `GRAPH_CACHE_PATH`;
   - `USE_REAL_DATA_FETCHER`;
   - sample fallback;
   - `set_graph_factory()` tests;
   - `reset_graph()`;
   - `api.main.graph` compatibility.

6. **How do we ensure startup load never triggers destructive `save_graph()` snapshot replacement?**

## Save behavior boundary

`save_graph()` has destructive snapshot semantics.

Therefore, startup load and save/rebuild integration must remain separate PRs.

Future startup loading must not:

- overwrite persisted graph truth;
- regenerate sample data and immediately persist it;
- save on read-only endpoints;
- persist layout/visualization state;
- silently change reset/reinitialize semantics.

## Recommended next implementation PR

### Title

Load persisted graph during application startup

### Expected behavior

1. If graph persistence is configured and persisted graph rows exist, load graph truth through `AssetGraphRepository.load_graph()`.
2. If no persisted graph exists, preserve current initialization behavior.
3. Preserve `graph_state.graph_factory` precedence.
4. Preserve `reset_graph()` semantics.
5. Preserve `api.main.graph` compatibility.

## Test plan for next PR

The startup-load implementation PR should include tests for:

### Existing factory behavior

- `set_graph_factory()` still takes precedence.
- No repository load is attempted when a factory is set.

### Empty persistence fallback

- Configured empty DB does not produce an empty accidental production graph unless explicitly selected.
- Existing fallback path remains unchanged.

### Persisted graph startup load

- Persisted assets are loaded;
- Persisted relationships are loaded;
- Persisted regulatory events are loaded.

### Directed relationship contract

- Explicit reverse strengths survive startup loading.

### Legacy compatibility

- `bidirectional=True` row expands only when no explicit reverse row exists.

### Reset semantics

- `reset_graph()` clears cached state and settings cache as before;
- Next `get_graph()` reinitializes using the selected source.

### Compatibility reference

- `api.main.graph` and lifecycle graph do not diverge after startup/load/reset.

### Failure handling

- Configured unreachable DB behavior is explicit and tested.

## Non-goals

This seam note does not implement:

- repository loading during startup;
- repository saving;
- reset/reinitialize persistence behavior;
- hosted readiness checks;
- migrations;
- API route changes;
- frontend changes;
- layout persistence;
- scanner configuration changes.

## Follow-up sequence

1. Implement startup persisted graph loading.
2. Define explicit save/rebuild trigger semantics.
3. Extend hosted readiness to prove persisted graph loading.
4. Defer migrations until schema evolution becomes a concrete blocker.
5. Defer layout persistence until graph-truth lifecycle behavior is stable.

---

## Appendix: Current implementation details

### `api/app_factory.py` lifespan handler

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

### Available settings (src/config/settings.py)

- `asset_graph_database_url: str | None`
- `database_url: str | None`
- `postgres_url: str | None`
- `graph_cache_path: str | None`
- `real_data_cache_path: str | None`
- `use_real_data_fetcher: bool`
