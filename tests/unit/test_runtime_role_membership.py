"""Unit tests for runtime role membership and topology-scoped login principal approval."""

from unittest.mock import MagicMock

import pytest

from src.data.database import (
    COORDINATION_RUNTIME_CAPABILITY,
    COORDINATION_RUNTIME_ROLE,
    GRAPH_RUNTIME_CAPABILITY,
    GRAPH_RUNTIME_ROLE,
    _verify_runtime_capability_roles,
)
from src.data.runtime_role_membership import (
    APPROVED_RUNTIME_LOGIN_PRINCIPALS,
    get_approved_login_principals,
)


def test_approved_runtime_login_principals_base_definitions() -> None:
    """Ensure baseline dictionary defines least-privilege principals for each runtime role."""
    assert APPROVED_RUNTIME_LOGIN_PRINCIPALS["fardb_runtime_auth"] == frozenset(
        {"fardb_login_auth", "fardb_login_auth_prod"}
    )
    assert APPROVED_RUNTIME_LOGIN_PRINCIPALS["fardb_runtime_graph"] == frozenset({"fardb_login_graph"})
    assert APPROVED_RUNTIME_LOGIN_PRINCIPALS["fardb_runtime_coordination"] == frozenset({"fardb_login_coordination"})


def test_get_approved_login_principals_separated_topology() -> None:
    """Separated topology must restrict coordination role strictly to coordination login."""
    coordination_logins = get_approved_login_principals(
        COORDINATION_RUNTIME_ROLE,
        combined_topology=False,
    )
    assert coordination_logins == ("fardb_login_coordination",)

    graph_logins = get_approved_login_principals(
        GRAPH_RUNTIME_ROLE,
        combined_topology=False,
    )
    assert graph_logins == ("fardb_login_graph",)


def test_get_approved_login_principals_combined_topology() -> None:
    """Combined topology must approve graph login for coordination role."""
    coordination_logins = get_approved_login_principals(
        COORDINATION_RUNTIME_ROLE,
        combined_topology=True,
    )
    assert coordination_logins == ("fardb_login_coordination", "fardb_login_graph")

    graph_logins = get_approved_login_principals(
        GRAPH_RUNTIME_ROLE,
        combined_topology=True,
    )
    assert graph_logins == ("fardb_login_graph",)


def test_get_approved_login_principals_unknown_role_raises() -> None:
    """Querying an unknown capability role must raise ValueError."""
    with pytest.raises(ValueError, match="Unknown capability role: unknown_role"):
        get_approved_login_principals("unknown_role")


def test_verify_runtime_capability_roles_passes_combined_topology_flag() -> None:
    """_verify_runtime_capability_roles passes combined_topology based on requested capabilities."""
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = True
    mock_conn.execute.return_value = mock_result

    # 1. Combined capabilities: ("graph", "coordination")
    combined_caps = (GRAPH_RUNTIME_CAPABILITY, COORDINATION_RUNTIME_CAPABILITY)
    _verify_runtime_capability_roles(mock_conn, combined_caps, ["assets"])

    # Collect all approved_logins bound in connection.execute calls
    executed_params = [
        call.args[1]
        for call in mock_conn.execute.call_args_list
        if len(call.args) > 1 and "approved_logins" in call.args[1]
    ]
    coordination_call_params = [p for p in executed_params if p["role_name"] == COORDINATION_RUNTIME_ROLE]
    assert len(coordination_call_params) == 1
    assert sorted(coordination_call_params[0]["approved_logins"]) == ["fardb_login_coordination", "fardb_login_graph"]

    # 2. Separated coordination capability: ("coordination",)
    mock_conn.reset_mock()
    separated_coordination = (COORDINATION_RUNTIME_CAPABILITY,)
    _verify_runtime_capability_roles(mock_conn, separated_coordination, ["distributed_locks"])

    executed_params = [
        call.args[1]
        for call in mock_conn.execute.call_args_list
        if len(call.args) > 1 and "approved_logins" in call.args[1]
    ]
    coordination_call_params = [p for p in executed_params if p["role_name"] == COORDINATION_RUNTIME_ROLE]
    assert len(coordination_call_params) == 1
    assert coordination_call_params[0]["approved_logins"] == ["fardb_login_coordination"]
