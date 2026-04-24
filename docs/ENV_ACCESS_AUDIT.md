# Runtime Environment Access Audit

**Date:** 2026-04-24
**Purpose:** Complete inventory and classification of direct environment variable access across runtime files
**Scope:** `api/` and `src/` directories (excluding tests/scripts)

## Executive Summary

This audit catalogues all direct `os.getenv()` and `os.environ[]` usage in runtime code to inform settings migration strategy. All 15 runtime occurrences have been classified according to migration priority rules.

**Key Findings:**

- **No immediate migration candidates within the audit scope** - Recent PRs (e.g., #1051) have already migrated appropriate runtime candidates from `api/` and `src/`
- **All remaining env access has architectural justification** for staying as direct reads
- **No dead code found** - All env variable access is actively used
- **Settings layer functioning correctly** - Centralized config mechanism working as designed

## Classification Results

### Summary by Action

| Classification                | Count  | Percentage |
| ----------------------------- | ------ | ---------- |
| DEFER (intentional)           | 8      | 53%        |
| LEAVE LOCAL (settings loader) | 7      | 47%        |
| MIGRATE NOW                   | 0      | 0%         |
| REMOVE (dead code)            | 0      | 0%         |
| **TOTAL**                     | **15** | **100%**   |

### Classification Rules Applied

1. **MIGRATE NOW**: Core runtime config that is stable, non-dynamic, and safe via cached settings
2. **DEFER**: Dynamic behavior, security-sensitive startup, or anything where caching changes semantics
3. **LEAVE LOCAL**: CLI scripts, tests, dev tooling, or the settings loader itself
4. **REMOVE**: Unused or stale code

## Detailed Inventory

### api/auth.py - DEFER (6 occurrences)

All environment access in this file is classified as **DEFER** due to security-sensitive startup characteristics.

| Line | Variable          | Usage           | Rationale for DEFER                                                                                                                                     |
| ---- | ----------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 20   | `SECRET_KEY`      | JWT signing key | Security-critical crypto key; migration should be handled in a dedicated auth settings seam to preserve fail-fast startup and token validation behavior |
| 221  | `ADMIN_USERNAME`  | User seeding    | Startup-only bootstrap; read once during module init; not runtime config                                                                                |
| 222  | `ADMIN_PASSWORD`  | User seeding    | Startup-only bootstrap; read once during module init; not runtime config                                                                                |
| 227  | `ADMIN_EMAIL`     | User seeding    | Startup-only bootstrap; read once during module init; not runtime config                                                                                |
| 228  | `ADMIN_FULL_NAME` | User seeding    | Startup-only bootstrap; read once during module init; not runtime config                                                                                |
| 229  | `ADMIN_DISABLED`  | User seeding    | Startup-only bootstrap; read once during module init; not runtime config                                                                                |

**Analysis:**

`SECRET_KEY` (line 20): Used for JWT encoding/decoding. It is a valid future settings-migration candidate, but should be deferred to a dedicated auth settings seam because it is security-critical and currently participates in module-level fail-fast initialization.

- `ADMIN_*` variables (lines 221-229): Used exclusively in `_seed_credentials_from_env()` function, called once at module initialization (line 242). These are transient bootstrap credentials for initial user setup, not ongoing runtime configuration. They are not user-facing runtime settings and are intentionally read once during initialization. Migrating to Settings would not improve semantics.

### api/cors_utils.py - DEFER (2 occurrences)

All environment access in this file is classified as **DEFER** because migrating it changes CORS/test override semantics and should be handled as a dedicated CORS settings seam.

| Line | Variable          | Usage                         | Rationale for DEFER                                                                                       |
| ---- | ----------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------- |
| 131  | `ENV`             | CORS validation (per-request) | Duplicates `Settings.env`; migrate only in a dedicated CORS seam due to dynamic override behavior         |
| 134  | `ALLOWED_ORIGINS` | CORS validation (per-request) | Duplicates `Settings.allowed_origins`; migrate only in a dedicated CORS seam due to parsing/behavior risk |

**Analysis:**

Both variables are read within the `validate_origin()` function, which is called on CORS validation paths. These same variables are already represented in `src/config/settings.py`, so the current implementation creates a split source of truth.

This is an architectural smell, not a pattern to copy:

- production code is currently shaped partly by test override convenience;
- direct reads bypass the typed Settings model;
- parsing behavior can diverge from `Settings.allowed_origins`;
- future changes risk inconsistent CORS behavior depending on which path reads the env.

Classification remains **DEFER**, not because the current duplication is ideal, but because migrating this safely requires a dedicated CORS settings PR with explicit tests for dynamic override behavior, cache invalidation, and parsing compatibility.

### src/config/settings.py - LEAVE LOCAL (7 occurrences)

All environment access in this file is classified as **LEAVE LOCAL** because this IS the centralized settings mechanism.

| Line | Variable                   | Purpose                                          |
| ---- | -------------------------- | ------------------------------------------------ |
| 105  | `ENV`                      | Settings loader - canonical env→Settings mapping |
| 106  | `ALLOWED_ORIGINS`          | Settings loader - canonical env→Settings mapping |
| 107  | `GRAPH_CACHE_PATH`         | Settings loader - canonical env→Settings mapping |
| 108  | `REAL_DATA_CACHE_PATH`     | Settings loader - canonical env→Settings mapping |
| 109  | `USE_REAL_DATA_FETCHER`    | Settings loader - canonical env→Settings mapping |
| 110  | `ASSET_GRAPH_DATABASE_URL` | Settings loader - canonical env→Settings mapping |
| 111  | `DATABASE_URL`             | Settings loader - canonical env→Settings mapping |

**Analysis:**

These reads occur in the `load_settings()` function (lines 92-112), which is the canonical loader for the centralized settings mechanism. By definition, the loader must read from the environment. These reads are already cached via the `@lru_cache` decorator on `get_settings()` (line 115).

**Note:** `DATABASE_URL` was recently migrated in `api/database.py` (PR #1051), demonstrating the settings migration pattern working correctly.

## Non-Runtime Files (Out of Scope)

For completeness, environment variable usage in non-runtime files:

| File                                   | Variables                                                           | Classification | Notes                          |
| -------------------------------------- | ------------------------------------------------------------------- | -------------- | ------------------------------ |
| `.github/scripts/schema_report_cli.py` | `SCHEMA_REPORT_LOG`                                                 | LEAVE LOCAL    | CLI tooling                    |
| `main.py`                              | `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`                      | LEAVE LOCAL    | Dev/test script                |
| `run_tests.py`                         | `TEST_SECRET_KEY`                                                   | LEAVE LOCAL    | Test runner                    |
| `test_supabase.py`                     | `SUPABASE_URL`, `SUPABASE_KEY`, `RUN_SUPABASE_TESTS`, `LOAD_DOTENV` | LEAVE LOCAL    | Test file                      |
| `test_postgres.py`                     | `ASSET_GRAPH_DATABASE_URL`, `DATABASE_URL`, `RUN_POSTGRES_TESTS`    | LEAVE LOCAL    | Test file                      |
| `tests/**`                             | Various                                                             | LEAVE LOCAL    | Test files excluded from scope |

## Recommendations

### Immediate Actions

1. **No code migrations required** - All runtime env access has been appropriately classified as DEFER or LEAVE
2. **Retain and surface this audit** - Link this document from a relevant README or ADR and keep it updated when runtime environment-variable usage changes
3. **Monitor new additions** - Future PRs adding `os.getenv()` should justify why they can't use `get_settings()`

### Future Considerations

1. **CORS Settings Seam**: `api/cors_utils.py` should be reviewed in a dedicated PR because it reads `ENV` and `ALLOWED_ORIGINS` directly even though both are already represented in `src/config/settings.py`. The current direct-read behavior supports dynamic override tests, but it creates a split source of truth and bypasses Settings parsing. A future CORS seam should decide whether to migrate to `get_settings()` with explicit `get_settings.cache_clear()` usage in tests, or retain direct reads with documented justification.

2. **Auth Module Refactor**: The admin seeding logic in `api/auth.py` could potentially be refactored to use a different initialization pattern, but the current approach is appropriate for startup-only bootstrap credentials.

3. **ADR Documentation**: Consider creating an Architecture Decision Record (ADR) documenting:
   - Why CORS validation uses dynamic env reads
   - Why auth uses module-level SECRET_KEY initialization
   - Settings migration criteria and patterns

## Validation

This audit was validated against the runtime audit scope only: `api/` and `src/`. Test files, scripts, and root-level helper files were excluded from the 15 runtime-match count and are listed separately as non-runtime context.

1. **Exhaustive runtime search**: Grep for `os.getenv(` and `os.environ[` across the audited runtime directories (`api/` and `src/`)
2. **Runtime scope filter**: Focused on `api/` and `src/` directories only
3. **Full file review**: Read complete context of each file containing env access
4. **Classification criteria**: Applied task-defined rules consistently

**Search Commands Used:**

```bash
# Find all os.getenv usage
grep -r "os\.getenv(" api/ src/

# Find all os.environ usage
grep -r "os\.environ\[" api/ src/
```

**Results:**

- `os.getenv(` - 15 matches in audited runtime files under `api/` and `src/` (all classified)
- `os.environ[` - 0 matches in audited runtime files under `api/` and `src/`

All runtime env access has been appropriately classified as DEFER or LEAVE LOCAL.

## Appendix: Recent Migration History

Recent successful migrations to `Settings`:

- **PR #1051**: Migrated `DATABASE_URL` access from `api/database.py` to use `get_settings().database_url`
  - Demonstrates the migration pattern working correctly
  - Shows that appropriate candidates have already been migrated

This audit confirms that the low-hanging fruit has been harvested, and remaining direct env access has architectural justification.

---

**Audit Completed:** 2026-04-24
**Next Review:** When new environment variables are introduced or CORS/auth architecture changes
