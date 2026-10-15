"""Guards and ownership helpers for explicitly disposable PostgreSQL tests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
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
_ROLE_IDENTIFIER = r'(?:"(?:[^"]|"")+"|[a-zA-Z_][a-zA-Z0-9_$]*)'
_SQL_QUOTED_TOKEN = re.compile(r"'(?:[^'\\]|'')*'|\"(?:[^\"]|\"\")*\"")
_owned_roles: dict[str, int] = {}


class DisposableTargetError(RuntimeError):
    """Raised when a test target is not the harness-attested disposable cluster."""

    def __init__(
        self,
        message: str,
        *,
        category: str | None = None,
        operation: str | None = None,
        timeout: int | None = None,
        returncode: int | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.operation = operation
        self.timeout = timeout
        self.returncode = returncode


def _enabled() -> bool:
    """Return whether the harness explicitly enabled disposable integration tests."""
    return any(os.environ.get(name) == "1" for name in ENABLE_ENVIRONMENTS)


def _loopback_host(value: str, *, allow_localhost: bool = True) -> bool:
    """Validate a URI host independently of numeric-only hostaddr overrides."""
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
    _validate_harness_container(_read_harness_record(), database_url)
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
    _validate_harness_container(_read_harness_record(), database_url)
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
        """Attest each newly opened physical operator connection."""
        attest_connection(dbapi_connection, database_url)

    return engine


def _parse_role_ddl(rendered_sql: str) -> tuple[str, str] | None:
    """Fully interpret only the single-role forms used by this harness."""
    bootstrap = Path(__file__).parents[2] / "scripts" / "bootstrap_database_capability_roles.sql"
    if rendered_sql == bootstrap.read_text(encoding="utf-8"):
        return None  # Exact reviewed bootstrap remains independently attested, not parsed as ad hoc DDL.
    statement = rendered_sql.strip()
    if statement.endswith(";"):
        statement = statement[:-1].rstrip()
    unquoted = _SQL_QUOTED_TOKEN.sub("", statement)
    if (
        any(marker in unquoted for marker in (";", "--", "/*", "'", '"', "\\"))
        or re.search(r"\$[a-zA-Z0-9_]*\$", unquoted)
        or re.match(r"^DO\b", statement, re.I)
    ):
        raise DisposableTargetError("unsupported or multi-statement SQL before role DDL execution")
    if re.match(
        r"^(?:(?:DROP|REASSIGN)\s+OWNED\b|COMMENT\s+ON\s+(?:ROLE|USER|GROUP)\b|SECURITY\s+LABEL\b)",
        statement,
        re.I,
    ):
        raise DisposableTargetError("unsupported role metadata or owned-object mutation")
    if not re.match(r"^(?:CREATE|DROP|ALTER)\s+(?:ROLE|USER|GROUP|OWNED)\b", statement, re.I):
        return None
    match = re.fullmatch(
        rf"(CREATE ROLE|DROP ROLE(?: IF EXISTS)?|ALTER ROLE)\s+({_ROLE_IDENTIFIER})(.*)",
        statement,
        re.I | re.S,
    )
    if match is None:
        raise DisposableTargetError("unsupported role DDL")
    command, identifier, tail = match.groups()
    command = command.upper()
    if command == "CREATE ROLE":
        option = (
            r"(?:NO)?(?:LOGIN|INHERIT|SUPERUSER|CREATEDB|CREATEROLE|BYPASSRLS|REPLICATION)"
            r"|CONNECTION\s+LIMIT\s+-?\d+|PASSWORD\s+'(?:[^'\\]|'')*'"
        )
        accepted = re.fullmatch(rf"(?:\s+(?:{option}))*\s*", tail, re.I)
    elif command == "ALTER ROLE":
        accepted = re.fullmatch(rf"\s+RENAME TO\s+{_ROLE_IDENTIFIER}\s*", tail, re.I)
    else:
        accepted = re.fullmatch(r"\s*", tail, re.I)
    if accepted is None:
        raise DisposableTargetError("unsupported or multi-role DDL")
    name = identifier[1:-1].replace('""', '"') if identifier.startswith('"') else identifier.lower()
    return command, name


def _ddl_role_name(rendered_sql: str) -> str | None:
    """Return the affected role only after complete supported-DDL validation."""
    parsed = _parse_role_ddl(rendered_sql)
    return parsed[1] if parsed else None


def execute_capability_bootstrap(cursor, mapping=None, *, target_database_url: str | None = None) -> None:
    """Delegate bootstrap to the identity-checked target-local orchestrator."""
    if target_database_url is None:
        target_database_url = os.environ.get(URL_ENV)
    from scripts.bootstrap_database_capability_roles import bootstrap_capability_roles

    if mapping is None:
        cursor.execute("SELECT current_database()")
        database_name = cursor.fetchone()[0]
        mapping = {role: [database_name] for role in _CANONICAL_CAPABILITY_ROLES}
    bootstrap_capability_roles(cursor, mapping, target_database_url=target_database_url)


class OwnedRoleCursor(PsycopgCursor):
    """Fence fixture CREATE/DROP roles and reject unsupported role/ownership DDL.

    This is not a general SQL sandbox: memberships and object SQL remain caller-owned.
    RENAME serves recorded prior-state restoration; only the exact reviewed bootstrap
    script bypasses ad hoc DDL parsing after independent connection attestation.
    """

    def _execute_driver(self, query, parameters):
        """Delegate to psycopg only after statement and ownership guards succeed."""
        return super().execute(query, parameters)

    @staticmethod
    def _execution_parameters(arguments, kwargs):
        """Resolve driver-compatible positional or keyword parameters exactly once."""
        if set(kwargs) - {"vars"}:
            raise TypeError("unexpected cursor execution keyword")
        if len(arguments) > 1 or ("vars" in kwargs and arguments):
            raise TypeError("cursor parameters supplied more than once")
        return arguments[0] if arguments else kwargs.get("vars")

    def _validate_role_mutation(self, command: str, role_name: str | None) -> None:
        """Fence creation namespace and cleanup against the invocation-owned role OID."""
        if (
            command == "CREATE ROLE"
            and role_name not in _CANONICAL_CAPABILITY_ROLES | _CANONICAL_TEST_LOGIN_ROLES
            and (not role_name or not role_name.startswith(f"{_ROLE_PREFIX}{invocation_id()}_"))
        ):
            raise DisposableTargetError("refusing creation outside the invocation role namespace")
        if command.startswith("DROP ROLE"):
            self._validate_role_cleanup(command, role_name)

    def _validate_role_cleanup(self, command: str, role_name: str | None) -> None:
        """Permit an absent IF EXISTS target or require its recorded live role identity."""
        oid = owned_role_oid(role_name or "")
        with self.connection.cursor(cursor_factory=PsycopgCursor) as check:
            check.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (role_name,))
            row = check.fetchone()
        if row is None and command == "DROP ROLE IF EXISTS":
            return
        if oid is None:
            raise DisposableTargetError("refusing cleanup of a role not created by this invocation")
        if row is None or int(row[0]) != oid:
            raise DisposableTargetError("refusing cleanup after role name/OID ownership changed")

    def execute(self, query, *arguments, **kwargs):
        """Adapt positional and psycopg keyword parameters before enforcing mutation guards."""
        parameters = OwnedRoleCursor._execution_parameters(arguments, kwargs)
        rendered = self.mogrify(query, parameters).decode("utf-8", errors="replace")
        parsed = _parse_role_ddl(rendered)
        command, role_name = parsed if parsed else ("", None)
        self._validate_role_mutation(command, role_name)
        result = self._execute_driver(query, parameters)
        if command == "CREATE ROLE" and role_name:
            record_created_role(
                self.connection,
                role_name,
                canonical_test_role=role_name in _CANONICAL_CAPABILITY_ROLES | _CANONICAL_TEST_LOGIN_ROLES,
            )
        return result


CONTAINER_RECORD_ENV = "FARDB_EPHEMERAL_POSTGRES_CONTAINER_RECORD"


def _read_harness_record() -> dict:
    """Reject native/unowned test execution before any mutation connection opens."""
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


_ALLOWED_DOCKER_SUBCOMMANDS = frozenset(
    {
        "cp",
        "create",
        "exec",
        "info",
        "inspect",
        "ps",
        "rm",
        "run",
        "start",
        "stop",
        "volume",
    }
)
_ALLOWED_VOLUME_SUBCOMMANDS = frozenset({"create", "inspect", "ls", "prune", "rm"})
_ALLOWED_EXEC_COMMANDS = frozenset(
    {
        "id",
        "mkdir",
        "mktemp",
        "pg_controldata",
        "pg_isready",
        "postgres",
        "rm",
        "rmdir",
        "sha256sum",
        "stat",
        "test",
    }
)
_GLOBAL_OPTIONS_WITH_ARGS = frozenset(
    {
        "-H",
        "--host",
        "-c",
        "--context",
        "--config",
        "-l",
        "--log-level",
        "--tlscacert",
        "--tlscert",
        "--tlskey",
    }
)


def _docker_operation_type(command: list[str]) -> str:
    """Extract a safe, sanitized Docker operation descriptor without exposing arguments or credentials."""
    if not command:
        return "docker"
    subcommand = None
    subcommand_idx = -1
    i = 1
    while i < len(command):
        arg = command[i]
        if arg in _GLOBAL_OPTIONS_WITH_ARGS:
            i += 2
            continue
        if arg.startswith("-") and "=" in arg:
            i += 1
            continue
        if arg.startswith("-"):
            i += 1
            continue
        subcommand = arg
        subcommand_idx = i
        break

    if not subcommand or subcommand not in _ALLOWED_DOCKER_SUBCOMMANDS:
        return "docker"

    if subcommand == "volume" and subcommand_idx + 1 < len(command):
        next_arg = command[subcommand_idx + 1]
        if next_arg in _ALLOWED_VOLUME_SUBCOMMANDS:
            return f"docker volume {next_arg}"
        return "docker volume"

    if subcommand == "exec" and subcommand_idx + 2 < len(command):
        for j in range(subcommand_idx + 2, len(command)):
            inner = command[j]
            if not inner.startswith("-"):
                inner_name = Path(inner).name
                if inner_name in _ALLOWED_EXEC_COMMANDS:
                    return f"docker exec {inner_name}"
                break
        return "docker exec"

    return f"docker {subcommand}"


def _docker_command(command: list[str], *, input_bytes: bytes | None = None, timeout: int = 30):
    """Run a fixed Docker argv without publishing captured credentials."""
    import subprocess

    operation = _docker_operation_type(command)
    try:
        result = subprocess.run(command, input=input_bytes, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise DisposableTargetError(
            f"owned Docker transport timeout during {operation} ({timeout}s)",
            category="timeout",
            operation=operation,
            timeout=timeout,
        ) from None
    except OSError as exc:
        err_name = type(exc).__name__
        raise DisposableTargetError(
            f"owned Docker transport OS error during {operation}: {err_name}",
            category="os_error",
            operation=operation,
            timeout=timeout,
        ) from None
    if result.returncode:
        raise DisposableTargetError(
            f"owned Docker operation failed during {operation} (exit status {result.returncode})",
            category="command_failed",
            operation=operation,
            returncode=result.returncode,
        ) from None
    return result


def _docker_cli() -> str:
    """Find a working Docker interface without changing saved contexts."""
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
    if not re.fullmatch(r"[0-9a-f]{64}", container_id):
        raise DisposableTargetError("full container ID required")
    items = json.loads(_docker_command([cli, "inspect", container_id]).stdout)
    if len(items) != 1 or items[0]["Id"] != container_id:
        raise DisposableTargetError("ambiguous container identity")
    return items[0]


def _validate_container_process(container, major, host, env, mounts) -> None:
    """Check the unchanged process, image and publication predicates first."""
    valid = (
        container["State"]["Running"]
        and container["Config"]["Image"] == f"postgres:{major}"
        and not host.get("Binds")
        and not host.get("Mounts")
        and host["RestartPolicy"]["Name"] == "no"
        and env.get("POSTGRES_USER") == "test"
        and env.get("POSTGRES_DB") == "test_db"
        and len(mounts) == 1
    )
    if not valid:
        raise DisposableTargetError("container ownership, image, mounts or loopback binding is invalid")


def _validate_loopback_publication(ports) -> None:
    """Require exactly one publication bound to the original loopback address."""
    if not ports or len(ports) != 1 or ports[0]["HostIp"] != "127.0.0.1":
        raise DisposableTargetError("container ownership, image, mounts or loopback binding is invalid")


def _validate_anonymous_mount(container, env, mounts):
    """Reject every mount except the image's owned anonymous data volume."""
    mount = mounts[0]
    if (
        mount["Type"] != "volume"
        or mount["Destination"] != env.get("PGDATA")
        or mount["Destination"] not in container["Config"].get("Volumes", {})
        or not re.fullmatch(r"[0-9a-f]{64}", mount.get("Name", ""))
        or not mount["Source"].endswith("/volumes/" + mount["Name"] + "/_data")
    ):
        raise DisposableTargetError("container data storage is not an owned anonymous volume")
    return mount


