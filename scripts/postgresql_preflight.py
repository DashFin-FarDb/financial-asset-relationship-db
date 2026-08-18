"""Run the target-bound, read-only CQ-03D PostgreSQL preflight."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import SplitResult, parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from scripts.postgresql_drift import (
    CHECK_DRIFT,
    CHECK_PASSED,
    DRIFT_DETECTED,
    EVALUATION_INCOMPLETE,
    NOT_EVALUATED,
    PASS,
    REQUIRED_CHECK_NOT_EVALUATED,
    DriftReport,
    RuntimeCheckUnavailable,
    RuntimeCompatibilityMismatch,
    evaluate_profile_drift,
    expected_adoption_history,
)
from scripts.postgresql_ledger import (
    COMPONENT_ORDER,
    EXPECTED_PROFILES,
    REPOSITORY_ROOT,
    TARGET_BINDINGS_ENV,
    TARGET_FINGERPRINT_ALGORITHM,
    TARGET_IDENTITY_INDETERMINATE,
    LedgerContractError,
    LedgerManifest,
    MigrationEntry,
    PlannedTarget,
    SupabaseCliError,
    TargetIdentityError,
    _assert_projection_has_no_link_state,
    _resolve_supabase_cli,
    _run_cli,
    _sanitized_cli_environment,
    disposable_migration_projection,
    load_and_validate_manifest,
    load_target_bindings,
    require_pinned_supabase_cli,
    resolve_target_plan,
    target_fingerprint,
)

PREFLIGHT_PERMIT_VERSION = "fardb-cq03d-preflight-permit-v1"
TARGET_ADAPTER_ID = "supabase-postgresql-routing-v1"
INSPECTION_DATABASE_URL_ENV = "FARDB_CQ03D_INSPECTION_DATABASE_URL"
PERMIT_FILE_ENV = "FARDB_CQ03D_PERMIT_FILE"
RUNTIME_DATABASE_URL_ENVS: Mapping[str, str] = dict(
    zip(
        COMPONENT_ORDER,
        (
            "FARDB_AUTH_RUNTIME_DATABASE_URL",
            "FARDB_GRAPH_RUNTIME_DATABASE_URL",
            "FARDB_COORDINATION_RUNTIME_DATABASE_URL",
        ),
        strict=True,
    )
)

PERMIT_INVALID = "PREFLIGHT_PERMIT_INVALID"
REPOSITORY_HEAD_MISMATCH = "REPOSITORY_HEAD_MISMATCH"
RUNTIME_AUTHORITY_MISMATCH = "RUNTIME_AUTHORITY_MISMATCH"
MIGRATION_PARITY_MISMATCH = "MIGRATION_PARITY_MISMATCH"
MIGRATION_PARITY_UNAVAILABLE = "MIGRATION_PARITY_UNAVAILABLE"

_PROJECT_REF = re.compile(r"^[a-z0-9]{20}$", re.ASCII)
_DIRECT_HOST = re.compile(r"^db[.](?P<ref>[a-z0-9]{20})[.]supabase[.]co$", re.ASCII)
_POOLER_HOST = re.compile(r"^[a-z0-9-]+[.]pooler[.]supabase[.]com$", re.ASCII)
_LOWER_HEX_40 = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_TIMESTAMP = re.compile(r"^[0-9]{14}$", re.ASCII)
_PERMIT_KEYS = {
    "version",
    "state",
    "repository_sha",
    "manifest_sha256",
    "profile",
    "lineage",
    "target_fingerprint_algorithm",
    "target_fingerprint",
    "migration_timestamp",
    "expected_catalog_digest",
    "history_only",
    "ddl_authorized",
    "ratifier",
    "approved_at",
    "expires_at",
    "evidence",
}
_EVIDENCE_KEYS = {
    "cq03b",
    "cq03c",
    "history",
    "runtime_compatibility",
    "runtime_authority",
}


class PreflightContractError(RuntimeError):
    """One bounded CQ-03D preflight control failure."""

    def __init__(self, reason_code: str) -> None:
        """Retain only a fixed public reason code."""
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class PreflightPermit:
    """One protected, one-marker CQ-03D preflight authorization."""

    repository_sha: str
    manifest_sha256: str
    profile: str
    lineage: str
    target_fingerprint: str
    migration_timestamp: str
    expected_catalog_digest: str


@dataclass(frozen=True, slots=True)
class RouteIdentity:
    """Protected route metadata retained only inside the adapter."""

    database_url: str
    project_ref: str


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """Bounded public CQ-03D preflight evidence without target secrets."""

    status: str
    reason_codes: tuple[str, ...]
    repository_sha: str
    manifest_sha256: str
    profile: str
    lineage: str
    target_fingerprint_algorithm: str
    target_fingerprint: str
    migration_timestamp: str
    identity: str
    history: str
    catalog: str
    runtime_compatibility: str
    runtime_authority: str
    migration_parity: str
    required_check_count: int
    evaluated_check_count: int
    application_owned_count: int
    provider_owned_count: int
    unknown_count: int
    expected_catalog_digest: str | None
    actual_catalog_digest: str | None
    parity_row_count: int

    def as_public_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe diagnostics."""
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "repository_sha": self.repository_sha,
            "manifest_sha256": self.manifest_sha256,
            "profile": self.profile,
            "lineage": self.lineage,
            "target_fingerprint_algorithm": self.target_fingerprint_algorithm,
            "target_fingerprint": self.target_fingerprint,
            "migration_timestamp": self.migration_timestamp,
            "identity": self.identity,
            "history": self.history,
            "catalog": self.catalog,
            "runtime_compatibility": self.runtime_compatibility,
            "runtime_authority": self.runtime_authority,
            "migration_parity": self.migration_parity,
            "required_check_count": self.required_check_count,
            "evaluated_check_count": self.evaluated_check_count,
            "application_owned_count": self.application_owned_count,
            "provider_owned_count": self.provider_owned_count,
            "unknown_count": self.unknown_count,
            "expected_catalog_digest": self.expected_catalog_digest,
            "actual_catalog_digest": self.actual_catalog_digest,
            "parity_row_count": self.parity_row_count,
        }


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate protected JSON keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PreflightContractError(PERMIT_INVALID)
        result[key] = value
    return result


