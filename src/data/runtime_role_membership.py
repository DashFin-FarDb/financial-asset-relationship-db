"""Shared PostgreSQL usable-role membership query fragments."""

USABLE_ROLE_MEMBERSHIP_CTE_SQL = (
    "WITH RECURSIVE role_membership(member, roleid, member_is_superuser) AS ("
    "SELECT membership.member, membership.roleid, grantee.rolsuper "
    "FROM pg_auth_members AS membership "
    "JOIN pg_roles AS grantee ON grantee.oid = membership.member "
    "WHERE (COALESCE((to_jsonb(membership) ->> 'inherit_option')::boolean, TRUE) "
    "OR COALESCE((to_jsonb(membership) ->> 'set_option')::boolean, TRUE) OR grantee.rolsuper) "
    "UNION SELECT role_membership.member, membership.roleid, "
    "role_membership.member_is_superuser OR member_role.rolsuper "
    "FROM role_membership JOIN pg_roles AS member_role "
    "ON member_role.oid = role_membership.roleid "
    "JOIN pg_auth_members AS membership "
    "ON membership.member = role_membership.roleid "
    "WHERE (COALESCE((to_jsonb(membership) ->> 'inherit_option')::boolean, TRUE) "
    "OR COALESCE((to_jsonb(membership) ->> 'set_option')::boolean, TRUE) "
    "OR role_membership.member_is_superuser OR member_role.rolsuper)) "
)
