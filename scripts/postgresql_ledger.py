"""Validate and execute FarDB's profile-scoped PostgreSQL migration ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = REPOSITORY_ROOT / "supabase" / "ledger-profiles.json"
TARGET_BINDINGS_ENV = "FARDB_POSTGRES_TARGET_BINDINGS_FILE"

MANIFEST_VERSION = "fardb-ledger-profiles-v1"
TARGET_BINDING_VERSION = "fardb-target-bindings-v1"
TARGET_FINGERPRINT_ALGORITHM = "fardb-target-fingerprint-v1"
PROVIDER_STATEMENTS_ALGORITHM = "fardb-provider-statements-v1"
TARGET_IDENTITY_INDETERMINATE = "TARGET_IDENTITY_INDETERMINATE"
PINNED_SUPABASE_CLI_VERSION = "2.114.0"
DISPOSABLE_CLI_CONFIG = b'project_id = "fardb-ledger-projection"\n'

COMPONENT_ORDER = ("auth", "graph", "coordination")
LOGICAL_TARGET_ORDER = ("auth", "graph", "coordination")
EXPECTED_PROFILES: dict[str, tuple[str, ...]] = {
    "auth": ("auth",),
    "graph": ("graph",),
    "coordination": ("coordination",),
    "combined": COMPONENT_ORDER,
}
EXPECTED_MANAGED_TABLES: dict[str, tuple[str, ...]] = {
    "auth": ("user_credentials",),
    "graph": (
        "assets",
        "asset_relationships",
        "regulatory_events",
        "regulatory_event_assets",
        "rebuild_jobs",
        "relationship_evidence",
        "relationship_assertions",
        "relationship_assertion_evidence",
        "relationship_assertion_events",
        "relationship_projection_revisions",
        "relationship_projection_edges",
        "relationship_projection_publications",
    ),
    "coordination": ("distributed_locks",),
}

_EXPECTED_RECEIPTS = (
    (
        "20251019202442",
        "create_finance_dashboard_tables",
        55,
        "protected-reviewed-statement-evidence",
        "a0876b49e1715b5d28d1db02e8787d8137d3c8c608e0031ed183df45884d7b66",
    ),
    (
        "20260723074054",
        "adr0007_public_deny_untrusted_roles",
        1,
        "protected-reviewed-statement-evidence",
        "1f32791a479a88f25498f2d4a0c7610c8c73fd94ca4520d0d087945900c4aacb",
    ),
    (
        "20260723074126",
        "adr0007_revoke_public_execute_helper",
        1,
        "protected-reviewed-statement-evidence",
        "4e6f8153401574850a3d0e41e5c1919a9d076afada6806b7f5b919f3fe62ba18",
    ),
    (
        "20260723092314",
        "adr0007_default_privileges_for_role_postgres",
        1,
        "protected-reviewed-statement-evidence",
        "c0d774395ec0599048ade5309b3998795d49a0467596ad26c5728eaa373e9500",
    ),
    (
        "20260809112436",
        "cq_01_02_runtime_capability_contract",
        1,
        "protected-reviewed-statement-evidence",
        "7d0cb353bfac38a9077a82ad2b696941332f0ad866514828b1d8fa1a67fe3e4f",
    ),
    (
        "20260809115020",
        "grant_fardb_runtime_capabilities_to_login_roles",
        1,
        "protected-restricted-membership-evidence",
        "0dbabd5fd58b8f241a8a12dd73fd2e48f57ae93873aef6c2c45e459f2c201b02",
    ),
)

_MIGRATION_FILENAME = re.compile(r"^(?P<timestamp>[0-9]{14})_[a-z0-9_]+[.]sql$")
_LOWER_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SAFE_LOGICAL_TARGET = re.compile(r"^[a-z][a-z0-9_-]*$")
_HOSTED_DATABASE_SUFFIXES = (".supabase.co", ".supabase.net", ".pooler.supabase.com")
_HOSTED_DATABASE_HOSTS = frozenset(("pooler.supabase.com",))
_PROJECTION_FORBIDDEN_PATHS = (
    Path("supabase/.temp/project-ref"),
    Path("supabase/.branches"),
)
_SAFE_CLI_ENVIRONMENT = (
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "SYSTEMROOT",
    "TMPDIR",
)


class LedgerContractError(RuntimeError):
    """Raised when repository ledger bytes do not satisfy the ratified contract."""


class TargetIdentityError(LedgerContractError):
    """Raised before execution when protected target identity is incomplete or ambiguous."""

    def __init__(self) -> None:
        """Create the fixed, non-sensitive target-identity diagnostic."""
        super().__init__(TARGET_IDENTITY_INDETERMINATE)


class TargetProfileConflictError(LedgerContractError):
    """Raised when aliases select conflicting or partial profiles for one target."""


class HostedWriteBarrierError(LedgerContractError):
    """Raised before subprocess execution for a forbidden Supabase operation."""


class SupabaseCliError(LedgerContractError):
    """Raised with a bounded message when the pinned CLI fails."""


@dataclass(frozen=True, slots=True)
class MigrationEntry:
    """One immutable migration selected from a component ledger."""

    component: str
    timestamp: str
    filename: str
    sha256: str
    path: Path


@dataclass(frozen=True, slots=True)
class LedgerManifest:
    """Validated manifest bytes and their resolved immutable migrations."""

    path: Path
    raw_bytes: bytes = field(repr=False)
    data: Mapping[str, Any] = field(repr=False)
    migrations: tuple[MigrationEntry, ...]

    @property
    def sha256(self) -> str:
        """Return the digest of the exact manifest bytes."""
        return sha256_bytes(self.raw_bytes)

    def migrations_for_profile(self, profile: str) -> tuple[MigrationEntry, ...]:
        """Return the selected profile's deterministic timestamp-sorted union."""
        components = EXPECTED_PROFILES.get(profile)
        if components is None:
            raise LedgerContractError(f"unknown ledger profile: {profile}")
        selected = [migration for migration in self.migrations if migration.component in components]
        return tuple(sorted(selected, key=lambda migration: migration.timestamp))


