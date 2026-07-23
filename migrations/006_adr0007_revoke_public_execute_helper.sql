-- ADR 0007 / H-P0-04: version slot only.
-- Idempotent backfill placeholder for hosts that already applied an earlier
-- 006 revision. Current deny-by-default posture lives entirely in
-- 005_adr0007_public_deny_untrusted_roles.sql; this file intentionally has
-- no privilege statements so adjacent migrations do not duplicate security logic.

BEGIN;
COMMIT;