def _container_identity(container: dict, major: int) -> dict:
    """Reject ambiguous storage and expose only non-secret ownership fields."""
    host = container["HostConfig"]
    env = dict(item.split("=", 1) for item in container["Config"]["Env"])
    mounts = container["Mounts"]
    ports = container["NetworkSettings"]["Ports"].get("5432/tcp")
    _validate_container_process(container, major, host, env, mounts)
    _validate_loopback_publication(ports)
    mount = _validate_anonymous_mount(container, env, mounts)
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


def _validate_owned_host_endpoint(database_url: str, record: dict) -> None:
    """Bind runtime or operator credentials to the independently inspected publication."""
    validate_effective_loopback_url(database_url)
    parsed = urlsplit(database_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (
        parsed.scheme not in ("postgresql", "postgres")
        or parsed.port != record["port"]
        or parsed.hostname not in ("127.0.0.1", "localhost")
        or not re.fullmatch(r"/[a-zA-Z0-9_]+", parsed.path)
        or parsed.fragment
        or set(query) - {"host", "hostaddr", "sslmode"}
        or any(value not in ("127.0.0.1", "localhost") for value in query.get("host", []))
        or any(value != "127.0.0.1" for value in query.get("hostaddr", []))
    ):
        raise DisposableTargetError("mutation target does not match the harness-owned published endpoint")


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


def _validate_harness_container(record: dict, database_url: str) -> None:
    """Independently inspect lifecycle, storage and harness ownership before mutation."""
    cli = _docker_cli()
    if record["docker_cli"] != cli:
        raise DisposableTargetError("container record Docker interface differs from the independent host interface")
    container = _inspect_container(cli, record["id"])
    current = _container_identity(container, record["major"])
    if any(current[key] != record[key] for key in current):
        raise DisposableTargetError("owned container restarted or changed identity/storage")
    if record["owner"] == "local-created":
        if container["Config"].get("Labels", {}).get("fardb.test.invocation") != record["invocation"]:
            raise DisposableTargetError("local container invocation ownership is unverified")
    elif (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("PG_SERVICE_ID") != record["id"]
        or record["invocation"]
        != f"{os.environ.get('GITHUB_RUN_ID')}-{os.environ.get('GITHUB_RUN_ATTEMPT')}-pg{record['major']}"
    ):
        raise DisposableTargetError("exact current Actions service identity required")
    _validate_owned_host_endpoint(database_url, record)
    control = _docker_command(
        [record["docker_cli"], "exec", record["id"], "pg_controldata", record["pgdata"]]
    ).stdout.decode()
    identifier = re.search(r"Database system identifier:\s*(\d+)", control)
    if not identifier or identifier.group(1) != record["system_identifier"]:
        raise DisposableTargetError("owned container cluster identity changed")


class ContainerCliRunner:
    """Execute pinned CLI mutations in the exact owned PostgreSQL container namespace."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.record = _read_harness_record()
        self.cli = self.record["docker_cli"]
        _internal_cli_url(database_url, self.record)
        self.validate()
        self.directory: str | None = None
        self.private_parent: str | None = None
        self.parent_identity: str | None = None
        self.digests: dict[str, str] = {}

    def validate(self) -> None:
        """Check exact storage, process lifecycle and independent cluster identity."""
        _validate_harness_container(self.record, self.database_url)

    def _validate_private_parent(self, path: str, *, adopt: bool = False) -> None:
        """Require the exclusively created parent and its recorded inode/ownership."""
        expected = f"/run/fardb-cli-{invocation_id()}"
        if path != expected:
            raise DisposableTargetError("malformed container private parent")
        self.validate()
        _docker_command([self.cli, "exec", self.record["id"], "test", "!", "-L", path])
        _docker_command([self.cli, "exec", self.record["id"], "test", "-d", path])
        uid = _docker_command([self.cli, "exec", self.record["id"], "id", "-u"]).stdout.decode().strip()
        metadata = (
            _docker_command([self.cli, "exec", self.record["id"], "stat", "-c", "%a:%u:%d:%i", "--", path])
            .stdout.decode()
            .strip()
        )
        if not uid.isdigit() or not re.fullmatch(rf"700:{uid}:\d+:\d+", metadata):
            raise DisposableTargetError("unsafe container private parent permissions or owner")
        if adopt:
            self.parent_identity = metadata
            self.private_parent = path
        elif metadata != self.parent_identity:
            raise DisposableTargetError("container private parent changed identity")

    def __enter__(self):
        """Allocate random CLI state beneath an exclusively owned mode-0700 parent."""
        self.validate()
        parent = f"/run/fardb-cli-{invocation_id()}"
        _docker_command([self.cli, "exec", self.record["id"], "mkdir", "-m", "700", "--", parent])
        self._validate_private_parent(parent, adopt=True)
        try:
            output = _docker_command(
                [self.cli, "exec", self.record["id"], "mktemp", "-d", "-p", parent, "cli-XXXXXX"]
            ).stdout.decode()
            candidate = output.removesuffix("\n")
            self._validate_private_directory(candidate)
            self.directory = candidate
            print(json.dumps({"cli_private_parent": parent, "cli_private_directory": candidate}))
            return self._prepare_cli()
        except BaseException:
            self.__exit__()
            raise

    def _validate_private_directory(self, path: str) -> None:
        """Validate the random direct child before transfer or cleanup adoption."""
        if self.private_parent is None:
            raise DisposableTargetError("container private parent is not active")
        if re.fullmatch(rf"{re.escape(self.private_parent)}/cli-[a-zA-Z0-9]{{6}}", path) is None:
            raise DisposableTargetError("malformed container private directory")
        self._validate_private_parent(self.private_parent)
        for argv in (["test", "!", "-L", path], ["test", "-d", path]):
            _docker_command([self.cli, "exec", self.record["id"], *argv])
        uid = _docker_command([self.cli, "exec", self.record["id"], "id", "-u"]).stdout.decode().strip()
        metadata = (
            _docker_command([self.cli, "exec", self.record["id"], "stat", "-c", "%a:%u", "--", path])
            .stdout.decode()
            .strip()
        )
        if not uid.isdigit() or metadata != f"700:{uid}":
            raise DisposableTargetError("unsafe container private directory permissions or owner")

    def _prepare_cli(self):
        """Copy and compatibility-check the pinned executable in validated private state."""
        if self.directory is None:
            raise DisposableTargetError("CLI runner context is not active")
        executable = shutil.which("supabase")
        if not executable:
            raise DisposableTargetError("pinned Supabase executable unavailable")
        self._copy_files({"supabase": Path(executable).resolve()})
        result = self._execute([self.directory + "/supabase", "--version"], 15)
        from scripts.postgresql_ledger import PINNED_SUPABASE_CLI_VERSION

        if result.returncode or result.stdout.strip() != PINNED_SUPABASE_CLI_VERSION:
            raise DisposableTargetError("pinned CLI is incompatible with the container image")
        return self

    def _copy_files(self, files: dict) -> None:
        """Transfer regular validated bytes and reject any container checksum mismatch."""
        import io
        import tarfile

        if self.directory is None:
            raise DisposableTargetError("CLI runner context is not active")
        self._validate_private_directory(self.directory)
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
        except subprocess.TimeoutExpired:
            _docker_command([self.cli, "stop", "--time", "5", self.record["id"]])
            raise DisposableTargetError(
                f"CLI timed out ({timeout}s); owned container stopped",
                category="timeout",
                operation="supabase",
                timeout=timeout,
            ) from None
        except KeyboardInterrupt:
            _docker_command([self.cli, "stop", "--time", "5", self.record["id"]])
            raise
        return subprocess.CompletedProcess(argv, result.returncode, result.stdout.decode(), result.stderr.decode())

    def __call__(self, command, *, timeout, **_kwargs):
        """Adapt only ledger's fixed version/push commands to container-local execution."""
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
        """Remove adopted children and the empty, still-owned parent only."""
        if self.directory is not None:
            self._validate_private_directory(self.directory)
            _docker_command([self.cli, "exec", self.record["id"], "rm", "-rf", "--", self.directory])
            self.directory = None
        if self.private_parent is not None:
            self._validate_private_parent(self.private_parent)
            _docker_command([self.cli, "exec", self.record["id"], "rmdir", "--", self.private_parent])
            self.private_parent = None
            self.parent_identity = None


def verify_applied_profile(database_url: str, manifest, profile: str) -> None:
    """Read catalog and exact history through the host-side attested session after CLI writes."""
    from scripts.postgresql_drift import catalog_digest, normalized_managed_catalog

    with attested_connection(database_url) as connection, connection.cursor() as cursor:
        normalized = normalized_managed_catalog(cursor, profile)
        actual = catalog_digest(normalized)
        expected = manifest.catalog_digest_for_profile(profile)
        if actual != expected:
            raise DisposableTargetError(f"post-CLI {profile} catalog digest mismatch: {actual} != {expected}")
        cursor.execute("SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version")
        expected_history = [(m.timestamp, m.filename[15:-4]) for m in manifest.migrations_for_profile(profile)]
        if cursor.fetchall() != expected_history:
            raise DisposableTargetError("post-CLI host-side migration history differs from the selected profile")
        evidence = os.environ.get("FARDB_POSTGRES_EVIDENCE_DIR")
        if evidence:
            from uuid import uuid4

            Path(evidence, f"catalog-{profile}-{uuid4().hex}.json").write_text(
                json.dumps(
                    {
                        "profile": profile,
                        "actual": actual,
                        "expected": expected,
                        "history": expected_history,
                        "normalized_catalog": normalized,
                    }
                )
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


def _run_pytest(pytest_args: list[str], output: Any) -> int:
    """Launch pytest with the same interpreter that loaded the harness."""
    import subprocess

    return subprocess.run(
        [sys.executable, "-m", "pytest", *pytest_args], stdout=output, stderr=subprocess.STDOUT, check=False
    ).returncode


def _finalize_harness(cli, container_id, volume, invocation, old_ids, old_volumes, report, evidence, result_code):
    """Clean owned resources before inventory preservation and evidence publication."""
    if container_id and container_id not in old_ids:
        try:
            _cleanup_local_container(cli, container_id, volume, invocation, old_ids, old_volumes)
        except DisposableTargetError as exc:
            report["cleanup_failure"] = str(exc)
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


def _create_harness_container(cli: str, major: int, invocation: str) -> str:
    """Create a fresh container only after the caller's locked inventory capture."""
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
    return container_id


def _fresh_storage_volume(cli: str, container_id: str) -> tuple[str, dict]:
    """Inspect storage before adopting its name for any later cleanup."""
    created = _inspect_container(cli, container_id)
    if (
        not created["HostConfig"]["AutoRemove"]
        or created["HostConfig"].get("Binds")
        or created["HostConfig"].get("Mounts")
        or len(created["Mounts"]) != 1
    ):
        raise DisposableTargetError("fresh-container storage setup is ambiguous")
    return created["Mounts"][0]["Name"], created


def _wait_for_owned_postgres(cli: str, container_id: str) -> None:
    """Bound readiness only after the owned container has been started."""
    import time

    deadline = time.monotonic() + 45
    while True:
        try:
            _docker_command([cli, "exec", container_id, "pg_isready", "-U", "test", "-d", "test_db"])
            break
        except DisposableTargetError:
            if time.monotonic() > deadline:
                raise DisposableTargetError("new PostgreSQL container readiness timeout") from None
            time.sleep(1)


def _run_locked_container_harness(cli: str, major: int, pytest_args: list[str]) -> int:
    """Own fresh anonymous storage, attest both endpoints and clean up only this run."""
    import tempfile
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
        container_id = _create_harness_container(cli, major, invocation)
        if container_id in old_ids:
            raise DisposableTargetError("refusing reused container")
        volume, created = _fresh_storage_volume(cli, container_id)
        if volume in old_volumes or created["Config"]["Labels"].get("fardb.test.invocation") != invocation:
            raise DisposableTargetError("container storage is not newly owned")
        _docker_command([cli, "start", container_id])
        _wait_for_owned_postgres(cli, container_id)
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
                result_code = _run_pytest(args, output)
            print((evidence / "pytest.log").read_text()[-16000:])
        report["exit_code"] = result_code
    except (DisposableTargetError, OSError) as exc:
        report["failure"] = str(exc)
        print("Harness failed: " + str(exc))
    finally:
        result_code = _finalize_harness(
            cli, container_id, volume, invocation, old_ids, old_volumes, report, evidence, result_code
        )
    return result_code


def _main() -> int:
    """Provide only the owned local harness and exact Actions service attestation modes."""
    import argparse

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
