"""Unit contracts for the target-bound CQ-03D read-only preflight."""

from __future__ import annotations

import inspect
import json
import subprocess  # nosec B404 - fixed-command test doubles only
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from psycopg2.extensions import parse_dsn

from scripts import postgresql_preflight as preflight
from scripts.postgresql_drift import (
    CHECK_DRIFT,
    CHECK_PASSED,
    DRIFT_DETECTED,
    EVALUATION_INCOMPLETE,
    PASS,
    RuntimeCompatibilityMismatch,
)
from scripts.postgresql_ledger import (
    TARGET_FINGERPRINT_ALGORITHM,
    PlannedTarget,
    SupabaseCliError,
    TargetIdentityError,
    load_and_validate_manifest,
    target_fingerprint,
)

pytestmark = pytest.mark.unit

PROJECT_REF = "abcdefghijklmnopqrst"
DATABASE_ID = "16384"


def _certificate(tmp_path: Path) -> Path:
    """Create one non-secret test trust root path."""
    certificate = tmp_path / "root.crt"
    certificate.write_text("test trust root\n", encoding="utf-8")
    return certificate


def _database_url(tmp_path: Path, *, pooler: bool = False) -> str:
    """Build one documented Supabase direct or session-pooler route."""
    certificate = _certificate(tmp_path)
    if pooler:
        host = "aws-0-eu-west-2.pooler.supabase.com"
        username = f"fardb_runtime_graph.{PROJECT_REF}"
    else:
        host = f"db.{PROJECT_REF}.supabase.co"
        username = "postgres"
    return f"postgresql://{username}:secret@{host}:5432/postgres" f"?sslmode=verify-full&sslrootcert={certificate}"


def _target(database_url: str) -> PlannedTarget:
    """Build a protected hosted target bound to the production adapter identity."""
    identity = (preflight.TARGET_ADAPTER_ID, PROJECT_REF, DATABASE_ID)
    return PlannedTarget(
        logical_targets=("graph",),
        profile="graph",
        lineage="hosted-legacy-v1",
        execution_class="hosted",
        fingerprint=target_fingerprint(*identity),
        database_url=database_url,
        canonical_identity=identity,
    )


def _permit_document(repository_sha: str, profile: str = "graph") -> dict[str, object]:
    """Build one valid, protected permit document."""
    manifest = load_and_validate_manifest()
    migration = manifest.migrations_for_profile(profile)[0]
    return {
        "version": preflight.PREFLIGHT_PERMIT_VERSION,
        "state": "approved",
        "repository_sha": repository_sha,
        "manifest_sha256": manifest.sha256,
        "profile": profile,
        "lineage": "hosted-legacy-v1",
        "target_fingerprint_algorithm": TARGET_FINGERPRINT_ALGORITHM,
        "target_fingerprint": "a" * 64,
        "migration_timestamp": migration.timestamp,
        "expected_catalog_digest": manifest.catalog_digest_for_profile(profile),
        "history_only": True,
        "ddl_authorized": False,
        "ratifier": "repository-owner",
        "approved_at": "2026-08-18T09:00:00Z",
        "expires_at": "2026-08-18T11:00:00Z",
        "evidence": {
            "cq03b": "passed",
            "cq03c": "passed",
            "history": "reviewed",
            "runtime_compatibility": "reviewed",
            "runtime_authority": "reviewed",
        },
    }


def _write_permit(tmp_path: Path, document: dict[str, object]) -> Path:
    """Write one exact owner-only test permit."""
    path = tmp_path / "permit.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)
    return path


def test_permit_binds_one_current_marker_and_exact_repository_state(tmp_path: Path) -> None:
    """The protected permit validates exact head, manifest, profile, and next marker fields."""
    manifest = load_and_validate_manifest()
    document = _permit_document("1" * 40)
    permit = preflight.load_preflight_permit(
        _write_permit(tmp_path, document),
        manifest,
        now=datetime(2026, 8, 18, 10, tzinfo=timezone.utc),
    )

    assert permit.repository_sha == "1" * 40
    assert permit.migration_timestamp == manifest.migrations_for_profile("graph")[0].timestamp
    assert permit.lineage == "hosted-legacy-v1"


