"""Unit contracts for the target-bound CQ-03D read-only preflight."""

from __future__ import annotations

import inspect
import json
import os
import subprocess  # nosec B404 - fixed-command test doubles only
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

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


def _collection_target(database_url: str) -> PlannedTarget:
    """Build the exact combined hosted target shape bound by Stage 1 authorization."""
    identity = (preflight.TARGET_ADAPTER_ID, PROJECT_REF, DATABASE_ID)
    return PlannedTarget(
        logical_targets=("auth", "graph", "coordination"),
        profile="combined",
        lineage="hosted-legacy-v1",
        execution_class="hosted",
        fingerprint="a" * 64,
        database_url=database_url,
        canonical_identity=identity,
    )


def _collection_run_target(tmp_path: Path, monkeypatch):
    """Configure one mock Stage 1 target and its approved identity inputs."""
    manifest = load_and_validate_manifest()
    target = _collection_target("postgresql://operator:secret@localhost:5432/postgres")
    route = preflight.RouteIdentity(target.database_url, PROJECT_REF)
    monkeypatch.setattr(preflight, "load_and_validate_manifest", lambda: manifest)
    monkeypatch.setattr(preflight, "_repository_sha", lambda: "1" * 40)
    monkeypatch.setattr(preflight, "_supabase_route_identity", lambda _value: route)
    monkeypatch.setattr(preflight, "_verified_target", lambda *_args: target)
    monkeypatch.setattr(preflight, "_runtime_routes", lambda _target: {key: route for key in target.logical_targets})
    monkeypatch.setenv(preflight.TARGET_BINDINGS_ENV, str(tmp_path / "bindings.json"))
    monkeypatch.setenv(preflight.INSPECTION_DATABASE_URL_ENV, target.database_url)


def _migration_parity_fixture(tmp_path: Path):
    """Build the shared local-only migration-list expectation for parity tests."""
    route = preflight._supabase_route_identity(_database_url(tmp_path))
    target = _target(route.database_url)
    manifest = load_and_validate_manifest()
    migration = manifest.migrations_for_profile("graph")[0]
    expected = tuple(
        (str(receipt["timestamp"]), str(receipt["name"]))
        for receipt in manifest.data["lineages"]["hosted-legacy-v1"]["receipts"]
    )
    rows = [{"local": "", "remote": timestamp, "time": ""} for timestamp, _name in expected]
    rows.append({"local": migration.timestamp, "remote": "", "time": ""})
    return route, target, manifest, migration, expected, rows


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


def _collection_authorization_document(repository_sha: str = "1" * 40) -> dict[str, object]:
    """Build one valid test-only Stage 1 authorization for the ratified target shape."""
    manifest = load_and_validate_manifest()
    return {
        "version": preflight.COLLECTION_AUTHORIZATION_VERSION,
        "state": "unused",
        "repository_sha": repository_sha,
        "manifest_sha256": manifest.sha256,
        "profile": preflight.COLLECTION_PROFILE,
        "lineage": preflight.COLLECTION_LINEAGE,
        "target_fingerprint_algorithm": TARGET_FINGERPRINT_ALGORITHM,
        "target_fingerprint": "a" * 64,
        "migration_timestamp": preflight.COLLECTION_MARKER,
        "expected_catalog_digest": manifest.catalog_digest_for_profile(preflight.COLLECTION_PROFILE),
        "operator": "test-operator",
        "ratifier": "test-ratifier",
        "approved_at": "2020-01-01T00:00:00Z",
        "expires_at": "2099-01-01T00:00:00Z",
        "scope": "read-only-evidence-collection",
    }


def _write_collection_authorization(tmp_path: Path, document: dict[str, object] | None = None) -> Path:
    """Write one owner-only test authorization file."""
    path = tmp_path / "collection-authorization.json"
    path.write_text(json.dumps(document or _collection_authorization_document()), encoding="utf-8")
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
    manifest = load_and_validate_manifest()

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.load_preflight_permit(path, manifest)


