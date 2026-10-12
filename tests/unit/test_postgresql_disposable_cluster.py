"""Unit checks for the disposable PostgreSQL harness boundary."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from tests.integration import postgresql_disposable_cluster as guard


def test_unverified_cluster_is_rejected_before_connect_or_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing harness identity fails before a PostgreSQL connection is opened."""
    monkeypatch.setenv(guard.ENABLE_ENVIRONMENTS[0], "1")
    monkeypatch.delenv(guard.SYSTEM_IDENTIFIER_ENV, raising=False)
    connect = Mock(side_effect=AssertionError("connection must not be opened"))
    monkeypatch.setattr(guard.psycopg2, "connect", connect)

    with pytest.raises(guard.DisposableTargetError, match="must be supplied by the harness"):
        guard.connect_attested("postgresql://test@127.0.0.1/test_db")
    connect.assert_not_called()


def test_connected_but_mismatched_system_identifier_closes_before_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    """A target that answers with a different identifier never escapes the guard."""
    monkeypatch.setenv(guard.ENABLE_ENVIRONMENTS[0], "1")
    monkeypatch.setenv(guard.SYSTEM_IDENTIFIER_ENV, "123456789")
    monkeypatch.setattr(guard, "_read_harness_record", Mock(return_value={"system_identifier": "123456789"}))
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = ("987654321",)
    monkeypatch.setattr(guard.psycopg2, "connect", Mock(return_value=connection))

    with pytest.raises(guard.DisposableTargetError, match="does not match"):
        guard.connect_attested("postgresql://test@127.0.0.1/test_db")
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://test@127.0.0.1/test_db?hostaddr=192.0.2.25",
        "postgresql://test@localhost/test_db?host=localhost&hostaddr=2001:db8::1",
        "postgresql://test@localhost/test_db?host=localhost,example.com",
        "postgresql://test@db.example/test_db?host=localhost&hostaddr=127.0.0.1",
    ],
)
def test_effective_loopback_guard_rejects_overrides_before_connect(database_url: str, monkeypatch) -> None:
    """Neither host nor hostaddr parameters can redirect an attested URI."""
    monkeypatch.setenv(guard.ENABLE_ENVIRONMENTS[0], "1")
    monkeypatch.setenv(guard.SYSTEM_IDENTIFIER_ENV, "123456789")
    connect = Mock(side_effect=AssertionError("connection must not be opened"))
    monkeypatch.setattr(guard.psycopg2, "connect", connect)

    with pytest.raises(guard.DisposableTargetError):
        guard.connect_attested(database_url)
    connect.assert_not_called()


