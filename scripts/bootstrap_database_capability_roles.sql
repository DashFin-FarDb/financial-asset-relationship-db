-- Run explicitly with psql as a PostgreSQL superuser before the normal FarDB migration.
-- This is a cluster-role bootstrap only; it creates no login, credential, or runtime API.
DO $fardb$
DECLARE
    capability_role text;
    delegable_membership record;
BEGIN
    IF NOT COALESCE((SELECT rolsuper FROM pg_roles WHERE rolname = CURRENT_USER), FALSE) THEN
        RAISE EXCEPTION
            'FarDB capability-role bootstrap requires a PostgreSQL superuser';
    END IF;

    FOREACH capability_role IN ARRAY ARRAY[
        'fardb_runtime_auth',
        'fardb_runtime_graph',
        'fardb_runtime_coordination'
    ]
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = capability_role) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION',
                capability_role
            );
        END IF;

        FOR delegable_membership IN
            SELECT grantee.rolname AS member_name, grantor.rolname AS grantor_name
            FROM pg_auth_members AS membership
            JOIN pg_roles AS role ON role.oid = membership.roleid
            JOIN pg_roles AS grantee ON grantee.oid = membership.member
            JOIN pg_roles AS grantor ON grantor.oid = membership.grantor
            WHERE role.rolname = capability_role AND membership.admin_option
        LOOP
            EXECUTE format(
                'REVOKE %I FROM %I GRANTED BY %I CASCADE',
                capability_role,
                delegable_membership.member_name,
                delegable_membership.grantor_name
            );
        END LOOP;

        IF EXISTS (
            SELECT 1
            FROM pg_roles AS role
            WHERE role.rolname = capability_role
              AND (
                  role.rolcanlogin
                  OR role.rolsuper
                  OR role.rolcreatedb
                  OR role.rolcreaterole
                  OR role.rolbypassrls
                  OR role.rolreplication
                  OR has_database_privilege(role.oid, current_database(), 'CREATE')
                  OR EXISTS (
                      SELECT 1
                      FROM pg_namespace AS namespace
                      WHERE has_schema_privilege(role.oid, namespace.oid, 'CREATE')
                  )
                  OR EXISTS (
                      SELECT 1 FROM pg_auth_members AS membership
                      WHERE membership.member = role.oid
                  )
                  OR EXISTS (
                      SELECT 1 FROM pg_auth_members AS membership
                      WHERE membership.roleid = role.oid AND membership.admin_option
                  )
              )
        ) THEN
            RAISE EXCEPTION 'unsafe FarDB capability role: %', capability_role;
        END IF;
    END LOOP;
END
$fardb$;
