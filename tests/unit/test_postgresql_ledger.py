"""Contract tests for the profile-scoped PostgreSQL migration ledger."""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 - test double types for an allowlisted shell-free command
from pathlib import Path

import pytest

from scripts import postgresql_ledger as ledger
from src.data.database import POSTGRESQL_MANAGED_TABLES

pytestmark = pytest.mark.unit


def _copy_manifest(tmp_path: Path) -> Path:
    """Copy the canonical Supabase source tree into an isolated test root."""
    destination = tmp_path / "supabase"
    shutil.copytree(ledger.DEFAULT_MANIFEST_PATH.parent, destination)
    return destination / "ledger-profiles.json"


def _read_manifest(path: Path) -> dict:
    """Read a mutable manifest copy used only by negative tests."""
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(path: Path, value: dict) -> None:
    """Write deterministic JSON for a disposable negative-test fixture."""
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _migration_path(manifest_path: Path, component: str) -> Path:
    """Resolve one component's only baseline migration in a copied ledger."""
    value = _read_manifest(manifest_path)
    filename = value["components"][component]["migrations"][0]["filename"]
    return manifest_path.parent / "ledgers" / component / "migrations" / filename


def _replace_migration_bytes(manifest_path: Path, component: str, content: bytes) -> Path:
    """Replace test migration bytes and keep its manifest digest internally consistent."""
    migration_path = _migration_path(manifest_path, component)
    migration_path.write_bytes(content)
    value = _read_manifest(manifest_path)
    value["components"][component]["migrations"][0]["sha256"] = ledger.sha256_bytes(content)
    _write_manifest(manifest_path, value)
    return migration_path


def _binding_target(
    logical_target: str,
    *,
    profile: str | None = None,
    identity: str | None = None,
    lineage: str = "fresh-v1",
    execution_class: str = "loopback",
) -> dict[str, str]:
    """Build one synthetic protected target binding."""
    identity_value = identity or logical_target
    return {
        "logical_target": logical_target,
        "profile": profile or logical_target,
        "lineage": lineage,
        "execution_class": execution_class,
        "identity_assurance": "operator-attested-immutable-v1",
        "adapter_id": "postgresql-test-adapter-v1",
        "authority_namespace_id": f"namespace-{identity_value}",
        "database_id": f"database-{identity_value}",
    }