def test_owned_role_cleanup_requires_the_recorded_oid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cleanup skips a missing or replaced role rather than dropping by name."""
    role = guard.OwnedRole("fdbt_12345678_role_ab12", 42)
    monkeypatch.setitem(guard._owned_roles, role.name, role.oid)
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (99,)

    assert guard.drop_owned_role(connection, role) is False
    assert guard._owned_roles[role.name] == role.oid


@pytest.mark.parametrize(
    "address",
    [
        "LOCALHOST",
        "localhost.",
        "localhost",
        "db.example",
        "",
        "[::1]",
        "::1%lo",
        "127.0.0.1,::1",
        "127.0.0.1%20",
        "%4cOCALHOST",
    ],
)
def test_helper_rejects_named_hostaddr_before_connect(address, monkeypatch) -> None:
    """The mutation-connection guard uses the same numeric-only address rule."""
    monkeypatch.setenv(guard.ENABLE_ENVIRONMENTS[0], "1")
    monkeypatch.setenv(guard.SYSTEM_IDENTIFIER_ENV, "12345")
    connect = Mock()
    monkeypatch.setattr(guard.psycopg2, "connect", connect)
    with pytest.raises(guard.DisposableTargetError):
        guard.connect_attested("postgresql://test@localhost/test_db?hostaddr=" + address)
    connect.assert_not_called()


@pytest.mark.parametrize(
    "version,columns",
    [
        (150019, "roleid, member, grantor, admin_option"),
        (160014, "roleid, member, grantor, admin_option, inherit_option, set_option"),
    ],
)
def test_collision_snapshot_retains_available_membership_options(version, columns) -> None:
    """PG15 snapshots omit nonexistent options while PG16 retains both new flags."""
    from tests.integration.test_runtime_authority_postgres import _role_and_membership_snapshot

    connection = MagicMock(server_version=version)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (True, False)
    memberships = [(1, 2, 3, True)] if version < 160000 else [(1, 2, 3, True, False, True)]
    cursor.fetchall.return_value = memberships
    assert _role_and_membership_snapshot(connection, 1) == ((True, False), tuple(memberships))
    query = cursor.execute.call_args_list[-1].args[0]
    assert query.startswith("SELECT " + columns + " FROM pg_auth_members")
    assert cursor.execute.call_args_list[-1].args[1] == (1, 1)
    if version < 160000:
        assert "inherit_option" not in query and "set_option" not in query


def _container_fixture():
    """Represent exactly one loopback service with image-declared anonymous storage."""
    return {
        "Id": "a" * 64,
        "Image": "sha256:reviewed",
        "State": {"Running": True, "StartedAt": "start", "Pid": 123},
        "Config": {
            "Image": "postgres:16",
            "Env": ["POSTGRES_USER=test", "POSTGRES_DB=test_db", "PGDATA=/data"],
            "Volumes": {"/data": {}},
        },
        "HostConfig": {"Binds": None, "Mounts": None, "RestartPolicy": {"Name": "no"}},
        "NetworkSettings": {"Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55000"}]}},
        "Mounts": [
            {
                "Type": "volume",
                "Name": "b" * 64,
                "Source": "/var/lib/docker/volumes/" + "b" * 64 + "/_data",
                "Destination": "/data",
            }
        ],
    }


@pytest.mark.parametrize("change", ["image", "bind", "named", "public", "restart", "multiple"])
def test_container_identity_rejects_ambiguous_or_persistent_setup(change) -> None:
    """Container-local CLI is unavailable for the wrong image, mounts or lifecycle."""
    container = _container_fixture()
    if change == "image":
        container["Config"]["Image"] = "postgres:18"
    if change == "bind":
        container["HostConfig"]["Binds"] = ["existing:/data"]
    if change == "named":
        container["Mounts"][0]["Name"] = "persistent"
    if change == "public":
        container["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostIp"] = "0.0.0.0"
    if change == "restart":
        container["HostConfig"]["RestartPolicy"]["Name"] = "always"
    if change == "multiple":
        container["Mounts"].append(container["Mounts"][0])
    with pytest.raises(guard.DisposableTargetError):
        guard._container_identity(container, 16)


def test_cli_record_required_before_any_docker_mutation(monkeypatch) -> None:
    """A caller cannot replace ownership proof with an attested unrelated session."""
    monkeypatch.delenv(guard.CONTAINER_RECORD_ENV, raising=False)
    docker = Mock()
    monkeypatch.setattr(guard, "_docker_command", docker)
    with pytest.raises(guard.DisposableTargetError, match="ownership record"):
        guard.ContainerCliRunner("postgresql://test:test@127.0.0.1:55000/test_db?sslmode=disable")
    docker.assert_not_called()


def test_cli_binding_uses_container_local_port_not_the_host_port(monkeypatch) -> None:
    """The fixed namespace URL preserves only the explicitly selected database."""
    monkeypatch.setenv(guard.ENABLE_ENVIRONMENTS[0], "1")
    record = {"port": 55000}
    url = "postgresql://test:test@127.0.0.1:55000/fardb_authority_test?sslmode=disable"
    assert (
        guard._internal_cli_url(url, record)
        == "postgresql://test:test@127.0.0.1:5432/fardb_authority_test?sslmode=disable"
    )
    for suffix in ("&dbname=other", "&hostaddr=127.0.0.2", "&port=5432", "&service=other"):
        with pytest.raises(guard.DisposableTargetError):
            guard._internal_cli_url(url + suffix, record)
    with pytest.raises(guard.DisposableTargetError):
        guard._internal_cli_url(url.replace(":55000/", ":55001/"), record)


def test_runner_rejects_container_restart_before_cli(monkeypatch) -> None:
    """Changing the lifecycle of the same container ID invalidates its record."""
    container = _container_fixture()
    runner = object.__new__(guard.ContainerCliRunner)
    runner.cli = "docker"
    runner.record = guard._container_identity(container, 16)
    container["State"]["StartedAt"] = "restarted"
    monkeypatch.setattr(guard, "_inspect_container", lambda *_: container)
    docker = Mock()
    monkeypatch.setattr(guard, "_docker_command", docker)
    with pytest.raises(guard.DisposableTargetError, match="restarted"):
        runner.validate()
    docker.assert_not_called()


def test_runner_transfer_checksum_mismatch_rejects_before_execution(monkeypatch) -> None:
    """A changed executable/projection cannot reach migration execution."""
    runner = object.__new__(guard.ContainerCliRunner)
    runner.cli = "docker"
    runner.record = {"id": "a" * 64}
    runner.directory = "/tmp/owned"
    runner.digests = {"supabase": "reviewed"}
    monkeypatch.setattr(guard, "_docker_command", Mock(return_value=Mock(stdout=b"different file")))
    with pytest.raises(guard.DisposableTargetError, match="checksum"):
        runner._verify_transferred_bytes()


def test_runner_timeout_stops_only_the_recorded_container(monkeypatch) -> None:
    """A timed-out Docker client cannot leave its migration alive or stop another ID."""
    import subprocess

    runner = object.__new__(guard.ContainerCliRunner)
    runner.cli = "docker"
    runner.record = {"id": "a" * 64}
    runner.directory = "/tmp/owned"
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("docker", 1)))
    stop = Mock()
    monkeypatch.setattr(guard, "_docker_command", stop)
    with pytest.raises(guard.DisposableTargetError, match="timed out"):
        runner._execute(["/tmp/owned/supabase", "--version"], 1)
    stop.assert_called_once_with(["docker", "stop", "--time", "5", "a" * 64])


@pytest.mark.parametrize("change", ["invocation", "identifier", "owner"])
def test_cli_record_mismatch_rejects_before_docker_use(change, tmp_path, monkeypatch) -> None:
    """An unrelated ownership record cannot authorize CLI setup or migration."""
    import json

    record = {"invocation": "abcdefgh12345678", "system_identifier": "12345", "owner": "local-created"}
    if change == "invocation":
        record["invocation"] = "different12345678"
    elif change == "identifier":
        record["system_identifier"] = "99999"
    else:
        record["owner"] = "discovered-existing"
    path = tmp_path / "record.json"
    path.write_text(json.dumps(record))
    monkeypatch.setenv(guard.CONTAINER_RECORD_ENV, str(path))
    monkeypatch.setenv(guard.ENABLE_ENVIRONMENTS[0], "1")
    monkeypatch.setenv(guard.SYSTEM_IDENTIFIER_ENV, "12345")
    monkeypatch.setenv(guard.INVOCATION_ID_ENV, "abcdefgh12345678")
    docker = Mock()
    monkeypatch.setattr(guard, "_docker_command", docker)
    with pytest.raises(guard.DisposableTargetError):
        guard.ContainerCliRunner("postgresql://test:test@127.0.0.1:55000/test_db?sslmode=disable")
    docker.assert_not_called()


@pytest.mark.parametrize("container_id", ["a" * 12, "name", "", "postgres:16"])
def test_only_full_container_ids_can_be_inspected(container_id, monkeypatch) -> None:
    """A name, image or truncated prefix cannot select the mutation namespace."""
    docker = Mock()
    monkeypatch.setattr(guard, "_docker_command", docker)
    with pytest.raises(guard.DisposableTargetError, match="full container ID"):
        guard._inspect_container("docker", container_id)
    docker.assert_not_called()


@pytest.mark.parametrize("actual", ["canonical", "different"])
def test_post_cli_catalog_is_read_through_host_attestation(actual, monkeypatch) -> None:
    """A successful CLI cannot substitute for host-side catalog/history verification."""
    from scripts import postgresql_drift as drift

    attested = MagicMock()
    cursor = attested.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    monkeypatch.setattr(guard, "attested_connection", attested)
    monkeypatch.setattr(drift, "normalized_managed_catalog", Mock(return_value={}))
    monkeypatch.setattr(drift, "catalog_digest", Mock(return_value=actual))
    manifest = Mock()
    manifest.catalog_digest_for_profile.return_value = "canonical"
    manifest.migrations_for_profile.return_value = []
    monkeypatch.delenv("FARDB_POSTGRES_EVIDENCE_DIR", raising=False)
    if actual == "canonical":
        guard.verify_applied_profile("host-attested-url", manifest, "auth")
        cursor.execute.assert_called_once_with(
            "SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version"
        )
    else:
        with pytest.raises(guard.DisposableTargetError, match="digest mismatch"):
            guard.verify_applied_profile("host-attested-url", manifest, "auth")
    attested.assert_called_once_with("host-attested-url")


def test_docker_transport_timeout_does_not_publish_credential_arguments(monkeypatch) -> None:
    """Transport failures expose a bounded reason rather than the Docker command's env arguments."""
    import subprocess

    command = ["docker", "create", "-e", "POSTGRES_PASSWORD=private-fixture-value"]
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired(command, 1)))
    with pytest.raises(guard.DisposableTargetError, match="transport failed") as error:
        guard._docker_command(command)
    assert error.value.__suppress_context__ is True
    assert error.value.__cause__ is None
    assert "private-fixture-value" not in str(error.value)


