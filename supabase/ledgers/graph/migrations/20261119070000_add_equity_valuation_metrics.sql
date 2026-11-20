-- Add optional equity valuation fields and preserve snapshot-hash version identity.
-- Transaction policy: one atomic transaction; nullable metric fields; existing attestations remain v1.
BEGIN;

ALTER TABLE public.assets
    ADD COLUMN forward_pe_ratio DOUBLE PRECISION,
    ADD COLUMN peg_ratio DOUBLE PRECISION,
    ADD COLUMN price_to_sales_ratio DOUBLE PRECISION,
    ADD COLUMN price_to_book_ratio DOUBLE PRECISION,
    ADD COLUMN eps_growth_next_year DOUBLE PRECISION,
    ADD COLUMN eps_growth_next_5_years DOUBLE PRECISION;

ALTER TABLE public.rebuild_jobs
    ADD COLUMN snapshot_attestation_version VARCHAR(16) NOT NULL DEFAULT 'v1';

ALTER TABLE public.relationship_projection_publications
    ADD COLUMN snapshot_attestation_version VARCHAR(16) NOT NULL DEFAULT 'v1';

COMMIT;
