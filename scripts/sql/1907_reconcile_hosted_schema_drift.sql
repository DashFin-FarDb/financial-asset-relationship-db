-- One-time historical hosted schema reconciliation script for Issue #1907 (already applied).
-- Brings the hosted PostgreSQL schema into parity with the 6-migration `combined` ledger
-- without rewriting tables, blocking live writes during index builds, or weakening RLS.
--
-- Scope:
--   1. Create the 3 missing foreign-key indexes CONCURRENTLY (outside transaction) from
--      20260822164127_add_graph_foreign_key_indexes.sql.
--   2. Restore `DEFAULT false` on `public.asset_relationships.bidirectional`.
--   3. Align `public.user_credentials` string columns from `varchar(255)` to `text` (metadata-only).
--   4. Align `public.rebuild_jobs.ck_rebuild_jobs_status` literal order using `NOT VALID` +
--      out-of-transaction `VALIDATE CONSTRAINT` to avoid blocking scans.
--   5. Align `public.grac_v1_reject_mutation()` body whitespace with the reviewed ledger definition.
--
-- Intentionally out of scope (tracked separately):
--   - `FORCE ROW LEVEL SECURITY` on 7 core tables (hosted is stricter; do not weaken RLS here).
--   - Swapped `attnum` column ordinal positions on 3 tables (irreversible without table rewrite).
--   - Supabase provider-managed ACLs and `default_privileges` (`anon`, `authenticated`, `service_role`).

-- 1. Missing foreign-key indexes (non-blocking concurrent builds outside transaction)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_asset_relationships_target_asset_id
    ON public.asset_relationships USING btree (target_asset_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_regulatory_event_assets_asset_id
    ON public.regulatory_event_assets USING btree (asset_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_regulatory_events_asset_id
    ON public.regulatory_events USING btree (asset_id);

BEGIN;

-- 2. Missing column default
ALTER TABLE public.asset_relationships
    ALTER COLUMN bidirectional SET DEFAULT false;

-- 3. Align user_credentials varchar(255) -> text (metadata-only, no table rewrite)
ALTER TABLE public.user_credentials
    ALTER COLUMN username TYPE text,
    ALTER COLUMN email TYPE text,
    ALTER COLUMN full_name TYPE text,
    ALTER COLUMN hashed_password TYPE text;

-- 4. Align ck_rebuild_jobs_status literal order without full-table scan under ACCESS EXCLUSIVE
ALTER TABLE public.rebuild_jobs
    DROP CONSTRAINT IF EXISTS ck_rebuild_jobs_status;

ALTER TABLE public.rebuild_jobs
    ADD CONSTRAINT ck_rebuild_jobs_status
    CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled', 'cancel_requested'))
    NOT VALID;

-- 5. Align grac_v1_reject_mutation() body whitespace with the reviewed ledger definition
CREATE OR REPLACE FUNCTION public.grac_v1_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog'
AS $function$
BEGIN
    RAISE EXCEPTION 'GRAC v1 immutability: % forbidden on %', TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END;
$function$;

COMMIT;

-- Validate the constraint outside the transaction under SHARE UPDATE EXCLUSIVE
ALTER TABLE public.rebuild_jobs
    VALIDATE CONSTRAINT ck_rebuild_jobs_status;