@pytest.mark.parametrize("version,options", [(150019, ""), (160014, " WITH INHERIT TRUE, SET TRUE")])
def test_catalog_fixture_uses_supported_membership_grant(version, options) -> None:
    """The bounded-query fixture remains active on PG15 without unsupported option syntax."""
    from psycopg2 import sql

    from tests.integration.test_runtime_authority_postgres import _grant_usable_membership

    cursor = Mock()
    cursor.connection.server_version = version
    _grant_usable_membership(cursor, "capability", "login")
    cursor.execute.assert_called_once_with(
        sql.SQL("GRANT {} TO {}" + options).format(sql.Identifier("capability"), sql.Identifier("login"))
    )


def test_native_numeric_attestation_without_owned_container_is_rejected(monkeypatch) -> None:
    """Opt-in and a manually supplied cluster ID cannot enable native fixture mutations."""
    monkeypatch.setenv(guard.ENABLE_ENVIRONMENTS[0], "1")
    monkeypatch.setenv(guard.SYSTEM_IDENTIFIER_ENV, "12345")
    monkeypatch.delenv(guard.CONTAINER_RECORD_ENV, raising=False)
    connect = Mock()
    monkeypatch.setattr(guard.psycopg2, "connect", connect)
    with pytest.raises(guard.DisposableTargetError, match="ownership record"):
        guard.connect_attested("postgresql://test@127.0.0.1/test_db")
    connect.assert_not_called()


