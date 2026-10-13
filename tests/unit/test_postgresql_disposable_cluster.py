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
        assert "inherit_option" not in query
        assert "set_option" not in query


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
        overridden_url = url + suffix
        with pytest.raises(guard.DisposableTargetError):
            guard._internal_cli_url(overridden_url, record)
    wrong_port_url = url.replace(":55000/", ":55001/")
    with pytest.raises(guard.DisposableTargetError):
        guard._internal_cli_url(wrong_port_url, record)


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
    runner.directory = "/run/owned"
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
    runner.directory = "/run/owned"
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


@pytest.mark.parametrize(
    "statement",
    [
        "DROP ROLE IF EXISTS absent, existing",
        'DROP ROLE IF EXISTS "absent", "existing"',
        "DROP ROLE absent; DROP ROLE existing",
        "SELECT 1; DROP ROLE existing",
        "DROP ROLE absent -- hidden\n, existing",
        "DROP USER existing",
        "DROP OWNED BY absent, existing CASCADE",
        "CREATE ROLE new IN ROLE existing",
        "ALTER ROLE existing SUPERUSER",
        "DO $$ BEGIN EXECUTE 'DROP ROLE existing'; END $$",
    ],
)
def test_unsupported_role_ddl_rejected_before_driver_execution(statement) -> None:
    """No unsupported form can reach the driver's mutation or ownership query."""
    cursor = MagicMock()
    cursor.mogrify.return_value = statement.encode()
    with pytest.raises(guard.DisposableTargetError):
        guard.OwnedRoleCursor.execute(cursor, statement)
    cursor.connection.cursor.assert_not_called()
    cursor._execute_driver.assert_not_called()


@pytest.mark.parametrize(
    "statement, expected",
    [
        ('DROP ROLE IF EXISTS "quoted;role";', ("DROP ROLE IF EXISTS", "quoted;role")),
        ('DROP ROLE "double""quote"', ("DROP ROLE", 'double"quote')),
        ("CREATE ROLE owned LOGIN PASSWORD 'safe' NOINHERIT CONNECTION LIMIT 7", ("CREATE ROLE", "owned")),
        ('ALTER ROLE "original" RENAME TO "saved"', ("ALTER ROLE", "original")),
    ],
)
def test_role_ddl_parser_fully_consumes_supported_forms(statement, expected) -> None:
    """Quoted identifiers and current fixture options preserve their exact names."""
    assert guard._parse_role_ddl(statement) == expected


def _private_runner(monkeypatch):
    """Create a runner whose owned parent is separately validated by focused tests."""
    runner = object.__new__(guard.ContainerCliRunner)
    runner.cli = "docker"
    runner.record = {"id": "a" * 64}
    runner.directory = None
    runner.private_parent = None
    runner.parent_identity = None
    monkeypatch.setattr(guard, "invocation_id", lambda: "invocation")
    monkeypatch.setattr(runner, "validate", Mock())

    def parent(path, *, adopt=False):
        """Model successful ownership adoption without accepting an untrusted child."""
        assert path == "/run/fardb-cli-invocation"
        if adopt:
            runner.private_parent = path
            runner.parent_identity = "700:0:1:2"

    monkeypatch.setattr(runner, "_validate_private_parent", parent)
    return runner


@pytest.mark.parametrize(
    "output",
    [
        b"",
        b"/elsewhere/other\n",
        b"/run/fardb-cli-invocation/cli-ABC123\nextra\n",
        b"/run/fardb-cli-invocation/../bad\n",
    ],
)
def test_malformed_mktemp_output_never_becomes_a_cleanup_target(monkeypatch, output) -> None:
    """Untrusted output cannot become a transfer or recursive cleanup argument."""
    runner = _private_runner(monkeypatch)
    docker = Mock(return_value=Mock(stdout=output))
    monkeypatch.setattr(guard, "_docker_command", docker)
    with pytest.raises(guard.DisposableTargetError, match="malformed"):
        runner.__enter__()
    runner.__exit__()
    assert runner.directory is None
    assert runner.private_parent is None
    commands = [call.args[0] for call in docker.call_args_list]
    assert commands == [
        ["docker", "exec", "a" * 64, "mkdir", "-m", "700", "--", "/run/fardb-cli-invocation"],
        ["docker", "exec", "a" * 64, "mktemp", "-d", "-p", "/run/fardb-cli-invocation", "cli-XXXXXX"],
        ["docker", "exec", "a" * 64, "rmdir", "--", "/run/fardb-cli-invocation"],
    ]