def test_permit_rejects_duplicate_raw_json_keys(tmp_path: Path) -> None:
    """A protected JSON parser cannot silently accept the last duplicate value."""
    path = tmp_path / "permit.json"
    path.write_text('{"version":"first","version":"second"}', encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.load_preflight_permit(path, load_and_validate_manifest())


def test_permit_descriptor_closes_when_handle_creation_fails(tmp_path: Path, monkeypatch) -> None:
    """A failed descriptor-to-handle transfer cannot leak the protected permit FD."""
    path = _write_permit(tmp_path, _permit_document("1" * 40))
    descriptor = preflight.os.open(path, preflight.os.O_RDONLY)
    closed: list[int] = []
    real_close = preflight.os.close

    def close(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    def fail_fdopen(*_args, **_kwargs):
        """Model failure before ownership transfers to a file handle."""
        raise OSError("fdopen")

    monkeypatch.setattr(preflight.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(preflight.os, "close", close)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight._decode_permit_document(descriptor)

    assert closed == [descriptor]


@pytest.mark.parametrize("case", ["mode", "symlink", "symlink-loop", "expired", "ddl", "evidence", "marker"])
def test_permit_fails_closed_on_ambiguous_or_excess_authority(tmp_path: Path, case: str) -> None:
    """Permissions, validity, authority, evidence, and marker ambiguity all use one code."""
    manifest = load_and_validate_manifest()
    document = _permit_document("1" * 40)
    now = datetime(2026, 8, 18, 10, tzinfo=timezone.utc)
    if case == "expired":
        now = datetime(2026, 8, 18, 12, tzinfo=timezone.utc)
    elif case == "ddl":
        document["ddl_authorized"] = True
    elif case == "evidence":
        evidence = document["evidence"]
        assert isinstance(evidence, dict)
        del evidence["history"]
    elif case == "marker":
        document["migration_timestamp"] = "0" * 14
    path = _write_permit(tmp_path, document)
    if case == "mode":
        path.chmod(0o644)
    elif case == "symlink":
        target = tmp_path / "permit-target.json"
        path.rename(target)
        path.symlink_to(target)
    elif case == "symlink-loop":
        path.unlink()
        path.symlink_to(path)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.load_preflight_permit(path, manifest, now=now)


def test_supabase_adapter_accepts_only_direct_or_session_pooler_verify_full(tmp_path: Path) -> None:
    """Both documented routes resolve one protected project namespace."""
    direct = preflight._supabase_route_identity(_database_url(tmp_path))
    pooler = preflight._supabase_route_identity(_database_url(tmp_path, pooler=True))

    assert direct.project_ref == PROJECT_REF
    assert pooler.project_ref == PROJECT_REF
    assert direct.database_url.startswith("postgresql://")


def test_supabase_adapter_rejects_replaceable_trust_root(tmp_path: Path) -> None:
    """A group/other-writable CA file cannot anchor a protected route."""
    database_url = _database_url(tmp_path)
    (tmp_path / "root.crt").chmod(0o666)

    with pytest.raises(TargetIdentityError):
        preflight._supabase_route_identity(database_url)


def test_runtime_helpers_force_read_only_and_check_every_credential(tmp_path: Path, monkeypatch) -> None:
    """Compatibility uses each runtime route and preserves the libpq options space."""
    routes = {
        component: preflight._supabase_route_identity(_database_url(tmp_path, pooler=component != "auth"))
        for component in ("auth", "graph", "coordination")
    }
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        preflight,
        "_runtime_compatibility",
        lambda route, component: calls.append((component, route.database_url)),
    )

    preflight._runtime_routes_compatible(routes)

    read_only_url = preflight._read_only_url(routes["auth"])
    assert "options=-c%20default_transaction_read_only%3Don" in read_only_url
    assert "options=-c+default_transaction_read_only%3Don" not in read_only_url
    assert parse_dsn(read_only_url)["options"] == "-c default_transaction_read_only=on"
    assert [component for component, _url in calls] == ["auth", "graph", "coordination"]


def test_runtime_route_incompatibility_propagates_as_drift_signal(tmp_path: Path, monkeypatch) -> None:
    """One incompatible runtime credential stops the aggregate compatibility callback."""
    routes = {
        component: preflight._supabase_route_identity(_database_url(tmp_path, pooler=component != "auth"))
        for component in ("auth", "graph", "coordination")
    }

    def check_route(_route, component: str) -> None:
        if component == "graph":
            raise RuntimeCompatibilityMismatch()

    monkeypatch.setattr(preflight, "_runtime_compatibility", check_route)

    with pytest.raises(RuntimeCompatibilityMismatch):
        preflight._runtime_routes_compatible(routes)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.replace(":5432/", ":6543/"),
        lambda value: value.replace("sslmode=verify-full", "sslmode=require"),
        lambda value: value + "&options=-c%20default_transaction_read_only%3Doff",
        lambda value: value.replace("db.abcdefghijklmnopqrst.supabase.co", "database.example.com"),
    ],
)
def test_supabase_adapter_rejects_unapproved_routing_or_tls(tmp_path: Path, mutation) -> None:
    """Transaction pooling, weak TLS, caller options, and unknown hosts fail identity."""
    with pytest.raises(TargetIdentityError):
        preflight._supabase_route_identity(mutation(_database_url(tmp_path)))


