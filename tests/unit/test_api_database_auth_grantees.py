"""Focused auth capability-grantee authority regressions."""

from unittest.mock import MagicMock

import pytest

from api import database as api_database
from src.data.database import SchemaCompatibilityError
from src.data.runtime_role_membership import USABLE_ROLE_MEMBERSHIP_CTE_SQL

pytestmark = pytest.mark.unit


def test_ensure_runtime_access_fails_before_catalog_or_ddl(monkeypatch) -> None:
    """Legacy provisioning cannot inspect or mutate a PostgreSQL target."""
    execute = MagicMock()
    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    fetch_value = MagicMock()
    monkeypatch.setattr(api_database, "fetch_value", fetch_value)
    monkeypatch.setattr(api_database, "execute", execute)

    with pytest.raises(SchemaCompatibilityError, match="profile-scoped Supabase ledger"):
        api_database.ensure_runtime_access()

    execute.assert_not_called()
    fetch_value.assert_not_called()


def test_verify_runtime_access_catalog_counts_only_usable_login_grantees(monkeypatch) -> None:
    """Read-only role verification permits at most one usable runtime login path."""
    fetch_value = MagicMock(return_value=True)
    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    monkeypatch.setattr(api_database, "fetch_value", fetch_value)

    api_database.verify_runtime_access_catalog()

    safe_role_query = fetch_value.call_args_list[0].args[0]
    assert USABLE_ROLE_MEMBERSHIP_CTE_SQL in safe_role_query
    assert "has_schema_privilege(role.oid, namespace.oid, 'CREATE')" in safe_role_query
    assert "WITH RECURSIVE role_membership(member, roleid, member_is_superuser)" in safe_role_query
    assert "to_jsonb(membership) ->> 'inherit_option'" in safe_role_query
    assert "to_jsonb(membership) ->> 'set_option'" in safe_role_query
    assert "membership.inherit_option" not in safe_role_query
    assert "membership.set_option" not in safe_role_query
    assert safe_role_query.count("::boolean, TRUE)") == 4
    assert "OR grantee.rolsuper" in safe_role_query
    assert "membership.roleid = role.oid" in safe_role_query
    assert "membership.admin_option" in safe_role_query
    assert "JOIN pg_roles AS member_role ON member_role.oid = role_membership.roleid" in safe_role_query
    assert "membership.member = role_membership.roleid" in safe_role_query
    assert "OR role_membership.member_is_superuser OR member_role.rolsuper" in safe_role_query
    assert "role_membership.member = grantee.oid" in safe_role_query
    assert "role_membership.roleid = role.oid" in safe_role_query
    assert "cross_rel.relname = ANY(%s)" in safe_role_query
    assert "has_any_column_privilege(role.oid, cross_rel.oid, 'SELECT')" in safe_role_query
    assert "has_sequence_privilege(role.oid, cross_sequence.oid, 'UPDATE')" in safe_role_query
    assert "has_function_privilege(role.oid, cross_proc.oid, 'EXECUTE')" in safe_role_query
    assert fetch_value.call_args_list[0].args[1][1] == list(api_database._NON_AUTH_MANAGED_TABLES)
    assert ") <= 1" in safe_role_query


def test_verify_runtime_authority_rejects_unsafe_auth_capability_role(monkeypatch) -> None:
    """A falsy safe-role catalog result must reject the auth capability contract."""
    fetch_value = MagicMock(side_effect=[True, 1, True, True, False, True, True, True, True])
    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    monkeypatch.setattr(api_database, "fetch_value", fetch_value)

    with pytest.raises(SchemaCompatibilityError, match="capability contract is incompatible"):
        api_database.verify_runtime_authority()

    for usable_membership_query in (call.args[0] for call in fetch_value.call_args_list[:3]):
        assert "current_setting('server_version_num')::integer >= 160000" in usable_membership_query
        assert "pg_has_role(login.oid, assumable.oid, 'USAGE')" in usable_membership_query
        assert "pg_has_role(login.oid, assumable.oid, 'SET')" in usable_membership_query
        assert "ELSE pg_has_role(login.oid, assumable.oid, 'MEMBER') END" in usable_membership_query

    safe_role_query = fetch_value.call_args_list[4].args[0]
    assert USABLE_ROLE_MEMBERSHIP_CTE_SQL in safe_role_query
    assert "has_schema_privilege(role.oid, namespace.oid, 'CREATE')" in safe_role_query
    assert "grantee.rolcanlogin" in safe_role_query
    assert "WITH RECURSIVE role_membership(member, roleid, member_is_superuser)" in safe_role_query
    assert "to_jsonb(membership) ->> 'inherit_option'" in safe_role_query
    assert "to_jsonb(membership) ->> 'set_option'" in safe_role_query
    assert "membership.inherit_option" not in safe_role_query
    assert "membership.set_option" not in safe_role_query
    assert safe_role_query.count("::boolean, TRUE)") == 4
    assert "OR grantee.rolsuper" in safe_role_query
    assert "membership.roleid = role.oid" in safe_role_query
    assert "membership.admin_option" in safe_role_query
    assert "JOIN pg_roles AS member_role ON member_role.oid = role_membership.roleid" in safe_role_query
    assert "membership.member = role_membership.roleid" in safe_role_query
    assert "OR role_membership.member_is_superuser OR member_role.rolsuper" in safe_role_query
    assert "grantee.rolname <> session_user" not in safe_role_query
    assert "role_membership.member = grantee.oid" in safe_role_query
    assert "role_membership.roleid = role.oid" in safe_role_query
    assert ") <= 1" in safe_role_query
