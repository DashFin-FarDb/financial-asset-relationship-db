"""Focused auth capability-grantee authority regressions."""

from unittest.mock import MagicMock

import pytest

from api import database as api_database
from src.data.database import CapabilityRoleBootstrapRequiredError, SchemaCompatibilityError

pytestmark = pytest.mark.unit


def test_ensure_runtime_access_counts_only_usable_login_grantees(monkeypatch) -> None:
    """Provisioning must reject delegable, usable, and superuser membership paths."""
    execute = MagicMock()
    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    fetch_value = MagicMock(side_effect=[None, 2])
    monkeypatch.setattr(api_database, "fetch_value", fetch_value)
    monkeypatch.setattr(api_database, "execute", execute)

    api_database.ensure_runtime_access()

    authority_ddl = execute.call_args_list[0].args[0]
    assert api_database._AUTH_ROLE_MEMBERSHIP_CTE_SQL in authority_ddl
    assert "grantee.rolcanlogin" in authority_ddl
    assert "WITH RECURSIVE role_membership(member, roleid, member_is_superuser)" in authority_ddl
    assert "to_jsonb(membership) ->> 'inherit_option'" in authority_ddl
    assert "to_jsonb(membership) ->> 'set_option'" in authority_ddl
    assert "membership.inherit_option" not in authority_ddl
    assert "membership.set_option" not in authority_ddl
    assert authority_ddl.count("::boolean, TRUE)") == 4
    assert "OR grantee.rolsuper" in authority_ddl
    assert "membership.roleid = role.oid" in authority_ddl
    assert "membership.admin_option" in authority_ddl
    assert "JOIN pg_roles AS member_role ON member_role.oid = role_membership.roleid" in authority_ddl
    assert "membership.member = role_membership.roleid" in authority_ddl
    assert "OR role_membership.member_is_superuser OR member_role.rolsuper" in authority_ddl
    assert "role_membership.member = grantee.oid" in authority_ddl
    assert "role_membership.roleid = role.oid" in authority_ddl
    assert "> 1" in authority_ddl


def test_ensure_runtime_access_rejects_schema_create_and_owned_relations(monkeypatch) -> None:
    """Provisioning must reject schema CREATE and migration-authority ownership."""
    execute = MagicMock()
    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    monkeypatch.setattr(api_database, "fetch_value", MagicMock(side_effect=[None, 2]))
    monkeypatch.setattr(api_database, "execute", execute)

    api_database.ensure_runtime_access()

    authority_ddl = execute.call_args_list[0].args[0]
    assert "has_schema_privilege(role.oid, namespace.oid, 'CREATE')" in authority_ddl
    assert "has_schema_privilege(role.oid, current_schema(), 'CREATE')" not in authority_ddl
    assert "database.datname = current_database() AND database.datdba = role.oid" in authority_ddl
    assert "namespace.nspname = current_schema() AND namespace.nspowner = role.oid" in authority_ddl
    assert "rel.relkind IN ('r', 'p', 'S')" in authority_ddl
    assert "rel.relowner = role.oid" in authority_ddl


def test_ensure_runtime_access_requires_bootstrap_for_missing_role(monkeypatch) -> None:
    """A non-superuser migration owner must not create the auth capability role."""
    execute = MagicMock()
    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    monkeypatch.setattr(api_database, "fetch_value", MagicMock(side_effect=[None, 0]))
    monkeypatch.setattr(api_database, "execute", execute)

    with pytest.raises(
        CapabilityRoleBootstrapRequiredError,
        match="bootstrap_database_capability_roles.sql as a PostgreSQL superuser",
    ):
        api_database.ensure_runtime_access()

    execute.assert_not_called()


def test_verify_runtime_authority_rejects_other_usable_login_grantees(monkeypatch) -> None:
    """Runtime auth capability must have no other usable or superuser login path."""
    fetch_value = MagicMock(side_effect=[True, 1, True, False, True, True, True, True])
    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    monkeypatch.setattr(api_database, "fetch_value", fetch_value)

    with pytest.raises(SchemaCompatibilityError, match="capability contract is incompatible"):
        api_database.verify_runtime_authority()

    safe_role_query = fetch_value.call_args_list[3].args[0]
    assert api_database._AUTH_ROLE_MEMBERSHIP_CTE_SQL in safe_role_query
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
    assert "grantee.rolname <> session_user" in safe_role_query
    assert "role_membership.member = grantee.oid" in safe_role_query
    assert "role_membership.roleid = role.oid" in safe_role_query