def _resolved_permit_path(path: Path) -> Path:
    """Resolve one absolute path without accepting indirection or traversal."""
    try:
        if not path.is_absolute() or ".." in path.parts:
            raise PreflightContractError(PERMIT_INVALID)
        resolved_path = path.resolve(strict=True)
        if resolved_path != path:
            raise PreflightContractError(PERMIT_INVALID)
        return resolved_path
    except PreflightContractError:
        raise
    except (OSError, RuntimeError) as exc:
        raise PreflightContractError(PERMIT_INVALID) from exc


def _open_permit_descriptor(path: Path) -> int:
    """Open and attest one owner-only regular permit without following links."""
    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)  # NOSONAR - normalized owner-only control file, never exposed
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise PreflightContractError(PERMIT_INVALID)
        if os.name != "nt" and (stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.geteuid()):
            raise PreflightContractError(PERMIT_INVALID)
        return descriptor
    except PreflightContractError:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        raise
    except OSError as exc:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        raise PreflightContractError(PERMIT_INVALID) from exc


def _decode_permit_document(descriptor: int) -> Mapping[str, object]:
    """Decode one bounded strict-UTF-8 permit object and consume its descriptor."""
    try:
        handle = os.fdopen(descriptor, "rb")
        descriptor = -1
        with handle:
            raw_bytes = handle.read(65_537)
        if len(raw_bytes) > 65_536:
            raise PreflightContractError(PERMIT_INVALID)
        text = raw_bytes.decode("utf-8", errors="strict")
        if text.startswith("\ufeff"):
            raise PreflightContractError(PERMIT_INVALID)
        document = json.loads(text, object_pairs_hook=_object_without_duplicate_keys)
    except PreflightContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise PreflightContractError(PERMIT_INVALID) from exc
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
    if not isinstance(document, dict):
        raise PreflightContractError(PERMIT_INVALID)
    return document


