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


def login_membership_sql(*, require_login_principals: bool, dbapi: bool) -> str:
    """Check role membership against approved logins with the caller's bind syntax."""
    grantees = (
        "FROM pg_roles AS grantee WHERE grantee.rolcanlogin "
        "AND grantee.oid <> (SELECT datdba FROM pg_database WHERE datname = current_database()) "
        "AND EXISTS (SELECT 1 FROM role_membership WHERE role_membership.member = grantee.oid "
        "AND role_membership.roleid = role.oid)"
    )
    count = f"(SELECT COUNT(*) {grantees}) >= 1 AND " if require_login_principals else ""
    approved = "grantee.rolname = ANY(%s)" if dbapi else "grantee.rolname IN :approved_logins"
    return f"{USABLE_ROLE_MEMBERSHIP_CTE_SQL}SELECT {count}NOT EXISTS (SELECT 1 {grantees} AND NOT ({approved}))"


AUTH_RUNTIME_ROLE = "fardb_runtime_auth"
GRAPH_RUNTIME_ROLE = "fardb_runtime_graph"
COORDINATION_RUNTIME_ROLE = "fardb_runtime_coordination"

APPROVED_RUNTIME_LOGIN_PRINCIPALS: dict[str, frozenset[str]] = {
    AUTH_RUNTIME_ROLE: frozenset({"fardb_login_auth", "fardb_login_auth_prod"}),
    GRAPH_RUNTIME_ROLE: frozenset({"fardb_login_graph"}),
    COORDINATION_RUNTIME_ROLE: frozenset({"fardb_login_coordination"}),
}


def get_approved_login_principals(
    capability_role: str,
    *,
    combined_topology: bool = False,
) -> tuple[str, ...]:
    """Return sorted tuple of approved login principals for a capability role.

    In a combined topology (where a single database hosts both graph and coordination
    capabilities), the graph login principal ('fardb_login_graph') is also approved
    for 'fardb_runtime_coordination'. In a separated topology, each capability role
    is strictly restricted to its dedicated login principal.
    """
    principals = APPROVED_RUNTIME_LOGIN_PRINCIPALS.get(capability_role)
    if principals is None:
        raise ValueError(f"Unknown capability role: {capability_role}")
    if capability_role == "fardb_runtime_coordination" and combined_topology:
        return tuple(sorted(principals | {"fardb_login_graph"}))
    return tuple(sorted(principals))
