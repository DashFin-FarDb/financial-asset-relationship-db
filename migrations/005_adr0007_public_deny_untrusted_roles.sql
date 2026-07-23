-- ADR 0007 / H-P0-04: deny-by-default for provider untrusted roles on public.
-- FastAPI remains the only product ingress; anon/authenticated receive no
-- table, view, sequence, or function authority on the exposed public schema.
-- Apply through governed migration authority against the target hosted database.
-- Rollback: restore prior grants/policies from restricted backup only.
--
-- Default privileges: revoke for postgres and supabase_admin (hosted grantors).
-- Policy drop is intentional: Data API policies must not survive RLS enablement;
-- FastAPI is the only product ingress (BYPASSRLS / custom policies out of scope).

BEGIN;

DO $$
DECLARE
    target_schema constant text := 'public';
    default_priv_prefix constant text :=
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I ';
    owner_role text;
    rel record;
    pol record;
    fn regprocedure;
BEGIN
    -- Enable RLS on every public base/partitioned table (idempotent).
    FOR rel IN
        SELECT c.relname AS table_name
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = target_schema
          AND c.relkind IN ('r', 'p')
          AND NOT c.relrowsecurity
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',
            target_schema,
            rel.table_name
        );
    END LOOP;

    -- Drop public-schema policies so enabling RLS does not revive Data API paths.
    FOR pol IN
        SELECT policyname, tablename
        FROM pg_policies
        WHERE schemaname = target_schema
    LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON %I.%I',
            pol.policyname,
            target_schema,
            pol.tablename
        );
    END LOOP;

    -- Revoke direct privileges from provider untrusted roles.
    -- Include PUBLIC on functions: Postgres defaults GRANT EXECUTE TO PUBLIC, and
    -- REVOKE FROM anon/authenticated alone does not remove that grant path.
    EXECUTE format(
        'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM anon, authenticated',
        target_schema
    );
    EXECUTE format(
        'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I FROM anon, authenticated',
        target_schema
    );
    EXECUTE format(
        'REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA %I FROM PUBLIC',
        target_schema
    );
    EXECUTE format(
        'REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA %I FROM anon, authenticated',
        target_schema
    );

    -- Guarded revoke for known privileged helper overloads (skip if absent).
    FOR fn IN
        SELECT p.oid::regprocedure
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = target_schema
          AND p.proname = 'is_requester_admin'
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON FUNCTION %s FROM PUBLIC, anon, authenticated',
            fn
        );
    END LOOP;

    -- Deny-by-default for future objects from known public-schema grantor roles.
    -- Skip roles the migration runner cannot alter (e.g. hosted supabase_admin).
    FOREACH owner_role IN ARRAY ARRAY['postgres', 'supabase_admin']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = owner_role) THEN
            CONTINUE;
        END IF;
        BEGIN
            EXECUTE format(
                default_priv_prefix || 'REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated',
                owner_role,
                target_schema
            );
            EXECUTE format(
                default_priv_prefix || 'REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated',
                owner_role,
                target_schema
            );
            EXECUTE format(
                default_priv_prefix || 'REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC',
                owner_role,
                target_schema
            );
            EXECUTE format(
                default_priv_prefix || 'REVOKE ALL PRIVILEGES ON FUNCTIONS FROM anon, authenticated',
                owner_role,
                target_schema
            );
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE
                    'skip default privileges for role % (insufficient privilege)',
                    owner_role;
        END;
    END LOOP;
END
$$;

COMMIT;
