# PR: Typed rebuild lock TTL configuration chain (#1228 + configuration slice of #1219)

## Status

Planning reference for the PR on feature/issue-1228-lock-ttl-configuration-chain. Core implementation
landed in #1220; this PR completes boundary tests, operator docs, and settings field metadata.

## Primary objective

Single authoritative, validated configuration path:

`REBUILD_LOCK_TTL_SECONDS` → `Settings` (Pydantic, `gt=0`) → `GraphLifecycleSettings` → `graph_admin` rebuild orchestration.

## Architectural decisions (pre-implementation)

| Decision | Choice |
|----------|--------|
| Setting ownership | Base `Settings` in `src/config/settings.py` |
| Lifecycle boundary | `GraphLifecycleSettings` maps from `get_settings()` |
| Validation | `Field(gt=0)`; no `getattr` / manual `<= 0` guards in consumers |
| Backwards compatibility | Unset env → 300; invalid values fail at settings load |
| Out of scope | Lock refresh retry reimplementation (#1220) |

## Files changed

- `src/config/settings.py` — field `description`
- `tests/unit/test_graph_lifecycle_providers.py` — propagation test
- `docs/enterprise-deployment-operating-model.md` — operator env var
- `docs/graph-persistence-lifecycle-seam.md` — settings boundary

## Validation

```bash
pytest tests/unit/test_settings.py -k "rebuild_lock_ttl" -v
pytest tests/unit/test_graph_lifecycle_providers.py -v
```
