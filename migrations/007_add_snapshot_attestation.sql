-- Migration 007: Add snapshot_sha256 to rebuild_jobs and relationship_projection_publications

ALTER TABLE rebuild_jobs ADD COLUMN snapshot_sha256 TEXT;
ALTER TABLE relationship_projection_publications ADD COLUMN snapshot_sha256 TEXT;
