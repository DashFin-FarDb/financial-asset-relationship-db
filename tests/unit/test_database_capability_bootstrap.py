"""Unit regressions for the identity-bound capability bootstrap coordinator."""

from __future__ import annotations

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, Mock, call

import psycopg2
import pytest

from scripts import bootstrap_database_capability_roles as bootstrap


@pytest.mark.parametrize("mapping", [None, {}, [], "null"])
def test_mapping_rejects_incomplete_targets(mapping) -> None:
    """The coordinator rejects missing keys before it can open a target session."""
    with pytest.raises(bootstrap.BootstrapTargetError, match="complete FarDB bootstrap target mapping"):
        bootstrap._normalize_mapping(mapping)


def test_mapping_keeps_all_capabilities_and_deduplicates_each_target() -> None:
    """The normalized mapping remains complete while repeated databases are checked once."""
    mapping = {role: ["graph_db", "auth_db", "graph_db"] for role in bootstrap._ROLE_NAMES}
    normalized = bootstrap._normalize_mapping(mapping)
    assert normalized == {role: ["graph_db", "auth_db"] for role in bootstrap._ROLE_NAMES}


def test_catalog_database_name_cannot_override_connection_route() -> None:
    """Libpq quotes the catalog-selected database name as a value, not DSN options."""
    target_url = "postgresql://bootstrap:placeholder@127.0.0.1:5432/control?sslmode=disable&hostaddr=127.0.0.1"
    database_name = "target_db host=192.0.2.8 port=1 user=attacker"
    dsn = psycopg2.extensions.make_dsn(
        target_url,
        dbname=database_name,
        connect_timeout=bootstrap._CONNECT_TIMEOUT_SECONDS,
        application_name="fardb-capability-bootstrap-target",
    )

    parameters = bootstrap.psycopg2.extensions.parse_dsn(dsn)

    assert parameters["dbname"] == database_name
    assert parameters["host"] == "127.0.0.1"
    assert parameters["hostaddr"] == "127.0.0.1"
    assert parameters["port"] == "5432"
    assert parameters["user"] == "bootstrap"
    assert parameters["sslmode"] == "disable"


def test_coordinator_locks_shared_catalogs_in_fixed_order_with_bounded_waits() -> None:
    """Shared locks conflict with other writers while permitting own transaction writes."""
    cursor = MagicMock()
    bootstrap._lock_coordinator_catalogs(cursor)
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements[:2] == ["SET LOCAL lock_timeout = %s", "SET LOCAL statement_timeout = %s"]
    assert statements[2:] == [
        "LOCK TABLE pg_catalog.pg_authid IN SHARE ROW EXCLUSIVE MODE",
        "LOCK TABLE pg_catalog.pg_auth_members IN SHARE ROW EXCLUSIVE MODE",
        "LOCK TABLE pg_catalog.pg_database IN SHARE ROW EXCLUSIVE MODE",
    ]
    assert cursor.execute.call_args_list[0].args[1] == ("5s",)


def test_non_superuser_is_rejected_before_privileged_catalog_locks() -> None:
    """A migration owner gets the SQL contract error before lock acquisition."""
    cursor = MagicMock()
    cursor.fetchone.return_value = (False,)
    with pytest.raises(psycopg2.Error, match="FarDB capability-role bootstrap requires a PostgreSQL superuser"):
        bootstrap._require_superuser(cursor)
    assert cursor.execute.call_count == 1
    assert "LOCK TABLE" not in str(cursor.execute.call_args.args[0])


def test_target_schema_lock_uses_share_mode_and_bounded_waits() -> None:
    """Each database protects its local namespace ACLs with a write-conflicting lock."""
    connection = MagicMock()
    bootstrap._lock_target_schema_catalog(connection)
    statements = [call.args[0] for call in connection.cursor.return_value.__enter__.return_value.execute.call_args_list]
    assert statements == [
        "SET LOCAL lock_timeout = %s",
        "SET LOCAL statement_timeout = %s",
        "LOCK TABLE pg_catalog.pg_namespace IN SHARE MODE",
    ]


def test_new_role_schema_check_reads_actual_public_acl() -> None:
    """A not-yet-visible role is checked through the target's real schema ACL."""
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (True,)
    assert bootstrap._public_schema_create_exists(connection) is True
    query = cursor.execute.call_args.args[0]
    assert "aclexplode" in query
    assert "acldefault('n', namespace.nspowner)" in query
    assert "acl.grantee = 0" in query
    assert "acl.privilege_type = 'CREATE'" in query


