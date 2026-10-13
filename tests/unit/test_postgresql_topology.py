"""Live identity proof and retained-session verification regressions."""

from unittest.mock import MagicMock

import pytest

from src.data.database import SchemaCompatibilityError, _ConnectionBoundEngine
from src.data.postgresql_topology import DatabaseIdentity, read_database_identity, same_database


def identity_engine(identifier="12345", oid=16384, name="test_db"):
    """Model an engine whose retained connection exposes a complete live identity."""
    engine = MagicMock()
    engine.url = "postgresql://runtime@127.0.0.1/test_db"
    connection = MagicMock()
    connection.engine = engine
    connection.execute.return_value.fetchall.return_value = [(identifier, oid, name)]
    engine.connect.return_value.__enter__.return_value = connection
    return engine


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [("12345", 1, "db"), ("12345", 1, "db")],
        [("12345", 1)],
        [("invalid", 1, "db")],
        [("0", 1, "db")],
        [("12345", 0, "db")],
        [("12345", "1", "db")],
        [("12345", 1, "")],
    ],
)
def test_identity_rejects_missing_ambiguous_or_malformed_rows(rows) -> None:
    """An uncertain identity cannot enable combined authority."""
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = rows
    with pytest.raises(SchemaCompatibilityError, match="could not be established"):
        read_database_identity(connection)


def test_identity_permission_failure_is_closed_with_original_cause() -> None:
    """A runtime role without identity access receives no fallback or grant."""
    connection = MagicMock()
    failure = PermissionError("identity access denied")
    connection.execute.side_effect = failure
    with pytest.raises(SchemaCompatibilityError) as raised:
        read_database_identity(connection)
    assert raised.value.__cause__ is failure
    assert connection.execute.call_count == 1


@pytest.mark.parametrize(
    "other",
    [
        DatabaseIdentity("999", 16384, "test_db"),
        DatabaseIdentity("12345", 16385, "test_db"),
        DatabaseIdentity("12345", 16384, "other_db"),
    ],
)
def test_equal_names_or_oids_do_not_prove_same_cluster_and_database(other) -> None:
    """Each identity coordinate must match, including the cluster identifier."""
    identity = DatabaseIdentity("12345", 16384, "test_db")
    assert not same_database(identity, other)
    assert same_database(identity, identity)


def test_verification_adapter_rejects_connection_from_another_engine() -> None:
    """Identity cannot be read on one engine and verified through another."""
    engine = identity_engine()
    connection = identity_engine().connect().__enter__()
    with pytest.raises(SchemaCompatibilityError, match="does not belong"):
        _ConnectionBoundEngine(engine, connection)


def test_verification_adapter_retains_caller_connection_ownership() -> None:
    """Nested verification cannot replace or close the identity-proved session."""
    engine = identity_engine()
    connection = engine.connect().__enter__()
    bound = _ConnectionBoundEngine(engine, connection)
    with bound.connect() as actual:
        assert actual is connection
    connection.close.assert_not_called()