@pytest.mark.parametrize("metadata", [b"700:0\n", b"777:0\n", b"700:99\n"])
def test_private_directory_checks_mode_and_owner_before_adoption(monkeypatch, metadata) -> None:
    """Only a private child owned by the container exec user is accepted."""
    runner = _private_runner(monkeypatch)
    runner.private_parent = "/run/fardb-cli-invocation"
    docker = Mock(side_effect=[Mock(stdout=b""), Mock(stdout=b""), Mock(stdout=b"0\n"), Mock(stdout=metadata)])
    monkeypatch.setattr(guard, "_docker_command", docker)
    path = "/run/fardb-cli-invocation/cli-ABC123"
    if metadata == b"700:0\n":
        runner._validate_private_directory(path)
    else:
        with pytest.raises(guard.DisposableTargetError, match="permissions or owner"):
            runner._validate_private_directory(path)


def test_cli_setup_failure_cleans_only_a_validated_private_directory(monkeypatch) -> None:
    """Failed binary preparation removes the adopted child then its empty parent."""
    runner = _private_runner(monkeypatch)
    path = "/run/fardb-cli-invocation/cli-ABC123"
    validated = Mock()
    monkeypatch.setattr(runner, "_validate_private_directory", validated)
    docker = Mock(return_value=Mock(stdout=(path + "\n").encode()))
    monkeypatch.setattr(guard, "_docker_command", docker)
    monkeypatch.setattr(runner, "_prepare_cli", Mock(side_effect=RuntimeError("incompatible")))
    with pytest.raises(RuntimeError, match="incompatible"):
        runner.__enter__()
    assert runner.directory is None
    assert runner.private_parent is None
    assert validated.call_count == 2
    assert docker.call_args_list[-2].args[0] == ["docker", "exec", "a" * 64, "rm", "-rf", "--", path]
    assert docker.call_args.args[0] == ["docker", "exec", "a" * 64, "rmdir", "--", "/run/fardb-cli-invocation"]


@pytest.mark.parametrize("metadata", [b"777:0:1:2", b"700:99:1:2", b"700:0:1:3"])
def test_private_parent_replacement_or_unsafe_ownership_prevents_cleanup(monkeypatch, metadata) -> None:
    """Cleanup cannot adopt a changed parent even when its pathname matches."""
    runner = object.__new__(guard.ContainerCliRunner)
    runner.cli = "docker"
    runner.record = {"id": "a" * 64}
    runner.private_parent = "/run/fardb-cli-invocation"
    runner.parent_identity = "700:0:1:2"
    runner.directory = None
    monkeypatch.setattr(runner, "validate", Mock())
    monkeypatch.setattr(guard, "invocation_id", lambda: "invocation")
    docker = Mock(side_effect=[Mock(stdout=b""), Mock(stdout=b""), Mock(stdout=b"0"), Mock(stdout=metadata)])
    monkeypatch.setattr(guard, "_docker_command", docker)
    with pytest.raises(guard.DisposableTargetError):
        runner.__exit__()
    assert all("rmdir" not in call.args[0] and "rm" not in call.args[0] for call in docker.call_args_list)


@pytest.mark.parametrize("configured", [False, True])
def test_shell_entrypoint_uses_python3_without_python_alias(tmp_path, monkeypatch, configured) -> None:
    """Resolve the explicit interpreter or python3 before launching any Docker work."""
    import os
    import subprocess
    from pathlib import Path

    binary = tmp_path / ("configured-python" if configured else "python3")
    binary.write_text('#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\nprintf "%s\\n" "$@" > "$ARGV_FILE"\n')
    binary.chmod(0o700)
    (tmp_path / "dirname").symlink_to("/usr/bin/dirname")
    args = tmp_path / "args"
    env = {**os.environ, "PATH": str(tmp_path), "ARGV_FILE": str(args)}
    env.pop("PG_CONFIG", None)
    env.pop("FARDB_PYTHON", None)
    if configured:
        env["FARDB_PYTHON"] = str(binary)
    script = Path(__file__).parents[2] / "scripts/run_ephemeral_postgres_integration.sh"
    result = subprocess.run(["/bin/bash", str(script), "selected-test"], env=env, capture_output=True, check=False)
    assert result.returncode == 0
    assert args.read_text().splitlines()[-1] == "selected-test"
    env["FARDB_PYTHON"] = str(tmp_path / "missing")
    args.unlink()
    result = subprocess.run(["/bin/bash", str(script)], env=env, capture_output=True, check=False)
    assert result.returncode == 2
    assert not args.exists()