def test_bootstrap_mapping_is_bound_and_only_fixed_sql_is_executed(tmp_path, monkeypatch) -> None:
    """Untrusted target mapping stays a bound value; executable SQL comes from the reviewed file."""
    bootstrap_file = tmp_path / "bootstrap.sql"
    bootstrap_file.write_text("SELECT 'fixed-reviewed-bootstrap'", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "_BOOTSTRAP_SQL", bootstrap_file)
    cursor = MagicMock()
    mapping = {role: ["target_db"] for role in bootstrap._ROLE_NAMES}

    bootstrap._apply_bootstrap(cursor, mapping)

    expected_calls = [
        call(
            "SELECT pg_catalog.set_config('fardb.bootstrap_targets', %s, true)",
            (json.dumps(mapping, sort_keys=True, separators=(",", ":")),),
        ),
        call("SELECT 'fixed-reviewed-bootstrap'"),
    ]
    assert cursor.execute.call_args_list == expected_calls


def test_target_does_not_assume_visibility_of_coordinator_uncommitted_role() -> None:
    """Coordinator-only uncommitted roles are classified as new for ACL checks."""
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    coordinator_oids: dict[str, int | None] = {
        role: index for index, role in enumerate(bootstrap._ROLE_NAMES, start=10)
    }
    assert bootstrap._visible_target_role_oids(connection, coordinator_oids) == dict.fromkeys(bootstrap._ROLE_NAMES)


def test_indeterminate_commit_is_not_rolled_back_or_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A commit error reports unknown outcome and never claims rollback succeeded."""
    connection = MagicMock(autocommit=True)
    cursor = MagicMock()
    cursor.connection = connection
    cursor.execute.side_effect = lambda statement, *_args: (
        (_ for _ in ()).throw(OSError("connection lost during commit")) if statement == "COMMIT" else None
    )
    monkeypatch.setattr(bootstrap, "_lock_coordinator_catalogs", Mock())
    monkeypatch.setattr(bootstrap, "_require_superuser", Mock())
    monkeypatch.setattr(
        bootstrap, "_normalize_mapping", Mock(return_value={role: ["db"] for role in bootstrap._ROLE_NAMES})
    )
    monkeypatch.setattr(bootstrap, "_cluster_and_database_identity", Mock(return_value=("123", 42, "db")))
    monkeypatch.setattr(bootstrap, "_coordinator_targets", Mock(return_value={"db": (42, "db")}))
    monkeypatch.setattr(
        bootstrap,
        "_preflight_targets",
        Mock(return_value=({"db": connection}, {"db": dict.fromkeys(bootstrap._ROLE_NAMES)})),
    )
    monkeypatch.setattr(bootstrap, "_apply_bootstrap", Mock())
    monkeypatch.setattr(bootstrap, "_verify_target_schema_acl", Mock())

    with pytest.raises(bootstrap.BootstrapOutcomeIndeterminate, match="do not retry"):
        bootstrap.bootstrap_capability_roles(cursor, {role: ["db"] for role in bootstrap._ROLE_NAMES})
    assert not any(call.args and call.args[0] == "ROLLBACK" for call in cursor.execute.call_args_list)


def test_precommit_failure_rolls_back_coordinator_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed target or bootstrap check rolls back known uncommitted coordinator work."""
    connection = MagicMock(autocommit=True)
    cursor = MagicMock()
    cursor.connection = connection
    cursor.execute.return_value = None
    monkeypatch.setattr(bootstrap, "_lock_coordinator_catalogs", Mock())
    monkeypatch.setattr(bootstrap, "_require_superuser", Mock())
    monkeypatch.setattr(
        bootstrap, "_normalize_mapping", Mock(return_value={role: ["db"] for role in bootstrap._ROLE_NAMES})
    )
    monkeypatch.setattr(bootstrap, "_cluster_and_database_identity", Mock(return_value=("123", 42, "db")))
    monkeypatch.setattr(bootstrap, "_coordinator_targets", Mock(return_value={"db": (42, "db")}))
    monkeypatch.setattr(
        bootstrap,
        "_preflight_targets",
        Mock(return_value=({"db": connection}, {"db": dict.fromkeys(bootstrap._ROLE_NAMES)})),
    )
    monkeypatch.setattr(bootstrap, "_apply_bootstrap", Mock(side_effect=ValueError("unsafe schema ACL")))

    with pytest.raises(ValueError, match="unsafe schema ACL"):
        bootstrap.bootstrap_capability_roles(cursor, {role: ["db"] for role in bootstrap._ROLE_NAMES})
    assert any(call.args and call.args[0] == "ROLLBACK" for call in cursor.execute.call_args_list)
    assert not any(call.args and call.args[0] == "COMMIT" for call in cursor.execute.call_args_list)


def test_target_transaction_cleanup_preserves_coordinator_and_closed_sessions() -> None:
    """Cleanup releases only open target sessions, retaining coordinator ownership."""
    coordinator = MagicMock(closed=False)
    target = MagicMock(closed=False)
    closed = MagicMock(closed=True)
    bootstrap._release_target_transactions(
        {"coordinator": coordinator, "target": target, "closed": closed}, coordinator
    )
    target.rollback.assert_called_once_with()
    target.close.assert_not_called()
    coordinator.rollback.assert_not_called()
    coordinator.close.assert_not_called()
    closed.rollback.assert_not_called()
    closed.close.assert_not_called()


