-- DB-ADV-01 graph foreign-key index remediation; control issue: GitHub #1670.
-- Managed schema: public. Transaction policy: one atomic transaction.
-- Lock expectation: ordinary CREATE INDEX locks; apply only through the reviewed operator path.
-- Data/backfill behavior: index construction only; no application rows are changed.
-- Rollback/restore: forward-only; a later reviewed migration may drop these indexes if required.
-- Provider capability: none.

BEGIN;

CREATE INDEX ix_asset_relationships_target_asset_id
    ON public.asset_relationships (target_asset_id);

CREATE INDEX ix_regulatory_event_assets_asset_id
    ON public.regulatory_event_assets (asset_id);

CREATE INDEX ix_regulatory_events_asset_id
    ON public.regulatory_events (asset_id);

COMMIT;
