-- Migration 002: Add heartbeat tracking columns to rebuild_jobs
-- This migration adds columns for tracking rebuild executor liveness.
-- Safe to run multiple times (idempotent) - uses Python wrapper to check for column existence.

-- Note: SQLite does not support "ADD COLUMN IF NOT EXISTS" until version 3.35.0,
-- and even then it's not widely available. This migration must be applied via
-- a Python wrapper that checks column existence before executing ALTER TABLE.

-- These ALTER TABLE statements will fail if columns already exist.
-- The Python migration runner (see src/data/migrations.py or equivalent)
-- must check PRAGMA table_info(rebuild_jobs) before running these.

ALTER TABLE rebuild_jobs ADD COLUMN active_worker_id TEXT;
ALTER TABLE rebuild_jobs ADD COLUMN last_heartbeat_at TEXT;