@dataclass(frozen=True, slots=True)
class TargetBinding:
    """One protected logical-target binding with computed opaque identity."""

    logical_target: str
    profile: str
    lineage: str
    execution_class: str
    fingerprint: str
    canonical_identity: tuple[str, str, str] = field(repr=False)


@dataclass(frozen=True, slots=True)
class PlannedTarget:
    """One deduplicated physical-target execution selected before connections."""

    logical_targets: tuple[str, ...]
    profile: str
    lineage: str
    execution_class: str
    fingerprint: str
    database_url: str = field(repr=False)
    alias_database_urls: tuple[str, ...] = field(default=(), repr=False)


def sha256_bytes(value: bytes) -> str:
    """Return a lowercase SHA-256 digest for exact bytes."""
    return hashlib.sha256(value).hexdigest()


def provider_statements_digest(statements: Sequence[str]) -> str:
    """Hash exact ordered provider statement values under ADR 0010."""
    digest = hashlib.sha256()
    digest.update(PROVIDER_STATEMENTS_ALGORITHM.encode("ascii"))
    digest.update(b"\0")
    digest.update(struct.pack(">Q", len(statements)))
    for statement in statements:
        if not isinstance(statement, str):
            raise TypeError("provider statements must be strings")
        statement_bytes = statement.encode("utf-8", errors="strict")
        digest.update(struct.pack(">Q", len(statement_bytes)))
        digest.update(statement_bytes)
    return digest.hexdigest()


