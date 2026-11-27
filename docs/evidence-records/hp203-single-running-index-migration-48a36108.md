# H-P2-03 Hosted Migration Evidence Record (`48a36108`)

> **Scope:** SHA-bound operational evidence record for applying the H-P2-03 forward graph ledger migration
> (`20261127030000_enforce_single_running_rebuild_job.sql`) to hosted Supabase. All connection strings,
> credentials, hostnames, and project references are omitted/redacted.

## 1. Execution Metadata

| Field | Value |
| --- | --- |
| **Hardening ID** | `H-P2-03` (Partial unique index enforcing `<= 1` `RUNNING` rebuild job) |
| **Bound Repository Commit SHA** | `48a361081fdf08404d2e8cd0d1cdddb97516efc8` (`main`) |
| **Migration File** | `supabase/ledgers/graph/migrations/20261127030000_enforce_single_running_rebuild_job.sql` |
| **Migration File SHA-256** | `d5e223bf162aec23e5bfd328d9de2d6600726bf73033dffa43ac19ab4f62023b` |
| **Ledger Manifest SHA-256** | `88b78c38bea5251b443a5c4b7194da8f8641539d0b88287fbd1ece2abbfb2b2a` (`supabase/ledger-profiles.json`) |
| **Migration Version Recorded** | `20261127030000` (`enforce_single_running_rebuild_job`) |
| **Target Provider** | Hosted Supabase PostgreSQL (`combined` profile boundary) |
| **Execution Timestamp (UTC)** | `2026-11-27T03:25:28Z` |
| **Operator** | `mohavro` |
| **Outcome** | `PASS` (uneventful atomic DDL application; zero errors, zero drift) |
| **Tracking References** | Issue #1917, PR #1967 |

## 2. Pre-Check & Atomic DDL Application

1. **Pre-check on `public.rebuild_jobs`:**
   - `SELECT count(*) FROM public.rebuild_jobs WHERE status = 'running'` -> `0`
   - Index `uq_rebuild_jobs_single_running` pre-existing -> `False`
2. **Atomic DDL executed (`BEGIN; ... COMMIT;`):**
   ```sql
   CREATE UNIQUE INDEX uq_rebuild_jobs_single_running
       ON public.rebuild_jobs (status)
       WHERE (status = 'running');
   ```
3. **Catalog verification (`pg_indexes`):**
   - Verified index definition:
     `CREATE UNIQUE INDEX uq_rebuild_jobs_single_running ON public.rebuild_jobs USING btree (status) WHERE ((status)::text = 'running'::text)`
4. **Migration history reconciliation:**
   - Recorded `(version='20261127030000', name='enforce_single_running_rebuild_job')` in `supabase_migrations.schema_migrations` -> `True`

## 3. Post-Migration Parity & Runtime Verification

| Verification Check | Algorithm / Command | Result |
| --- | --- | --- |
| **Normalized `combined` catalog digest** | `fardb-pg-catalog-v2` (`scripts/postgresql_drift.py`) | **MATCH** (`fcf0076f5b94de7b083f1ef78496e5b55c95ad2a8f23574d6cc5c84c063fde1f` == `supabase/ledger-profiles.json`) |
| **Database authorization gate** | `python scripts/check_database_authorization.py` (restricted runtime roles) | **PASS** (`database authorization gate passed`, exit `0`) |
| **Cross-boundary restore skew check (H-P2-05)** | `python scripts/check_restore_boundary_skew.py` (Graph vs Coordination runtime roles) | **PASS** (exit `0`, see redacted JSON below) |

### Redacted `check_restore_boundary_skew.py` Output

```json
{
  "status": "PASS",
  "same_boundary": false,
  "running_jobs_count": 0,
  "active_locks_count": 0,
  "total_locks_count": 0,
  "boundary_skew_seconds": null,
  "max_skew_seconds": 300.0,
  "reasons": []
}
```

## 4. Redaction & Boundary Attestation

- No raw database URLs, passwords, tokens, hostnames, or provider project IDs are recorded in this artifact.
- This record attests only to the H-P2-03 migration execution and post-migration verification against commit `48a361081fdf08404d2e8cd0d1cdddb97516efc8` on `2026-11-27`.
