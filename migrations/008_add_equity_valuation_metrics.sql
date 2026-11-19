-- SQLite compatibility upgrade 008; applied conditionally by src.data.migrations.
-- All values are nullable; existing assets and non-equity records remain valid.
ALTER TABLE assets ADD COLUMN forward_pe_ratio REAL;
ALTER TABLE assets ADD COLUMN peg_ratio REAL;
ALTER TABLE assets ADD COLUMN price_to_sales_ratio REAL;
ALTER TABLE assets ADD COLUMN price_to_book_ratio REAL;
ALTER TABLE assets ADD COLUMN eps_growth_next_year REAL;
ALTER TABLE assets ADD COLUMN eps_growth_next_5_years REAL;
ALTER TABLE rebuild_jobs ADD COLUMN snapshot_attestation_version TEXT NOT NULL DEFAULT 'v1';
ALTER TABLE relationship_projection_publications
    ADD COLUMN snapshot_attestation_version TEXT NOT NULL DEFAULT 'v1';
