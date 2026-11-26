-- Bounded hosted schema reconciliation script for Issue #1907 (CQ-03D prerequisite).
-- Brings the hosted PostgreSQL schema into parity with the 6-migration `combined` ledger
-- without rewriting tables or weakening Row Level Security.
--
-- Scope:
--   1. Create the 3 missing foreign-key indexes from 20260822164127_add_graph_foreign_key_indexes.sql.
--   2. Restore `DEFAULT false` on `public.asset_relationships.bidirectional`.
--   3. Align `public.user_credentials` string columns from `varchar(255)` to `text` (metadata-only in PostgreSQL).
--   4. Align `public.rebuild_jobs.ck_rebuild_jobs_status` CHECK constraint literal order.
--
-- Intentionally out of scope (tracked separately):
--   - `FORCE ROW LEVEL SECURITY` on 7 core tables (hosted is stricter; do not weaken RLS here).
--   - Swapped `attnum` column ordinal positions on 3 tables (irreversible without table rewrite).
--   - Supabase provider-managed ACLs and `default_privileges` (`anon`, `authenticated`, `service_role`).

BEGIN;

-- 1. Missing foreign-key indexes
CREATE INDEX IF NOT EXISTS ix_asset_relationships_target_asset_id
    ON public.asset_relationships USING btree (target_asset_id);

CREATE INDEX IF NOT EXISTS ix_regulatory_event_assets_asset_id
    ON public.regulatory_event_assets USING btree (asset_id);

CREATE INDEX IF NOT EXISTS ix_regulatory_events_asset_id
    ON public.regulatory_events USING btree (asset_id);

-- 2. Missing column default
ALTER TABLE public.asset_relationships
    ALTER COLUMN bidirectional SET DEFAULT false;

-- 3. Align user_credentials varchar(255) -> text (metadata-only, no table rewrite)
ALTER TABLE public.user_credentials
    ALTER COLUMN username TYPE text,
    ALTER COLUMN email TYPE text,
    ALTER COLUMN full_name TYPE text,
    ALTER COLUMN hashed_password TYPE text;

-- 4. Align ck_rebuild_jobs_status literal order
ALTER TABLE public.rebuild_jobs
    DROP CONSTRAINT IF EXISTS ck_rebuild_jobs_status;

ALTER TABLE public.rebuild_jobs
    ADD CONSTRAINT ck_rebuild_jobs_status
    CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled', 'cancel_requested'));

COMMIT;
