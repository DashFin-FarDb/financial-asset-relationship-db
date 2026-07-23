-- ADR 0007 / H-P0-04: deny-by-default for provider untrusted roles on public.
-- FastAPI remains the only product ingress; anon/authenticated receive no
-- table, view, sequence, or function authority on the exposed public schema.
-- Apply through governed migration authority against the target hosted database.
-- Rollback: restore prior grants/policies from restricted backup only.

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
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', rel.table_name);
    END LOOP;
END
$$;

-- Drop existing public-schema policies so enabling RLS does not revive Data API paths.
DO $$
DECLARE
    pol record;
BEGIN
    FOR pol IN
        SELECT policyname, tablename
        FROM pg_policies
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', pol.policyname, pol.tablename);
    END LOOP;
END
$$;

-- Revoke direct privileges from provider untrusted roles.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

-- Explicit revoke for known privileged helper (defense in depth).
-- Postgres defaults GRANT EXECUTE TO PUBLIC on new functions; revoke that too.
REVOKE ALL PRIVILEGES ON FUNCTION public.is_requester_admin() FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION public.is_requester_admin() FROM anon, authenticated;

-- Prevent future objects created by this role from re-granting untrusted access.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL PRIVILEGES ON FUNCTIONS FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC;

COMMIT;