def _write_bindings(path: Path, manifest: ledger.LedgerManifest, targets: list[dict[str, str]]) -> Path:
    """Write a mode-0600 protected binding document."""
    document = {
        "binding_version": ledger.TARGET_BINDING_VERSION,
        "manifest_sha256": manifest.sha256,
        "target_fingerprint_algorithm": ledger.TARGET_FINGERPRINT_ALGORITHM,
        "targets": targets,
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def _planned_target(
    *,
    profile: str = "graph",
    database_url: str = "postgresql://operator:secret@localhost:5432/graph",
    lineage: str = "fresh-v1",
    execution_class: str = "loopback",
) -> ledger.PlannedTarget:
    """Build one synthetic execution plan entry."""
    logical_targets = ledger.LOGICAL_TARGET_ORDER if profile == "combined" else (profile,)
    return ledger.PlannedTarget(
        logical_targets=logical_targets,
        profile=profile,
        lineage=lineage,
        execution_class=execution_class,
        fingerprint="0" * 64,
        database_url=database_url,
    )


def test_manifest_and_profile_unions_are_deterministic() -> None:
    """The committed manifest must resolve exact, timestamp-ordered component unions."""
    manifest = ledger.load_and_validate_manifest()

    assert manifest.sha256 == "d3625e9af90eed107cc90d392557308b0c339d9c23d792381e9f1658e8ec03fb"
    assert (
        tuple(
            table_name
            for component in ledger.COMPONENT_ORDER
            for table_name in ledger.EXPECTED_MANAGED_TABLES[component]
        )
        == POSTGRESQL_MANAGED_TABLES
    )
    assert tuple(entry.component for entry in manifest.migrations_for_profile("combined")) == ledger.COMPONENT_ORDER
    for profile, components in ledger.EXPECTED_PROFILES.items():
        selected = manifest.migrations_for_profile(profile)
        assert tuple(entry.component for entry in selected) == components
        assert [entry.timestamp for entry in selected] == sorted(entry.timestamp for entry in selected)
        assert all(ledger.sha256_bytes(entry.path.read_bytes()) == entry.sha256 for entry in selected)


def test_digest_algorithms_have_stable_unicode_vectors() -> None:
    """Statement and target digests must use exact bytes and NFC-normalized identity."""
    assert ledger.provider_statements_digest(["SELECT 1;", "SELECT 'é';"]) == (
        "7f6053a44754bf5af2d9f1a76c5391414974242f90c7ce89119f9e43d1b59f73"
    )
    assert ledger.target_fingerprint("adapter", "namespace", "database") == (
        "66a0aaa8ea5c960d771b1018500a01379ebd93676c3b2d9971a4d4ad22bda0a8"
    )
    assert ledger.target_fingerprint("adapte\u0301r", "namespace", "database") == ledger.target_fingerprint(
        "adaptér", "namespace", "database"
    )


@pytest.mark.parametrize(
    "value", [None, "", " padded", "padded ", "line\nfeed", "next\u0085line", "delete\x7f", "\ud800"]
)
def test_target_identity_rejects_indeterminate_values(value: object) -> None:
    """Missing, ambiguous, control-bearing, and non-UTF-8 identities fail closed."""
    with pytest.raises(ledger.TargetIdentityError, match=ledger.TARGET_IDENTITY_INDETERMINATE):
        ledger.target_fingerprint(value, "namespace", "database")


@pytest.mark.parametrize(
    "mutation",
    [
        "digest",
        "extra-file",
        "missing-file",
        "symlink",
        "component-symlink",
        "path-traversal",
        "bad-utf8",
        "forbidden-sql",
        "global-timestamp",
    ],
)
def test_manifest_rejects_migration_tampering(tmp_path: Path, mutation: str) -> None:
    """Every migration byte, path, identity, and directory entry is immutable."""
    manifest_path = _copy_manifest(tmp_path)
    graph_path = _migration_path(manifest_path, "graph")

    if mutation == "digest":
        graph_path.write_bytes(graph_path.read_bytes() + b"\n")
    elif mutation == "extra-file":
        graph_path.with_name("unexpected.sql").write_text("SELECT 1;\n", encoding="utf-8")
    elif mutation == "missing-file":
        graph_path.unlink()
    elif mutation == "symlink":
        external = tmp_path / "external.sql"
        external.write_bytes(graph_path.read_bytes())
        graph_path.unlink()
        graph_path.symlink_to(external)
    elif mutation == "component-symlink":
        component_directory = graph_path.parents[1]
        external_component = tmp_path / "external-graph"
        shutil.copytree(component_directory, external_component)
        shutil.rmtree(component_directory)
        component_directory.symlink_to(external_component, target_is_directory=True)
    elif mutation == "path-traversal":
        value = _read_manifest(manifest_path)
        value["components"]["graph"]["migrations"][0]["filename"] = "../escape.sql"
        _write_manifest(manifest_path, value)
    elif mutation == "bad-utf8":
        _replace_migration_bytes(manifest_path, "graph", b"BEGIN;\n\xff\nCOMMIT;\n")
    elif mutation == "forbidden-sql":
        _replace_migration_bytes(manifest_path, "graph", b"BEGIN;\nCREATE ROLE unsafe;\nCOMMIT;\n")
    else:
        value = _read_manifest(manifest_path)
        graph_entry = value["components"]["graph"]["migrations"][0]
        coordination_entry = value["components"]["coordination"]["migrations"][0]
        old_path = _migration_path(manifest_path, "coordination")
        new_filename = graph_entry["filename"].replace("graph", "coordination")
        new_path = old_path.with_name(new_filename)
        old_path.rename(new_path)
        coordination_entry["timestamp"] = graph_entry["timestamp"]
        coordination_entry["filename"] = new_filename
        _write_manifest(manifest_path, value)

    with pytest.raises(ledger.LedgerContractError):
        ledger.load_and_validate_manifest(manifest_path)


def test_sql_guard_ignores_forbidden_words_in_comments_and_quoted_values(tmp_path: Path) -> None:
    """Guardrail keywords have authority only when they are executable SQL tokens."""
    manifest_path = _copy_manifest(tmp_path)
    _replace_migration_bytes(
        manifest_path,
        "graph",
        b"""BEGIN;
-- CREATE ROLE ignored_line_comment;
/* DROP TABLE ignored_block_comment; */
SELECT 'ALTER ROLE ignored_string; IF EXISTS; supabase_migrations';
SELECT $$DROP SCHEMA ignored_dollar_quote;$$;
COMMIT;
""",
    )

    ledger.load_and_validate_manifest(manifest_path)


def test_sql_guard_rejects_quoted_provider_history_identifier(tmp_path: Path) -> None:
    """Quoting the provider-history schema cannot bypass its write guard."""
    manifest_path = _copy_manifest(tmp_path)
    _replace_migration_bytes(
        manifest_path,
        "graph",
        b'BEGIN;\nDELETE FROM "supabase_migrations".schema_migrations;\nCOMMIT;\n',
    )

    with pytest.raises(ledger.LedgerContractError, match="forbidden conditional or authority SQL"):
        ledger.load_and_validate_manifest(manifest_path)


def test_sql_guard_rejects_forbidden_keywords_separated_by_comments(tmp_path: Path) -> None:
    """Comments cannot split a forbidden executable keyword sequence."""
    manifest_path = _copy_manifest(tmp_path)
    _replace_migration_bytes(manifest_path, "graph", b"BEGIN;\nCREATE/**/ROLE unsafe;\nCOMMIT;\n")

    with pytest.raises(ledger.LedgerContractError, match="forbidden conditional or authority SQL"):
        ledger.load_and_validate_manifest(manifest_path)


def test_sql_guard_requires_executable_transaction_tokens(tmp_path: Path) -> None:
    """Transaction words in comments do not satisfy the explicit transaction contract."""
    manifest_path = _copy_manifest(tmp_path)
    _replace_migration_bytes(manifest_path, "graph", b"-- BEGIN;\nSELECT 1;\n/* COMMIT; */\n")

    with pytest.raises(ledger.LedgerContractError, match="lacks an explicit transaction"):
        ledger.load_and_validate_manifest(manifest_path)


@pytest.mark.parametrize("mutation", ["duplicate-key", "bad-utf8", "bom", "extra-state"])
def test_manifest_rejects_noncanonical_control_input(tmp_path: Path, mutation: str) -> None:
    """The manifest parser rejects ambiguous JSON and retained Supabase state."""
    manifest_path = _copy_manifest(tmp_path)
    if mutation == "duplicate-key":
        raw = manifest_path.read_text(encoding="utf-8")
        manifest_path.write_text(raw.replace("{\n", '{\n  "manifest_version": "duplicate",\n', 1), encoding="utf-8")
    elif mutation == "bad-utf8":
        manifest_path.write_bytes(b"{\xff}")
    elif mutation == "bom":
        manifest_path.write_bytes(b"\xef\xbb\xbf" + manifest_path.read_bytes())
    else:
        (manifest_path.parent / ".temp").mkdir()

    with pytest.raises(ledger.LedgerContractError):
        ledger.load_and_validate_manifest(manifest_path)


def test_separate_target_bindings_resolve_in_stable_order(tmp_path: Path) -> None:
    """Distinct protected identities select only their component profiles."""
    manifest = ledger.load_and_validate_manifest()
    targets = [_binding_target(target) for target in ledger.LOGICAL_TARGET_ORDER]
    binding_path = _write_bindings(tmp_path / "bindings.json", manifest, targets)
    urls = {target: f"postgresql://operator@localhost:5432/{target}" for target in ledger.LOGICAL_TARGET_ORDER}

    plan = ledger.resolve_target_plan(binding_path, manifest, urls)

    assert tuple(item.logical_targets[0] for item in plan) == ledger.LOGICAL_TARGET_ORDER
    assert tuple(item.profile for item in plan) == ledger.LOGICAL_TARGET_ORDER
    assert all(item.alias_database_urls == (item.database_url,) for item in plan)
    assert len({item.fingerprint for item in plan}) == 3


def test_target_binding_document_may_cover_more_targets_than_the_current_run(tmp_path: Path) -> None:
    """A protected deployment-wide binding file may be reused for a configured subset."""
    manifest = ledger.load_and_validate_manifest()
    targets = [_binding_target(target) for target in ledger.LOGICAL_TARGET_ORDER]
    binding_path = _write_bindings(tmp_path / "bindings.json", manifest, targets)

    plan = ledger.resolve_target_plan(
        binding_path,
        manifest,
        {"auth": "postgresql://operator@localhost:5432/auth"},
    )

    assert len(plan) == 1
    assert plan[0].logical_targets == ("auth",)
    assert plan[0].profile == "auth"


def test_explicit_combined_binding_deduplicates_one_physical_target(tmp_path: Path) -> None:
    """Only three explicit combined aliases may resolve to one execution."""
    manifest = ledger.load_and_validate_manifest()
    targets = [_binding_target(target, profile="combined", identity="shared") for target in ledger.LOGICAL_TARGET_ORDER]
    binding_path = _write_bindings(tmp_path / "bindings.json", manifest, targets)
    shared_url = "postgresql://operator@localhost:5432/shared"

    plan = ledger.resolve_target_plan(
        binding_path,
        manifest,
        dict.fromkeys(ledger.LOGICAL_TARGET_ORDER, shared_url),
    )

    assert len(plan) == 1
    assert plan[0].logical_targets == ledger.LOGICAL_TARGET_ORDER
    assert plan[0].profile == "combined"
    assert plan[0].alias_database_urls == (shared_url, shared_url, shared_url)


@pytest.mark.parametrize("case", ["partial-alias", "same-url-different-id", "bad-mode", "manifest-mismatch"])
def test_target_bindings_fail_closed_on_conflicts(tmp_path: Path, case: str) -> None:
    """Alias, identity, permission, and manifest ambiguity stop before execution."""
    manifest = ledger.load_and_validate_manifest()
    if case == "partial-alias":
        targets = [_binding_target("auth"), _binding_target("graph", identity="auth")]
        urls = {"auth": "postgresql://operator@localhost/shared", "graph": "postgresql://operator@localhost/shared"}
    else:
        targets = [_binding_target("auth"), _binding_target("graph")]
        urls = {"auth": "postgresql://operator@localhost/shared", "graph": "postgresql://operator@localhost/shared"}
    binding_path = _write_bindings(tmp_path / "bindings.json", manifest, targets)
    if case == "bad-mode":
        binding_path.chmod(0o644)
    elif case == "manifest-mismatch":
        value = json.loads(binding_path.read_text(encoding="utf-8"))
        value["manifest_sha256"] = "0" * 64
        binding_path.write_text(json.dumps(value), encoding="utf-8")

    error = ledger.TargetProfileConflictError if case == "partial-alias" else ledger.TargetIdentityError
    with pytest.raises(error):
        ledger.resolve_target_plan(binding_path, manifest, urls)


@pytest.mark.parametrize("case", ["missing-key", "duplicate-key", "bad-utf8", "symlink"])
def test_malformed_protected_bindings_use_fixed_identity_reason(tmp_path: Path, case: str) -> None:
    """Malformed protected input never leaks parser or filesystem distinctions."""
    manifest = ledger.load_and_validate_manifest()
    binding_path = _write_bindings(tmp_path / "bindings.json", manifest, [_binding_target("auth")])
    if case == "missing-key":
        value = json.loads(binding_path.read_text(encoding="utf-8"))
        del value["targets"][0]["database_id"]
        binding_path.write_text(json.dumps(value), encoding="utf-8")
    elif case == "duplicate-key":
        raw = binding_path.read_text(encoding="utf-8")
        binding_path.write_text(raw.replace("{\n", '{\n  "binding_version": "duplicate",\n', 1), encoding="utf-8")
    elif case == "bad-utf8":
        binding_path.write_bytes(b"{\xff}")
    else:
        target = tmp_path / "binding-target.json"
        binding_path.rename(target)
        binding_path.symlink_to(target)

    with pytest.raises(ledger.TargetIdentityError, match=ledger.TARGET_IDENTITY_INDETERMINATE):
        ledger.resolve_target_plan(
            binding_path,
            manifest,
            {"auth": "postgresql://operator@localhost/auth"},
        )


def test_unknown_logical_database_target_is_indeterminate(tmp_path: Path) -> None:
    """The resolver rejects configured targets outside the ratified logical set."""
    manifest = ledger.load_and_validate_manifest()
    binding_path = _write_bindings(tmp_path / "bindings.json", manifest, [_binding_target("auth")])

    with pytest.raises(ledger.TargetIdentityError, match=ledger.TARGET_IDENTITY_INDETERMINATE):
        ledger.resolve_target_plan(
            binding_path,
            manifest,
            {
                "auth": "postgresql://operator@localhost/auth",
                "unknown": "postgresql://operator@localhost/unknown",
            },
        )


def test_observed_fingerprint_collision_is_indeterminate(tmp_path: Path, monkeypatch) -> None:
    """Distinct protected canonical inputs may never share one observed fingerprint."""
    manifest = ledger.load_and_validate_manifest()
    binding_path = _write_bindings(
        tmp_path / "bindings.json",
        manifest,
        [_binding_target("auth"), _binding_target("graph")],
    )
    monkeypatch.setattr(ledger, "target_fingerprint", lambda *_values: "f" * 64)

    with pytest.raises(ledger.TargetIdentityError):
        ledger.resolve_target_plan(
            binding_path,
            manifest,
            {
                "auth": "postgresql://operator@localhost/auth",
                "graph": "postgresql://operator@localhost/graph",
            },
        )


@pytest.mark.parametrize(
    "target",
    [
        _planned_target(lineage="hosted-legacy-v1"),
        _planned_target(execution_class="hosted"),
        _planned_target(database_url="postgresql://operator@project.supabase.co/postgres"),
        _planned_target(
            database_url="postgresql://operator@database.example/graph",
            execution_class="loopback",
        ),
    ],
)
def test_hosted_profile_write_barrier_rejects_nonfresh_targets(target: ledger.PlannedTarget) -> None:
    """No hosted or legacy-lineage target can become executable before CQ-03D."""
    with pytest.raises(ledger.HostedWriteBarrierError):
        ledger.assert_profile_write_allowed(target)


def test_profile_write_barrier_requires_explicit_database_name() -> None:
    """A PostgreSQL service URL without a selected database is not executable."""
    target = _planned_target(database_url="postgresql://operator@localhost/")

    with pytest.raises(ledger.HostedWriteBarrierError):
        ledger.assert_profile_write_allowed(target)


def test_profile_write_barrier_checks_every_combined_alias_url() -> None:
    """A safe first DSN cannot hide a hosted or mislabeled alias for one target."""
    target = ledger.PlannedTarget(
        logical_targets=ledger.LOGICAL_TARGET_ORDER,
        profile="combined",
        lineage="fresh-v1",
        execution_class="loopback",
        fingerprint="0" * 64,
        database_url="postgresql://operator@localhost/shared",
        alias_database_urls=(
            "postgresql://operator@localhost/shared",
            "postgresql://operator@project.supabase.co/postgres",
            "postgresql://operator@localhost/shared",
        ),
    )

    with pytest.raises(ledger.HostedWriteBarrierError):
        ledger.assert_profile_write_allowed(target)


@pytest.mark.parametrize(
    "command",
    [
        ("link",),
        ("db", "pull"),
        ("migration", "repair"),
        ("db", "reset", "--linked"),
        ("db", "reset", "--db-url", "postgresql://operator@localhost/db"),
        ("db", "push", "--linked"),
        ("db", "push", "--project-ref", "protected"),
        ("db", "push", "--password", "protected"),
        ("db", "push", "--dry-run"),
    ],
)
def test_every_forbidden_supabase_operation_is_blocked(command: tuple[str, ...]) -> None:
    """The subprocess allowlist rejects every pre-CQ-03D forbidden operation."""
    target = _planned_target()

    with pytest.raises(ledger.HostedWriteBarrierError):
        ledger.assert_allowed_supabase_command(command, target)


def test_disposable_projection_preserves_exact_bytes_and_cleans_up() -> None:
    """A generated CLI workspace contains only selected exact bytes and is removed."""
    manifest = ledger.load_and_validate_manifest()
    selected = manifest.migrations_for_profile("combined")
    retained_path: Path | None = None

    with ledger.disposable_profile_projection(manifest, "combined") as workdir:
        retained_path = workdir
        migration_directory = workdir / "supabase" / "migrations"
        config_path = workdir / "supabase" / "config.toml"
        assert config_path.read_bytes() == ledger.DISPOSABLE_CLI_CONFIG
        assert {path.name for path in migration_directory.iterdir()} == {entry.filename for entry in selected}
        for entry in selected:
            projected = migration_directory / entry.filename
            assert projected.read_bytes() == entry.path.read_bytes()
            if os.name != "nt":
                assert projected.stat().st_mode & 0o777 == 0o600
        if os.name != "nt":
            assert config_path.stat().st_mode & 0o777 == 0o600
        assert not (workdir / "supabase" / ".temp" / "project-ref").exists()
        assert not (workdir / "supabase" / ".branches").exists()

    assert retained_path is not None
    assert not retained_path.exists()


def test_projection_rechecks_source_digest_after_manifest_load(tmp_path: Path) -> None:
    """A migration changed after preflight cannot enter an execution projection."""
    manifest_path = _copy_manifest(tmp_path)
    manifest = ledger.load_and_validate_manifest(manifest_path)
    graph_path = _migration_path(manifest_path, "graph")
    graph_path.write_bytes(graph_path.read_bytes() + b"\n")
    projection = ledger.disposable_profile_projection(manifest, "graph")

    with pytest.raises(ledger.LedgerContractError, match="source migration digest changed"):
        with projection:
            pass


def test_profile_application_uses_pinned_cli_fixed_command_and_clean_environment(
    monkeypatch,
) -> None:
    """The executor captures output, strips provider secrets, and invokes only fixed db push."""
    manifest = ledger.load_and_validate_manifest()
    target = _planned_target()
    calls: list[tuple[list[str], dict[str, str]]] = []
    projected_workdir: Path | None = None

    def runner(command, **kwargs):
        """Capture the fixed child process contract without starting a process."""
        nonlocal projected_workdir
        calls.append((list(command), dict(kwargs["env"])))
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout=f"{ledger.PINNED_SUPABASE_CLI_VERSION}\n", stderr="")
        projected_workdir = Path(command[command.index("--workdir") + 1])
        assert projected_workdir.is_dir()
        return subprocess.CompletedProcess(command, 0, stdout='{"ok":true}\n', stderr="")

    monkeypatch.setattr(ledger, "_resolve_supabase_cli", lambda: "/usr/local/bin/supabase")
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "must-not-reach-child")
    monkeypatch.setenv("PGPASSWORD", "must-not-reach-child")
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "must-not-reach-child")

    ledger.apply_profile_to_database(target, manifest, runner=runner)

    assert len(calls) == 2
    push_command, child_environment = calls[1]
    assert push_command[-4:] == ["db", "push", "--db-url", target.database_url]
    assert "--linked" not in push_command
    assert "--project-ref" not in push_command
    assert "SUPABASE_ACCESS_TOKEN" not in child_environment
    assert "PGPASSWORD" not in child_environment
    assert "SUPABASE_PROJECT_REF" not in child_environment
    assert child_environment["SUPABASE_TELEMETRY_DISABLED"] == "1"
    assert projected_workdir is not None
    assert not projected_workdir.exists()