def _protected_permit_document(path: Path) -> Mapping[str, object]:
    """Read one absolute, owner-only, non-symlink permit file."""
    resolved_path = _resolved_permit_path(path)
    return _decode_permit_document(_open_permit_descriptor(resolved_path))


def _utc_timestamp(value: object) -> datetime:
    """Parse one exact UTC permit timestamp."""
    if not isinstance(value, str):
        raise PreflightContractError(PERMIT_INVALID)
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise PreflightContractError(PERMIT_INVALID) from exc


def _validate_permit_envelope(document: Mapping[str, object]) -> None:
    """Require the exact bounded approval envelope and evidence references."""
    if set(document) != _PERMIT_KEYS:
        raise PreflightContractError(PERMIT_INVALID)
    evidence = document["evidence"]
    evidence_is_complete = (
        isinstance(evidence, dict)
        and set(evidence) == _EVIDENCE_KEYS
        and all(isinstance(value, str) and bool(value.strip()) for value in evidence.values())
    )
    ratifier = document["ratifier"]
    checks = (
        document["version"] == PREFLIGHT_PERMIT_VERSION,
        document["state"] == "approved",
        document["history_only"] is True,
        document["ddl_authorized"] is False,
        evidence_is_complete,
        isinstance(ratifier, str) and bool(ratifier.strip()) and ratifier == ratifier.strip(),
    )
    if not all(checks):
        raise PreflightContractError(PERMIT_INVALID)


def _validate_permit_window(document: Mapping[str, object], now: datetime | None) -> None:
    """Require a timezone-aware instant inside the permit's UTC validity window."""
    approved_at = _utc_timestamp(document["approved_at"])
    expires_at = _utc_timestamp(document["expires_at"])
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise PreflightContractError(PERMIT_INVALID)
    if not approved_at <= current_time.astimezone(UTC) < expires_at:
        raise PreflightContractError(PERMIT_INVALID)


def _validated_permit_binding(document: Mapping[str, object], manifest: LedgerManifest) -> PreflightPermit:
    """Bind exact permit strings to the current manifest and one canonical marker."""
    field_names = (
        "repository_sha",
        "manifest_sha256",
        "profile",
        "lineage",
        "target_fingerprint_algorithm",
        "target_fingerprint",
        "migration_timestamp",
        "expected_catalog_digest",
    )
    values = tuple(document[name] for name in field_names)
    if not all(isinstance(value, str) for value in values):
        raise PreflightContractError(PERMIT_INVALID)
    (
        repository_sha,
        manifest_sha256,
        profile,
        lineage,
        fingerprint_algorithm,
        fingerprint,
        migration_timestamp,
        expected_catalog_digest,
    ) = tuple(str(value) for value in values)
    format_checks = (
        _LOWER_HEX_40.fullmatch(repository_sha) is not None,
        _LOWER_HEX_64.fullmatch(manifest_sha256) is not None,
        profile in EXPECTED_PROFILES,
        lineage == "hosted-legacy-v1",
        fingerprint_algorithm == TARGET_FINGERPRINT_ALGORITHM,
        _LOWER_HEX_64.fullmatch(fingerprint) is not None,
        _TIMESTAMP.fullmatch(migration_timestamp) is not None,
        _LOWER_HEX_64.fullmatch(expected_catalog_digest) is not None,
    )
    if not all(format_checks):
        raise PreflightContractError(PERMIT_INVALID)
    binding_checks = (
        manifest_sha256 == manifest.sha256,
        expected_catalog_digest == manifest.catalog_digest_for_profile(profile),
        migration_timestamp in {entry.timestamp for entry in manifest.migrations_for_profile(profile)},
    )
    if not all(binding_checks):
        raise PreflightContractError(PERMIT_INVALID)
    return PreflightPermit(
        repository_sha,
        manifest_sha256,
        profile,
        lineage,
        fingerprint,
        migration_timestamp,
        expected_catalog_digest,
    )


