# Runtime Environment Access Audit

**Date:** 2026-04-24
**Purpose:** Complete inventory and classification of direct environment variable access across runtime files
**Scope:** `api/` and `src/` directories (excluding tests/scripts)

## Executive Summary

This audit catalogues all direct `os.getenv()` and `os.environ[]` usage in runtime code to inform settings migration strategy. All 15 runtime occurrences have been classified according to migration priority rules.

**Key Findings:**

- **No immediate migration candidates** - Recent PRs (e.g., #1051) have already migrated appropriate candidates
- **All remaining env access has architectural justification** for staying as direct reads
- **No dead code found** - All env variable access is actively used
- **Settings layer functioning correctly** - Centralized config mechanism working as designed

## Classification Results

### Summary by Action

| Classification | Count | Percentage |
|----------------|-------|------------|
| DEFER (intentional) | 8 | 53% |
| LEAVE (settings loader) | 7 | 47% |
| MIGRATE NOW | 0 | 0% |
| REMOVE (dead code) | 0 | 0% |
| **TOTAL** | **15** | **100%** |

### Classification Rules Applied

1. **MIGRATE NOW**: Core runtime config that is stable, non-dynamic, and safe via cached settings
2. **DEFER**: Dynamic behavior, security-sensitive startup, or anything where caching changes semantics
3. **LEAVE LOCAL**: CLI scripts, tests, dev tooling, or the settings loader itself
4. **REMOVE**: Unused or stale code

## Detailed Inventory

### api/auth.py - DEFER (6 occurrences)

All environment access in this file is classified as **DEFER** due to security-sensitive startup characteristics.

| Line | Variable | Usage | Rationale for DEFER |
|------|----------|-------|---------------------|
| 20 | `SECRET_KEY` | JWT signing key | Security-critical crypto key; module-level initialization; fail-fast validation appropriate; caching provides no value |
| 221 | `ADMIN_USERNAME` | User seeding | Startup-only bootstrap; read once during module init; not runtime config |
| 222 | `ADMIN_PASSWORD` | User seeding | Startup-only bootstrap; read once during module init; not runtime config |
| 227 | `ADMIN_EMAIL` | User seeding | Startup-only bootstrap; read once during module init; not runtime config |
| 228 | `ADMIN_FULL_NAME` | User seeding | Startup-only bootstrap; read once during module init; not runtime config |
| 229 | `ADMIN_DISABLED` | User seeding | Startup-only bootstrap; read once during module init; not runtime config |

**Analysis:**

- `SECRET_KEY` (line 20): Used for JWT encoding/decoding. Module-level constant with explicit validation. This is security-sensitive startup configuration, not runtime config suitable for caching.

- `ADMIN_*` variables (lines 221-229): Used exclusively in `_seed_credentials_from_env()` function, called once at module initialization (line 242). These are transient bootstrap credentials for initial user setup, not ongoing runtime configuration. Migrating to Settings would not improve semantics.

### api/cors_utils.py - DEFER (2 occurrences)

All environment access in this file is classified as **DEFER** due to intentional dynamic behavior.

| Line | Variable | Usage | Rationale for DEFER |
|------|----------|-------|---------------------|
| 131 | `ENV` | CORS validation (per-request) | Explicitly documented dynamic behavior for test overrides |
| 134 | `ALLOWED_ORIGINS` | CORS validation (per-request) | Explicitly documented dynamic behavior for test overrides |

**Analysis:**

Both variables are read within the `validate_origin()` function, which is called on every CORS validation request. The code includes an explicit comment on line 130:

```python
# Read environment dynamically to support runtime overrides (e.g., during tests)
```

This dynamic behavior is intentional and architectural. Test scenarios rely on the ability to modify environment variables at runtime and see immediate effects. Caching these values via Settings would break this test design pattern.

**This matches the task description's example:** "DEFER: dynamic behavior (e.g. CORS)"

### src/config/settings.py - LEAVE (7 occurrences)

All environment access in this file is classified as **LEAVE** because this IS the centralized settings mechanism.

| Line | Variable | Purpose |
|------|----------|---------|
| 105 | `ENV` | Settings loader - canonical env→Settings mapping |
| 106 | `ALLOWED_ORIGINS` | Settings loader - canonical env→Settings mapping |
| 107 | `GRAPH_CACHE_PATH` | Settings loader - canonical env→Settings mapping |
| 108 | `REAL_DATA_CACHE_PATH` | Settings loader - canonical env→Settings mapping |
| 109 | `USE_REAL_DATA_FETCHER` | Settings loader - canonical env→Settings mapping |
| 110 | `ASSET_GRAPH_DATABASE_URL` | Settings loader - canonical env→Settings mapping |
| 111 | `DATABASE_URL` | Settings loader - canonical env→Settings mapping |

**Analysis:**

These reads occur in the `load_settings()` function (lines 92-112), which is the canonical loader for the centralized settings mechanism. By definition, the loader must read from the environment. These reads are already cached via the `@lru_cache` decorator on `get_settings()` (line 115).

**Note:** `DATABASE_URL` was recently migrated in `api/database.py` (PR #1051), demonstrating the settings migration pattern working correctly.

## Non-Runtime Files (Out of Scope)

For completeness, environment variable usage in non-runtime files:

| File | Variables | Classification | Notes |
|------|-----------|----------------|-------|
| `.github/scripts/schema_report_cli.py` | `SCHEMA_REPORT_LOG` | LEAVE | CLI tooling |
| `main.py` | `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY` | LEAVE | Dev/test script |
| `run_tests.py` | `TEST_SECRET_KEY` | LEAVE | Test runner |
| `test_supabase.py` | `SUPABASE_URL`, `SUPABASE_KEY`, `RUN_SUPABASE_TESTS` | LEAVE | Test file |
| `test_postgres.py` | `ASSET_GRAPH_DATABASE_URL`, `DATABASE_URL`, `RUN_POSTGRES_TESTS` | LEAVE | Test file |
| `tests/**` | Various | LEAVE | Test files excluded from scope |

## Recommendations

### Immediate Actions

1. **No code migrations required** - All runtime env access has been appropriately classified as DEFER or LEAVE
2. **Document DEFER decisions** - Consider adding this audit document to repository for future reference
3. **Monitor new additions** - Future PRs adding `os.getenv()` should justify why they can't use `get_settings()`

### Future Considerations

1. **CORS Test Strategy Review**: If test scenarios no longer require runtime environment override capability, `api/cors_utils.py` could potentially migrate to `get_settings()`. However, this would be a behavior change requiring careful evaluation and is explicitly OUT OF SCOPE for this audit.

2. **Auth Module Refactor**: The admin seeding logic in `api/auth.py` could potentially be refactored to use a different initialization pattern, but the current approach is appropriate for startup-only bootstrap credentials.

3. **ADR Documentation**: Consider creating an Architecture Decision Record (ADR) documenting:
   - Why CORS validation uses dynamic env reads
   - Why auth uses module-level SECRET_KEY initialization
   - Settings migration criteria and patterns

## Validation

This audit was validated by:

1. **Exhaustive search**: Grep for `os.getenv(` and `os.environ[` across entire repository
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
- `os.getenv(` - 15 matches in runtime files (all classified)
- `os.environ[` - 0 matches in runtime files

All runtime environment access has been accounted for and classified.

## Appendix: Recent Migration History

Recent successful migrations to `Settings`:

- **PR #1051**: Migrated `DATABASE_URL` access from `api/database.py` to use `get_settings().database_url`
  - Demonstrates the migration pattern working correctly
  - Shows that appropriate candidates have already been migrated

This audit confirms that the low-hanging fruit has been harvested, and remaining direct env access has architectural justification.

---

**Audit Completed:** 2026-04-24
**Next Review:** When new environment variables are introduced or CORS/auth architecture changes
