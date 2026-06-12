-- Migration 004: Add cancellation_requested_at column to rebuild_jobs

ALTER TABLE rebuild_jobs ADD COLUMN cancellation_requested_at TIMESTAMP;