def load_preflight_permit(
    path: Path | str,
    manifest: LedgerManifest,
    *,
    now: datetime | None = None,
) -> PreflightPermit:
    """Load and validate one protected, current, one-marker permit."""
    document = _protected_permit_document(Path(path))
    _validate_permit_envelope(document)
    _validate_permit_window(document, now)
    return _validated_permit_binding(document, manifest)


def _repository_sha() -> str:
    """Return the exact checked-out repository head only from a clean worktree."""
    git_environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    try:
        head_result = subprocess.run(
            ("git", "rev-parse", "--verify", "HEAD"),
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            env=git_environment,
        )
        status_result = subprocess.run(
            ("git", "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"),
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            env=git_environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PreflightContractError(REPOSITORY_HEAD_MISMATCH) from exc
    value = head_result.stdout.strip()
    checks = (
        head_result.returncode == 0,
        _LOWER_HEX_40.fullmatch(value) is not None,
        status_result.returncode == 0,
        not status_result.stdout,
    )
    if not all(checks):
        raise PreflightContractError(REPOSITORY_HEAD_MISMATCH)
    return value


def _query_parameters(query: str) -> dict[str, str]:
    """Parse a duplicate-free URL query."""
    pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True)
    parameters: dict[str, str] = {}
    for key, value in pairs:
        if key in parameters:
            raise TargetIdentityError()
        parameters[key] = value
    return parameters


def _parsed_supabase_route(database_url: str) -> tuple[SplitResult, str, str, dict[str, str]]:
    """Parse and validate the fixed PostgreSQL route surface."""
    try:
        if not database_url or database_url != database_url.strip():
            raise TargetIdentityError()
        parsed = urlsplit(database_url)
        if parsed.scheme not in ("postgres", "postgresql", "postgresql+psycopg2"):
            raise TargetIdentityError()
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
        username = unquote(parsed.username or "")
        password = parsed.password
        database = unquote(parsed.path.removeprefix("/"))
        parameters = _query_parameters(parsed.query)
    except TargetIdentityError:
        raise
    except ValueError as exc:
        raise TargetIdentityError() from exc
    checks = (
        not parsed.fragment,
        port == 5432,
        bool(username),
        password not in (None, ""),
        database == "postgres",
        set(parameters) == {"sslmode", "sslrootcert"},
        parameters.get("sslmode") == "verify-full",
    )
    if not all(checks):
        raise TargetIdentityError()
    return parsed, host, username, parameters


def _project_ref_for_route(host: str, username: str) -> str:
    """Extract one protected project reference from an approved route shape."""
    direct = _DIRECT_HOST.fullmatch(host)
    if direct is not None:
        project_ref = direct.group("ref")
    else:
        pooler = _POOLER_HOST.fullmatch(host)
        if pooler is None or "." not in username:
            raise TargetIdentityError()
        project_ref = username.rsplit(".", 1)[1]
    if not _PROJECT_REF.fullmatch(project_ref):
        raise TargetIdentityError()
    return project_ref


def _supabase_route_identity(database_url: str) -> RouteIdentity:
    """Require documented direct/session-pooler routing with verified TLS."""
    parsed, host, username, parameters = _parsed_supabase_route(database_url)
    _validate_trust_root(parameters["sslrootcert"])
    project_ref = _project_ref_for_route(host, username)
    normalized_url = urlunsplit(("postgresql", parsed.netloc, parsed.path, parsed.query, ""))
    return RouteIdentity(normalized_url, project_ref)


def _validate_trust_root(value: str) -> None:
    """Require one normalized regular CA file that unprivileged users cannot replace in place."""
    try:
        root_certificate = Path(value)
        if not root_certificate.is_absolute() or ".." in root_certificate.parts:
            raise TargetIdentityError()
        resolved_certificate = root_certificate.resolve(strict=True)
        if resolved_certificate != root_certificate:
            raise TargetIdentityError()
        metadata = root_certificate.lstat()
        parent_metadata = root_certificate.parent.stat()
    except TargetIdentityError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise TargetIdentityError() from exc
    permitted_owners = {os.geteuid(), 0} if os.name != "nt" else set()
    checks = (
        stat.S_ISREG(metadata.st_mode),
        not metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH),
        os.name == "nt" or metadata.st_uid in permitted_owners,
        os.name == "nt" or parent_metadata.st_uid in permitted_owners,
        not parent_metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH),
    )
    if not all(checks):
        raise TargetIdentityError()