@pytest.mark.parametrize("existing_volume", [False, True])
def test_failed_start_cleanup_removes_only_owned_resources(existing_volume, monkeypatch) -> None:
    """An unstarted container is removed without deleting any supplied pre-existing volume."""
    container_id, volume, invocation = "a" * 64, "b" * 64, "invocation"
    container = _container_fixture()
    container["Config"]["Labels"] = {"fardb.test.invocation": invocation}
    monkeypatch.setattr(guard, "_inspect_container", Mock(return_value=container))
    calls = []
    remaining = {container_id}

    def docker(command, **_kwargs):
        """Simulate a failed startup and Docker's exact-ID removal operations."""
        calls.append(command)
        if command[1] == "stop":
            raise guard.DisposableTargetError("never started")
        if command[1] == "rm":
            remaining.remove(container_id)
        output = " ".join(remaining) if command[1] == "ps" else volume if command[1:3] == ["volume", "ls"] else ""
        return Mock(stdout=output.encode())

    monkeypatch.setattr(guard, "_docker_command", docker)
    guard._cleanup_local_container(
        "docker", container_id, volume, invocation, set(), {volume} if existing_volume else set()
    )
    assert ["docker", "rm", "--force", container_id] in calls
    assert (["docker", "volume", "rm", volume] in calls) is not existing_volume


def test_cleanup_rejects_a_preexisting_container_without_docker_calls(monkeypatch) -> None:
    """Even a supplied container ID cannot authorize cleanup when it predates this run."""
    docker = Mock()
    monkeypatch.setattr(guard, "_docker_command", docker)
    with pytest.raises(guard.DisposableTargetError, match="pre-existing"):
        guard._cleanup_local_container("docker", "a" * 64, "b" * 64, "invocation", {"a" * 64}, set())
    docker.assert_not_called()


@pytest.mark.parametrize("failure", [False, True])
def test_daemon_lock_rejects_concurrent_versions_and_releases(monkeypatch, failure) -> None:
    """Both majors share the reservation and release it on success or failure."""
    held: set[str] = set()
    calls = []
    lock_id = "c" * 64

    def docker(command, **_kwargs):
        """Simulate Docker's atomic daemon-wide name reservation."""
        calls.append(command)
        if command[1] == "create":
            if held:
                raise guard.DisposableTargetError("name conflict")
            held.add(lock_id)
            return Mock(stdout=lock_id.encode())
        assert command == ["docker", "rm", "--volumes", lock_id]
        held.remove(lock_id)
        return Mock(stdout=b"")

    def run(_cli, _major, _args):
        """Reject the competing major before its inventory or mutation body."""
        assert held == {lock_id}
        with pytest.raises(guard.DisposableTargetError, match="exclusive Docker daemon harness lock"):
            guard.run_container_harness(15, [])
        assert held == {lock_id}
        if failure:
            raise RuntimeError("validation failed")
        return 0

    monkeypatch.setattr(guard, "_docker_cli", lambda: "docker")
    monkeypatch.setattr(guard, "_docker_command", docker)
    body = Mock(side_effect=run)
    monkeypatch.setattr(guard, "_run_locked_container_harness", body)
    if failure:
        with pytest.raises(RuntimeError, match="validation failed"):
            guard.run_container_harness(16, [])
    else:
        assert guard.run_container_harness(16, []) == 0
    body.assert_called_once_with("docker", 16, [])
    assert not held
    assert [command[1] for command in calls] == ["create", "create", "rm"]
    assert calls[0][3] == calls[1][3]
    with guard._exclusive_daemon_harness_lock("docker", 15):
        assert held == {lock_id}
    assert not held