def _canonical_identity_value(value: object) -> str:
    """Normalize one protected identity input or fail with the public reason code."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise TargetIdentityError()
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise TargetIdentityError()
    normalized = unicodedata.normalize("NFC", value)
    if not normalized or normalized != normalized.strip():
        raise TargetIdentityError()
    try:
        normalized.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise TargetIdentityError() from exc
    return normalized


def canonical_target_identity(
    adapter_id: object,
    authority_namespace_id: object,
    database_id: object,
) -> tuple[str, str, str]:
    """Return the three protected canonical target-fingerprint inputs."""
    return (
        _canonical_identity_value(adapter_id),
        _canonical_identity_value(authority_namespace_id),
        _canonical_identity_value(database_id),
    )


def target_fingerprint(adapter_id: object, authority_namespace_id: object, database_id: object) -> str:
    """Compute the versioned opaque database-target fingerprint from immutable inputs."""
    canonical_values = canonical_target_identity(adapter_id, authority_namespace_id, database_id)
    digest = hashlib.sha256()
    digest.update(TARGET_FINGERPRINT_ALGORITHM.encode("ascii"))
    digest.update(b"\0")
    for value in canonical_values:
        encoded = value.encode("utf-8")
        digest.update(struct.pack(">Q", len(encoded)))
        digest.update(encoded)
    return digest.hexdigest()


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON object keys instead of accepting the last value."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LedgerContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json_object(path: Path, *, protected: bool = False) -> tuple[bytes, dict[str, Any]]:
    """Read strict UTF-8 JSON bytes from a regular non-symlink file."""
    if path.is_symlink() or not path.is_file():
        raise LedgerContractError("JSON control input must be a regular non-symlink file")
    if protected and os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise TargetIdentityError()
    raw_bytes = path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LedgerContractError("JSON control input is not strict UTF-8") from exc
    if text.startswith("\ufeff"):
        raise LedgerContractError("JSON control input must not contain a byte-order mark")
    try:
        value = json.loads(text, object_pairs_hook=_object_without_duplicate_keys)
    except LedgerContractError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise LedgerContractError("JSON control input is invalid") from exc
    if not isinstance(value, dict):
        raise LedgerContractError("JSON control input must contain an object")
    return raw_bytes, value


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], location: str) -> None:
    """Require an exact key set at one manifest location."""
    actual = set(value)
    if actual != expected:
        raise LedgerContractError(f"{location} keys do not match the contract")


def _require_string_list(value: object, location: str) -> tuple[str, ...]:
    """Return a duplicate-free tuple of strings."""
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise LedgerContractError(f"{location} must be a string list")
    if len(value) != len(set(value)):
        raise LedgerContractError(f"{location} contains duplicates")
    return tuple(value)


def _validate_migration_sql(entry: MigrationEntry, receipt_timestamps: frozenset[str]) -> None:
    """Enforce forward-only baseline structure without reparsing or rewriting SQL."""
    raw_bytes = entry.path.read_bytes()
    try:
        sql_text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LedgerContractError(f"migration is not strict UTF-8: {entry.filename}") from exc
    if sql_text.startswith("\ufeff"):
        raise LedgerContractError(f"migration has a byte-order mark: {entry.filename}")
    upper_text = sql_text.upper()
    if "BEGIN;" not in upper_text or "COMMIT;" not in upper_text:
        raise LedgerContractError(f"migration lacks an explicit transaction: {entry.filename}")
    forbidden_patterns = (
        r"\bIF[ \t\r\n]+(?:NOT[ \t\r\n]+)?EXISTS\b",
        r"\bCREATE[ \t\r\n]+ROLE\b",
        r"\bALTER[ \t\r\n]+ROLE\b",
        r"\bDROP[ \t\r\n]+(?:TABLE|SCHEMA|ROLE|POLICY|FUNCTION|TRIGGER|CONSTRAINT)\b",
        r"\bSUPABASE_MIGRATIONS\b",
    )
    if any(re.search(pattern, upper_text) for pattern in forbidden_patterns):
        raise LedgerContractError(f"migration contains forbidden conditional or authority SQL: {entry.filename}")
    if entry.timestamp in receipt_timestamps:
        raise LedgerContractError(f"migration reuses a historical provider timestamp: {entry.filename}")


def _validate_component_migrations(  # noqa: C901
    manifest_path: Path,
    component: str,
    component_value: Mapping[str, Any],
    receipt_timestamps: frozenset[str],
) -> tuple[MigrationEntry, ...]:
    """Validate one component directory against its exact manifest entries."""
    migrations_value = component_value.get("migrations")
    if not isinstance(migrations_value, list) or not migrations_value:
        raise LedgerContractError(f"component {component} must declare migrations")
    migration_directory = manifest_path.parent / "ledgers" / component / "migrations"
    if migration_directory.is_symlink() or not migration_directory.is_dir():
        raise LedgerContractError(f"component migration directory is invalid: {component}")

    entries: list[MigrationEntry] = []
    expected_filenames: set[str] = set()
    previous_timestamp: str | None = None
    for raw_entry in migrations_value:
        if not isinstance(raw_entry, dict):
            raise LedgerContractError(f"component {component} migration entry is invalid")
        _require_exact_keys(raw_entry, {"timestamp", "filename", "sha256"}, f"components.{component}.migration")
        timestamp = raw_entry["timestamp"]
        filename = raw_entry["filename"]
        expected_digest = raw_entry["sha256"]
        if not all(isinstance(value, str) for value in (timestamp, filename, expected_digest)):
            raise LedgerContractError(f"component {component} migration metadata must be strings")
        filename_match = _MIGRATION_FILENAME.fullmatch(filename)
        if filename_match is None or filename_match.group("timestamp") != timestamp:
            raise LedgerContractError(f"component {component} migration filename is invalid")
        try:
            datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        except ValueError as exc:
            raise LedgerContractError(f"component {component} migration timestamp is invalid") from exc
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise LedgerContractError(f"component {component} migration timestamps are not strictly increasing")
        previous_timestamp = timestamp
        if not _LOWER_HEX_DIGEST.fullmatch(expected_digest):
            raise LedgerContractError(f"component {component} migration digest is invalid")
        if PurePosixPath(filename).name != filename:
            raise LedgerContractError(f"component {component} migration path is unsafe")
        migration_path = migration_directory / filename
        if migration_path.is_symlink() or not migration_path.is_file():
            raise LedgerContractError(f"component {component} migration file is missing")
        if sha256_bytes(migration_path.read_bytes()) != expected_digest:
            raise LedgerContractError(f"component {component} migration digest does not match")
        expected_filenames.add(filename)
        entry = MigrationEntry(component, timestamp, filename, expected_digest, migration_path)
        _validate_migration_sql(entry, receipt_timestamps)
        entries.append(entry)

    actual_entries = tuple(migration_directory.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in actual_entries):
        raise LedgerContractError(f"component {component} migration directory contains an invalid entry")
    if {path.name for path in actual_entries} != expected_filenames:
        raise LedgerContractError(f"component {component} migration directory does not match the manifest")
    return tuple(entries)


def _validate_lineages(lineages: object) -> frozenset[str]:
    """Validate the fresh and bounded legacy-hosted lineage records."""
    if not isinstance(lineages, dict) or set(lineages) != {"fresh-v1", "hosted-legacy-v1"}:
        raise LedgerContractError("lineage profiles do not match the contract")
    fresh = lineages["fresh-v1"]
    hosted = lineages["hosted-legacy-v1"]
    if not isinstance(fresh, dict) or not isinstance(hosted, dict):
        raise LedgerContractError("lineage profile entries must be objects")
    _require_exact_keys(fresh, {"adoption_state", "receipts"}, "lineages.fresh-v1")
    _require_exact_keys(hosted, {"adoption_state", "receipts"}, "lineages.hosted-legacy-v1")
    if fresh != {"adoption_state": "canonical-fresh", "receipts": []}:
        raise LedgerContractError("fresh-v1 lineage is invalid")
    if hosted.get("adoption_state") != "not-adopted-before-cq-03d":
        raise LedgerContractError("hosted-legacy-v1 must remain unadopted")
    receipts = hosted.get("receipts")
    if not isinstance(receipts, list) or len(receipts) != len(_EXPECTED_RECEIPTS):
        raise LedgerContractError("hosted-legacy-v1 receipt count is invalid")
    for receipt, expected in zip(receipts, _EXPECTED_RECEIPTS, strict=True):
        if not isinstance(receipt, dict):
            raise LedgerContractError("hosted-legacy-v1 receipt entry is invalid")
        _require_exact_keys(
            receipt,
            {"timestamp", "name", "statement_count", "classification", "statements_sha256", "provenance"},
            "lineages.hosted-legacy-v1.receipt",
        )
        actual = (
            receipt["timestamp"],
            receipt["name"],
            receipt["statement_count"],
            receipt["classification"],
            receipt["statements_sha256"],
        )
        if actual != expected:
            raise LedgerContractError("hosted-legacy-v1 receipt metadata does not match protected evidence")
        provenance = receipt["provenance"]
        if not isinstance(provenance, str) or not provenance or "://" in provenance or len(provenance) > 240:
            raise LedgerContractError("hosted-legacy-v1 provenance is not bounded")
    return frozenset(expected[0] for expected in _EXPECTED_RECEIPTS)


def load_and_validate_manifest(  # noqa: C901
    path: Path | str = DEFAULT_MANIFEST_PATH,
) -> LedgerManifest:
    """Load and strictly validate the profile manifest and every referenced byte."""
    manifest_path = Path(path)
    raw_bytes, manifest = _read_json_object(manifest_path)
    _require_exact_keys(
        manifest,
        {"manifest_version", "component_order", "algorithms", "components", "profiles", "lineages"},
        "manifest",
    )
    if manifest["manifest_version"] != MANIFEST_VERSION:
        raise LedgerContractError("manifest version is unsupported")
    if _require_string_list(manifest["component_order"], "component_order") != COMPONENT_ORDER:
        raise LedgerContractError("component order does not match the ratified order")
    algorithms = manifest["algorithms"]
    if algorithms != {
        "migration_digest": "sha256",
        "provider_statements_digest": PROVIDER_STATEMENTS_ALGORITHM,
        "target_fingerprint": TARGET_FINGERPRINT_ALGORITHM,
    }:
        raise LedgerContractError("manifest algorithms do not match the contract")

    supabase_root = manifest_path.parent
    for forbidden_name in ("migrations", "schemas", ".temp", ".branches"):
        if (supabase_root / forbidden_name).exists():
            raise LedgerContractError(f"non-canonical Supabase state is retained: {forbidden_name}")
    ledger_root = supabase_root / "ledgers"
    if ledger_root.is_symlink() or not ledger_root.is_dir():
        raise LedgerContractError("component ledger root is invalid")
    if {path.name for path in ledger_root.iterdir()} != set(COMPONENT_ORDER):
        raise LedgerContractError("component ledger directories do not match the manifest")

    receipt_timestamps = _validate_lineages(manifest["lineages"])
    components = manifest["components"]
    if not isinstance(components, dict) or tuple(components) != COMPONENT_ORDER:
        raise LedgerContractError("component declarations do not match the ratified order")
    all_migrations: list[MigrationEntry] = []
    assigned_tables: set[str] = set()
    for component in COMPONENT_ORDER:
        component_value = components[component]
        if not isinstance(component_value, dict):
            raise LedgerContractError(f"component {component} must be an object")
        _require_exact_keys(
            component_value,
            {"dependencies", "managed_tables", "migrations"},
            f"components.{component}",
        )
        dependencies = _require_string_list(component_value["dependencies"], f"components.{component}.dependencies")
        if dependencies:
            raise LedgerContractError(f"component {component} has an unratified dependency")
        managed_tables = _require_string_list(
            component_value["managed_tables"],
            f"components.{component}.managed_tables",
        )
        if managed_tables != EXPECTED_MANAGED_TABLES[component]:
            raise LedgerContractError(f"component {component} table ownership does not match the contract")
        if assigned_tables.intersection(managed_tables):
            raise LedgerContractError("managed table is assigned to multiple components")
        assigned_tables.update(managed_tables)
        all_migrations.extend(
            _validate_component_migrations(manifest_path, component, component_value, receipt_timestamps)
        )

    timestamps = [migration.timestamp for migration in all_migrations]
    if len(timestamps) != len(set(timestamps)):
        raise LedgerContractError("migration timestamps are not globally unique")
    if min(timestamps) <= max(receipt_timestamps):
        raise LedgerContractError("canonical baseline is not forward-dated after provider evidence")

    profiles = manifest["profiles"]
    if not isinstance(profiles, dict) or tuple(profiles) != tuple(EXPECTED_PROFILES):
        raise LedgerContractError("build profiles do not match the contract")
    for profile, expected_components in EXPECTED_PROFILES.items():
        profile_value = profiles[profile]
        if not isinstance(profile_value, dict):
            raise LedgerContractError(f"profile {profile} must be an object")
        _require_exact_keys(profile_value, {"components"}, f"profiles.{profile}")
        actual_components = _require_string_list(profile_value["components"], f"profiles.{profile}.components")
        if actual_components != expected_components:
            raise LedgerContractError(f"profile {profile} components do not match the contract")

    result = LedgerManifest(manifest_path, raw_bytes, manifest, tuple(all_migrations))
    combined = result.migrations_for_profile("combined")
    if tuple(migration.timestamp for migration in combined) != tuple(sorted(timestamps)):
        raise LedgerContractError("combined profile is not the deterministic timestamp-sorted union")
    return result


def _parse_target_binding_document(path: Path, manifest: LedgerManifest) -> tuple[TargetBinding, ...]:
    """Parse the protected target-binding file and compute every fingerprint."""
    _raw_bytes, document = _read_json_object(path, protected=True)
    _require_exact_keys(
        document,
        {"binding_version", "manifest_sha256", "target_fingerprint_algorithm", "targets"},
        "target bindings",
    )
    if document["binding_version"] != TARGET_BINDING_VERSION:
        raise TargetIdentityError()
    if document["manifest_sha256"] != manifest.sha256:
        raise TargetIdentityError()
    if document["target_fingerprint_algorithm"] != TARGET_FINGERPRINT_ALGORITHM:
        raise TargetIdentityError()
    targets = document["targets"]
    if not isinstance(targets, list) or not targets:
        raise TargetIdentityError()

    bindings: list[TargetBinding] = []
    for value in targets:
        if not isinstance(value, dict):
            raise TargetIdentityError()
        _require_exact_keys(
            value,
            {
                "logical_target",
                "profile",
                "lineage",
                "execution_class",
                "identity_assurance",
                "adapter_id",
                "authority_namespace_id",
                "database_id",
            },
            "target binding",
        )
        logical_target = value["logical_target"]
        profile = value["profile"]
        lineage = value["lineage"]
        execution_class = value["execution_class"]
        if not all(isinstance(item, str) for item in (logical_target, profile, lineage, execution_class)):
            raise TargetIdentityError()
        if not _SAFE_LOGICAL_TARGET.fullmatch(logical_target) or logical_target not in LOGICAL_TARGET_ORDER:
            raise TargetIdentityError()
        if profile not in EXPECTED_PROFILES or lineage not in ("fresh-v1", "hosted-legacy-v1"):
            raise TargetIdentityError()
        if execution_class not in ("disposable", "loopback", "hosted"):
            raise TargetIdentityError()
        if value["identity_assurance"] != "operator-attested-immutable-v1":
            raise TargetIdentityError()
        canonical_identity = canonical_target_identity(
            value["adapter_id"],
            value["authority_namespace_id"],
            value["database_id"],
        )
        fingerprint = target_fingerprint(*canonical_identity)
        bindings.append(
            TargetBinding(
                logical_target,
                profile,
                lineage,
                execution_class,
                fingerprint,
                canonical_identity,
            )
        )
    return tuple(bindings)


def _load_target_binding_document(path: Path, manifest: LedgerManifest) -> tuple[TargetBinding, ...]:
    """Load bindings while collapsing malformed protected input to one reason code."""
    try:
        return _parse_target_binding_document(path, manifest)
    except TargetIdentityError:
        raise
    except (KeyError, LedgerContractError, OSError, TypeError, ValueError) as exc:
        raise TargetIdentityError() from exc


def resolve_target_plan(
    binding_path: Path | str,
    manifest: LedgerManifest,
    database_urls: Mapping[str, str],
) -> tuple[PlannedTarget, ...]:
    """Resolve aliases and profile conflicts before any engine, connection, or SQL execution."""
    if set(database_urls) - set(LOGICAL_TARGET_ORDER):
        raise TargetIdentityError()
    required_targets = tuple(target for target in LOGICAL_TARGET_ORDER if target in database_urls)
    if not required_targets or any(not isinstance(database_urls[target], str) for target in required_targets):
        raise TargetIdentityError()
    bindings = _load_target_binding_document(Path(binding_path), manifest)
    binding_by_target = {binding.logical_target: binding for binding in bindings}
    if (
        len(binding_by_target) != len(bindings)
        or tuple(target for target in LOGICAL_TARGET_ORDER if target in binding_by_target) != required_targets
    ):
        raise TargetIdentityError()

    url_identities: dict[str, str] = {}
    identity_by_fingerprint: dict[str, tuple[str, str, str]] = {}
    grouped: dict[str, list[TargetBinding]] = defaultdict(list)
    for target in required_targets:
        binding = binding_by_target[target]
        database_url = database_urls[target]
        if not database_url or database_url != database_url.strip():
            raise TargetIdentityError()
        previous_fingerprint = url_identities.setdefault(database_url, binding.fingerprint)
        if previous_fingerprint != binding.fingerprint:
            raise TargetIdentityError()
        previous_identity = identity_by_fingerprint.setdefault(binding.fingerprint, binding.canonical_identity)
        if previous_identity != binding.canonical_identity:
            raise TargetIdentityError()
        grouped[binding.fingerprint].append(binding)

    planned: list[PlannedTarget] = []
    for fingerprint, aliases in grouped.items():
        aliases.sort(key=lambda binding: LOGICAL_TARGET_ORDER.index(binding.logical_target))
        logical_targets = tuple(binding.logical_target for binding in aliases)
        profiles = {binding.profile for binding in aliases}
        lineages = {binding.lineage for binding in aliases}
        execution_classes = {binding.execution_class for binding in aliases}
        if len(lineages) != 1 or len(execution_classes) != 1:
            raise TargetProfileConflictError("aliased target bindings disagree on lineage or execution class")
        if profiles == {"combined"}:
            if logical_targets != LOGICAL_TARGET_ORDER:
                raise TargetProfileConflictError("combined requires explicit auth, graph, and coordination aliases")
            profile = "combined"
        elif len(aliases) == 1 and aliases[0].profile == aliases[0].logical_target:
            profile = aliases[0].profile
        else:
            raise TargetProfileConflictError("aliased target bindings require one explicit combined profile")
        chosen_url = database_urls[logical_targets[0]]
        alias_urls = tuple(database_urls[logical_target] for logical_target in logical_targets)
        planned.append(
            PlannedTarget(
                logical_targets,
                profile,
                next(iter(lineages)),
                next(iter(execution_classes)),
                fingerprint,
                chosen_url,
                alias_urls,
            )
        )
    return tuple(sorted(planned, key=lambda item: LOGICAL_TARGET_ORDER.index(item.logical_targets[0])))


def _database_host(database_url: str) -> str:
    """Return a normalized PostgreSQL hostname without exposing it in failures."""
    try:
        parsed = urlsplit(database_url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise HostedWriteBarrierError("database URL is invalid") from exc
    if (
        parsed.scheme not in ("postgres", "postgresql")
        or not host
        or parsed.path in ("", "/")
        or port is not None
        and port <= 0
    ):
        raise HostedWriteBarrierError("database URL is not an explicit PostgreSQL target")
    return host.lower().rstrip(".")


def _is_hosted_database_host(host: str) -> bool:
    """Return whether a hostname is a known hosted Supabase endpoint."""
    return host in _HOSTED_DATABASE_HOSTS or any(host.endswith(suffix) for suffix in _HOSTED_DATABASE_SUFFIXES)


def assert_profile_write_allowed(target: PlannedTarget) -> None:
    """Reject hosted, legacy-lineage, or mislabeled loopback writes before subprocess execution."""
    if target.lineage != "fresh-v1":
        raise HostedWriteBarrierError("hosted legacy lineage is non-executable before CQ-03D")
    if target.execution_class not in ("disposable", "loopback"):
        raise HostedWriteBarrierError("target execution class is not writable in CQ-03B-R2")
    alias_urls = target.alias_database_urls or (target.database_url,)
    if target.database_url not in alias_urls:
        raise HostedWriteBarrierError("selected execution URL is absent from its alias set")
    for database_url in alias_urls:
        host = _database_host(database_url)
        if _is_hosted_database_host(host):
            raise HostedWriteBarrierError("hosted database writes are forbidden before CQ-03D")
        if target.execution_class == "loopback" and host not in ("localhost", "127.0.0.1", "::1"):
            raise HostedWriteBarrierError("loopback execution class does not resolve to loopback")


def assert_allowed_supabase_command(command: Sequence[str], target: PlannedTarget) -> None:
    """Enforce the fixed CQ-03B-R2 CLI allowlist before starting a subprocess."""
    tokens = tuple(command)
    if not tokens:
        raise HostedWriteBarrierError("empty Supabase command is forbidden")
    lowered = tuple(token.lower() for token in tokens)
    joined = " ".join(lowered)
    universally_forbidden = (
        " link",
        "db pull",
        "migration repair",
        "db reset --linked",
        "db reset --db-url",
    )
    if any(marker in f" {joined}" for marker in universally_forbidden):
        raise HostedWriteBarrierError("Supabase command is forbidden before CQ-03D")
    if any(flag in lowered for flag in ("--linked", "--project-ref", "--password", "--dry-run")):
        raise HostedWriteBarrierError("Supabase command contains a forbidden target or authority flag")
    fixed_shape = (
        len(tokens) == 9
        and lowered[0] == "--workdir"
        and bool(tokens[1])
        and lowered[2:8] == ("--yes", "--output-format", "json", "db", "push", "--db-url")
        and tokens[8] == target.database_url
    )
    if not fixed_shape:
        raise HostedWriteBarrierError("Supabase command is outside the fixed profile-application allowlist")
    assert_profile_write_allowed(target)


def _assert_projection_has_no_link_state(workdir: Path) -> None:
    """Reject retained CLI link or branch state in a disposable projection."""
    for relative_path in _PROJECTION_FORBIDDEN_PATHS:
        if (workdir / relative_path).exists():
            raise HostedWriteBarrierError("disposable Supabase projection retained forbidden link state")


@contextmanager
def disposable_profile_projection(manifest: LedgerManifest, profile: str) -> Iterator[Path]:
    """Yield a mode-0700 CLI workdir containing only exact selected migration bytes."""
    migrations = manifest.migrations_for_profile(profile)
    if not migrations:
        raise LedgerContractError(f"profile has no migrations: {profile}")
    temporary_directory = tempfile.TemporaryDirectory(prefix="fardb-ledger-projection-")
    workdir = Path(temporary_directory.name)
    try:
        workdir.chmod(0o700)
        migrations_directory = workdir / "supabase" / "migrations"
        migrations_directory.mkdir(parents=True, mode=0o700)
        (workdir / "supabase").chmod(0o700)
        config_path = workdir / "supabase" / "config.toml"
        with config_path.open("xb") as handle:
            handle.write(DISPOSABLE_CLI_CONFIG)
        config_path.chmod(0o600)
        for migration in migrations:
            if migration.path.is_symlink() or not migration.path.is_file():
                raise LedgerContractError(f"profile source migration is invalid: {migration.filename}")
            source_bytes = migration.path.read_bytes()
            if sha256_bytes(source_bytes) != migration.sha256:
                raise LedgerContractError(f"profile source migration digest changed: {migration.filename}")
            destination = migrations_directory / migration.filename
            with destination.open("xb") as handle:
                handle.write(source_bytes)
            destination.chmod(0o600)
        _assert_projection_has_no_link_state(workdir)
        yield workdir
        _assert_projection_has_no_link_state(workdir)
    finally:
        temporary_directory.cleanup()


def _sanitized_cli_environment(state_directory: Path, environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build a minimal CLI environment without provider tokens, passwords, or project refs."""
    source = os.environ if environment is None else environment
    sanitized = {name: source[name] for name in _SAFE_CLI_ENVIRONMENT if source.get(name)}
    sanitized.update(
        {
            "SUPABASE_HOME": str(state_directory),
            "SUPABASE_TELEMETRY_DISABLED": "1",
            "DO_NOT_TRACK": "1",
        }
    )
    return sanitized