def _read_only_url(route: RouteIdentity) -> str:
    """Force server-side default read-only transactions for helper connections."""
    parsed = urlsplit(route.database_url)
    parameters = _query_parameters(parsed.query)
    parameters["options"] = "-c default_transaction_read_only=on"
    query = urlencode(parameters, quote_via=quote)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def _prove_live_database_identity(connection, route: RouteIdentity, target: PlannedTarget) -> None:
    """Read and bind the connected database-instance OID inside one read-only transaction."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT database.oid::text FROM pg_catalog.pg_database AS database "
            "WHERE database.datname = pg_catalog.current_database()"
        )
        rows = cursor.fetchall()
    connection.rollback()
    if len(rows) != 1 or len(rows[0]) != 1:
        raise TargetIdentityError()
    database_id = str(rows[0][0])
    if not database_id.isascii() or not database_id.isdecimal() or int(database_id) <= 0:
        raise TargetIdentityError()
    identity = (TARGET_ADAPTER_ID, route.project_ref, database_id)
    if identity != target.canonical_identity or target_fingerprint(*identity) != target.fingerprint:
        raise TargetIdentityError()


def _discard_identity_connection(connection) -> None:
    """Best-effort rollback and close after identity proof fails."""
    if connection is None:
        return
    with suppress(Exception):
        connection.rollback()
    with suppress(Exception):
        connection.close()


def _connect_verified(route: RouteIdentity, target: PlannedTarget):
    """Open one read-only connection and bind its live database OID to the route."""
    connection = None
    try:
        import psycopg2  # type: ignore[import-untyped]

        connection = psycopg2.connect(route.database_url, connect_timeout=10)
        connection.set_session(readonly=True, autocommit=False)
        _prove_live_database_identity(connection, route, target)
        return connection
    except TargetIdentityError:
        _discard_identity_connection(connection)
        raise
    except Exception as exc:  # noqa: BLE001 - provider failures collapse to one identity result
        _discard_identity_connection(connection)
        raise TargetIdentityError() from exc


def _verified_target(
    manifest: LedgerManifest,
    permit: PreflightPermit,
    binding_path: Path,
    inspection_route: RouteIdentity,
) -> PlannedTarget:
    """Resolve exactly one protected hosted target selected by the permit."""
    bindings = tuple(
        binding
        for binding in load_target_bindings(binding_path, manifest)
        if binding.fingerprint == permit.target_fingerprint
    )
    if not bindings:
        raise TargetIdentityError()
    database_urls = {binding.logical_target: inspection_route.database_url for binding in bindings}
    plan = resolve_target_plan(binding_path, manifest, database_urls)
    if len(plan) != 1:
        raise TargetIdentityError()
    target = plan[0]
    adapter_id = target.canonical_identity[0] if target.canonical_identity else None
    checks = (
        target.profile == permit.profile,
        target.lineage == permit.lineage,
        target.execution_class == "hosted",
        target.fingerprint == permit.target_fingerprint,
        adapter_id == TARGET_ADAPTER_ID,
    )
    if not all(checks):
        raise TargetIdentityError()
    return target


def _runtime_routes(target: PlannedTarget) -> dict[str, RouteIdentity]:
    """Load every profile-required runtime route from the protected environment."""
    routes: dict[str, RouteIdentity] = {}
    for component in EXPECTED_PROFILES[target.profile]:
        value = os.environ.get(RUNTIME_DATABASE_URL_ENVS[component])
        if value is None:
            raise TargetIdentityError()
        routes[component] = _supabase_route_identity(value)
    return routes


def _prove_route(route: RouteIdentity, target: PlannedTarget) -> None:
    """Prove one route and close its read-only identity transaction."""
    connection = _connect_verified(route, target)
    try:
        connection.close()
    except Exception as exc:  # noqa: BLE001 - cleanup is a required preflight invariant
        raise PreflightContractError(EVALUATION_INCOMPLETE) from exc


def _runtime_compatibility(route: RouteIdentity, component: str) -> None:
    """Run one component runtime's schema/catalog checks through its own credential."""
    from api.database import bind_database_url, verify_runtime_access_catalog, verify_schema_compatibility
    from src.data.database import SchemaCompatibilityError, create_engine_from_url, verify_database_schema

    engine = None
    try:
        read_only_url = _read_only_url(route)
        if component in {"graph", "coordination"}:
            engine = create_engine_from_url(read_only_url)
            verify_database_schema(engine, required_capabilities={component})
        elif component == "auth":
            with bind_database_url(read_only_url):
                verify_schema_compatibility()
                verify_runtime_access_catalog()
        else:
            raise RuntimeCheckUnavailable()
    except SchemaCompatibilityError as exc:
        raise RuntimeCompatibilityMismatch() from exc
    except Exception as exc:  # noqa: BLE001 - unavailable dependency/catalog is a bounded result
        raise RuntimeCheckUnavailable() from exc
    finally:
        if engine is not None:
            engine.dispose()


