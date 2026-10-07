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

APPROVED_RUNTIME_LOGIN_PRINCIPALS: dict[str, frozenset[str]] = {
    "fardb_runtime_auth": frozenset({"fardb_login_auth", "fardb_login_auth_prod"}),
    "fardb_runtime_graph": frozenset({"fardb_login_graph"}),
    "fardb_runtime_coordination": frozenset({"fardb_login_coordination"}),
}


def get_approved_login_principals(capability_role: str) -> tuple[str, ...]:
    """Return sorted tuple of approved login principals for a capability role."""
    principals = APPROVED_RUNTIME_LOGIN_PRINCIPALS.get(capability_role)
    if principals is None:
        raise ValueError(f"Unknown capability role: {capability_role}")
    return tuple(sorted(principals))
