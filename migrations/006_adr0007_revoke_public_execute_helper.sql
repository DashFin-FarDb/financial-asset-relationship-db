-- ADR 0007 / H-P0-04 follow-up for environments that already applied earlier
-- 005/006 revisions before FOR ROLE postgres and schema-wide PUBLIC function
-- revokes landed in 005.
-- Idempotent: safe when current 005 already contains the same posture.
-- Fresh installs rely on 005; this file exists so already-migrated hosts converge.

BEGIN;

REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON FUNCTIONS FROM anon, authenticated;

COMMIT;
