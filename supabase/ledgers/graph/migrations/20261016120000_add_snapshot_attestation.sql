-- Add snapshot_sha256 to rebuild_jobs and relationship_projection_publications.
-- Transaction policy: one atomic transaction.

BEGIN;

ALTER TABLE public.rebuild_jobs
    ADD COLUMN snapshot_sha256 VARCHAR(64);

ALTER TABLE public.relationship_projection_publications
    ADD COLUMN snapshot_sha256 VARCHAR(64);

COMMIT;
