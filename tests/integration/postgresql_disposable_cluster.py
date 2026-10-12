"""Guards and ownership helpers for explicitly disposable PostgreSQL tests."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

import psycopg2
from psycopg2.extensions import cursor as PsycopgCursor

ENABLE_ENVIRONMENTS = (
    "FARDB_EPHEMERAL_POSTGRES_LEDGER_TESTS",
    "FARDB_EPHEMERAL_POSTGRES_AUTHORITY_TESTS",
)
URL_ENV = "FARDB_EPHEMERAL_POSTGRES_URL"
SYSTEM_IDENTIFIER_ENV = "FARDB_EPHEMERAL_POSTGRES_SYSTEM_IDENTIFIER"
INVOCATION_ID_ENV = "FARDB_EPHEMERAL_POSTGRES_INVOCATION_ID"
_ROLE_PREFIX = "fdbt_"
_CANONICAL_CAPABILITY_ROLES = {
    "fardb_runtime_auth",
    "fardb_runtime_graph",
    "fardb_runtime_coordination",
}
_CANONICAL_TEST_LOGIN_ROLES = {"fardb_login_auth", "fardb_login_graph", "fardb_login_coordination"}
_ROLE_DDL = re.compile(r"^\s*(CREATE ROLE|DROP ROLE(?: IF EXISTS)?|DROP OWNED BY)\s+(.+?)\s*;?\s*$", re.I | re.S)
_QUOTED_IDENTIFIER = re.compile(r'^"((?:[^"]|"")+)"')
_owned_roles: dict[str, int] = {}


class DisposableTargetError(RuntimeError):
    """Raised when a test target is not the harness-attested disposable cluster."""


def _enabled() -> bool:
    return any(os.environ.get(name) == "1" for name in ENABLE_ENVIRONMENTS)


def _loopback_host(value: str, *, allow_localhost: bool = True) -> bool:
    from ipaddress import ip_address

    value = value.strip().lower().rstrip(".")
    if value == "localhost":
        return allow_localhost
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    try:
        return ip_address(value).is_loopback
    except ValueError:
        return False


def _numeric_loopback_address(value: str) -> bool:
    """Reject hostnames, scopes and malformed numeric hostaddr values."""
    from scripts.postgresql_ledger import _is_numeric_loopback_address

    return _is_numeric_loopback_address(value)


def validate_effective_loopback_url(database_url: str) -> None:
    """Reject any URI or libpq override that can route away from loopback."""
    try:
        parsed = urlsplit(database_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        uri_host = parsed.hostname
    except ValueError as exc:
        raise DisposableTargetError("disposable PostgreSQL URL is invalid") from exc
    hosts = [uri_host, *query.get("host", [])]
    addresses = query.get("hostaddr", [])
    if not hosts or not all(host and _loopback_host(host) for host in hosts):
        raise DisposableTargetError("disposable PostgreSQL URI host must be loopback")
    if not all(address and _numeric_loopback_address(address) for address in addresses):
        raise DisposableTargetError("disposable PostgreSQL hostaddr override must be a loopback address")
    if "disable" in query.get("sslmode", []) and not _enabled():
        raise DisposableTargetError("sslmode=disable requires explicit disposable-test opt-in")


def expected_system_identifier() -> str:
    """Read the independent cluster identifier supplied by the harness."""
    if not _enabled():
        raise DisposableTargetError("explicit disposable PostgreSQL test opt-in is required")
    value = os.environ.get(SYSTEM_IDENTIFIER_ENV, "")
    if not value.isdigit():
        raise DisposableTargetError(f"{SYSTEM_IDENTIFIER_ENV} must be supplied by the harness")
    return value


def attest_connection(connection, database_url: str, expected_identifier: str | None = None) -> None:
    """Attest this live connection before it is used for any fixture mutation."""
    validate_effective_loopback_url(database_url)
    _read_harness_record()
    expected = expected_identifier or expected_system_identifier()
    if expected != expected_system_identifier():
        raise DisposableTargetError("requested system identifier differs from harness attestation")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT system_identifier::text FROM pg_control_system()")
            row = cursor.fetchone()
    except Exception as exc:  # psycopg2 reports privilege and unsupported-server failures here
        raise DisposableTargetError("cannot attest PostgreSQL system identifier on mutation connection") from exc
    if not row or str(row[0]) != expected:
        raise DisposableTargetError("PostgreSQL system identifier does not match the harness-attested cluster")
    connection.rollback()


def connect_attested(database_url: str):
    """Open and attest the exact connection that callers will use for mutations."""
    expected = expected_system_identifier()
    validate_effective_loopback_url(database_url)
    _read_harness_record()
    connection = psycopg2.connect(database_url)
    try:
        attest_connection(connection, database_url, expected)
    except Exception:
        connection.close()
        raise
    return connection


def connect_owned_attested(database_url: str):
    """Open an attested operator connection with OID-fenced role DDL tracking."""
    connection = connect_attested(database_url)
    connection.cursor_factory = OwnedRoleCursor
    return connection


@contextmanager
def attested_connection(database_url: str) -> Iterator:
    """Yield a connection after same-session identity and target validation."""
    connection = connect_attested(database_url)
    try:
        yield connection
    finally:
        connection.close()


def invocation_id() -> str:
    """Return a validated harness invocation identifier for test-owned role names."""
    value = os.environ.get(INVOCATION_ID_ENV, "")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{8,48}", value):
        raise DisposableTargetError(f"{INVOCATION_ID_ENV} must be supplied by the harness")
    return value.lower().replace("-", "")[:20]


def allocate_role_names(connection, names: Mapping[str, str]) -> dict[str, str]:
    """Allocate collision-free invocation-prefixed names without touching collisions."""
    prefix = f"{_ROLE_PREFIX}{invocation_id()}_"
    allocated: dict[str, str] = {}
    for key, logical_name in names.items():
        stem = re.sub(r"[^a-zA-Z0-9_]", "_", logical_name.lower()).strip("_") or "role"
        suffix = hashlib.sha256(f"{key}:{logical_name}".encode()).hexdigest()[:6]
        base = f"{prefix}{stem[:30]}_{suffix}"
        candidate = base[:63]
        counter = 0
        while True:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (candidate,))
                collision = cursor.fetchone() is not None
            if not collision:
                allocated[key] = candidate
                break
            counter += 1
            candidate = f"{base[:54]}_{counter:08x}"[:63]
    return allocated


def role_name_candidate(key: str, logical_name: str) -> str:
    """Return the first deterministic name considered by the collision allocator."""
    prefix = f"{_ROLE_PREFIX}{invocation_id()}_"
    stem = re.sub(r"[^a-zA-Z0-9_]", "_", logical_name.lower()).strip("_") or "role"
    suffix = hashlib.sha256(f"{key}:{logical_name}".encode()).hexdigest()[:6]
    return f"{prefix}{stem[:30]}_{suffix}"[:63]


@dataclass(frozen=True)
class OwnedRole:
    """Role identity created by this pytest process."""

    name: str
    oid: int


def record_created_role(connection, name: str, *, canonical_test_role: bool = False) -> OwnedRole:
    """Record a role only after CREATE ROLE succeeds in the current invocation."""
    invocation_owned = name.startswith(f"{_ROLE_PREFIX}{invocation_id()}_")
    canonical_role = name in _CANONICAL_CAPABILITY_ROLES | _CANONICAL_TEST_LOGIN_ROLES
    if not invocation_owned and not (canonical_test_role and canonical_role):
        raise DisposableTargetError("refusing to record a role outside this invocation namespace")
    with connection.cursor() as cursor:
        cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (name,))
        row = cursor.fetchone()
    if row is None:
        raise DisposableTargetError("new role is missing after successful creation")
    role = OwnedRole(name, int(row[0]))
    _owned_roles[name] = role.oid
    return role


def owned_role_oid(name: str) -> int | None:
    """Return the recorded OID for an invocation-owned role, if any."""
    return _owned_roles.get(name)


def verify_owned_role(connection, role: OwnedRole) -> bool:
    """Check the current name still refers to the exact role created by this run."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (role.name,))
        row = cursor.fetchone()
    return row is not None and int(row[0]) == role.oid and _owned_roles.get(role.name) == role.oid


