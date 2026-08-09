"""Focused capability-call coverage for reconciliation schema verification."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api import app_factory

pytestmark = pytest.mark.unit


def test_reconciliation_schema_verification_calls_each_separate_target_once(monkeypatch) -> None:
    """Separate graph and coordination engines must each be verified exactly once."""
    graph_engine = object()
    coordination_engine = object()
    verify_schema = MagicMock()
    verify_authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", verify_schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", verify_authority)

    app_factory._verify_reconciliation_schemas(graph_engine, coordination_engine)  # pylint: disable=protected-access

    assert verify_schema.call_count == 2
    assert verify_authority.call_count == 2
    assert verify_schema.call_args_list[0].kwargs["required_capabilities"] == {"graph"}
    assert verify_schema.call_args_list[1].kwargs["required_capabilities"] == {"coordination"}
    assert verify_authority.call_args_list[0].kwargs["required_capabilities"] == {"graph"}
    assert verify_authority.call_args_list[1].kwargs["required_capabilities"] == {"coordination"}


def test_reconciliation_schema_verification_combines_shared_target_capabilities(monkeypatch) -> None:
    """A shared engine must be verified once with the union of required capabilities."""
    shared_engine = object()
    verify_schema = MagicMock()
    verify_authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", verify_schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", verify_authority)

    app_factory._verify_reconciliation_schemas(shared_engine, shared_engine)  # pylint: disable=protected-access

    verify_schema.assert_called_once_with(shared_engine, required_capabilities={"graph", "coordination"})
    verify_authority.assert_called_once_with(shared_engine, required_capabilities={"graph", "coordination"})