def _runtime_routes_compatible(routes: Mapping[str, RouteIdentity]) -> None:
    """Require compatibility through every profile-required runtime credential."""
    for component in COMPONENT_ORDER:
        route = routes.get(component)
        if route is not None:
            _runtime_compatibility(route, component)


def _group_non_auth_routes(
    routes: Mapping[str, RouteIdentity],
) -> tuple[tuple[RouteIdentity, set[str]], ...]:
    """Group identical graph/coordination credentials for one authority check."""
    grouped: dict[str, tuple[RouteIdentity, set[str]]] = {}
    for component in ("graph", "coordination"):
        route = routes.get(component)
        if route is None:
            continue
        previous = grouped.get(route.database_url)
        if previous is None:
            grouped[route.database_url] = (route, {component})
        else:
            previous[1].add(component)
    return tuple(grouped.values())


def _runtime_authority(routes: Mapping[str, RouteIdentity]) -> str:
    """Verify each configured runtime login has only its required capability."""
    from api.database import bind_database_url, verify_runtime_authority
    from src.data.database import (
        SchemaCompatibilityError,
        create_engine_from_url,
        verify_runtime_database_authority,
    )

    try:
        auth_route = routes.get("auth")
        if auth_route is not None:
            with bind_database_url(_read_only_url(auth_route)):
                verify_runtime_authority()
        for route, capabilities in _group_non_auth_routes(routes):
            read_only_url = _read_only_url(route)
            engine = create_engine_from_url(read_only_url)
            try:
                verify_runtime_database_authority(engine, required_capabilities=capabilities)
            finally:
                engine.dispose()
    except SchemaCompatibilityError:
        return CHECK_DRIFT
    except Exception:  # noqa: BLE001 - dependency/provider failures are not proof of drift
        return NOT_EVALUATED
    return CHECK_PASSED


def assert_allowed_preflight_command(command: Sequence[str], target: PlannedTarget) -> None:
    """Allow only exact, explicit, read-only Supabase migration-list execution."""
    tokens = tuple(command)
    lowered = tuple(token.lower() for token in tokens)
    forbidden = {"--linked", "--project-ref", "--local", "--password", "--dry-run"}
    if any(token in forbidden for token in lowered):
        raise SupabaseCliError("Supabase preflight command is forbidden")
    fixed_shape = all(
        (
            len(tokens) == 9,
            lowered[:1] == ("--workdir",),
            bool(tokens[1:2] and tokens[1]),
            lowered[2:8] == ("--yes", "--output-format", "json", "migration", "list", "--db-url"),
            tokens[8:] == (target.database_url,),
        )
    )
    if not fixed_shape:
        raise SupabaseCliError("Supabase preflight command is outside the read-only allowlist")


