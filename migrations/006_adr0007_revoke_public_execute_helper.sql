-- ADR 0007 / H-P0-04 follow-up: revoke PUBLIC default EXECUTE on privileged helper.
-- Companion to 005_adr0007_public_deny_untrusted_roles.sql (PUBLIC retained EXECUTE).

BEGIN;

REVOKE ALL PRIVILEGES ON FUNCTION public.is_requester_admin() FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION public.is_requester_admin() FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC;

COMMIT;
