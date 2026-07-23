-- ADR 0007 / H-P0-04 follow-up for environments that already applied earlier
-- 005/006 revisions before FOR ROLE postgres and schema-wide PUBLIC function
-- revokes landed in 005.
-- Idempotent: safe when current 005 already contains the same posture.
-- Fresh installs rely on 005; this file exists so already-migrated hosts converge.

BEGIN;

DO $$
DECLARE
    target_schema constant text := 'public';
BEGIN
    EXECUTE format(
        'REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA %I FROM PUBLIC',
        target_schema
    );
    EXECUTE format(
        'REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA %I FROM anon, authenticated',
        target_schema
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA %I '
        'REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated',
        target_schema
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA %I '
        'REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated',
        target_schema
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA %I '
        'REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC',
        target_schema
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA %I '
        'REVOKE ALL PRIVILEGES ON FUNCTIONS FROM anon, authenticated',
        target_schema
    );
END
$$;

COMMIT;
