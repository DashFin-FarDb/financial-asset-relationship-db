"""Evaluate FarDB PostgreSQL ledger, catalog, and runtime drift read-only."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from scripts.postgresql_ledger import (
    CATALOG_NORMALIZATION_VERSION,
    EXPECTED_MANAGED_TABLES,
    EXPECTED_PROFILES,
    MANAGED_SCOPE_VERSION,
    LedgerManifest,
)

PASS = "PASS"
DRIFT_DETECTED = "DRIFT_DETECTED"
EVALUATION_INCOMPLETE = "EVALUATION_INCOMPLETE"

LEDGER_HISTORY_MISMATCH = "LEDGER_HISTORY_MISMATCH"
PROVIDER_SCHEMA_DRIFT = "PROVIDER_SCHEMA_DRIFT"
RUNTIME_COMPATIBILITY_MISMATCH = "RUNTIME_COMPATIBILITY_MISMATCH"

CHECK_PASSED = "PASSED"
CHECK_DRIFT = "DRIFT"
NOT_EVALUATED = "NOT_EVALUATED"

HIGHER_PRIORITY_CHECK_NOT_EVALUATED = "HIGHER_PRIORITY_CHECK_NOT_EVALUATED"
REQUIRED_CHECK_NOT_EVALUATED = "REQUIRED_CHECK_NOT_EVALUATED"
OUTSIDE_MANAGED_SCOPE = "OUTSIDE_MANAGED_SCOPE"
LINEAGE_NOT_ADOPTED = "LINEAGE_NOT_ADOPTED"

_CATEGORY_ORDER = (
    LEDGER_HISTORY_MISMATCH,
    PROVIDER_SCHEMA_DRIFT,
    RUNTIME_COMPATIBILITY_MISMATCH,
)
_PUBLIC_FUNCTIONS: Mapping[str, tuple[str, ...]] = {
    "auth": (),
    "graph": ("grac_v1_reject_mutation",),
    "coordination": (),
    "combined": ("grac_v1_reject_mutation",),
}


class Cursor(Protocol):
    """Minimal DB-API cursor surface used by the read-only evaluator."""

    description: Sequence[Sequence[Any]] | None

    def execute(self, query: str, parameters: object | None = None) -> object:
        """Execute one read-only catalog query."""
        ...

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Return all rows from the current query."""
        ...

    def __enter__(self) -> Cursor:
        """Enter the cursor context."""
        ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """Exit the cursor context."""
        ...


class Connection(Protocol):
    """Minimal DB-API connection surface used by the read-only evaluator."""

    def cursor(self) -> Cursor:
        """Return a cursor context manager."""
        ...

    def set_session(self, *, readonly: bool, autocommit: bool) -> None:
        """Set the transaction safety posture before catalog access."""
        ...

    def rollback(self) -> None:
        """Close the evaluator transaction without preserving any effects."""
        ...


class RuntimeCompatibilityMismatch(Exception):
    """Signal a completed runtime check whose required invariant failed."""


