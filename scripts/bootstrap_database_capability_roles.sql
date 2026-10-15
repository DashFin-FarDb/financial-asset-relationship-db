-- Executed only by scripts.bootstrap_database_capability_roles as a PostgreSQL superuser.
-- The orchestrator proves every mapped database identity and schema ACL before this block.
-- This is a cluster-role bootstrap only; it creates no login, credential, or runtime API.
DO $fardb$
DECLARE
    capability_role text;
    delegable_membership record;
    target_mapping jsonb;
    target_owners oid[];
BEGIN
    IF NOT COALESCE((SELECT rolsuper FROM pg_roles WHERE rolname = CURRENT_USER), FALSE) THEN
        RAISE EXCEPTION
            'FarDB capability-role bootstrap requires a PostgreSQL superuser';
    END IF;

    -- The operator supplies this setting transaction-locally before executing this DO block.
    -- Validate every target before creating a role or changing a membership.
    target_mapping := NULLIF(current_setting('fardb.bootstrap_targets', TRUE), '')::jsonb;
    IF target_mapping IS NULL OR jsonb_typeof(target_mapping) <> 'object' THEN
        RAISE EXCEPTION 'complete FarDB bootstrap target mapping is required';
    END IF;
    IF (SELECT count(*) FROM jsonb_object_keys(target_mapping)) <> 3
       OR NOT target_mapping ?& ARRAY['fardb_runtime_auth', 'fardb_runtime_graph', 'fardb_runtime_coordination'] THEN
        RAISE EXCEPTION 'complete FarDB bootstrap target mapping is required';
    END IF;
    FOR capability_role IN SELECT jsonb_object_keys(target_mapping)
    LOOP
        IF jsonb_typeof(target_mapping -> capability_role) <> 'array' THEN
            RAISE EXCEPTION 'invalid FarDB bootstrap target list: %', capability_role;
        END IF;
        IF jsonb_array_length(target_mapping -> capability_role) = 0 OR EXISTS (
            SELECT 1 FROM jsonb_array_elements(target_mapping -> capability_role) AS target(value)
            WHERE jsonb_typeof(target.value) <> 'string'
               OR NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = target.value #>> '{}')
        ) THEN
            RAISE EXCEPTION 'invalid FarDB bootstrap target database: %', capability_role;
        END IF;
    END LOOP;

    FOREACH capability_role IN ARRAY ARRAY[
        'fardb_runtime_auth',
        'fardb_runtime_graph',
        'fardb_runtime_coordination'
    ]
    LOOP
        SELECT array_agg(DISTINCT database.datdba) INTO target_owners
        FROM pg_database AS database
        JOIN jsonb_array_elements_text(target_mapping -> capability_role) AS target(name)
          ON database.datname = target.name;
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
              AND NOT (membership.member = ANY(target_owners))
        LOOP
            EXECUTE format(
                'REVOKE %I FROM %I GRANTED BY %I RESTRICT',
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
                  OR EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements_text(target_mapping -> capability_role) AS target(name)
                      JOIN pg_database AS target_database ON target_database.datname = target.name
                      WHERE has_database_privilege(role.oid, target_database.oid, 'CREATE')
                  )
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
                        AND NOT (membership.member = ANY(target_owners))
                  )
              )
        ) THEN
            RAISE EXCEPTION 'unsafe FarDB capability role: %', capability_role;
        END IF;
    END LOOP;
END
$fardb$;
