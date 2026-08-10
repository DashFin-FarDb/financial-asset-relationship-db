"""Focused auth capability-grantee authority regressions."""

from unittest.mock import MagicMock

import pytest

from api import database as api_database
from src.data.database import SchemaCompatibilityError

pytestmark = pytest.mark.unit


def test_ensure_runtime_access_rejects_more_than_one_login_grantee(monkeypatch) -> None:
    """Operator provisioning must not tolerate multiple logins reaching auth capability."""
    execute = MagicMock()
    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    monkeypatch.setattr(api_database, "fetch_value", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api_database, "execute", execute)

    api_database.ensure_runtime_access()

    authority_ddl = execute.call_args_list[0].args[0]
    assert "grantee.rolcanlogin" in authority_ddl
    assert "pg_has_role(grantee.oid, role.oid, 'MEMBER')" in authority_ddl
    assert "> 1" in authority_ddl


def test_verify_runtime_authority_rejects_other_login_grantees(monkeypatch) -> None:
    """Runtime auth capability must be reachable by session_user and no other login."""
    fetch_value = MagicMock(side_effect=[True, 1, True, False, True, True, True, True])
    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    monkeypatch.setattr(api_database, "fetch_value", fetch_value)

    with pytest.raises(SchemaCompatibilityError, match="capability contract is incompatible"):
        api_database.verify_runtime_authority()

    safe_role_query = fetch_value.call_args_list[3].args[0]
    assert "grantee.rolcanlogin" in safe_role_query
    assert "grantee.rolname <> session_user" in safe_role_query
    assert "pg_has_role(grantee.oid, role.oid, 'MEMBER')" in safe_role_query
