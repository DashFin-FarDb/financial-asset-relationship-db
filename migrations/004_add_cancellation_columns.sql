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
-- Note: This block will fail on SQLite if run directly via tools that don't ignore errors,
-- but our Python runner handles SQLite isolation.
-- DO NOT REMOVE: Needed for PostgreSQL environments that manually apply these SQL files.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'ck_rebuild_jobs_status' AND table_name = 'rebuild_jobs') THEN
        ALTER TABLE rebuild_jobs DROP CONSTRAINT ck_rebuild_jobs_status;
    END IF;

    ALTER TABLE rebuild_jobs ADD CONSTRAINT ck_rebuild_jobs_status
        CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled'));
EXCEPTION
    WHEN undefined_table THEN
        -- Handle case where rebuild_jobs doesn't exist yet (unlikely if 001 ran)
        NULL;
    WHEN OTHERS THEN
        -- If DO block is not supported (e.g. SQLite), ignore and rely on Python runner
        NULL;
END $$;