class RuntimeCheckUnavailable(Exception):
    """Signal that runtime compatibility could not be evaluated."""


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One required drift check without sensitive object details."""

    name: str
    category: str
    state: str
    reason_code: str | None = None
    expected_digest: str | None = None
    actual_digest: str | None = None


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Sanitized public result for one target/profile evaluation."""

    status: str
    primary_category: str | None
    reason_codes: tuple[str, ...]
    target_class: str
    profile: str
    lineage: str
    normalization_profile: str
    managed_scope_version: str
    required_check_count: int
    evaluated_check_count: int
    not_evaluated_count: int
    application_owned_count: int
    provider_owned_count: int
    unknown_count: int
    expected_catalog_digest: str | None
    actual_catalog_digest: str | None

    def as_public_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe public diagnostics."""
        return {
            "status": self.status,
            "primary_category": self.primary_category,
            "reason_codes": list(self.reason_codes),
            "target_class": self.target_class,
            "profile": self.profile,
            "lineage": self.lineage,
            "normalization_profile": self.normalization_profile,
            "managed_scope_version": self.managed_scope_version,
            "required_check_count": self.required_check_count,
            "evaluated_check_count": self.evaluated_check_count,
            "not_evaluated_count": self.not_evaluated_count,
            "application_owned_count": self.application_owned_count,
            "provider_owned_count": self.provider_owned_count,
            "unknown_count": self.unknown_count,
            "expected_catalog_digest": self.expected_catalog_digest,
            "actual_catalog_digest": self.actual_catalog_digest,
        }


def _normalized_text(value: object) -> object:
    """Normalize PostgreSQL-deparsed text without rewriting parsed semantics."""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, Mapping):
        return {str(key): _normalized_text(item) for key, item in value.items()}
    if isinstance(value, list):
        normalized: list[object] = [_normalized_text(item) for item in value]
        strings = [item for item in normalized if isinstance(item, str)]
        if len(strings) == len(normalized):
            return sorted(strings)
        return normalized
    return value


def canonical_catalog_bytes(document: Mapping[str, object]) -> bytes:
    """Serialize one normalized catalog as canonical UTF-8 JSON."""
    normalized = {key: _normalized_text(value) for key, value in document.items()}
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def catalog_digest(document: Mapping[str, object]) -> str:
    """Return the version-bound SHA-256 digest of a normalized catalog."""
    digest = hashlib.sha256()
    digest.update(CATALOG_NORMALIZATION_VERSION.encode("ascii"))
    digest.update(b"\0")
    digest.update(MANAGED_SCOPE_VERSION.encode("ascii"))
    digest.update(b"\0")
    digest.update(canonical_catalog_bytes(document))
    return digest.hexdigest()


def _rows(cursor: Cursor, query: str, parameters: object | None = None) -> list[dict[str, object]]:
    """Execute one SELECT and map its rows to deterministically keyed objects."""
    cursor.execute(query, parameters)
    columns = tuple(str(column[0]) for column in (cursor.description or ()))
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def expected_managed_tables(profile: str) -> tuple[str, ...]:
    """Return the sorted managed-table set for one exact build profile."""
    components = EXPECTED_PROFILES.get(profile)
    if components is None:
        return ()
    return tuple(sorted(table for component in components for table in EXPECTED_MANAGED_TABLES[component]))


def _is_application_relation(relation: Mapping[str, object], managed_tables: tuple[str, ...]) -> bool:
    """Return whether one public relation belongs to the selected profile."""
    kind = str(relation["kind"])
    name = str(relation["name"])
    if kind in ("r", "p"):
        return name in managed_tables
    return kind == "S" and relation["owned_table"] in managed_tables


def _public_scope(cursor: Cursor, profile: str) -> tuple[int, int, tuple[str, ...]]:
    """Classify public relations/functions without publishing their names."""
    managed_tables = expected_managed_tables(profile)
    relations = _rows(
        cursor,
        """
        SELECT c.relname AS name, c.relkind AS kind,
                owned.relname AS owned_table
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        LEFT JOIN pg_catalog.pg_depend AS d
            ON c.relkind = 'S' AND d.objid = c.oid AND d.deptype IN ('a', 'i')
        LEFT JOIN pg_catalog.pg_class AS owned ON owned.oid = d.refobjid
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
        ORDER BY c.relkind, c.relname
        """,
    )
    application_count = 0
    unknown: list[str] = []
    for relation in relations:
        if _is_application_relation(relation, managed_tables):
            application_count += 1
        else:
            unknown.append(f"relation:{relation['kind']}:{relation['name']}")

    functions = _rows(
        cursor,
        """
        SELECT p.proname AS name
        FROM pg_catalog.pg_proc AS p
        JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
        ORDER BY p.proname, pg_catalog.pg_get_function_identity_arguments(p.oid)
        """,
    )
    expected_functions = set(_PUBLIC_FUNCTIONS.get(profile, ()))
    for function in functions:
        name = str(function["name"])
        if name in expected_functions:
            application_count += 1
        else:
            unknown.append(f"function:{name}")
    return application_count, 0, tuple(unknown)


def normalized_managed_catalog(cursor: Cursor, profile: str) -> dict[str, object]:
    """Read and normalize the complete managed portable catalog subset."""
    tables = expected_managed_tables(profile)
    parameters = (list(tables),)
    document: dict[str, object] = {
        "normalization_profile": CATALOG_NORMALIZATION_VERSION,
        "managed_scope_version": MANAGED_SCOPE_VERSION,
        "profile": profile,
        "tables": _rows(
            cursor,
            """
            SELECT c.relname AS table_name, c.relrowsecurity AS row_security,
                    c.relforcerowsecurity AS force_row_security,
                    COALESCE(ARRAY(SELECT acl::text FROM unnest(c.relacl) acl ORDER BY acl::text), ARRAY[]::text[])
                    AS acl
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND c.relname = ANY(%s)
            ORDER BY c.relname
            """,
            parameters,
        ),
        "columns": _rows(
            cursor,
            """
            SELECT c.relname AS table_name, a.attnum AS position, a.attname AS column_name,
                    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                    a.attnotnull AS not_null, a.attidentity AS identity_kind,
                    a.attgenerated AS generated_kind,
                    pg_catalog.pg_get_expr(ad.adbin, ad.adrelid) AS default_expression,
                    COALESCE(ARRAY(SELECT acl::text FROM unnest(a.attacl) acl ORDER BY acl::text), ARRAY[]::text[])
                    AS acl
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_catalog.pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
            WHERE n.nspname = 'public' AND c.relname = ANY(%s)
                AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY c.relname, a.attnum
            """,
            parameters,
        ),
        "constraints": _rows(
            cursor,
            """
            SELECT c.relname AS table_name, con.conname AS constraint_name, con.contype AS constraint_type,
                    pg_catalog.pg_get_constraintdef(con.oid, false) AS definition
            FROM pg_catalog.pg_constraint con
            JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(%s)
            ORDER BY c.relname, con.conname
            """,
            parameters,
        ),
        "indexes": _rows(
            cursor,
            """
            SELECT table_class.relname AS table_name, index_class.relname AS index_name,
                    pg_catalog.pg_get_indexdef(index_class.oid, 0, false) AS definition
            FROM pg_catalog.pg_index idx
            JOIN pg_catalog.pg_class table_class ON table_class.oid = idx.indrelid
            JOIN pg_catalog.pg_class index_class ON index_class.oid = idx.indexrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = table_class.relnamespace
            WHERE n.nspname = 'public' AND table_class.relname = ANY(%s)
            ORDER BY table_class.relname, index_class.relname
            """,
            parameters,
        ),
        "policies": _rows(
            cursor,
            """
            SELECT c.relname AS table_name, pol.polname AS policy_name, pol.polpermissive AS permissive,
                    pol.polcmd AS command,
                    ARRAY(SELECT r.rolname FROM unnest(pol.polroles) role_oid
                        JOIN pg_catalog.pg_roles r ON r.oid = role_oid ORDER BY r.rolname) AS roles,
                    pg_catalog.pg_get_expr(pol.polqual, pol.polrelid) AS using_expression,
                    pg_catalog.pg_get_expr(pol.polwithcheck, pol.polrelid) AS check_expression
            FROM pg_catalog.pg_policy pol
            JOIN pg_catalog.pg_class c ON c.oid = pol.polrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(%s)
            ORDER BY c.relname, pol.polname
            """,
            parameters,
        ),
        "triggers": _rows(
            cursor,
            """
            SELECT c.relname AS table_name, t.tgname AS trigger_name,
                    pg_catalog.pg_get_triggerdef(t.oid, false) AS definition
            FROM pg_catalog.pg_trigger t
            JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(%s) AND NOT t.tgisinternal
            ORDER BY c.relname, t.tgname
            """,
            parameters,
        ),
        "sequences": _rows(
            cursor,
            """
            SELECT seq.relname AS sequence_name, owned.relname AS owned_table,
                    attr.attname AS owned_column, pg_catalog.format_type(s.seqtypid, NULL) AS data_type,
                    s.seqstart AS start_value, s.seqincrement AS increment_by,
                    s.seqmin AS min_value, s.seqmax AS max_value, s.seqcache AS cache_size,
                    s.seqcycle AS cycle,
                    COALESCE(ARRAY(SELECT acl::text FROM unnest(seq.relacl) acl ORDER BY acl::text), ARRAY[]::text[])
                    AS acl
            FROM pg_catalog.pg_class seq
            JOIN pg_catalog.pg_namespace n ON n.oid = seq.relnamespace
            JOIN pg_catalog.pg_sequence s ON s.seqrelid = seq.oid
            JOIN pg_catalog.pg_depend d ON d.objid = seq.oid AND d.deptype IN ('a', 'i')
            JOIN pg_catalog.pg_class owned ON owned.oid = d.refobjid
            JOIN pg_catalog.pg_attribute attr ON attr.attrelid = owned.oid AND attr.attnum = d.refobjsubid
            WHERE n.nspname = 'public' AND owned.relname = ANY(%s)
            ORDER BY seq.relname
            """,
            parameters,
        ),
        "functions": _rows(
            cursor,
            """
            SELECT p.proname AS function_name,
                    pg_catalog.pg_get_function_identity_arguments(p.oid) AS identity_arguments,
                    pg_catalog.pg_get_functiondef(p.oid) AS definition,
                    COALESCE(ARRAY(SELECT acl::text FROM unnest(p.proacl) acl ORDER BY acl::text), ARRAY[]::text[])
                    AS acl
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname = ANY(%s)
            ORDER BY p.proname, pg_catalog.pg_get_function_identity_arguments(p.oid)
            """,
            (list(_PUBLIC_FUNCTIONS.get(profile, ())),),
        ),
    }
    return document


def _history_check(cursor: Cursor, manifest: LedgerManifest, profile: str, lineage: str) -> CheckResult:
    """Compare exact ordered migration identities for an adopted lineage."""
    if lineage != "fresh-v1":
        return CheckResult("history", LEDGER_HISTORY_MISMATCH, NOT_EVALUATED, LINEAGE_NOT_ADOPTED)
    expected = [
        (entry.timestamp, entry.filename[len(entry.timestamp) + 1 : -4])
        for entry in manifest.migrations_for_profile(profile)
    ]
    try:
        cursor.execute("SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version")
        actual = [(str(version), str(name)) for version, name in cursor.fetchall()]
    except Exception:  # noqa: BLE001 - unavailable history is a bounded required-check result
        return CheckResult("history", LEDGER_HISTORY_MISMATCH, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)
    expected_digest = hashlib.sha256(canonical_catalog_bytes({"history": expected})).hexdigest()
    actual_digest = hashlib.sha256(canonical_catalog_bytes({"history": actual})).hexdigest()
    state = CHECK_PASSED if actual == expected else CHECK_DRIFT
    return CheckResult("history", LEDGER_HISTORY_MISMATCH, state, None, expected_digest, actual_digest)


def _catalog_check(
    cursor: Cursor,
    manifest: LedgerManifest,
    profile: str,
) -> tuple[CheckResult, int, int, int]:
    """Classify scope and compare the normalized profile catalog digest."""
    application_count, provider_count, unknown = _public_scope(cursor, profile)
    if unknown:
        return (
            CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, OUTSIDE_MANAGED_SCOPE),
            application_count,
            provider_count,
            len(unknown),
        )
    expected = manifest.catalog_digest_for_profile(profile)
    actual = catalog_digest(normalized_managed_catalog(cursor, profile))
    state = CHECK_PASSED if actual == expected else CHECK_DRIFT
    return (
        CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, state, None, str(expected), actual),
        application_count,
        provider_count,
        0,
    )


def _runtime_check(check: Callable[[], None] | None) -> CheckResult:
    """Run the profile-specific verify-only runtime authority check."""
    if check is None:
        return CheckResult(
            "runtime_compatibility",
            RUNTIME_COMPATIBILITY_MISMATCH,
            NOT_EVALUATED,
            REQUIRED_CHECK_NOT_EVALUATED,
        )
    try:
        check()
    except RuntimeCompatibilityMismatch:
        return CheckResult("runtime_compatibility", RUNTIME_COMPATIBILITY_MISMATCH, CHECK_DRIFT)
    except RuntimeCheckUnavailable:
        return CheckResult(
            "runtime_compatibility",
            RUNTIME_COMPATIBILITY_MISMATCH,
            NOT_EVALUATED,
            REQUIRED_CHECK_NOT_EVALUATED,
        )
    except Exception:  # noqa: BLE001 - unknown callback failures are unavailable, not proven drift
        return CheckResult(
            "runtime_compatibility",
            RUNTIME_COMPATIBILITY_MISMATCH,
            NOT_EVALUATED,
            REQUIRED_CHECK_NOT_EVALUATED,
        )
    return CheckResult("runtime_compatibility", RUNTIME_COMPATIBILITY_MISMATCH, CHECK_PASSED)


@contextmanager
def _read_only_cursor(connection: Connection) -> Iterator[Cursor]:
    """Enforce a read-only transaction and always release its snapshot."""
    connection.set_session(readonly=True, autocommit=False)
    try:
        with connection.cursor() as cursor:
            yield cursor
    finally:
        connection.rollback()


def select_public_status(checks: Sequence[CheckResult]) -> tuple[str, str | None, tuple[str, ...]]:
    """Apply ADR 0009 precedence without allowing unknown higher-priority state to be masked."""
    by_category = {check.category: check for check in checks}
    reasons = tuple(sorted({check.reason_code for check in checks if check.reason_code is not None}))
    for index, category in enumerate(_CATEGORY_ORDER):
        check = by_category[category]
        if check.state != CHECK_DRIFT:
            continue
        higher_or_equal = _CATEGORY_ORDER[: index + 1]
        if any(by_category[item].state == NOT_EVALUATED for item in higher_or_equal):
            return EVALUATION_INCOMPLETE, None, tuple(sorted(set(reasons + (HIGHER_PRIORITY_CHECK_NOT_EVALUATED,))))
        return DRIFT_DETECTED, category, reasons
    if any(check.state == NOT_EVALUATED for check in checks):
        return EVALUATION_INCOMPLETE, None, reasons
    return PASS, None, reasons


def evaluate_profile_drift(
    connection: Connection,
    manifest: LedgerManifest,
    profile: str,
    lineage: str,
    target_class: str,
    *,
    runtime_check: Callable[[], None] | None,
) -> DriftReport:
    """Evaluate all safe required checks and return only bounded public diagnostics."""
    if profile not in EXPECTED_PROFILES or lineage not in ("fresh-v1", "hosted-legacy-v1"):
        checks = (
            CheckResult("history", LEDGER_HISTORY_MISMATCH, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED),
            CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED),
            CheckResult(
                "runtime_compatibility",
                RUNTIME_COMPATIBILITY_MISMATCH,
                NOT_EVALUATED,
                REQUIRED_CHECK_NOT_EVALUATED,
            ),
        )
        status, primary, reasons = select_public_status(checks)
        return DriftReport(
            status,
            primary,
            reasons,
            target_class,
            profile,
            lineage,
            CATALOG_NORMALIZATION_VERSION,
            MANAGED_SCOPE_VERSION,
            3,
            0,
            3,
            0,
            0,
            0,
            None,
            None,
        )

    application_count = provider_count = unknown_count = 0
    history = CheckResult("history", LEDGER_HISTORY_MISMATCH, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)
    catalog = CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)
    try:
        with _read_only_cursor(connection) as cursor:
            history = _history_check(cursor, manifest, profile, lineage)
            catalog, application_count, provider_count, unknown_count = _catalog_check(cursor, manifest, profile)
    except Exception:  # noqa: BLE001 - transaction/catalog unavailability is a bounded required-check result
        catalog = CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)
    runtime = _runtime_check(runtime_check)
    checks = (history, catalog, runtime)
    status, primary, reasons = select_public_status(checks)
    not_evaluated = sum(check.state == NOT_EVALUATED for check in checks)
    return DriftReport(
        status,
        primary,
        reasons,
        target_class,
        profile,
        lineage,
        CATALOG_NORMALIZATION_VERSION,
        MANAGED_SCOPE_VERSION,
        len(checks),
        len(checks) - not_evaluated,
        not_evaluated,
        application_count,
        provider_count,
        unknown_count,
        catalog.expected_digest,
        catalog.actual_digest,
    )