def _resolve_supabase_cli(cli_name: str = "supabase") -> str:
    """Resolve only the pinned command name from PATH."""
    if cli_name != "supabase":
        raise SupabaseCliError("Supabase CLI command override is forbidden")
    resolved = shutil.which(cli_name)
    if resolved is None:
        raise SupabaseCliError("Supabase CLI is unavailable")
    return resolved


def _run_cli(
    command: Sequence[str],
    environment: Mapping[str, str],
    *,
    timeout_seconds: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    """Run one fixed, shell-free command while capturing all potentially sensitive output."""
    try:
        return runner(
            list(command),
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            env=dict(environment),
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SupabaseCliError("Supabase CLI execution failed") from exc


def require_pinned_supabase_cli(
    cli_path: str,
    environment: Mapping[str, str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """Require the exact reviewed Supabase CLI version before profile application."""
    result = _run_cli((cli_path, "--version"), environment, timeout_seconds=15, runner=runner)
    if result.returncode != 0 or result.stdout.strip() != PINNED_SUPABASE_CLI_VERSION:
        raise SupabaseCliError("Supabase CLI version does not match the pinned contract")


def apply_profile_to_database(
    target: PlannedTarget,
    manifest: LedgerManifest,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """Apply one fresh disposable profile through the pinned CLI and exact projection."""
    assert_profile_write_allowed(target)
    cli_path = _resolve_supabase_cli()
    with disposable_profile_projection(manifest, target.profile) as workdir:
        state_directory = Path(tempfile.mkdtemp(prefix="fardb-supabase-home-"))
        try:
            state_directory.chmod(0o700)
            environment = _sanitized_cli_environment(state_directory)
            require_pinned_supabase_cli(cli_path, environment, runner=runner)
            command = (
                cli_path,
                "--workdir",
                str(workdir),
                "--yes",
                "--output-format",
                "json",
                "db",
                "push",
                "--db-url",
                target.database_url,
            )
            assert_allowed_supabase_command(command[1:], target)
            result = _run_cli(command, environment, timeout_seconds=300, runner=runner)
            if result.returncode != 0:
                raise SupabaseCliError("Supabase CLI profile application failed")
            _assert_projection_has_no_link_state(workdir)
        finally:
            shutil.rmtree(state_directory)


def _build_parser() -> argparse.ArgumentParser:
    """Build the bounded ledger command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate the manifest and exact migration bytes")
    validate.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the repository ledger while emitting only bounded control metadata."""
    arguments = _build_parser().parse_args(argv)
    try:
        if arguments.command == "validate":
            manifest = load_and_validate_manifest(arguments.manifest)
            print(f"PostgreSQL ledger manifest valid: {manifest.sha256}")
            return 0
    except Exception as exc:  # noqa: BLE001 - never echo paths, SQL, URLs, or protected inputs
        print(f"PostgreSQL ledger validation failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