def _migration_list_rows(stdout: str) -> tuple[tuple[str, str], ...] | None:
    """Parse only the bounded local/remote fields from pinned CLI JSON."""
    try:
        payload = json.loads(stdout)
        rows = payload["data"]["migrations"]
        if not isinstance(rows, list):
            return None
        actual: list[tuple[str, str]] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"local", "remote", "time"}:
                return None
            values = (row["local"], row["remote"], row["time"])
            if not all(isinstance(value, str) for value in values):
                return None
            actual.append((str(values[0]), str(values[1])))
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
    return tuple(actual)


def _migration_parity(
    target: PlannedTarget,
    migration: MigrationEntry,
    expected_history: tuple[tuple[str, str], ...],
) -> tuple[str, int]:
    """Compare pinned CLI local/remote history for exactly one permitted marker."""
    cli_path = _resolve_supabase_cli()
    with disposable_migration_projection((migration,)) as workdir:
        state_directory = Path(tempfile.mkdtemp(prefix="fardb-cq03d-supabase-home-"))
        try:
            environment = _sanitized_cli_environment(state_directory)
            require_pinned_supabase_cli(cli_path, environment)
            command = (
                cli_path,
                "--workdir",
                str(workdir),
                "--yes",
                "--output-format",
                "json",
                "migration",
                "list",
                "--db-url",
                target.database_url,
            )
            assert_allowed_preflight_command(command[1:], target)
            result = _run_cli(command, environment, timeout_seconds=60)
            if result.returncode != 0:
                return NOT_EVALUATED, 0
            actual = _migration_list_rows(result.stdout)
            if actual is None:
                return NOT_EVALUATED, 0
            expected = [("", timestamp) for timestamp, _name in expected_history]
            expected.append((migration.timestamp, ""))
            state = CHECK_PASSED if sorted(actual) == sorted(expected) else CHECK_DRIFT
            _assert_projection_has_no_link_state(workdir)
            return state, len(actual)
        finally:
            try:
                shutil.rmtree(state_directory)
            except OSError as exc:
                raise PreflightContractError(EVALUATION_INCOMPLETE) from exc


def _report_status(drift_status: str, authority: str, parity: str) -> tuple[str, tuple[str, ...]]:
    """Select overall status without masking an unavailable required check."""
    if drift_status != PASS:
        return drift_status, ()
    if authority == NOT_EVALUATED:
        return EVALUATION_INCOMPLETE, (REQUIRED_CHECK_NOT_EVALUATED,)
    if authority == CHECK_DRIFT:
        return DRIFT_DETECTED, (RUNTIME_AUTHORITY_MISMATCH,)
    reasons: list[str] = []
    if parity == NOT_EVALUATED:
        return EVALUATION_INCOMPLETE, (MIGRATION_PARITY_UNAVAILABLE,)
    if parity == CHECK_DRIFT:
        reasons.append(MIGRATION_PARITY_MISMATCH)
    return (DRIFT_DETECTED, tuple(reasons)) if reasons else (PASS, ())


def _evaluate_verified_drift(
    inspection_route: RouteIdentity,
    runtime_routes: Mapping[str, RouteIdentity],
    target: PlannedTarget,
    manifest: LedgerManifest,
    permit: PreflightPermit,
) -> DriftReport:
    """Prove every route and evaluate drift while always closing inspection access."""
    inspection_connection = _connect_verified(inspection_route, target)
    try:
        for route in runtime_routes.values():
            _prove_route(route, target)
        return evaluate_profile_drift(
            inspection_connection,
            manifest,
            target.profile,
            target.lineage,
            target.execution_class,
            runtime_check=lambda: _runtime_routes_compatible(runtime_routes),
            adoption_timestamp=permit.migration_timestamp,
        )
    finally:
        try:
            inspection_connection.close()
        except Exception as exc:  # noqa: BLE001 - cleanup is a required preflight invariant
            raise PreflightContractError(EVALUATION_INCOMPLETE) from exc