def test_pytest_subprocess_uses_the_current_interpreter(monkeypatch) -> None:
    """A PATH alias cannot replace the configured harness interpreter."""
    import subprocess
    import sys

    run = Mock(return_value=Mock(returncode=17))
    monkeypatch.setattr(subprocess, "run", run)
    output = Mock()
    assert guard._run_pytest(["selected-test", "-q"], output) == 17
    run.assert_called_once_with(
        [sys.executable, "-m", "pytest", "selected-test", "-q"], stdout=output, stderr=subprocess.STDOUT, check=False
    )


def test_shell_rejects_non_python3_interpreter_before_launch(tmp_path) -> None:
    """A configured executable that fails the Python 3 probe cannot launch tests."""
    import os
    import subprocess
    from pathlib import Path

    binary = tmp_path / "not-python3"
    binary.write_text("#!/bin/sh\nexit 1\n")
    binary.chmod(0o700)
    env = {**os.environ, "FARDB_PYTHON": str(binary)}
    env.pop("PG_CONFIG", None)
    script = Path(__file__).parents[2] / "scripts/run_ephemeral_postgres_integration.sh"
    result = subprocess.run(["/bin/bash", str(script)], env=env, capture_output=True, check=False)
    assert result.returncode == 2
    assert b"must be Python 3" in result.stderr


@pytest.mark.parametrize(
    "statement",
    [
        "COMMENT ON ROLE protected IS 'changed'",
        "SECURITY LABEL ON ROLE protected IS 'changed'",
        "SECURITY LABEL FOR provider ON ROLE protected IS 'changed'",
        "SECURITY LABEL FOR \"quoted provider\" ON ROLE protected IS 'changed'",
        "REASSIGN OWNED BY protected TO test",
        "DROP OWNED BY protected",
        "DROP OWNED BY protected RESTRICT",
        "DROP OWNED BY absent, protected CASCADE",
    ],
)
@pytest.mark.parametrize(
    "variant",
    [
        "plain",
        "whitespace",
        "leading_comment",
        "inline_comment",
        "leading_line",
        "inline_line",
        "stacked",
        "trailing_stacked",
    ],
)
def test_role_metadata_and_owned_object_mutations_never_reach_driver(statement, variant) -> None:
    """Every unsupported family and separator variant fails before driver execution."""
    if variant == "whitespace":
        statement = " \n\t" + statement.replace(" ", "\n\t") + ";\n"
    elif variant == "leading_comment":
        statement = "/* prefix */ " + statement
    elif variant == "inline_comment":
        statement = statement.replace(" ", " /* separator */ ", 1)
    elif variant == "leading_line":
        statement = "-- prefix\n" + statement
    elif variant == "inline_line":
        statement = statement.replace(" ", " -- separator\n ", 1)
    elif variant == "stacked":
        statement = "SELECT 1; " + statement
    elif variant == "trailing_stacked":
        statement += "; SELECT 1"
    cursor = MagicMock()
    cursor.mogrify.return_value = statement.encode()
    with pytest.raises(guard.DisposableTargetError):
        guard.OwnedRoleCursor.execute(cursor, statement)
    cursor.connection.cursor.assert_not_called()
    cursor._execute_driver.assert_not_called()


def test_only_exact_reviewed_bootstrap_bypasses_ad_hoc_ddl_parser() -> None:
    """Preserve the attested bootstrap path without accepting arbitrary DO blocks."""
    from pathlib import Path

    bootstrap = Path(__file__).parents[2] / "scripts/bootstrap_database_capability_roles.sql"
    text = bootstrap.read_text(encoding="utf-8")
    assert guard._parse_role_ddl(text) is None
    with pytest.raises(guard.DisposableTargetError):
        guard._parse_role_ddl(text + "\nDROP ROLE protected")
    assert guard._parse_role_ddl("SELECT 'DROP OWNED BY protected'") is None


