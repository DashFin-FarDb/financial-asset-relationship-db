"""Focused capability-call coverage for reconciliation schema verification."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api import app_factory
from src.data.database import COORDINATION_RUNTIME_CAPABILITY, GRAPH_RUNTIME_CAPABILITY
from tests.unit.test_postgresql_topology import identity_engine

pytestmark = pytest.mark.unit


def test_reconciliation_schema_verification_calls_each_separate_target_once(monkeypatch) -> None:
    """Separate graph and coordination engines must each be verified exactly once."""
    graph_engine = identity_engine()
    coordination_engine = identity_engine(identifier="99999")
    verify_schema = MagicMock()
    verify_authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", verify_schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", verify_authority)

    app_factory._verify_reconciliation_schemas(graph_engine, coordination_engine)  # pylint: disable=protected-access

    assert verify_schema.call_count == 2
    assert verify_authority.call_count == 2
    assert verify_schema.call_args_list[0].args == (graph_engine,)
    assert verify_schema.call_args_list[0].kwargs["required_capabilities"] == {GRAPH_RUNTIME_CAPABILITY}
    assert verify_schema.call_args_list[1].args == (coordination_engine,)
    assert verify_schema.call_args_list[1].kwargs["required_capabilities"] == {COORDINATION_RUNTIME_CAPABILITY}
    assert verify_authority.call_args_list[0].kwargs["required_capabilities"] == {GRAPH_RUNTIME_CAPABILITY}
    assert verify_authority.call_args_list[1].kwargs["required_capabilities"] == {COORDINATION_RUNTIME_CAPABILITY}


def test_reconciliation_schema_verification_combines_shared_target_capabilities(monkeypatch) -> None:
    """A shared engine must be verified once with the union of required capabilities."""
    shared_engine = identity_engine()
    verify_schema = MagicMock()
    verify_authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", verify_schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", verify_authority)

    app_factory._verify_reconciliation_schemas(shared_engine, shared_engine)  # pylint: disable=protected-access

    required_capabilities = {GRAPH_RUNTIME_CAPABILITY, COORDINATION_RUNTIME_CAPABILITY}
    verify_schema.assert_called_once_with(
        shared_engine,
        required_capabilities=required_capabilities,
        combined_topology=True,
        verification_connection=shared_engine.identity_connections[0],
    )
    verify_authority.assert_called_once_with(
        shared_engine,
        required_capabilities=required_capabilities,
        combined_topology=True,
        verification_connection=shared_engine.identity_connections[0],
    )


@pytest.mark.parametrize("shared", [True, False])
def test_distinct_credentials_propagate_proved_physical_topology(monkeypatch, shared) -> None:
    """Distinct engines keep their scopes while receiving the live topology proof."""
    graph = identity_engine()
    coordination = identity_engine(identifier="12345" if shared else "99999")
    graph.identity_connections[0].execute.return_value.scalar_one.return_value = "graph_login"
    coordination.identity_connections[0].execute.return_value.scalar_one.return_value = "coordination_login"
    schema = MagicMock()
    authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", authority)
    app_factory._verify_reconciliation_schemas(graph, coordination)
    for verifier in (schema, authority):
        assert verifier.call_count == 2
        assert verifier.call_args_list[0].kwargs["combined_topology"] is shared
        assert verifier.call_args_list[1].kwargs["combined_topology"] is shared
        assert verifier.call_args_list[0].kwargs["verification_connection"] is graph.identity_connections[0]
        assert verifier.call_args_list[1].kwargs["verification_connection"] is coordination.identity_connections[0]
    for engine in (graph, coordination):
        engine.connect.assert_called_once()
        proved_connection = engine.identity_connections[0]
        assert proved_connection.execute.call_count == (3 if shared else 2)
        fresh_connection = engine.connect().__enter__()
        assert fresh_connection is not proved_connection
        fresh_connection.execute.assert_not_called()
    graph.identity_contexts[0].__exit__.assert_called_once()
    coordination.identity_contexts[0].__exit__.assert_called_once()


def test_unavailable_identity_stops_before_any_authority_check(monkeypatch) -> None:
    """A failed proof cannot broaden authority or start catalog verification."""
    from src.data.database import SchemaCompatibilityError

    graph = identity_engine()
    graph.identity_connections[0].execute.side_effect = PermissionError("denied")
    schema = MagicMock()
    authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", authority)
    with pytest.raises(SchemaCompatibilityError, match="identity"):
        app_factory._verify_reconciliation_schemas(graph, graph)
    schema.assert_not_called()
    authority.assert_not_called()


def test_changed_identity_blocks_recovery_after_verification(monkeypatch) -> None:
    """An identity change during catalog checks fails before recovery publication."""
    from src.data.database import SchemaCompatibilityError

    graph = identity_engine()
    connection = graph.identity_connections[0]
    first = MagicMock()
    first.fetchall.return_value = [("12345", 16384, "test_db")]
    second = MagicMock()
    second.fetchall.return_value = [("99999", 16384, "test_db")]
    connection.execute.side_effect = [first, second]
    monkeypatch.setattr("src.data.database.verify_database_schema", MagicMock())
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", MagicMock())
    with pytest.raises(SchemaCompatibilityError, match="changed"):
        app_factory._verify_reconciliation_schemas(graph, graph)


@pytest.mark.parametrize("invalid_login", [None, "", 42])
@pytest.mark.parametrize("invalid_target", ["graph", "coordination"])
def test_invalid_login_identity_stops_before_authority(monkeypatch, invalid_login, invalid_target) -> None:
    """Missing or malformed session login cannot establish combined capability scope."""
    from src.data.database import SchemaCompatibilityError

    graph = identity_engine()
    coordination = identity_engine()
    graph.identity_connections[0].execute.return_value.scalar_one.return_value = "graph_login"
    coordination.identity_connections[0].execute.return_value.scalar_one.return_value = "coordination_login"
    invalid_engine = graph if invalid_target == "graph" else coordination
    invalid_engine.identity_connections[0].execute.return_value.scalar_one.return_value = invalid_login
    schema = MagicMock()
    authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", authority)
    with pytest.raises(SchemaCompatibilityError, match="login identity"):
        app_factory._verify_reconciliation_schemas(graph, coordination)
    schema.assert_not_called()
    authority.assert_not_called()
    graph.identity_contexts[0].__exit__.assert_called_once()
    coordination.identity_contexts[0].__exit__.assert_called_once()


def test_shared_authenticated_login_combines_despite_distinct_active_roles(monkeypatch) -> None:
    """SET ROLE cannot change the login used to approve combined capabilities."""
    graph = identity_engine()
    coordination = identity_engine()

    def result_for_principal(connection, active_role):
        """Model identity plus distinct active roles for one authenticated login."""

        def execute(statement):
            """Expose separate authenticated and SET ROLE principals."""
            result = MagicMock()
            if str(statement) == "SELECT session_user":
                result.scalar_one.return_value = "shared_login"
            elif str(statement) == "SELECT current_user":
                result.scalar_one.return_value = active_role
            else:
                result.fetchall.return_value = [("12345", 16384, "test_db")]
            return result

        connection.execute.side_effect = execute

    result_for_principal(graph.identity_connections[0], "graph_active_role")
    result_for_principal(coordination.identity_connections[0], "coordination_active_role")
    schema = MagicMock()
    authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", authority)
    app_factory._verify_reconciliation_schemas(graph, coordination)
    for verifier in (schema, authority):
        assert verifier.call_count == 2
        assert all(
            call.kwargs["required_capabilities"] == {"graph", "coordination"} for call in verifier.call_args_list
        )
    for engine in (graph, coordination):
        queries = [str(call.args[0]) for call in engine.identity_connections[0].execute.call_args_list]
        assert "SELECT session_user" in queries
        assert "SELECT current_user" not in queries