def _evaluate_migration_parity(
    manifest: LedgerManifest,
    target: PlannedTarget,
    permit: PreflightPermit,
    drift_status: str,
    authority: str,
) -> tuple[str, int]:
    """Evaluate one permit-bound marker only after every earlier gate passes."""
    expected_history = expected_adoption_history(
        manifest,
        target.profile,
        target.lineage,
        permit.migration_timestamp,
    )
    if expected_history is None:
        raise PreflightContractError(PERMIT_INVALID)
    if drift_status != PASS or authority != CHECK_PASSED:
        return NOT_EVALUATED, 0
    if _repository_sha() != permit.repository_sha:
        raise PreflightContractError(REPOSITORY_HEAD_MISMATCH)
    migration = next(
        (
            entry
            for entry in manifest.migrations_for_profile(target.profile)
            if entry.timestamp == permit.migration_timestamp
        ),
        None,
    )
    if migration is None:
        raise PreflightContractError(PERMIT_INVALID)
    return _migration_parity(target, migration, expected_history)


def run_preflight(permit_path: Path | str) -> PreflightReport:
    """Execute CQ-03D-01 with no caller-overridable connector or subprocess runner."""
    manifest = load_and_validate_manifest()
    permit = load_preflight_permit(permit_path, manifest)
    repository_sha = _repository_sha()
    if permit.repository_sha != repository_sha:
        raise PreflightContractError(REPOSITORY_HEAD_MISMATCH)
    binding_value = os.environ.get(TARGET_BINDINGS_ENV)
    inspection_value = os.environ.get(INSPECTION_DATABASE_URL_ENV)
    if not binding_value or not inspection_value:
        raise TargetIdentityError()
    binding_path = Path(binding_value)
    inspection_route = _supabase_route_identity(inspection_value)
    target = _verified_target(manifest, permit, binding_path, inspection_route)
    runtime_routes = _runtime_routes(target)
    drift = _evaluate_verified_drift(inspection_route, runtime_routes, target, manifest, permit)
    authority = _runtime_authority(runtime_routes)
    parity, parity_row_count = _evaluate_migration_parity(manifest, target, permit, drift.status, authority)

    if _repository_sha() != permit.repository_sha:
        raise PreflightContractError(REPOSITORY_HEAD_MISMATCH)

    status, preflight_reasons = _report_status(drift.status, authority, parity)
    reasons = tuple(sorted(set(drift.reason_codes + preflight_reasons)))
    evaluated = 1 + drift.evaluated_check_count + int(authority != NOT_EVALUATED) + int(parity != NOT_EVALUATED)
    return PreflightReport(
        status,
        reasons,
        repository_sha,
        manifest.sha256,
        target.profile,
        target.lineage,
        TARGET_FINGERPRINT_ALGORITHM,
        target.fingerprint,
        permit.migration_timestamp,
        CHECK_PASSED,
        drift.history,
        drift.catalog,
        drift.runtime_compatibility,
        authority,
        parity,
        drift.required_check_count + 3,
        evaluated,
        drift.application_owned_count,
        drift.provider_owned_count,
        drift.unknown_count,
        drift.expected_catalog_digest,
        drift.actual_catalog_digest,
        parity_row_count,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the no-DSN command-line surface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--permit-file", default=os.environ.get(PERMIT_FILE_ENV), type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Emit only a bounded public report or a fixed failure code."""
    arguments = _build_parser().parse_args(argv)
    if arguments.permit_file is None:
        print(PERMIT_INVALID, file=sys.stderr)
        return 1
    try:
        report = run_preflight(arguments.permit_file)
    except TargetIdentityError:
        print(TARGET_IDENTITY_INDETERMINATE, file=sys.stderr)
        return 1
    except PreflightContractError as exc:
        print(exc.reason_code, file=sys.stderr)
        return 1
    except LedgerContractError:
        print(EVALUATION_INCOMPLETE, file=sys.stderr)
        return 1
    except Exception:  # noqa: BLE001 - never expose provider exceptions or protected inputs
        print(EVALUATION_INCOMPLETE, file=sys.stderr)
        return 1
    print(json.dumps(report.as_public_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if report.status == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