def test_profile_application_reports_only_bounded_cli_failure_identifiers(monkeypatch) -> None:
    """CLI failures expose a safe error class and SQLSTATE without raw target or statement text."""
    manifest = ledger.load_and_validate_manifest()
    target = _planned_target(database_url="postgresql://operator:protected@localhost/private_database")

    def runner(command, **_kwargs):
        """Return bounded structured CLI failure output for the executor boundary."""
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout=f"{ledger.PINNED_SUPABASE_CLI_VERSION}\n", stderr="")
        payload = {
            "error": {
                "code": "LegacyDbPushApplyError",
                "message": (
                    "protected statement failed against operator:protected@localhost/private_database "
                    "(SQLSTATE 25P01)"
                ),
            }
        }
        return subprocess.CompletedProcess(command, 1, stdout=json.dumps(payload), stderr="protected stderr")

    monkeypatch.setattr(ledger, "_resolve_supabase_cli", lambda: "/usr/local/bin/supabase")

    with pytest.raises(
        ledger.SupabaseCliError,
        match=r"profile application failed \(LegacyDbPushApplyError; SQLSTATE 25P01\)",
    ) as failure:
        ledger.apply_profile_to_database(target, manifest, runner=runner)

    public_message = str(failure.value)
    assert "protected" not in public_message
    assert "private_database" not in public_message