def test_live_database_oid_is_bound_to_the_protected_fingerprint(tmp_path: Path, monkeypatch) -> None:
    """The same connection proves read-only posture, live OID, and canonical identity."""

    class Cursor:
        """Return one immutable database OID."""

        def __enter__(self):
            """Enter the cursor fixture."""
            return self

        def __exit__(self, *_args):
            """Leave the cursor fixture without suppressing errors."""
            return None

        def execute(self, query: str) -> None:
            """Record the immutable catalog query."""
            assert "pg_catalog.pg_database" in query

        def fetchall(self):
            """Return one positive database OID."""
            return [(DATABASE_ID,)]

    class Connection:
        """Record transaction safety and cleanup."""

        def __init__(self) -> None:
            self.session: tuple[bool, bool] | None = None
            self.rollbacks = 0
            self.closed = False

        def set_session(self, *, readonly: bool, autocommit: bool) -> None:
            """Record the required read-only transaction posture."""
            self.session = (readonly, autocommit)

        def cursor(self):
            """Open the catalog cursor fixture."""
            return Cursor()

        def rollback(self) -> None:
            """Record transaction rollback."""
            self.rollbacks += 1

        def close(self) -> None:
            """Record connection close."""
            self.closed = True

    connection = Connection()
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=lambda *_args, **_kwargs: connection))
    route = preflight._supabase_route_identity(_database_url(tmp_path))

    returned = preflight._connect_verified(route, _target(route.database_url))

    assert returned is connection
    assert connection.session == (True, False)
    assert connection.rollbacks == 1


def test_live_database_oid_mismatch_fails_before_checks(tmp_path: Path, monkeypatch) -> None:
    """An attested binding for another database cannot authorize this route."""

    class Connection:
        """Provide the minimum mismatched identity connection surface."""

        def set_session(self, **_kwargs) -> None:
            """Accept the read-only session request."""
            return None

        def rollback(self) -> None:
            """Model rollback after rejected identity."""
            return None

        def close(self) -> None:
            """Model close after rejected identity."""
            return None

    class Cursor:
        """Return a live OID that mismatches the protected binding."""

        def __enter__(self):
            """Enter the cursor fixture."""
            return self

        def __exit__(self, *_args):
            """Leave the cursor fixture without suppressing errors."""
            return None

        def execute(self, _query: str) -> None:
            """Accept the fixed catalog query."""
            return None

        def fetchall(self):
            """Return the mismatched database OID."""
            return [("99999",)]

    connection = Connection()
    connection.cursor = Cursor  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=lambda *_args, **_kwargs: connection))
    route = preflight._supabase_route_identity(_database_url(tmp_path))

    with pytest.raises(TargetIdentityError, match=preflight.TARGET_IDENTITY_INDETERMINATE):
        preflight._connect_verified(route, _target(route.database_url))


