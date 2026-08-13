"""Regression coverage for PostgreSQL runtime sequence-ownership authority."""

from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy.engine import Engine

from src.data.database import SchemaCompatibilityError, verify_runtime_database_authority

pytestmark = pytest.mark.unit


def test_postgresql_authority_gate_covers_assumable_application_sequence_owner() -> None:
    """FarDB-owned serial/identity sequences must participate in the ownership gate."""
    runtime_engine = Mock(spec=Engine)
    runtime_engine.url = "postgresql://runtime:secret@database.invalid/fardb"
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = False
    runtime_engine.connect.return_value.__enter__ = MagicMock(return_value=connection)
    runtime_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"):
        verify_runtime_database_authority(runtime_engine)

    authority_query = str(connection.execute.call_args.args[0])
    parameters = connection.execute.call_args.args[1]
    assert "rel.relkind = 'S'" in authority_query
    assert "FROM pg_depend AS dependency" in authority_query
    assert "dependency.objid = rel.oid" in authority_query
    assert "dependency.deptype IN ('a', 'i')" in authority_query
    assert "owning_table.relname IN" in authority_query
    assert set(parameters["sequence_tables"]) == set(parameters["tables"])