@pytest.mark.parametrize("version, allowed", [((3, 9), False), ((3, 10), True), ((3, 14), True), ((4, 0), False)])
def test_shell_python_minimum_rejected_before_harness_or_docker(tmp_path, version, allowed) -> None:
    """Run the real shell probe with simulated versions before any harness invocation."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    interpreter = tmp_path / "configured-python"
    args = tmp_path / "harness-args"
    interpreter.write_text(
        f"#!{sys.executable}\nimport os,sys\n"
        f"sys.version_info = {version!r}\n"
        "if sys.argv[1] == '-c':\n    exec(sys.argv[2])\n"
        "else:\n    open(os.environ['HARNESS_ARGS'], 'w').write(' '.join(sys.argv[1:]))\n"
    )
    interpreter.chmod(0o700)
    env = {**os.environ, "FARDB_PYTHON": str(interpreter), "HARNESS_ARGS": str(args)}
    env.pop("PG_CONFIG", None)
    script = Path(__file__).parents[2] / "scripts/run_ephemeral_postgres_integration.sh"
    result = subprocess.run(["/bin/bash", str(script), "selected-test"], env=env, capture_output=True, check=False)
    if allowed:
        assert result.returncode == 0
        assert args.read_text().endswith("selected-test")
    else:
        assert result.returncode == 2
        assert not args.exists()
        assert b"Python 3.10 or newer" in result.stderr


@pytest.mark.parametrize("name", ["_database_host", "_validate_loopback_target"])
def test_ledger_invalid_url_constant_preserves_message_and_cause(name) -> None:
    """Constant extraction retains the existing public error and exception chaining."""
    from scripts import postgresql_ledger as ledger

    check = getattr(ledger, name)
    with pytest.raises(ledger.HostedWriteBarrierError) as error:
        check("postgresql://[")
    assert str(error.value) == "database URL is invalid"
    assert isinstance(error.value.__cause__, ValueError)


@pytest.mark.parametrize("kwargs", [{"unexpected": 1}, {"parameters": (1,)}, {"vars": (1,)}])
def test_cursor_adapter_rejects_unknown_or_duplicate_parameters_before_driver(kwargs) -> None:
    """Invalid Python call forms cannot reach role parsing or driver execution."""
    cursor = Mock()
    with pytest.raises(TypeError):
        guard.OwnedRoleCursor.execute(cursor, "SELECT 1", None, **kwargs)
    cursor.mogrify.assert_not_called()
    cursor._execute_driver.assert_not_called()


@pytest.mark.parametrize("keyword", [False, True])
def test_cursor_adapter_preserves_psycopg_parameter_calls(keyword) -> None:
    """Positional and vars keyword arguments deliver identical guarded parameters."""
    cursor = Mock()
    cursor.mogrify.return_value = b"SELECT 1"
    parameters = (1,)
    if keyword:
        guard.OwnedRoleCursor.execute(cursor, "SELECT %s", vars=parameters)
    else:
        guard.OwnedRoleCursor.execute(cursor, "SELECT %s", parameters)
    cursor._execute_driver.assert_called_once_with("SELECT %s", parameters)


def test_owned_parent_creation_refuses_existing_path_without_adoption(monkeypatch) -> None:
    """A colliding parent is never reused or removed."""
    runner = _private_runner(monkeypatch)
    docker = Mock(side_effect=guard.DisposableTargetError("already exists"))
    monkeypatch.setattr(guard, "_docker_command", docker)
    with pytest.raises(guard.DisposableTargetError, match="already exists"):
        runner.__enter__()
    runner.__exit__()
    assert runner.private_parent is None
    assert docker.call_count == 1


@pytest.mark.parametrize("fail_first", [False, True])
def test_role_allocation_publishes_only_after_success_and_rejects_other_invocations(monkeypatch, fail_first) -> None:
    """Allocation failure is retryable; completed state belongs to exactly one invocation."""
    from contextlib import nullcontext

    from tests.integration import test_runtime_authority_postgres as authority

    holder = authority._RoleAllocation()
    invocation = ["first"]
    monkeypatch.setattr(guard, "invocation_id", lambda: invocation[0])
    monkeypatch.setattr(authority, "invocation_id", lambda: invocation[0])
    monkeypatch.setattr(authority, "attested_connection", lambda _url: nullcontext(Mock()))
    allocation = Mock(return_value={"role": "owned"})
    monkeypatch.setattr(authority, "allocate_role_names", allocation)
    if fail_first:
        allocation.side_effect = RuntimeError("allocation failed")
        with pytest.raises(RuntimeError, match="allocation failed"):
            holder.initialize("target")
        assert holder.names == {}
        assert holder.invocation is None
        allocation.side_effect = None
    holder.initialize("target")
    calls = allocation.call_count
    holder.initialize("target")
    assert allocation.call_count == calls
    assert holder.names == {"role": "owned"}
    invocation[0] = "second"
    with pytest.raises(guard.DisposableTargetError, match="different invocation"):
        holder.initialize("target")
    assert allocation.call_count == calls


def test_role_allocation_lock_publishes_once_under_concurrent_access(monkeypatch) -> None:
    """Concurrent users cannot allocate or publish competing name sets."""
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import nullcontext

    from tests.integration import test_runtime_authority_postgres as authority

    holder = authority._RoleAllocation()
    monkeypatch.setattr(guard, "invocation_id", lambda: "first")
    monkeypatch.setattr(authority, "invocation_id", lambda: "first")
    monkeypatch.setattr(authority, "attested_connection", lambda _url: nullcontext(Mock()))
    allocation = Mock(return_value={"role": "owned"})
    monkeypatch.setattr(authority, "allocate_role_names", allocation)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(holder.initialize, ["target"] * 8))
    allocation.assert_called_once()
    assert holder.names == {"role": "owned"}


@pytest.mark.parametrize("cleanup_failed", [False, True])
def test_harness_finalization_cleans_before_inventory_and_records_failure(
    monkeypatch, tmp_path, cleanup_failed
) -> None:
    """Cleanup failures remain failures even when final inventory appears preserved."""
    events = []

    def cleanup(*_args):
        """Record cleanup ordering and optionally model an ownership rejection."""
        events.append("cleanup")
        if cleanup_failed:
            raise guard.DisposableTargetError("cleanup ownership rejected")

    def docker(command):
        """Record inventory only after cleanup has been attempted."""
        events.append("inventory")
        return Mock(stdout=b"existing\n")

    monkeypatch.setattr(guard, "_cleanup_local_container", cleanup)
    monkeypatch.setattr(guard, "_docker_command", docker)
    report: dict[str, object] = {}
    result = guard._finalize_harness(
        "docker", "owned", "volume", "invocation", {"existing"}, {"existing"}, report, tmp_path, 0
    )
    assert events == ["cleanup", "inventory", "inventory"]
    assert result == (1 if cleanup_failed else 0)
    assert report["existing_containers_preserved"] is True
    assert report["existing_volumes_preserved"] is True
    if cleanup_failed:
        assert report["cleanup_failure"] == "cleanup ownership rejected"
    assert (tmp_path / "report.json").is_file()


def test_harness_evidence_write_failure_propagates_after_owned_cleanup(monkeypatch, tmp_path) -> None:
    """Missing evidence cannot be reported as successful preservation."""
    cleanup = Mock()
    monkeypatch.setattr(guard, "_cleanup_local_container", cleanup)
    monkeypatch.setattr(guard, "_docker_command", Mock(return_value=Mock(stdout=b"existing\n")))
    with pytest.raises(FileNotFoundError):
        guard._finalize_harness(
            "docker", "owned", "volume", "invocation", {"existing"}, {"existing"}, {}, tmp_path / "missing", 0
        )
    cleanup.assert_called_once()


def test_readiness_failure_still_cleans_owned_resources_and_reports_preservation(monkeypatch, tmp_path) -> None:
    """A bounded startup failure follows the same cleanup and preservation path."""
    import tempfile

    inventory = [Mock(stdout=b"existing\n"), Mock(stdout=b"oldvolume\n"), Mock(stdout=b"started\n")]
    monkeypatch.setattr(tempfile, "mkdtemp", lambda **_kwargs: str(tmp_path))
    monkeypatch.setattr(guard, "_docker_command", Mock(side_effect=inventory))
    monkeypatch.setattr(guard, "_create_harness_container", lambda *_args: "owned")
    monkeypatch.setattr(
        guard,
        "_fresh_storage_volume",
        lambda *_args: ("newvolume", {"Config": {"Labels": {"fardb.test.invocation": "invocation"}}}),
    )
    monkeypatch.setattr("uuid.uuid4", lambda: Mock(hex="invocation"))
    monkeypatch.setattr(
        guard, "_wait_for_owned_postgres", Mock(side_effect=guard.DisposableTargetError("readiness timeout"))
    )
    finalize = Mock(return_value=1)
    monkeypatch.setattr(guard, "_finalize_harness", finalize)
    assert guard._run_locked_container_harness("docker", 16, []) == 1
    args = finalize.call_args.args
    assert args[1:4] == ("owned", "newvolume", "invocation")
    assert args[4:6] == ({"existing"}, {"oldvolume"})
    assert args[6]["failure"] == "readiness timeout"


def test_cursor_adapter_rejects_excess_positional_parameters_before_driver() -> None:
    """The adapter preserves the original two-argument interface boundary."""
    cursor = Mock()
    with pytest.raises(TypeError):
        guard.OwnedRoleCursor.execute(cursor, "SELECT 1", None, None)
    cursor.mogrify.assert_not_called()
    cursor._execute_driver.assert_not_called()


@pytest.mark.parametrize("autocommit", [True, False])
def test_bootstrap_mapping_and_block_share_transaction(autocommit: bool, monkeypatch) -> None:
    """Autocommit callers explicitly retain the mapping until bootstrap completes."""
    from scripts import bootstrap_database_capability_roles as bootstrap

    connection = MagicMock()
    connection.autocommit = autocommit
    cursor = MagicMock()
    cursor.connection = connection
    mapping = {name: ["test_db"] for name in guard._CANONICAL_CAPABILITY_ROLES}
    monkeypatch.setattr(bootstrap, "_lock_coordinator_catalogs", Mock())
    monkeypatch.setattr(bootstrap, "_cluster_and_database_identity", Mock(return_value=("123", 42, "test_db")))
    monkeypatch.setattr(bootstrap, "_coordinator_targets", Mock(return_value={"test_db": (42, "test_db")}))
    monkeypatch.setattr(
        bootstrap,
        "_preflight_targets",
        Mock(
            return_value=(
                {"test_db": connection},
                {"test_db": dict.fromkeys(bootstrap._ROLE_NAMES)},
            )
        ),
    )
    monkeypatch.setattr(bootstrap, "_verify_target_schema_acl", Mock())
    monkeypatch.setattr(
        bootstrap,
        "_apply_bootstrap",
        lambda active_cursor, _mapping, sql_text: (
            active_cursor.execute("SELECT set_config('fardb.bootstrap_targets', %s, true)", ("{}",)),
            active_cursor.execute(sql_text),
        ),
    )
    guard.execute_capability_bootstrap(cursor, mapping)
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    if autocommit:
        assert statements[0] == "BEGIN"
        assert statements[-1] == "COMMIT"
    else:
        connection.commit.assert_called_once()
    setup = [index for index, statement in enumerate(statements) if "set_config" in statement]
    blocks = [index for index, statement in enumerate(statements) if "DO $fardb$" in statement]
    assert len(setup) == 1
    assert len(blocks) == 1
    assert setup[0] < blocks[0]


def test_autocommit_bootstrap_failure_rolls_back(monkeypatch) -> None:
    """A bootstrap failure rolls back the explicit transaction instead of committing."""
    from scripts import bootstrap_database_capability_roles as bootstrap

    connection = MagicMock()
    connection.autocommit = True
    cursor = MagicMock()
    cursor.connection = connection

    mapping = {name: ["test_db"] for name in guard._CANONICAL_CAPABILITY_ROLES}
    monkeypatch.setattr(bootstrap, "_lock_coordinator_catalogs", Mock())
    monkeypatch.setattr(bootstrap, "_cluster_and_database_identity", Mock(return_value=("123", 42, "test_db")))
    monkeypatch.setattr(bootstrap, "_coordinator_targets", Mock(return_value={"test_db": (42, "test_db")}))
    monkeypatch.setattr(
        bootstrap,
        "_preflight_targets",
        Mock(
            return_value=(
                {"test_db": connection},
                {"test_db": dict.fromkeys(bootstrap._ROLE_NAMES)},
            )
        ),
    )

    def fail_after_mapping(active_cursor, _mapping, _sql_text):
        """Fail after the transaction-local target mapping has been set."""
        active_cursor.execute("SELECT set_config('fardb.bootstrap_targets', %s, true)", ("{}",))
        raise RuntimeError("bootstrap failed")

    monkeypatch.setattr(bootstrap, "_apply_bootstrap", fail_after_mapping)
    with pytest.raises(RuntimeError, match="bootstrap failed"):
        guard.execute_capability_bootstrap(cursor, mapping)
    assert cursor.execute.call_args_list[-1].args == ("ROLLBACK",)
    assert not any(call.args[0] == "COMMIT" for call in cursor.execute.call_args_list)