def drop_owned_role(connection, role: OwnedRole) -> bool:
    """Drop only a role whose current catalog OID still matches its ownership record."""
    if not verify_owned_role(connection, role):
        return False
    from psycopg2 import sql

    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role.name)))
    _owned_roles.pop(role.name, None)
    return True


def create_attested_engine(database_url: str, **kwargs):
    """Create an operator SQLAlchemy engine that attests each physical connection."""
    from sqlalchemy import create_engine, event

    engine = create_engine(database_url, **kwargs)

    @event.listens_for(engine, "connect")
    def _attest(dbapi_connection, _connection_record) -> None:
        attest_connection(dbapi_connection, database_url)

    return engine


def _ddl_role_name(rendered_sql: str) -> str | None:
    match = _ROLE_DDL.match(rendered_sql)
    if not match:
        return None
    identifier = _QUOTED_IDENTIFIER.match(match.group(2).strip())
    if identifier:
        return identifier.group(1).replace('""', '"')
    bare = re.match(r"([a-zA-Z_][a-zA-Z0-9_$]*)", match.group(2).strip())
    return bare.group(1) if bare else None


class OwnedRoleCursor(PsycopgCursor):
    """Cursor guard that records created roles and fences role cleanup by OID."""

    def execute(self, query, vars=None):
        rendered = self.mogrify(query, vars).decode("utf-8", errors="replace")
        match = _ROLE_DDL.match(rendered)
        role_name = _ddl_role_name(rendered)
        if match and match.group(1).upper().startswith(("DROP ROLE", "DROP OWNED")):
            oid = owned_role_oid(role_name or "")
            with self.connection.cursor(cursor_factory=PsycopgCursor) as check:
                check.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (role_name,))
                row = check.fetchone()
            if row is None and match.group(1).upper().startswith("DROP ROLE IF EXISTS"):
                pass
            elif oid is None:
                raise DisposableTargetError("refusing cleanup of a role not created by this invocation")
            elif row is None or int(row[0]) != oid:
                raise DisposableTargetError("refusing cleanup after role name/OID ownership changed")
        result = super().execute(query, vars)
        if match and match.group(1).upper() == "CREATE ROLE" and role_name:
            record_created_role(
                self.connection,
                role_name,
                canonical_test_role=role_name in _CANONICAL_CAPABILITY_ROLES | _CANONICAL_TEST_LOGIN_ROLES,
            )
        return result


