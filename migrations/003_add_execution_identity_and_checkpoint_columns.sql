-- Migration 003: Add execution identity and checkpoint columns to rebuild_jobs

ALTER TABLE rebuild_jobs ADD COLUMN execution_id TEXT;
ALTER TABLE rebuild_jobs ADD COLUMN checkpoint_data TEXT;