def test_target_transaction_cleanup_closes_failed_rollback_and_continues() -> None:
    """A failed target rollback closes that session and still releases later targets."""
    failed = MagicMock(closed=False)
    failed.rollback.side_effect = OSError("target disconnected")
    healthy = MagicMock(closed=False)
    bootstrap._release_target_transactions({"failed": failed, "healthy": healthy}, MagicMock())
    failed.close.assert_called_once_with()
    healthy.rollback.assert_called_once_with()
    healthy.close.assert_not_called()


def test_cli_null_mapping_rejected_before_connection(monkeypatch) -> None:
    """JSON null cannot silently select one database or open an operator connection."""
    monkeypatch.setenv("FARDB_BOOTSTRAP_DATABASE_URL", "postgresql://operator@127.0.0.1/test_db")
    connect = Mock()
    monkeypatch.setattr(bootstrap.psycopg2, "connect", connect)
    with pytest.raises(bootstrap.BootstrapTargetError, match="complete FarDB bootstrap target mapping"):
        bootstrap.main(["--targets-json", "null"])
    connect.assert_not_called()


def test_missing_mapping_rejected_before_transaction_or_mutation() -> None:
    """Direct callers must supply a complete mapping before bootstrap executes any SQL."""
    cursor = MagicMock()
    with pytest.raises(bootstrap.BootstrapTargetError, match="complete FarDB bootstrap target mapping"):
        bootstrap.bootstrap_capability_roles(cursor, None)
    cursor.execute.assert_not_called()


@pytest.mark.parametrize("mapping", [None, {}, {"fardb_runtime_auth": []}])
def test_invalid_mapping_rolls_back_existing_caller_transaction(mapping) -> None:
    """Invalid targets roll back prior caller writes without executing bootstrap SQL."""
    cursor = MagicMock()
    cursor.connection.autocommit = False
    with pytest.raises(bootstrap.BootstrapTargetError, match="bootstrap target"):
        bootstrap.bootstrap_capability_roles(cursor, mapping)
    cursor.execute.assert_not_called()
    cursor.connection.rollback.assert_called_once()
    cursor.connection.commit.assert_not_called()


@pytest.mark.parametrize(
    "database_name",
    [
        "target_db host=192.0.2.8 port=1 user=attacker",
        "postgresql://192.0.2.8/other",
        "target' hostaddr=192.0.2.8 sslmode=disable",
    ],
)
def test_catalog_name_is_separate_from_protected_connection_route(database_name, monkeypatch) -> None:
    """Catalog values remain database names and cannot replace operator routing parameters."""
    coordinator = MagicMock()
    target = MagicMock()
    connect = Mock(return_value=target)
    route = "postgresql://operator@127.0.0.1:5432/control?hostaddr=127.0.0.1&sslmode=require"
    monkeypatch.setattr(bootstrap.psycopg2, "connect", connect)
    monkeypatch.setattr(bootstrap, "_cluster_and_database_identity", Mock(return_value=("123", 43, database_name)))
    with ExitStack() as stack:
        observed = bootstrap._open_target_connections(
            coordinator, route, {database_name: (43, database_name)}, ("123", 42, "control"), stack
        )
        assert observed[database_name] is target
        args, kwargs = connect.call_args
        assert args == (route,)
        assert kwargs["dbname"] == database_name
        parameters = psycopg2.extensions.parse_dsn(psycopg2.extensions.make_dsn(*args, **kwargs))
        assert parameters["dbname"] == database_name
        assert parameters["host"] == "127.0.0.1"
        assert parameters["hostaddr"] == "127.0.0.1"
        assert parameters["port"] == "5432"
        assert parameters["user"] == "operator"
        assert parameters["sslmode"] == "require"
        assert parameters["connect_timeout"] == str(bootstrap._CONNECT_TIMEOUT_SECONDS)
    target.close.assert_called_once()


@pytest.mark.parametrize("identity", [("999", 43, "target"), ("123", 99, "target"), ("123", 43, "other")])
def test_secondary_connection_identity_mismatch_closes_before_acceptance(identity, monkeypatch) -> None:
    """Any cluster, OID or database-name mismatch rejects and releases the target session."""
    target = MagicMock()
    monkeypatch.setattr(bootstrap.psycopg2, "connect", Mock(return_value=target))
    monkeypatch.setattr(bootstrap, "_cluster_and_database_identity", Mock(return_value=identity))
    with ExitStack() as stack, pytest.raises(bootstrap.BootstrapTargetError, match="identity-proved cluster target"):
        bootstrap._open_target_connections(
            MagicMock(),
            "postgresql://operator@127.0.0.1/control",
            {"target": (43, "target")},
            ("123", 42, "control"),
            stack,
        )
    target.close.assert_called_once()