CONTAINER_RECORD_ENV = "FARDB_EPHEMERAL_POSTGRES_CONTAINER_RECORD"


def _read_harness_record() -> dict:
    """Reject native/unowned test execution before any mutation connection opens."""
    import json
    from pathlib import Path

    path = os.environ.get(CONTAINER_RECORD_ENV)
    if not path:
        raise DisposableTargetError("independent harness container ownership record required")
    record = json.loads(Path(path).read_text())
    if record.get("invocation") != os.environ.get(INVOCATION_ID_ENV):
        raise DisposableTargetError("container record belongs to a different invocation")
    if record.get("system_identifier") != expected_system_identifier():
        raise DisposableTargetError("container record differs from independent harness attestation")
    if record.get("owner") not in ("local-created", "github-job"):
        raise DisposableTargetError("container ownership is unverified")
    return record


def _docker_command(command: list[str], *, input_bytes: bytes | None = None, timeout: int = 30):
    """Run a fixed Docker argv without publishing captured credentials."""
    import subprocess

    try:
        result = subprocess.run(command, input=input_bytes, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise DisposableTargetError("owned Docker transport failed") from None
    if result.returncode:
        raise DisposableTargetError("owned Docker operation failed")
    return result


def _docker_cli() -> str:
    """Find a working Docker interface without changing saved contexts."""
    import shutil

    supplied = os.environ.get("FARDB_DOCKER_CLI")
    candidates = [supplied] if supplied else [shutil.which("docker"), shutil.which("docker.exe")]
    for candidate in candidates:
        if candidate:
            try:
                _docker_command([candidate, "info", "--format", "{{.ID}}"])
                return candidate
            except (DisposableTargetError, OSError):
                continue
    raise DisposableTargetError("no working Docker interface for an owned container")


def _inspect_container(cli: str, container_id: str) -> dict:
    """Inspect exactly one full immutable container identity."""
    import json

    if not re.fullmatch(r"[0-9a-f]{64}", container_id):
        raise DisposableTargetError("full container ID required")
    items = json.loads(_docker_command([cli, "inspect", container_id]).stdout)
    if len(items) != 1 or items[0]["Id"] != container_id:
        raise DisposableTargetError("ambiguous container identity")
    return items[0]


def _container_identity(container: dict, major: int) -> dict:
    """Reject ambiguous storage and expose only non-secret ownership fields."""
    host = container["HostConfig"]
    env = dict(item.split("=", 1) for item in container["Config"]["Env"])
    mounts = container["Mounts"]
    ports = container["NetworkSettings"]["Ports"].get("5432/tcp")
    valid = (
        container["State"]["Running"]
        and container["Config"]["Image"] == f"postgres:{major}"
        and not host.get("Binds")
        and not host.get("Mounts")
        and host["RestartPolicy"]["Name"] == "no"
        and env.get("POSTGRES_USER") == "test"
        and env.get("POSTGRES_DB") == "test_db"
        and len(mounts) == 1
        and ports
        and len(ports) == 1
        and ports[0]["HostIp"] == "127.0.0.1"
    )
    if not valid:
        raise DisposableTargetError("container ownership, image, mounts or loopback binding is invalid")
    mount = mounts[0]
    if (
        mount["Type"] != "volume"
        or mount["Destination"] != env.get("PGDATA")
        or mount["Destination"] not in container["Config"].get("Volumes", {})
        or not re.fullmatch(r"[0-9a-f]{64}", mount.get("Name", ""))
        or not mount["Source"].endswith("/volumes/" + mount["Name"] + "/_data")
    ):
        raise DisposableTargetError("container data storage is not an owned anonymous volume")
    return {
        "id": container["Id"],
        "image": container["Config"]["Image"],
        "image_id": container["Image"],
        "started_at": container["State"]["StartedAt"],
        "pid": container["State"]["Pid"],
        "pgdata": env["PGDATA"],
        "volume": mount["Name"],
        "volume_source": mount["Source"],
        "port": int(ports[0]["HostPort"]),
        "major": major,
    }


def _internal_cli_url(database_url: str, record: dict) -> str:
    """Bind the selected host database to the verified container-local endpoint."""
    from urllib.parse import urlencode, urlunsplit

    validate_effective_loopback_url(database_url)
    parsed = urlsplit(database_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (
        parsed.scheme not in ("postgresql", "postgres")
        or parsed.port != record["port"]
        or parsed.hostname not in ("127.0.0.1", "localhost")
        or parsed.username != "test"
        or parsed.password != "test"
        or not re.fullmatch(r"/[a-zA-Z0-9_]+", parsed.path)
        or parsed.fragment
        or set(query) - {"host", "hostaddr", "sslmode"}
        or query.get("sslmode") != ["disable"]
        or any(value not in ("127.0.0.1", "localhost") for value in query.get("host", []))
        or any(value != "127.0.0.1" for value in query.get("hostaddr", []))
    ):
        raise DisposableTargetError("CLI target does not match the harness-owned published endpoint")
    return urlunsplit(("postgresql", "test:test@127.0.0.1:5432", parsed.path, urlencode({"sslmode": "disable"}), ""))


class ContainerCliRunner:
    """Execute pinned CLI mutations in the exact owned PostgreSQL container namespace."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.record = _read_harness_record()
        self.cli = self.record["docker_cli"]
        _internal_cli_url(database_url, self.record)
        self.validate()
        self.directory: str | None = None
        self.digests: dict[str, str] = {}

    def validate(self) -> None:
        """Check exact storage, process lifecycle and independent cluster identity."""
        current = _container_identity(_inspect_container(self.cli, self.record["id"]), self.record["major"])
        if any(current[key] != self.record[key] for key in current):
            raise DisposableTargetError("owned container restarted or changed identity/storage")
        control = _docker_command(
            [self.cli, "exec", self.record["id"], "pg_controldata", self.record["pgdata"]]
        ).stdout.decode()
        identifier = re.search(r"Database system identifier:\s*(\d+)", control)
        if not identifier or identifier.group(1) != self.record["system_identifier"]:
            raise DisposableTargetError("owned container cluster identity changed")

    def __enter__(self):
        """Prepare invocation-private CLI files inside the verified container."""
        import shutil
        from pathlib import Path
        from uuid import uuid4

        self.validate()
        self.directory = f"/tmp/fardb-cli-{invocation_id()}-{uuid4().hex}"
        _docker_command([self.cli, "exec", self.record["id"], "mkdir", "-m", "700", self.directory])
        executable = shutil.which("supabase")
        if not executable:
            raise DisposableTargetError("pinned Supabase executable unavailable")
        self._copy_files({"supabase": Path(executable).resolve()})
        result = self._execute([self.directory + "/supabase", "--version"], 15)
        if result.returncode or result.stdout.strip() != "2.114.0":
            raise DisposableTargetError("pinned CLI is incompatible with the container image")
        return self

    def _copy_files(self, files: dict) -> None:
        """Transfer regular validated bytes and reject any container checksum mismatch."""
        import io
        import tarfile

        buffer = io.BytesIO()
        digests = {}
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for name, path in files.items():
                if path.is_symlink() or not path.is_file() or name.startswith("/") or ".." in name.split("/"):
                    raise DisposableTargetError("CLI transfer requires exact regular projection files")
                data = path.read_bytes()
                digests[name] = hashlib.sha256(data).hexdigest()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o700 if name == "supabase" else 0o600
                archive.addfile(info, io.BytesIO(data))
        _docker_command([self.cli, "cp", "-", self.record["id"] + ":" + self.directory], input_bytes=buffer.getvalue())
        self.digests.update(digests)
        self._verify_transferred_bytes()

    def _verify_transferred_bytes(self) -> None:
        """Check that container-local executable and projection bytes remain exact."""
        if self.directory is None:
            raise DisposableTargetError("CLI runner context is not active")
        for name, digest in self.digests.items():
            actual = (
                _docker_command([self.cli, "exec", self.record["id"], "sha256sum", self.directory + "/" + name])
                .stdout.decode()
                .split()[0]
            )
            if actual != digest:
                raise DisposableTargetError("CLI executable or profile transfer checksum mismatch")

    def _execute(self, argv: list[str], timeout: int):
        """Keep CLI cwd/state private and stop only the owned container on timeout."""
        import subprocess

        if self.directory is None:
            raise DisposableTargetError("CLI runner context is not active")
        command = [
            self.cli,
            "exec",
            "--workdir",
            self.directory,
            self.record["id"],
            "env",
            "-i",
            "PATH=/usr/local/bin:/usr/bin:/bin",
            "SUPABASE_TELEMETRY_DISABLED=1",
            "DO_NOT_TRACK=1",
            "HOME=" + self.directory,
            "SUPABASE_HOME=" + self.directory,
            "XDG_CONFIG_HOME=" + self.directory,
            *argv,
        ]
        try:
            result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            _docker_command([self.cli, "stop", "--time", "5", self.record["id"]])
            raise DisposableTargetError("CLI timed out/cancelled; owned container stopped") from None
        return subprocess.CompletedProcess(argv, result.returncode, result.stdout.decode(), result.stderr.decode())

    def __call__(self, command, *, timeout, **_kwargs):
        """Adapt only ledger's fixed version/push commands to container-local execution."""
        from pathlib import Path

        if self.directory is None:
            raise DisposableTargetError("CLI runner context is not active")
        self.validate()
        if tuple(command[1:]) == ("--version",):
            argv = [self.directory + "/supabase", "--version"]
        elif (
            len(command) == 10
            and command[1] == "--workdir"
            and tuple(command[3:9]) == ("--yes", "--output-format", "json", "db", "push", "--db-url")
            and command[9] == self.database_url
        ):
            projection = Path(command[2])
            if any(p.is_symlink() for p in projection.rglob("*")):
                raise DisposableTargetError("symlink in CLI projection")
            files = {"projection/" + str(p.relative_to(projection)): p for p in projection.rglob("*") if p.is_file()}
            self._copy_files(files)
            argv = [
                self.directory + "/supabase",
                "--workdir",
                self.directory + "/projection",
                *command[3:9],
                _internal_cli_url(self.database_url, self.record),
            ]
        else:
            raise DisposableTargetError("unexpected test CLI command or target")
        self._verify_transferred_bytes()
        result = self._execute(argv, timeout)
        self.validate()
        self._verify_transferred_bytes()
        if len(argv) > 2:
            from scripts.postgresql_ledger import _PROJECTION_FORBIDDEN_PATHS

            for relative in _PROJECTION_FORBIDDEN_PATHS:
                _docker_command(
                    [
                        self.cli,
                        "exec",
                        self.record["id"],
                        "test",
                        "!",
                        "-e",
                        self.directory + "/projection/" + str(relative),
                    ]
                )
        return result

    def __exit__(self, *_args):
        """Remove only this runner's private directory in the same live owned container."""
        self.validate()
        _docker_command([self.cli, "exec", self.record["id"], "rm", "-rf", "--", self.directory])


def verify_applied_profile(database_url: str, manifest, profile: str) -> None:
    """Read catalog and exact history through the host-side attested session after CLI writes."""
    from scripts.postgresql_drift import catalog_digest, normalized_managed_catalog

    with attested_connection(database_url) as connection, connection.cursor() as cursor:
        actual = catalog_digest(normalized_managed_catalog(cursor, profile))
        expected = manifest.catalog_digest_for_profile(profile)
        if actual != expected:
            raise DisposableTargetError(f"post-CLI {profile} catalog digest mismatch: {actual} != {expected}")
        cursor.execute("SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version")
        expected_history = [(m.timestamp, m.filename[15:-4]) for m in manifest.migrations_for_profile(profile)]
        if cursor.fetchall() != expected_history:
            raise DisposableTargetError("post-CLI host-side migration history differs from the selected profile")
        evidence = os.environ.get("FARDB_POSTGRES_EVIDENCE_DIR")
        if evidence:
            import json
            from pathlib import Path
            from uuid import uuid4

            Path(evidence, f"catalog-{profile}-{uuid4().hex}.json").write_text(
                json.dumps({"profile": profile, "actual": actual, "expected": expected, "history": expected_history})
            )


def _capture_record(cli: str, container_id: str, major: int, invocation: str, owner: str) -> dict:
    """Capture identity only after independent harness ownership was established."""
    identity = _container_identity(_inspect_container(cli, container_id), major)
    version = _docker_command([cli, "exec", container_id, "postgres", "--version"]).stdout.decode().strip()
    if not re.search(rf"PostgreSQL\) {major}\.", version):
        raise DisposableTargetError("PostgreSQL major does not match the harness version guard")
    control = _docker_command([cli, "exec", container_id, "pg_controldata", identity["pgdata"]]).stdout.decode()
    identifier = re.search(r"Database system identifier:\s*(\d+)", control)
    if not identifier:
        raise DisposableTargetError("cannot read independent container system identifier")
    return {
        **identity,
        "system_identifier": identifier.group(1),
        "docker_cli": cli,
        "invocation": invocation,
        "owner": owner,
        "version": version,
    }


def _cleanup_local_container(
    cli: str, container_id: str, volume: str | None, invocation: str, old_ids: set[str], old_volumes: set[str]
) -> None:
    """Clean only the created identity, including a container that failed to start."""
    if container_id in old_ids:
        raise DisposableTargetError("refusing cleanup of a pre-existing container")
    current = set(_docker_command([cli, "ps", "-aq", "--no-trunc"]).stdout.decode().split())
    if container_id not in current:
        return
    container = _inspect_container(cli, container_id)
    if container["Config"].get("Labels", {}).get("fardb.test.invocation") != invocation:
        raise DisposableTargetError("local cleanup ownership changed")
    owned_mount = any(m.get("Type") == "volume" and m.get("Name") == volume for m in container["Mounts"])
    try:
        _docker_command([cli, "stop", "--time", "5", container_id])
    except DisposableTargetError:
        pass
    current = set(_docker_command([cli, "ps", "-aq", "--no-trunc"]).stdout.decode().split())
    if container_id in current:
        _docker_command([cli, "rm", "--force", container_id])
    remaining = set(_docker_command([cli, "volume", "ls", "-q"]).stdout.decode().split())
    if (
        volume
        and volume not in old_volumes
        and volume in remaining
        and owned_mount
        and re.fullmatch(r"[0-9a-f]{64}", volume)
    ):
        _docker_command([cli, "volume", "rm", volume])


@contextmanager
def _exclusive_daemon_harness_lock(cli: str, major: int) -> Iterator[str]:
    """Reserve one daemon-wide name; unrelated Docker clients remain unrestricted."""
    name = "fardb-postgres-integration-exclusive-lock"
    try:
        result = _docker_command(
            [
                cli,
                "create",
                "--name",
                name,
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/var/lib/postgresql/data",
                "--entrypoint",
                "true",
                f"postgres:{major}",
            ]
        )
    except DisposableTargetError:
        raise DisposableTargetError(
            "cannot acquire exclusive Docker daemon harness lock; another invocation or stale lock may exist"
        ) from None
    lock_id = result.stdout.decode().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", lock_id):
        raise DisposableTargetError("Docker daemon lock returned an invalid ownership ID")
    try:
        yield lock_id
    finally:
        _docker_command([cli, "rm", "--volumes", lock_id])


def run_container_harness(major: int, pytest_args: list[str]) -> int:
    """Serialize local harnesses on their daemon before inventory or test resources."""
    if major not in (15, 16):
        raise DisposableTargetError("this harness supports only PostgreSQL 15 and 16")
    cli = _docker_cli()
    with _exclusive_daemon_harness_lock(cli, major):
        return _run_locked_container_harness(cli, major, pytest_args)


def _run_locked_container_harness(cli: str, major: int, pytest_args: list[str]) -> int:
    """Own fresh anonymous storage, attest both endpoints and clean up only this run."""
    import json
    import subprocess
    import tempfile
    import time
    from pathlib import Path
    from uuid import uuid4

    if major not in (15, 16):
        raise DisposableTargetError("this harness supports only PostgreSQL 15 and 16")
    invocation = uuid4().hex
    evidence = Path(tempfile.mkdtemp(prefix=f"fardb-pg{major}-amended-"))
    old_ids = set(_docker_command([cli, "ps", "-aq", "--no-trunc"]).stdout.decode().split())
    old_volumes = set(_docker_command([cli, "volume", "ls", "-q"]).stdout.decode().split())
    container_id = None
    volume = None
    report: dict[str, Any] = {
        "invocation": invocation,
        "evidence": str(evidence),
        "preservation_boundary": "daemon-exclusive cooperating harnesses; unrelated Docker clients are unrestricted",
    }
    result_code = 1
    try:
        container_id = (
            _docker_command(
                [
                    cli,
                    "create",
                    "--rm",
                    "--name",
                    f"fardb-pr1870-pg{major}-{invocation[:12]}",
                    "--label",
                    "fardb.test.invocation=" + invocation,
                    "-e",
                    "POSTGRES_USER=test",
                    "-e",
                    "POSTGRES_PASSWORD=test",
                    "-e",
                    "POSTGRES_DB=test_db",
                    "-p",
                    "127.0.0.1::5432",
                    f"postgres:{major}",
                ]
            )
            .stdout.decode()
            .strip()
        )
        if container_id in old_ids:
            raise DisposableTargetError("refusing reused container")
        created = _inspect_container(cli, container_id)
        if (
            not created["HostConfig"]["AutoRemove"]
            or created["HostConfig"].get("Binds")
            or created["HostConfig"].get("Mounts")
            or len(created["Mounts"]) != 1
        ):
            raise DisposableTargetError("fresh-container storage setup is ambiguous")
        volume = created["Mounts"][0]["Name"]
        if volume in old_volumes or created["Config"]["Labels"].get("fardb.test.invocation") != invocation:
            raise DisposableTargetError("container storage is not newly owned")
        _docker_command([cli, "start", container_id])
        deadline = time.monotonic() + 45
        while True:
            try:
                _docker_command([cli, "exec", container_id, "pg_isready", "-U", "test", "-d", "test_db"])
                break
            except DisposableTargetError:
                if time.monotonic() > deadline:
                    raise DisposableTargetError("new PostgreSQL container readiness timeout") from None
                time.sleep(1)
        record = _capture_record(cli, container_id, major, invocation, "local-created")
        report.update(record)
        record_path = evidence / "ownership.json"
        record_path.write_text(json.dumps(record, indent=2))
        record_path.chmod(0o600)
        target = f"postgresql://test:test@127.0.0.1:{record['port']}/test_db?sslmode=disable"
        os.environ.update(
            {
                ENABLE_ENVIRONMENTS[0]: "1",
                ENABLE_ENVIRONMENTS[1]: "1",
                URL_ENV: target,
                SYSTEM_IDENTIFIER_ENV: record["system_identifier"],
                INVOCATION_ID_ENV: invocation,
                CONTAINER_RECORD_ENV: str(record_path),
                "FARDB_POSTGRES_TEST_URL": target,
                "FARDB_POSTGRES_EVIDENCE_DIR": str(evidence),
            }
        )
        with ContainerCliRunner(target):
            report["cli_compatible"] = True
        with attested_connection(target):
            report["host_attested"] = True
        if os.environ.get("FARDB_POSTGRES_COMPATIBILITY_ONLY") == "1":
            result_code = 0
        else:
            args = pytest_args or [
                "tests/integration/test_postgresql_ledger_profiles.py",
                "tests/integration/test_postgres_runtime_capability_sql.py",
                "tests/integration/test_runtime_authority_postgres.py",
                "-v",
                "-rs",
                "--tb=short",
            ]
            with (evidence / "pytest.log").open("w") as output:
                result_code = subprocess.run(
                    ["python", "-m", "pytest", *args], stdout=output, stderr=subprocess.STDOUT, check=False
                ).returncode
            print((evidence / "pytest.log").read_text()[-16000:])
        report["exit_code"] = result_code
    except (DisposableTargetError, OSError) as exc:
        report["failure"] = str(exc)
        print("Harness failed: " + str(exc))
    finally:
        if container_id and container_id not in old_ids:
            try:
                _cleanup_local_container(cli, container_id, volume, invocation, old_ids, old_volumes)
            except DisposableTargetError:
                result_code = 1
        current_ids = set(_docker_command([cli, "ps", "-aq", "--no-trunc"]).stdout.decode().split())
        current_volumes = set(_docker_command([cli, "volume", "ls", "-q"]).stdout.decode().split())
        report.update(
            container_removed=container_id not in current_ids,
            owned_volume_removed=volume not in current_volumes,
            existing_containers_preserved=old_ids <= current_ids,
            existing_volumes_preserved=old_volumes <= current_volumes,
        )
        if not all(
            report[k]
            for k in (
                "container_removed",
                "owned_volume_removed",
                "existing_containers_preserved",
                "existing_volumes_preserved",
            )
        ):
            result_code = 1
        (evidence / "report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    return result_code


def _main() -> int:
    """Provide only the owned local harness and exact Actions service attestation modes."""
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("harness", "attest-job"))
    parser.add_argument("--major", type=int, required=True)
    parser.add_argument("--record")
    options, rest = parser.parse_known_args()
    if options.mode == "harness":
        return run_container_harness(options.major, rest)
    if options.major not in (15, 16):
        raise DisposableTargetError("unsupported PostgreSQL major")
    container_id = os.environ.get("PG_SERVICE_ID", "")
    if os.environ.get("GITHUB_ACTIONS") != "true" or not container_id or not options.record:
        raise DisposableTargetError("exact current Actions service identity required")
    invocation = f"{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}-pg{options.major}"
    record = _capture_record(_docker_cli(), container_id, options.major, invocation, "github-job")
    path = Path(options.record)
    path.write_text(json.dumps(record))
    path.chmod(0o600)
    target = f"postgresql://test:test@127.0.0.1:{record['port']}/test_db?sslmode=disable"
    os.environ.update(
        {
            ENABLE_ENVIRONMENTS[0]: "1",
            ENABLE_ENVIRONMENTS[1]: "1",
            SYSTEM_IDENTIFIER_ENV: record["system_identifier"],
            INVOCATION_ID_ENV: invocation,
            CONTAINER_RECORD_ENV: str(path),
        }
    )
    with ContainerCliRunner(target):
        pass
    with attested_connection(target):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