def test_runtime_route_cleanup_failure_is_incomplete(tmp_path: Path, monkeypatch) -> None:
    """A route whose verified connection cannot close never counts as proved."""
    route = preflight._supabase_route_identity(_database_url(tmp_path))

    class Connection:
        """Expose one deterministic close failure."""

        def close(self) -> None:
            """Fail the required cleanup invariant."""
            raise OSError("close failed")

    monkeypatch.setattr(preflight, "_connect_verified", lambda *_args: Connection())

    with pytest.raises(preflight.PreflightContractError, match=preflight.EVALUATION_INCOMPLETE):
        preflight._prove_route(route, _target(route.database_url))


def test_preflight_cli_allowlist_is_migration_list_only(tmp_path: Path) -> None:
    """No dry-run, repair, push, reset, link, or implicit target command is accepted."""
    route = preflight._supabase_route_identity(_database_url(tmp_path))
    target = _target(route.database_url)
    allowed = (
        "--workdir",
        "/private/projection",
        "--yes",
        "--output-format",
        "json",
        "migration",
        "list",
        "--db-url",
        target.database_url,
    )

    preflight.assert_allowed_preflight_command(allowed, target)
    with pytest.raises(SupabaseCliError):
        preflight.assert_allowed_preflight_command(
            allowed[:-4] + ("db", "push", "--db-url", target.database_url), target
        )


@pytest.mark.parametrize(
    "stdout",
    (
        "not-json",
        '{"data":{"migrations":{}}}',
        '{"data":{"migrations":[{"local":"1","remote":"","extra":""}]}}',
        '{"data":{"migrations":[{"local":1,"remote":"","time":""}]}}',
    ),
)
def test_migration_list_parser_rejects_unbounded_or_malformed_rows(stdout: str) -> None:
    """Unexpected provider output is unavailable evidence, never partial parity proof."""
    assert preflight._migration_list_rows(stdout) is None


def test_migration_parity_projects_only_permit_and_requires_exact_remote_prefix(tmp_path: Path, monkeypatch) -> None:
    """Pinned CLI parity accepts legacy remote rows plus one local-only marker."""
    route = preflight._supabase_route_identity(_database_url(tmp_path))
    target = _target(route.database_url)
    manifest = load_and_validate_manifest()
    migration = manifest.migrations_for_profile("graph")[0]
    expected_history = tuple(
        (str(receipt["timestamp"]), str(receipt["name"]))
        for receipt in manifest.data["lineages"]["hosted-legacy-v1"]["receipts"]
    )
    rows = [{"local": "", "remote": timestamp, "time": ""} for timestamp, _name in expected_history]
    rows.append({"local": migration.timestamp, "remote": "", "time": ""})
    commands: list[tuple[str, ...]] = []

    monkeypatch.setattr(preflight, "_resolve_supabase_cli", lambda: "/bin/supabase")
    monkeypatch.setattr(preflight, "require_pinned_supabase_cli", lambda *_args, **_kwargs: None)

    def run_cli(command, _environment, *, timeout_seconds):
        """Return the bounded pinned-CLI history fixture."""
        commands.append(tuple(command))
        assert timeout_seconds == 60
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"data": {"migrations": rows}}), stderr="")

    monkeypatch.setattr(preflight, "_run_cli", run_cli)

    state, count = preflight._migration_parity(target, migration, expected_history)

    assert (state, count) == (CHECK_PASSED, len(rows))
    assert commands[0][-4:-2] == ("migration", "list")
    assert "push" not in commands[0]
    assert "--dry-run" not in commands[0]


