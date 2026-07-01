-- Migration 004: Add cancellation support to rebuild_jobs
-- NOTE: This migration is SUPERSEDED by updates to 001_initial.sql for new deployments.
--
-- For PostgreSQL: Adds cancellation_requested_at as TIMESTAMPTZ and updates the
-- status check constraint to include 'cancel_requested'.
--
-- For SQLite: Handled by the Python migration runner (_apply_upgrade_004_cancellation_columns)
-- which performs a safe table-swap to update the CHECK constraint.
--
-- This file remains as an ordered SQL artifact but the Python runner
-- handles backend-specific nuances and idempotency.

-- 1. Add column (using TIMESTAMPTZ for PG consistency, SQLite will map to TIMESTAMP/DATETIME)
ALTER TABLE rebuild_jobs ADD COLUMN cancellation_requested_at TIMESTAMP WITH TIME ZONE;

-- 2. Update CHECK constraint (PostgreSQL specific path)
-- Note: SQLite does not support ALTER TABLE DROP/ADD CONSTRAINT; its schema updates are handled by the Python runner.
ALTER TABLE rebuild_jobs DROP CONSTRAINT IF EXISTS ck_rebuild_jobs_status;
ALTER TABLE rebuild_jobs ADD CONSTRAINT ck_rebuild_jobs_status
    CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled'));