def test_collection_authorization_is_bound_to_the_ratified_profile_and_marker(tmp_path: Path) -> None:
    """Stage 1 accepts only the separately ratified combined hosted lineage and marker."""
    manifest = load_and_validate_manifest()
    document = _collection_authorization_document()
    authorization = preflight.load_collection_authorization(
        _write_collection_authorization(tmp_path, document),
        manifest,
        now=datetime(2026, 11, 21, 10, tzinfo=timezone.utc),
    )

    assert authorization.profile == "combined"
    assert authorization.lineage == "hosted-legacy-v1"
    assert authorization.migration_timestamp == "20260817153547"

    document["migration_timestamp"] = "0" * 14
    invalid_authorization_path = _write_collection_authorization(tmp_path, document)
    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.load_collection_authorization(
            invalid_authorization_path,
            manifest,
            now=datetime(2026, 11, 21, 10, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("case", ["expired", "scope", "operator", "ratifier", "consumed"])
def test_collection_authorization_rejects_invalid_approval_envelope(tmp_path: Path, case: str) -> None:
    """Expiry, scope, named approval, and final-state requirements fail closed."""
    manifest = load_and_validate_manifest()
    document = _collection_authorization_document()
    now = datetime(2026, 11, 21, 10, tzinfo=timezone.utc)
    if case == "expired":
        now = datetime(2100, 1, 1, tzinfo=timezone.utc)
    elif case == "scope":
        document["scope"] = "read-write"
    elif case == "operator":
        document["operator"] = ""
    elif case == "ratifier":
        document["ratifier"] = ""
    else:
        document["state"] = "consumed"
    path = _write_collection_authorization(tmp_path, document)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.load_collection_authorization(path, manifest, now=now)


def test_collection_authorization_concurrent_consumption_has_one_winner(tmp_path: Path, monkeypatch) -> None:
    """Concurrent invocations cannot both consume the same protected record."""
    path = _write_collection_authorization(tmp_path)
    manifest = load_and_validate_manifest()
    now = datetime(2026, 11, 21, 10, tzinfo=timezone.utc)
    validation_entered = Event()
    allow_first_to_finish = Event()
    real_validate = preflight._validated_collection_authorization
    validation_count = 0

    def pause_first_after_validation(document, current_manifest, current_now):
        """Hold the first consumer inside the lock while the competing call starts."""
        nonlocal validation_count
        validation_count += 1
        if validation_count == 1:
            validation_entered.set()
            assert allow_first_to_finish.wait(timeout=5)
        return real_validate(document, current_manifest, current_now)

    monkeypatch.setattr(preflight, "_validated_collection_authorization", pause_first_after_validation)

    def consume() -> str:
        """Race one authorization consumer and expose only its bounded outcome."""
        try:
            preflight.consume_collection_authorization(path, manifest, now=now)
        except preflight.PreflightContractError:
            return "rejected"
        return "consumed"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(consume)
            assert validation_entered.wait(timeout=5)
            second = executor.submit(consume)
            assert second.result(timeout=5) == "rejected"
            allow_first_to_finish.set()
            assert first.result(timeout=5) == "consumed"
    finally:
        allow_first_to_finish.set()

    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "consumed"


def test_collection_authorization_replace_failure_preserves_unused_json(tmp_path: Path, monkeypatch) -> None:
    """A failed atomic replacement leaves a complete, still-unused authorization."""
    path = _write_collection_authorization(tmp_path)
    manifest = load_and_validate_manifest()
    original = path.read_text(encoding="utf-8")
    monkeypatch.setattr(preflight.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace failed")))

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.consume_collection_authorization(path, manifest, now=datetime(2026, 11, 21, tzinfo=timezone.utc))

    assert path.read_text(encoding="utf-8") == original
    assert json.loads(original)["state"] == "unused"
    assert tuple(item.name for item in tmp_path.glob(".collection-authorization.json.*")) == (
        ".collection-authorization.json.lock",
    )


def test_collection_authorization_rejects_changed_record_before_consuming(tmp_path: Path) -> None:
    """A replaced authorization cannot be consumed by an invocation that loaded another record."""
    path = _write_collection_authorization(tmp_path)
    manifest = load_and_validate_manifest()
    expected = preflight.load_collection_authorization(path, manifest, now=datetime(2026, 11, 21, tzinfo=timezone.utc))
    replacement = _collection_authorization_document()
    replacement["operator"] = "replacement-operator"
    path.write_text(json.dumps(replacement), encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.consume_collection_authorization(
            path, manifest, expected, now=datetime(2026, 11, 21, tzinfo=timezone.utc)
        )

    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "unused"
    assert json.loads(path.read_text(encoding="utf-8"))["operator"] == "replacement-operator"


def test_collection_authorization_rejects_hard_link_alias(tmp_path: Path) -> None:
    """A replacement cannot leave a second filename with a reusable unused inode."""
    path = _write_collection_authorization(tmp_path)
    alias_path = tmp_path / "authorization-alias.json"
    try:
        os.link(path, alias_path)
    except OSError as exc:
        pytest.skip(f"hard-link creation unavailable: {exc}")

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.consume_collection_authorization(path, load_and_validate_manifest())

    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "unused"
    assert json.loads(alias_path.read_text(encoding="utf-8"))["state"] == "unused"


def test_collection_authorization_is_consumed_when_first_connection_fails(tmp_path: Path, monkeypatch) -> None:
    """A failed first connection still spends the authorization before any retry."""
    path = _write_collection_authorization(tmp_path)
    _collection_run_target(tmp_path, monkeypatch)

    def fail_connection(*_args, **_kwargs):
        """Represent the first database connection failure without making a network call."""
        raise TargetIdentityError()

    monkeypatch.setattr(preflight, "_connect_verified", fail_connection)
    with pytest.raises(TargetIdentityError):
        preflight.run_collection(path)

    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "consumed"


def test_collection_rechecks_sha_after_consumption_before_connecting(tmp_path: Path, monkeypatch) -> None:
    """A changed reviewed SHA consumes authorization and stops before connection."""
    path = _write_collection_authorization(tmp_path)
    _collection_run_target(tmp_path, monkeypatch)
    sha_values = ["1" * 40, "2" * 40]
    monkeypatch.setattr(preflight, "_repository_sha", lambda: sha_values.pop(0))
    monkeypatch.setattr(
        preflight,
        "_connect_verified",
        lambda *_args, **_kwargs: pytest.fail("a changed SHA must stop before the first connection"),
    )

    with pytest.raises(preflight.PreflightContractError, match=preflight.REPOSITORY_HEAD_MISMATCH):
        preflight.run_collection(path)

    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "consumed"


def test_collection_rejects_authorization_for_different_repository_sha_before_consumption(
    tmp_path: Path, monkeypatch
) -> None:
    """A stale authorization is rejected without spending it or connecting."""
    path = _write_collection_authorization(tmp_path)
    _collection_run_target(tmp_path, monkeypatch)
    monkeypatch.setattr(preflight, "_repository_sha", lambda: "2" * 40)
    consume = Mock(side_effect=AssertionError("a stale authorization must not be consumed"))
    monkeypatch.setattr(preflight, "consume_collection_authorization", consume)

    with pytest.raises(preflight.PreflightContractError, match=preflight.REPOSITORY_HEAD_MISMATCH):
        preflight.run_collection(path)

    consume.assert_not_called()
    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "unused"


def test_collection_rechecks_authorization_window_after_consumption(tmp_path: Path, monkeypatch) -> None:
    """An authorization that expires during pre-connect checks cannot start a connection."""
    path = _write_collection_authorization(tmp_path)
    _collection_run_target(tmp_path, monkeypatch)
    authorization = preflight.load_collection_authorization(
        path,
        load_and_validate_manifest(),
        now=datetime(2026, 11, 21, 10, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(preflight, "load_collection_authorization", lambda *_args: authorization)
    consumed = Mock(return_value=authorization)
    monkeypatch.setattr(preflight, "consume_collection_authorization", consumed)

    def expire_after_consumption(document, *, now):
        """Simulate expiry between atomic consumption and connection startup."""
        assert document == {
            "approved_at": authorization.approved_at,
            "expires_at": authorization.expires_at,
        }
        assert now is None
        raise preflight.PreflightContractError(preflight.PERMIT_INVALID)

    monkeypatch.setattr(
        preflight,
        "_validate_permit_window",
        expire_after_consumption,
    )

    def fail_expired_connection(_route, _target, before_connection=None, *, route_label=None):
        """Run the newly enforced window guard before rejecting a connection attempt."""
        before_connection()
        pytest.fail("an expired authorization must stop before the first connection")

    monkeypatch.setattr(preflight, "_connect_verified", fail_expired_connection)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.run_collection(path)

    consumed.assert_called_once()


def test_connect_verified_preserves_expired_collection_authorization(monkeypatch) -> None:
    """The per-connection approval guard retains its permit error instead of becoming identity drift."""
    route = preflight.RouteIdentity("postgresql://runtime@host/postgres", PROJECT_REF)
    target = _collection_target(route.database_url)
    connect = Mock()
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))

    def expired() -> None:
        """Reject a connection after the one-use approval expires."""
        raise preflight.PreflightContractError(preflight.PERMIT_INVALID)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight._connect_verified(route, target, expired)

    connect.assert_not_called()


def test_connect_verified_preserves_contract_errors_from_identity_proof(monkeypatch) -> None:
    """Identity proof must preserve bounded contract and target errors during cleanup."""
    route = preflight.RouteIdentity("postgresql://runtime@host/postgres", PROJECT_REF)
    target = _collection_target(route.database_url)
    connection = Mock()
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=Mock(return_value=connection)))

    for expected in (preflight.PreflightContractError(preflight.PERMIT_INVALID), TargetIdentityError()):
        monkeypatch.setattr(preflight, "_prove_live_database_identity", Mock(side_effect=expected))
        with pytest.raises(type(expected)) as captured:
            preflight._connect_verified(route, target)
        assert captured.value is expected

    assert connection.rollback.call_count == 2
    assert connection.close.call_count == 2


def test_connect_verified_sanitizes_unexpected_preconnection_guard_failure(monkeypatch, capsys) -> None:
    """Unexpected guard failures stop before connecting and emit the fixed identity diagnostic."""
    route = preflight.RouteIdentity("postgresql://runtime@host/postgres", PROJECT_REF)
    target = _collection_target(route.database_url)
    connect = Mock()
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    secret = "untrusted guard failure detail"

    def fail_guard() -> None:
        """Represent an unexpected protected pre-connection guard failure."""
        raise RuntimeError(secret)

    monkeypatch.setattr(
        preflight,
        "_run_selected_stage",
        lambda _arguments: preflight._connect_verified(route, target, fail_guard, route_label="inspection"),
    )

    assert preflight.main(()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"{preflight.TARGET_IDENTITY_INDETERMINATE}\n"
    assert secret not in captured.err
    connect.assert_not_called()


def test_collection_rechecks_authorization_window_before_each_connection(tmp_path: Path, monkeypatch) -> None:
    """An approval that expires between Stage 1 connections blocks the next connection."""
    path = _write_collection_authorization(tmp_path)
    _collection_run_target(tmp_path, monkeypatch)
    authorization = preflight.load_collection_authorization(
        path, load_and_validate_manifest(), now=datetime(2026, 11, 21, 10, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(preflight, "load_collection_authorization", lambda *_args: authorization)
    consumed = Mock(return_value=authorization)
    monkeypatch.setattr(preflight, "consume_collection_authorization", consumed)
    connection = MagicMock()
    connection_attempts = 0
    connections_opened = 0
    window_checks = 0

    def connect(_route, _target, before_connection=None, *, route_label=None):
        """Run the Stage 1 window guard before simulating a new connection."""
        nonlocal connection_attempts, connections_opened
        connection_attempts += 1
        before_connection()
        connections_opened += 1
        return connection

    def validate_window(_document, *, now):
        """Expire approval only when Stage 1 attempts its second connection."""
        nonlocal window_checks
        window_checks += 1
        assert now is None
        if window_checks == 2:
            raise preflight.PreflightContractError(preflight.PERMIT_INVALID)

    monkeypatch.setattr(preflight, "_validate_permit_window", validate_window)
    monkeypatch.setattr(preflight, "_connect_verified", connect)
    monkeypatch.setattr(preflight, "_psycopg_database_identity", lambda _connection: object())
    monkeypatch.setattr(preflight, "_retained_target_identity", lambda *_args: None)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight.run_collection(path)

    assert connection_attempts == 2
    assert connections_opened == 1
    assert window_checks == 2
    assert connection.close.call_count == 1
    consumed.assert_called_once()
    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "unused"


def test_collection_identity_failure_stops_all_evidence_queries(tmp_path: Path, monkeypatch) -> None:
    """A live identity failure prevents all five collection evidence checks."""
    path = _write_collection_authorization(tmp_path)
    _collection_run_target(tmp_path, monkeypatch)
    monkeypatch.setattr(
        preflight,
        "_connect_verified",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TargetIdentityError()),
    )

    def fail_if_evidence_runs(*_args, **_kwargs):
        """Fail if any post-identity evidence collector is reached."""
        pytest.fail("evidence checks must not run")

    for name in ("_evaluate_verified_drift", "_runtime_authority"):
        monkeypatch.setattr(preflight, name, fail_if_evidence_runs)

    with pytest.raises(TargetIdentityError):
        preflight.run_collection(path)

    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "consumed"


def test_collection_runtime_identity_mismatch_stops_authority_check(monkeypatch) -> None:
    """A runtime route identity failure is not downgraded to a later authority check."""
    target = _collection_target("postgresql://operator:secret@localhost:5432/postgres")
    route = preflight.RouteIdentity(target.database_url, PROJECT_REF)
    connection = MagicMock()
    monkeypatch.setattr(preflight, "_connect_verified", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(preflight, "_psycopg_database_identity", lambda _connection: object())
    monkeypatch.setattr(preflight, "_retained_target_identity", lambda *_args: None)
    verification_error = preflight._ConnectionVerificationError(preflight.CONNECTION_OPEN_FAILED, "graph")

    def fail_runtime_route(*_args):
        """Return a sanitized route error that the evaluator would otherwise downgrade."""
        raise verification_error

    monkeypatch.setattr(preflight, "_runtime_routes_compatible", fail_runtime_route)
    monkeypatch.setattr(preflight, "_prove_route", lambda *_args: None)

    def evaluate_after_identity_rollback(*_args, **kwargs):
        """The drift evaluator starts only after the identity transaction is released."""
        connection.rollback.assert_called_once()
        return _evaluate_runtime_callback(kwargs)

    monkeypatch.setattr(
        preflight,
        "evaluate_profile_drift",
        evaluate_after_identity_rollback,
    )

    manifest = load_and_validate_manifest()
    authorization = preflight.CollectionAuthorization(
        "1" * 40,
        manifest.sha256,
        "combined",
        "hosted-legacy-v1",
        "a" * 64,
        preflight.COLLECTION_MARKER,
        manifest.catalog_digest_for_profile("combined"),
        "operator",
        "ratifier",
        "2026-11-21T12:00:00Z",
        "2026-11-21T13:00:00Z",
    )

    def fail_authority(*_args):
        """Fail if runtime authority runs after runtime identity could not be proved."""
        pytest.fail("runtime authority must not follow a failed runtime identity proof")

    monkeypatch.setattr(preflight, "_runtime_authority", fail_authority)
    with pytest.raises(preflight._ConnectionVerificationError) as captured:
        preflight._evaluate_verified_drift(
            route,
            {key: route for key in target.logical_targets},
            target,
            manifest,
            authorization,
        )
    assert captured.value is verification_error
    assert captured.value.category == preflight.CONNECTION_OPEN_FAILED
    assert captured.value.route_label == "graph"
    connection.close.assert_called()


def test_collection_runtime_expiry_preserves_authorization_error(monkeypatch) -> None:
    """A runtime compatibility expiry remains an authorization failure."""
    target = _collection_target("postgresql://operator:secret@localhost:5432/postgres")
    route = preflight.RouteIdentity(target.database_url, PROJECT_REF)
    connection = MagicMock()
    monkeypatch.setattr(preflight, "_connect_verified", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(preflight, "_psycopg_database_identity", lambda _connection: object())
    monkeypatch.setattr(preflight, "_retained_target_identity", lambda *_args: None)
    monkeypatch.setattr(preflight, "_prove_route", lambda *_args: None)

    def expire_authorization(*_args):
        """Reject runtime compatibility after the approved window expires."""
        raise preflight.PreflightContractError(preflight.PERMIT_INVALID)

    def evaluate_runtime(*_args, **kwargs):
        """Model the drift evaluator treating callback failures as unavailable."""
        return _evaluate_runtime_callback(kwargs)

    monkeypatch.setattr(
        preflight,
        "_runtime_routes_compatible",
        expire_authorization,
    )
    monkeypatch.setattr(preflight, "evaluate_profile_drift", evaluate_runtime)

    manifest = load_and_validate_manifest()
    authorization = preflight.CollectionAuthorization(
        "1" * 40,
        manifest.sha256,
        "combined",
        "hosted-legacy-v1",
        "a" * 64,
        preflight.COLLECTION_MARKER,
        manifest.catalog_digest_for_profile("combined"),
        "operator",
        "ratifier",
        "2026-11-21T12:00:00Z",
        "2026-11-21T13:00:00Z",
    )
    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight._evaluate_verified_drift(
            route,
            {key: route for key in target.logical_targets},
            target,
            manifest,
            authorization,
        )

    connection.close.assert_called_once()


def _evaluate_runtime_callback(kwargs):
    """Model the drift evaluator swallowing runtime failures as unavailable evidence."""
    try:
        kwargs["runtime_check"]()
    except preflight.RuntimeCheckUnavailable:
        return SimpleNamespace(status=EVALUATION_INCOMPLETE)
    pytest.fail("the runtime identity failure should be represented as unavailable inside the evaluator")
    return None


def test_collection_uses_five_ratified_checks_without_migration_parity(tmp_path: Path, monkeypatch) -> None:
    """Collection reports only identity, history, catalog, compatibility, and authority."""

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            frozen = cls(2026, 11, 21, 12, 30, tzinfo=timezone.utc)
            return frozen if tz is not None else frozen.replace(tzinfo=None)

    monkeypatch.setattr(preflight, "datetime", FrozenDateTime)
    authorization = preflight.CollectionAuthorization(
        "1" * 40,
        load_and_validate_manifest().sha256,
        "combined",
        "hosted-legacy-v1",
        "2" * 64,
        preflight.COLLECTION_MARKER,
        load_and_validate_manifest().catalog_digest_for_profile("combined"),
        "operator",
        "ratifier",
        "2026-11-21T12:00:00Z",
        "2026-11-21T13:00:00Z",
    )
    manifest = load_and_validate_manifest()
    target = _collection_target("postgresql://operator:secret@localhost:5432/postgres")
    route = preflight.RouteIdentity(target.database_url, PROJECT_REF)
    drift = SimpleNamespace(
        status=PASS,
        reason_codes=(),
        history="PASSED",
        catalog="PASSED",
        runtime_compatibility="PASSED",
        required_check_count=3,
        evaluated_check_count=3,
        application_owned_count=1,
        provider_owned_count=0,
        protected_legacy_count=0,
        restricted_helper_count=0,
        unknown_count=0,
        expected_catalog_digest="a" * 64,
        actual_catalog_digest="a" * 64,
    )
    connection = MagicMock()
    monkeypatch.setattr(preflight, "load_and_validate_manifest", lambda: manifest)
    monkeypatch.setattr(preflight, "load_collection_authorization", lambda *_args: authorization)
    monkeypatch.setattr(preflight, "consume_collection_authorization", lambda *_args: authorization)
    monkeypatch.setattr(preflight, "_repository_sha", lambda: authorization.repository_sha)
    monkeypatch.setattr(preflight, "_supabase_route_identity", lambda _value: route)
    monkeypatch.setattr(preflight, "_verified_target", lambda *_args: target)
    monkeypatch.setattr(preflight, "_runtime_routes", lambda _target: {key: route for key in target.logical_targets})
    monkeypatch.setattr(preflight, "_connect_verified", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(preflight, "_psycopg_database_identity", lambda _connection: object())
    monkeypatch.setattr(preflight, "_retained_target_identity", lambda *_args: None)
    monkeypatch.setattr(preflight, "_evaluate_verified_drift", lambda *_args: drift)
    monkeypatch.setattr(preflight, "_runtime_authority", lambda *_args: CHECK_PASSED)
    monkeypatch.setattr(
        preflight,
        "expected_adoption_history",
        lambda *_args: tuple((str(index), "receipt") for index in range(6)),
    )
    monkeypatch.setattr(
        preflight,
        "_evaluate_migration_parity",
        lambda *_args: pytest.fail("collection must not evaluate migration parity"),
    )
    monkeypatch.setenv(preflight.TARGET_BINDINGS_ENV, str(tmp_path / "bindings.json"))
    monkeypatch.setenv(preflight.INSPECTION_DATABASE_URL_ENV, target.database_url)

    report = preflight.run_collection(tmp_path / "authorization.json")

    assert report.status == PASS
    assert report.required_check_count == report.evaluated_check_count == 5
    assert report.history_timestamp_count == 6
    assert "migration_parity" not in report.as_public_dict()
    connection.close.assert_called_once()


def test_permit_descriptor_closes_when_handle_creation_fails(tmp_path: Path, monkeypatch) -> None:
    """A failed descriptor-to-handle transfer cannot leak the protected permit FD."""
    path = _write_permit(tmp_path, _permit_document("1" * 40))
    closed: list[int] = []
    real_close = preflight.os.close

    def close(fd: int) -> None:
        """Record and close the descriptor opened by the production helper."""
        closed.append(fd)
        real_close(fd)

    def fail_fdopen(*_args, **_kwargs):
        """Model failure before ownership transfers to a file handle."""
        raise OSError("fdopen")

    monkeypatch.setattr(preflight.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(preflight.os, "close", close)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight._open_permit_handle(path)

    assert len(closed) == 1


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


def _stub_runtime_engines(monkeypatch):
    """Supply distinct live-identity doubles without contacting placeholder providers."""
    from urllib.parse import urlsplit

    from src.data import database as data_database
    from tests.unit.test_postgresql_topology import identity_engine

    engines = []

    def create(url):
        """Represent project-specific identities independent of credential text."""
        parsed = urlsplit(url)
        reference = (parsed.hostname or "") if (parsed.hostname or "").startswith("db.") else parsed.username or ""
        identifier = "99999" if "other" in reference or "ref2" in reference else "12345"
        engine = identity_engine(identifier=identifier)
        engines.append(engine)
        return engine

    monkeypatch.setattr(data_database, "create_engine_from_url", create)
    return engines


def test_runtime_helpers_force_read_only_and_check_every_credential(tmp_path: Path, monkeypatch) -> None:
    """Compatibility uses each runtime route and preserves the libpq options space."""
    _stub_runtime_engines(monkeypatch)
    routes = {
        component: preflight._supabase_route_identity(_database_url(tmp_path, pooler=component != "auth"))
        for component in ("auth", "graph", "coordination")
    }
    calls: list[tuple[str, str, bool | None]] = []
    monkeypatch.setattr(
        preflight,
        "_runtime_compatibility",
        lambda route, component, *, combined_topology=None, verified_session=None: calls.append(
            (component, route.database_url, combined_topology)
        ),
    )

    preflight._runtime_routes_compatible(routes)

    read_only_url = preflight._read_only_url(routes["auth"])
    assert "options=-c%20default_transaction_read_only%3Don" in read_only_url
    assert "options=-c+default_transaction_read_only%3Don" not in read_only_url
    assert parse_dsn(read_only_url)["options"] == "-c default_transaction_read_only=on"
    assert [component for component, _url, _combined in calls] == ["auth", "graph", "coordination"]


def test_auth_helper_import_isolated_from_production_application_settings(tmp_path: Path) -> None:
    """Standalone auth checks do not require unrelated production credentials."""
    read_only_url = preflight._read_only_url(preflight._supabase_route_identity(_database_url(tmp_path)))
    environment = dict(preflight.os.environ)
    for name in (
        "DATABASE_URL",
        "POSTGRES_URL",
        "COORDINATION_DATABASE_URL",
        "SECRET_KEY",
        "ADMIN_USERNAME",
    ):
        environment.pop(name, None)
    environment["ENV"] = "production"
    environment["FARDB_AUTH_RUNTIME_DATABASE_URL"] = read_only_url
    program = """
import os
from scripts import postgresql_preflight as preflight

read_only_url = os.environ["FARDB_AUTH_RUNTIME_DATABASE_URL"]
api_database = preflight._import_api_database(read_only_url)
assert api_database.DATABASE_URL == read_only_url
assert "DATABASE_URL" not in os.environ
assert os.environ["ENV"] == "production"
"""

    result = subprocess.run(  # noqa: S603  # nosec B603 - fixed interpreter and repository-owned import
        [sys.executable, "-c", program],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        cwd=preflight.REPOSITORY_ROOT,
    )

    assert result.returncode == 0, result.stderr


def test_graph_checks_do_not_import_auth_database(tmp_path: Path, monkeypatch) -> None:
    """Graph compatibility and authority have no API import-time dependency."""
    from src.data import database as data_database

    _stub_runtime_engines(monkeypatch)
    monkeypatch.setattr(data_database, "verify_database_schema", lambda _engine, **_kwargs: None)
    monkeypatch.setattr(data_database, "verify_runtime_database_authority", lambda _engine, **_kwargs: None)
    monkeypatch.setattr(
        preflight.importlib,
        "import_module",
        lambda _name: pytest.fail("graph compatibility imported auth database helpers"),
    )

    route = preflight._supabase_route_identity(_database_url(tmp_path, pooler=True))
    preflight._runtime_compatibility(route, "graph")
    assert preflight._runtime_authority({"graph": route}) == CHECK_PASSED


def test_runtime_route_incompatibility_propagates_as_drift_signal(tmp_path: Path, monkeypatch) -> None:
    """One incompatible runtime credential stops the aggregate compatibility callback."""
    _stub_runtime_engines(monkeypatch)
    routes = {
        component: preflight._supabase_route_identity(_database_url(tmp_path, pooler=component != "auth"))
        for component in ("auth", "graph", "coordination")
    }

    def check_route(_route, component: str, **_kwargs) -> None:
        """Model one component-specific runtime incompatibility."""
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
    candidate = mutation(_database_url(tmp_path))

    with pytest.raises(TargetIdentityError):
        preflight._supabase_route_identity(candidate)


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


@pytest.mark.parametrize(
    ("failure_stage", "expected_category"),
    [
        ("open", preflight.CONNECTION_OPEN_FAILED),
        ("session", preflight.READ_ONLY_SESSION_SETUP_FAILED),
        ("identity", preflight.LIVE_IDENTITY_VERIFICATION_FAILED),
    ],
)
def test_connection_failures_report_sanitized_stage_and_route(
    tmp_path: Path, monkeypatch, capsys, failure_stage: str, expected_category: str
) -> None:
    """Connection diagnostics identify a fixed stage without exposing provider errors."""
    secret = "provider-secret-must-not-appear"
    route = preflight.RouteIdentity(_database_url(tmp_path), PROJECT_REF)
    target = _target(route.database_url)

    class Cursor:
        """Raise a provider-like failure while proving live identity."""

        def __enter__(self):
            """Enter the cursor fixture."""
            return self

        def __exit__(self, *_args):
            """Leave the cursor fixture without suppressing failures."""
            return None

        def execute(self, _query: str) -> None:
            """Raise the fake provider exception."""
            raise RuntimeError(secret)

    class Connection:
        """Record cleanup and fail at the selected post-open stage."""

        def __init__(self) -> None:
            self.rollbacks = 0
            self.closed = False

        def set_session(self, **_kwargs) -> None:
            """Fail at session setup when selected by the fixture."""
            if failure_stage == "session":
                raise RuntimeError(secret)

        def cursor(self):
            """Open the identity proof cursor."""
            return Cursor()

        def rollback(self) -> None:
            """Record cleanup of the staged fake session."""
            self.rollbacks += 1

        def close(self) -> None:
            """Record closure of the staged fake session."""
            self.closed = True

    connection = Connection()

    def connect(*_args, **_kwargs):
        """Raise at connection open or return the staged fake session."""
        if failure_stage == "open":
            raise RuntimeError(secret)
        return connection

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    monkeypatch.setattr(
        preflight,
        "_run_selected_stage",
        lambda _arguments: preflight._connect_verified(route, target, route_label="inspection"),
    )

    assert preflight.main(()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"{preflight.TARGET_IDENTITY_INDETERMINATE} diagnostic={expected_category} route=inspection\n"
    )
    assert secret not in captured.out + captured.err
    if failure_stage != "open":
        assert connection.rollbacks == 1
        assert connection.closed


def test_missing_psycopg2_reports_sanitized_connection_open_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    """A missing driver produces the fixed open-stage diagnostic without import details."""
    route = preflight.RouteIdentity(_database_url(tmp_path), PROJECT_REF)
    target = _target(route.database_url)
    monkeypatch.setitem(sys.modules, "psycopg2", None)
    monkeypatch.setattr(
        preflight,
        "_run_selected_stage",
        lambda _arguments: preflight._connect_verified(route, target, route_label="inspection"),
    )

    assert preflight.main(()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"{preflight.TARGET_IDENTITY_INDETERMINATE} "
        f"diagnostic={preflight.CONNECTION_OPEN_FAILED} route=inspection\n"
    )


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
    target = _target(route.database_url)

    with pytest.raises(TargetIdentityError, match=preflight.TARGET_IDENTITY_INDETERMINATE):
        preflight._connect_verified(route, target)


def test_runtime_route_cleanup_failure_is_incomplete(tmp_path: Path, monkeypatch) -> None:
    """A route whose verified connection cannot close never counts as proved."""
    route = preflight._supabase_route_identity(_database_url(tmp_path))
    target = _target(route.database_url)

    class Connection:
        """Expose one deterministic close failure."""

        def close(self) -> None:
            """Fail the required cleanup invariant."""
            raise OSError("close failed")

    monkeypatch.setattr(preflight, "_connect_verified", lambda *_args, **_kwargs: Connection())

    with pytest.raises(preflight.PreflightContractError, match=preflight.EVALUATION_INCOMPLETE):
        preflight._prove_route(route, target)


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
    _route, target, _manifest, migration, expected_history, rows = _migration_parity_fixture(tmp_path)
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
    _route, target, _manifest, migration, expected_history, rows = _migration_parity_fixture(tmp_path)
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


def test_explicit_collection_argument_ignores_permit_environment_default(monkeypatch, capsys) -> None:
    """An explicit stage selector is not blocked by the other stage's environment default."""
    monkeypatch.setenv(preflight.PERMIT_FILE_ENV, "protected-permit.json")
    selected: list[Path] = []

    def run_collection(path: Path):
        """Record selected Stage 1 path and return a bounded successful report."""
        selected.append(path)
        return SimpleNamespace(status=PASS, as_public_dict=lambda: {"status": PASS})

    monkeypatch.setattr(preflight, "run_collection", run_collection)

    assert preflight.main(("--collection-authorization-file", "protected-authorization.json")) == 0
    assert selected == [Path("protected-authorization.json")]
    assert json.loads(capsys.readouterr().out)["status"] == PASS


def test_explicit_permit_argument_ignores_collection_environment_default(monkeypatch, capsys) -> None:
    """An explicit permit selector is not blocked by the collection environment default."""
    monkeypatch.setenv(preflight.COLLECTION_AUTHORIZATION_FILE_ENV, "protected-authorization.json")
    selected: list[Path] = []

    def run_preflight(path: Path):
        """Record selected permit-bound path and return a bounded successful report."""
        selected.append(path)
        return SimpleNamespace(status=PASS, as_public_dict=lambda: {"status": PASS})

    monkeypatch.setattr(preflight, "run_preflight", run_preflight)

    assert preflight.main(("--permit-file", "protected-permit.json")) == 0
    assert selected == [Path("protected-permit.json")]
    assert json.loads(capsys.readouterr().out)["status"] == PASS


def test_two_environment_defaults_without_explicit_selector_are_rejected(monkeypatch, capsys) -> None:
    """Ambiguous environment-only stage selection fails closed."""
    monkeypatch.setenv(preflight.PERMIT_FILE_ENV, "protected-permit.json")
    monkeypatch.setenv(preflight.COLLECTION_AUTHORIZATION_FILE_ENV, "protected-authorization.json")

    assert preflight.main(()) == 1
    assert capsys.readouterr().err.strip() == preflight.PERMIT_INVALID


def test_two_explicit_stage_arguments_are_rejected(monkeypatch, capsys) -> None:
    """The command cannot select collection and permit-bound execution together."""
    monkeypatch.delenv(preflight.PERMIT_FILE_ENV, raising=False)
    monkeypatch.delenv(preflight.COLLECTION_AUTHORIZATION_FILE_ENV, raising=False)

    assert preflight.main(("--permit-file", "permit.json", "--collection-authorization-file", "auth.json")) == 1
    assert capsys.readouterr().err.strip() == preflight.PERMIT_INVALID


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


def test_is_shared_physical_target_evaluates_project_ref() -> None:
    """_is_shared_physical_target returns True only when both non-empty project_refs match."""
    route_a = preflight.RouteIdentity("postgresql://user:pass@host:5432/postgres", "proj1234567890123456")
    route_b = preflight.RouteIdentity("postgresql://user2:pass2@host2:5432/postgres", "proj1234567890123456")
    route_c = preflight.RouteIdentity("postgresql://user3:pass3@host3:5432/postgres", "other123456789012345")
    route_empty = preflight.RouteIdentity("postgresql://user4:pass4@host4:5432/postgres", "")

    assert preflight._is_shared_physical_target(route_a, route_b) is True
    assert preflight._is_shared_physical_target(route_a, route_c) is False
    assert preflight._is_shared_physical_target(route_a, route_empty) is False
    assert preflight._is_shared_physical_target(route_a, None) is False
    assert preflight._is_shared_physical_target(None, route_b) is False
    assert preflight._is_shared_physical_target(None, None) is False

    # Same project_ref but different physical database paths
    route_diff_db = preflight.RouteIdentity("postgresql://user:pass@host:5432/otherdb", "proj1234567890123456")
    assert preflight._is_shared_physical_target(route_a, route_diff_db) is False

    # Database path normalisation (e.g. unquoted percent-encoding: /postgres vs /%70ostgres)
    route_encoded_db = preflight.RouteIdentity("postgresql://user:pass@host:5432/%70ostgres", "proj1234567890123456")
    assert preflight._is_shared_physical_target(route_a, route_encoded_db) is True


def test_runtime_routes_compatible_passes_combined_topology_based_on_route_identity(
    tmp_path: Path, monkeypatch
) -> None:
    """_runtime_routes_compatible passes combined_topology=True only when graph and coordination share target."""
    _stub_runtime_engines(monkeypatch)
    certificate = _certificate(tmp_path)
    url_shared = f"postgresql://user:pass@db.{PROJECT_REF}.supabase.co:5432/postgres?sslmode=verify-full&sslrootcert={certificate}"
    url_other = f"postgresql://user:pass@db.otherprojectref12345.supabase.co:5432/postgres?sslmode=verify-full&sslrootcert={certificate}"

    route_shared = preflight._supabase_route_identity(url_shared)
    route_other = preflight._supabase_route_identity(url_other)

    recorded_calls: list[tuple[str, bool | None]] = []
    monkeypatch.setattr(
        preflight,
        "_runtime_compatibility",
        lambda _route, component, *, combined_topology=None, verified_session=None: recorded_calls.append(
            (component, combined_topology)
        ),
    )

    # Combined topology: graph and coordination share project_ref
    preflight._runtime_routes_compatible({"graph": route_shared, "coordination": route_shared})
    assert recorded_calls == [("graph", True), ("coordination", True)]

    # Separated topology: graph and coordination have different project_ref
    recorded_calls.clear()
    preflight._runtime_routes_compatible({"graph": route_shared, "coordination": route_other})
    assert recorded_calls == [("graph", False), ("coordination", False)]


def test_runtime_authority_passes_combined_topology_to_verifier(monkeypatch) -> None:
    """_runtime_authority passes combined_topology to verify_runtime_database_authority."""
    from src.data import database as data_database

    engines = _stub_runtime_engines(monkeypatch)
    recorded_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        data_database,
        "verify_runtime_database_authority",
        lambda _engine, *, required_capabilities=(), combined_topology=None, verification_connection=None: recorded_calls.append(
            {"capabilities": required_capabilities, "combined_topology": combined_topology}
        ),
    )

    route_shared_1 = preflight.RouteIdentity(
        "postgresql://user1:pass@db.ref1.supabase.co:5432/postgres", "shared_project_ref1"
    )
    route_shared_2 = preflight.RouteIdentity(
        "postgresql://user2:pass@db.ref1.supabase.co:5432/postgres", "shared_project_ref1"
    )
    route_distinct = preflight.RouteIdentity(
        "postgresql://user3:pass@db.ref2.supabase.co:5432/postgres", "other_project_ref2"
    )

    monkeypatch.setattr(preflight, "_read_only_url", lambda r: r.database_url)

    # Shared targets -> combined_topology=True
    status = preflight._runtime_authority({"graph": route_shared_1, "coordination": route_shared_2})
    assert status == CHECK_PASSED
    assert len(recorded_calls) == 2
    assert all(c["combined_topology"] is True for c in recorded_calls)

    # Distinct targets -> combined_topology=False
    recorded_calls.clear()
    status = preflight._runtime_authority({"graph": route_shared_1, "coordination": route_distinct})
    assert status == CHECK_PASSED
    assert len(recorded_calls) == 2
    assert all(c["combined_topology"] is False for c in recorded_calls)
    assert sum(engine.dispose.call_count for engine in engines) == 4


def test_preflight_rejects_equal_project_routes_with_different_live_clusters(monkeypatch) -> None:
    """Provider names cannot override conflicting live cluster identities."""
    from src.data import database as data_database
    from tests.unit.test_postgresql_topology import identity_engine

    engines = [identity_engine(identifier="12345"), identity_engine(identifier="99999")]
    monkeypatch.setattr(data_database, "create_engine_from_url", lambda _url: engines.pop(0))
    monkeypatch.setattr(preflight, "_read_only_url", lambda route: route.database_url)
    route = preflight.RouteIdentity("postgresql://runtime@host/postgres", "same_project")
    with preflight._verified_non_auth_connections({"graph": route, "coordination": route}) as (sessions, combined):
        assert len(sessions) == 2
        assert combined is False


def test_preflight_rejects_unavailable_live_identity(monkeypatch) -> None:
    """No readable identity means no authority verification or route fallback."""
    from src.data import database as data_database
    from tests.unit.test_postgresql_topology import identity_engine

    engine = identity_engine()
    engine.identity_connections[0].execute.side_effect = PermissionError("denied")
    monkeypatch.setattr(data_database, "create_engine_from_url", lambda _url: engine)
    monkeypatch.setattr(preflight, "_read_only_url", lambda route: route.database_url)
    verifier = Mock()
    monkeypatch.setattr(data_database, "verify_runtime_database_authority", verifier)
    route = preflight.RouteIdentity("postgresql://runtime@host/postgres", "same_project")
    assert preflight._runtime_authority({"graph": route}) == preflight.NOT_EVALUATED
    verifier.assert_not_called()
    engine.dispose.assert_called_once()


def test_runtime_authority_preserves_target_identity_failure(monkeypatch) -> None:
    """A later authority-stage identity failure remains a fail-closed identity error."""
    from src.data import database as data_database

    route = preflight.RouteIdentity("postgresql://runtime@host/postgres", "same_project")
    monkeypatch.setattr(
        preflight,
        "_verified_non_auth_connections",
        lambda *_args: nullcontext(({"graph": (Mock(), Mock())}, False)),
    )
    monkeypatch.setattr(
        data_database,
        "verify_runtime_database_authority",
        Mock(side_effect=TargetIdentityError()),
    )

    with pytest.raises(TargetIdentityError):
        preflight._runtime_authority({"graph": route})


def test_runtime_authority_preserves_expired_collection_window(monkeypatch) -> None:
    """An expired Stage 1 approval is not downgraded to unavailable authority evidence."""
    route = preflight.RouteIdentity("postgresql://runtime@host/postgres", "same_project")
    connection_context = MagicMock()
    connection_context.__enter__.side_effect = preflight.PreflightContractError(preflight.PERMIT_INVALID)
    monkeypatch.setattr(preflight, "_verified_non_auth_connections", lambda *_args: connection_context)

    with pytest.raises(preflight.PreflightContractError, match=preflight.PERMIT_INVALID):
        preflight._runtime_authority({"graph": route})


def test_preflight_preserves_union_for_identical_runtime_credentials(monkeypatch) -> None:
    """One combined credential must be verified once with both required capabilities."""
    from src.data import database as data_database

    engines = _stub_runtime_engines(monkeypatch)
    monkeypatch.setattr(preflight, "_read_only_url", lambda route: route.database_url)
    verifier = Mock()
    monkeypatch.setattr(data_database, "verify_runtime_database_authority", verifier)
    route = preflight.RouteIdentity("postgresql://runtime@db.shared.supabase.co/postgres", "shared")
    assert preflight._runtime_authority({"graph": route, "coordination": route}) == CHECK_PASSED
    assert len(engines) == 2
    verifier.assert_called_once_with(
        engines[0],
        required_capabilities={"graph", "coordination"},
        combined_topology=True,
        verification_connection=engines[0].identity_connections[0],
    )
    for engine in engines:
        engine.dispose.assert_called_once()


def test_preflight_rejects_identical_credentials_with_conflicting_live_identities(monkeypatch) -> None:
    """A routed credential yielding different clusters cannot acquire a combined scope."""
    from src.data import database as data_database
    from tests.unit.test_postgresql_topology import identity_engine

    engines = [identity_engine(identifier="12345"), identity_engine(identifier="99999")]
    monkeypatch.setattr(data_database, "create_engine_from_url", lambda _url: engines.pop(0))
    monkeypatch.setattr(preflight, "_read_only_url", lambda route: route.database_url)
    verifier = Mock()
    monkeypatch.setattr(data_database, "verify_runtime_database_authority", verifier)
    route = preflight.RouteIdentity("postgresql://runtime@db.shared.supabase.co/postgres", "shared")
    with pytest.raises(TargetIdentityError, match=preflight.TARGET_IDENTITY_INDETERMINATE):
        preflight._runtime_authority({"graph": route, "coordination": route})
    verifier.assert_not_called()


@pytest.mark.parametrize(
    "oid,identifier,name", [(16385, "12345", "postgres"), (16384, "99999", "postgres"), (16384, "12345", "other")]
)
def test_retained_session_must_match_permit_and_inspection_identity(tmp_path, monkeypatch, oid, identifier, name):
    """Rerouted sessions cannot verify even if both runtime credentials agree."""
    from src.data import database as data_database
    from src.data.postgresql_topology import DatabaseIdentity
    from tests.unit.test_postgresql_topology import identity_engine

    route = preflight._supabase_route_identity(_database_url(tmp_path))
    target = _target(route.database_url)
    monkeypatch.setattr(data_database, "create_engine_from_url", lambda _url: identity_engine(identifier, oid, name))
    _assert_context_entry_raises(
        preflight._verified_non_auth_connections(
            {"graph": route}, target, DatabaseIdentity("12345", int(DATABASE_ID), "postgres")
        ),
        preflight.TargetIdentityError,
    )


def test_auth_catalog_checks_reuse_permit_proved_connection(tmp_path, monkeypatch):
    """Auth schema and authority predicates cannot silently open a new session."""
    route = preflight._supabase_route_identity(_database_url(tmp_path))
    connection = Mock()
    api = Mock()
    api.bind_database_url.return_value = MagicMock()
    monkeypatch.setattr(preflight, "_import_api_database", lambda _url: api)
    preflight._runtime_compatibility(route, "auth", auth_connection=connection)
    api.verify_schema_compatibility.assert_called_once_with(verification_connection=connection)
    api.verify_runtime_access_catalog.assert_called_once_with(verification_connection=connection)


def test_auth_retained_session_rejects_reroute_before_verification(tmp_path, monkeypatch):
    """A valid earlier route probe cannot authorize a different retained cluster."""
    from src.data.postgresql_topology import DatabaseIdentity

    route = preflight._supabase_route_identity(_database_url(tmp_path))
    target = _target(route.database_url)
    connection = Mock()
    monkeypatch.setattr(
        preflight,
        "_connect_verified",
        lambda _route, _target, _before_connection=None, *, route_label=None: connection,
    )
    monkeypatch.setattr(
        preflight,
        "_psycopg_database_identity",
        lambda _connection: DatabaseIdentity("99999", int(DATABASE_ID), "postgres"),
    )
    _assert_context_entry_raises(
        preflight._verified_auth_connection(
            {"auth": route}, target, DatabaseIdentity("12345", int(DATABASE_ID), "postgres")
        ),
        preflight.TargetIdentityError,
    )
    connection.close.assert_called_once()


def _assert_context_entry_raises(context_manager, error_type: type[Exception]) -> None:
    """Assert a context manager rejects entry and close it if it unexpectedly enters."""
    try:
        context_manager.__enter__()
    except error_type:
        return
    context_manager.__exit__(None, None, None)
    pytest.fail(f"context entry should raise {error_type.__name__}")


def test_retained_session_accepts_exact_permit_identity(tmp_path, monkeypatch):
    """The catalog verifier receives the same session that proved the planned target."""
    from src.data import database as data_database
    from src.data.postgresql_topology import DatabaseIdentity
    from tests.unit.test_postgresql_topology import identity_engine

    route = preflight._supabase_route_identity(_database_url(tmp_path))
    target = _target(route.database_url)
    engine = identity_engine(name="postgres")
    monkeypatch.setattr(data_database, "create_engine_from_url", lambda _url: engine)
    verifier = Mock()
    monkeypatch.setattr(data_database, "verify_runtime_database_authority", verifier)
    assert (
        preflight._runtime_authority({"graph": route}, target, DatabaseIdentity("12345", int(DATABASE_ID), "postgres"))
        == CHECK_PASSED
    )
    assert verifier.call_args.kwargs["verification_connection"] is engine.identity_connections[0]
    engine.connect.assert_called_once()
    assert engine.identity_connections[0].execute.call_count == 2


def test_auth_authority_catalog_uses_retained_connection(monkeypatch) -> None:
    """Every auth-authority predicate, including final catalog checks, retains its proved session."""
    from api import database as api_database

    monkeypatch.setattr(api_database, "DATABASE_TYPE", "postgresql")
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.side_effect = [
        (True,),
        ("fardb_login_auth",),
        (1,),
        (True,),
        (True,),
        (True,),
        (True,),
        (True,),
        (True,),
        (True,),
    ]
    monkeypatch.setattr(api_database, "get_approved_login_principals", lambda _role: ("fardb_login_auth",))
    get_connection = Mock(side_effect=AssertionError("must retain verified connection"))
    monkeypatch.setattr(api_database, "get_connection", get_connection)
    api_database.verify_runtime_authority(verification_connection=connection)
    get_connection.assert_not_called()
    assert connection.cursor.call_count > 3


def test_psycopg_identity_query_failure_is_classified() -> None:
    """Denied control-file access keeps the documented failure classification."""
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = PermissionError("pg_control_system denied")
    with pytest.raises(TargetIdentityError, match=preflight.TARGET_IDENTITY_INDETERMINATE):
        preflight._psycopg_database_identity(connection)