def test_migration_parity_cleanup_failure_is_incomplete(tmp_path: Path, monkeypatch) -> None:
    """A CLI state directory that cannot be cleaned up prevents a passing result."""
    route = preflight._supabase_route_identity(_database_url(tmp_path))
    target = _target(route.database_url)
    manifest = load_and_validate_manifest()
    migration = manifest.migrations_for_profile("graph")[0]
    expected_history = tuple(
        (str(receipt["timestamp"]), str(receipt["name"]))
        for receipt in manifest.data["lineages"]["hosted-legacy-v1"]["receipts"]
    )
    rows = [{"local": "", "remote": timestamp, "time": ""} for timestamp, _name in expected_history]
    rows.append({"local": migration.timestamp, "remote": "", "time": ""})
    real_rmtree = preflight.shutil.rmtree

    monkeypatch.setattr(preflight, "_resolve_supabase_cli", lambda: "/bin/supabase")
    monkeypatch.setattr(preflight, "require_pinned_supabase_cli", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        preflight,
        "_run_cli",
        lambda command, _environment, *, timeout_seconds: subprocess.CompletedProcess(
            command, 0, stdout=json.dumps({"data": {"migrations": rows}}), stderr=""
        ),
    )

    def cleanup_then_fail(path: Path, *args, **kwargs) -> None:
        """Remove the fixture while modeling an operator-visible cleanup failure."""
        real_rmtree(path, *args, **kwargs)
        if "fardb-cq03d-supabase-home-" in str(path):
            raise OSError("cleanup failed")

    monkeypatch.setattr(preflight.shutil, "rmtree", cleanup_then_fail)

    with pytest.raises(preflight.PreflightContractError, match=preflight.EVALUATION_INCOMPLETE):
        preflight._migration_parity(target, migration, expected_history)


def test_preflight_status_and_public_surface_fail_closed() -> None:
    """The public runner exposes no connector/runner override and preserves gate order."""
    assert tuple(inspect.signature(preflight.run_preflight).parameters) == ("permit_path",)
    assert preflight._report_status(PASS, CHECK_PASSED, CHECK_PASSED) == (PASS, ())
    assert preflight._report_status(PASS, CHECK_DRIFT, preflight.NOT_EVALUATED) == (
        DRIFT_DETECTED,
        (preflight.RUNTIME_AUTHORITY_MISMATCH,),
    )
    assert preflight._report_status(PASS, CHECK_PASSED, preflight.NOT_EVALUATED) == (
        EVALUATION_INCOMPLETE,
        (preflight.MIGRATION_PARITY_UNAVAILABLE,),
    )


def test_repository_state_rejects_unreviewed_worktree_changes(monkeypatch) -> None:
    """An exact HEAD cannot authorize locally modified or untracked preflight code."""
    results = [
        subprocess.CompletedProcess(("git",), 0, stdout="1" * 40 + "\n", stderr=""),
        subprocess.CompletedProcess(("git",), 0, stdout="?? scripts/substitute.py\n", stderr=""),
    ]

    def run(*_args, **_kwargs):
        """Return the next deterministic Git result."""
        return results.pop(0)

    monkeypatch.setattr(preflight.subprocess, "run", run)

    with pytest.raises(preflight.PreflightContractError, match=preflight.REPOSITORY_HEAD_MISMATCH):
        preflight._repository_sha()


def test_repository_state_ignores_caller_git_indirection(monkeypatch) -> None:
    """Permit SHA proof cannot be redirected through inherited Git control variables."""
    monkeypatch.setenv("GIT_DIR", "/attacker/repository/.git")
    results = [
        subprocess.CompletedProcess(("git",), 0, stdout="1" * 40 + "\n", stderr=""),
        subprocess.CompletedProcess(("git",), 0, stdout="", stderr=""),
    ]

    def run(*_args, **kwargs):
        """Return clean Git results after asserting environment sanitization."""
        assert "GIT_DIR" not in kwargs["env"]
        return results.pop(0)

    monkeypatch.setattr(preflight.subprocess, "run", run)

    assert preflight._repository_sha() == "1" * 40
