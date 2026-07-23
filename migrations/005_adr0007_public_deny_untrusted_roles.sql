-- ADR 0007 / H-P0-04: deny-by-default for provider untrusted roles on public.
-- FastAPI remains the only product ingress; anon/authenticated receive no
-- table, view, sequence, or function authority on the exposed public schema.
-- Apply through governed migration authority against the target hosted database.
-- Rollback: restore prior grants/policies from restricted backup only.
--
-- Object owners in the hosted target are postgres; DEFAULT PRIVILEGES therefore
-- use FOR ROLE postgres so future objects keep the deny-by-default posture.

BEGIN;

-- Enable RLS on every public base/partitioned table (idempotent).
DO $$
DECLARE
    rel record;
BEGIN
    FOR rel IN
        SELECT c.relname AS table_name
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND NOT c.relrowsecurity
    LOOP
        EXECUTE format(
            'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',
            rel.table_name
        );
    END LOOP;
END
$$;

-- Drop public-schema policies so enabling RLS does not revive Data API paths.
DO $$
DECLARE
    pol record;
BEGIN
    FOR pol IN
        SELECT policyname, tablename
        FROM pg_policies
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON public.%I',
            pol.policyname,
            pol.tablename
        );
    END LOOP;
END
$$;

-- Revoke direct privileges from provider untrusted roles.
-- Include PUBLIC on functions: Postgres defaults GRANT EXECUTE TO PUBLIC, and
-- REVOKE FROM anon/authenticated alone does not remove that grant path.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

-- Guarded revoke for known privileged helper overloads (skip cleanly if absent).
DO $$
DECLARE
    fn regprocedure;
BEGIN
    FOR fn IN
        SELECT p.oid::regprocedure
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname = 'is_requester_admin'
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON FUNCTION %s FROM PUBLIC, anon, authenticated',
            fn
        );
    END LOOP;
END
$$;

-- Deny-by-default for future objects created by the public-schema owner role.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON FUNCTIONS FROM anon, authenticated;

COMMIT;
