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
_PUBLIC_FUNCTIONS: Mapping[str, tuple[tuple[str, str], ...]] = {
    "auth": (),
    "graph": (("grac_v1_reject_mutation", ""),),
    "coordination": (),
    "combined": (("grac_v1_reject_mutation", ""),),
}
_PROVIDER_SCHEMAS = frozenset(
    {
        "auth",
        "extensions",
        "graphql",
        "graphql_public",
        "net",
        "pgbouncer",
        "pgmq",
        "realtime",
        "storage",
        "supabase_functions",
        "supabase_migrations",
        "vault",
    }
)
_PROVIDER_EXTENSIONS = frozenset({"plpgsql"})
_APPLICATION_EXTENSIONS: Mapping[str, tuple[str, ...]] = {
    "auth": (),
    "graph": (),
    "coordination": (),
    "combined": (),
}
_SQL_TEXT_COLUMNS = frozenset({"check_expression", "default_expression", "definition", "using_expression"})


class Cursor(Protocol):
    """Minimal DB-API cursor surface used by the read-only evaluator."""

    description: Sequence[Sequence[Any]] | None

    def execute(self, query: str, parameters: object | None = None) -> object:
        """Execute one read-only catalog query."""
        raise NotImplementedError

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Return all rows from the current query."""
        raise NotImplementedError

    def __enter__(self) -> Cursor:
        """Enter the cursor context."""
        raise NotImplementedError

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """Exit the cursor context."""
        raise NotImplementedError


class Connection(Protocol):
    """Minimal DB-API connection surface used by the read-only evaluator."""

    def cursor(self) -> Cursor:
        """Return a cursor context manager."""
        raise NotImplementedError

    def set_session(self, *, readonly: bool, autocommit: bool) -> None:
        """Set the transaction safety posture before catalog access."""
        raise NotImplementedError

    def rollback(self) -> None:
        """Close the evaluator transaction without preserving any effects."""
        raise NotImplementedError


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
    """Sort order-insensitive arrays while preserving identifiers exactly."""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return {str(key): _normalized_text(item) for key, item in value.items()}
    if isinstance(value, list):
        normalized: list[object] = [_normalized_text(item) for item in value]
        strings = [item for item in normalized if isinstance(item, str)]
        if len(strings) == len(normalized):
            return sorted(strings)
        return normalized
    return value


def _string_token_end(value: str, index: int, delimiter: str, escape_backslashes: bool = False) -> int | None:
    """Scan one SQL string or identifier without regex backtracking."""
    while index < len(value):
        if escape_backslashes and value[index] == "\\":
            index += 2
            continue
        if value[index] == delimiter:
            if index + 1 < len(value) and value[index + 1] == delimiter:
                index += 2
                continue
            return index + 1
        index += 1
    return None


def _dollar_token_end(value: str, start: int) -> int | None:
    """Scan one PostgreSQL dollar-quoted body with an identifier tag."""
    tag_end = start + 1
    if tag_end < len(value) and value[tag_end] != "$":
        if not (value[tag_end].isalpha() or value[tag_end] == "_"):
            return None
        tag_end += 1
        while tag_end < len(value) and (value[tag_end].isalnum() or value[tag_end] == "_"):
            tag_end += 1
    if tag_end >= len(value) or value[tag_end] != "$":
        return None
    delimiter = value[start : tag_end + 1]
    closing = value.find(delimiter, tag_end + 1)
    return None if closing < 0 else closing + len(delimiter)


def _quoted_sql_token_end(value: str, start: int) -> int | None:
    """Return the exclusive end of a quoted token using bounded scanners."""
    if value.startswith("E'", start):
        return _string_token_end(value, start + 2, "'", True)
    if value[start] in {"'", '"'}:
        return _string_token_end(value, start + 1, value[start])
    if value[start] == "$":
        return _dollar_token_end(value, start)
    return None


def _normalize_sql_text(value: str) -> str:
    """Collapse deparser whitespace outside quoted SQL tokens and bodies."""
    output: list[str] = []
    pending_space = False
    index = 0
    while index < len(value):
        token_end = _quoted_sql_token_end(value, index)
        if token_end is not None:
            fragment = value[index:token_end]
            index = token_end
        elif value[index].isspace():
            pending_space = True
            index += 1
            continue
        else:
            fragment = value[index]
            index += 1
        if pending_space and output:
            output.append(" ")
        output.append(fragment)
        pending_space = False
    return "".join(output)


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
    rows: list[dict[str, object]] = []
    for row in cursor.fetchall():
        mapped = dict(zip(columns, row, strict=True))
        for column in _SQL_TEXT_COLUMNS.intersection(mapped):
            value = mapped[column]
            if isinstance(value, str):
                mapped[column] = _normalize_sql_text(value)
        rows.append(mapped)
    return rows


def expected_managed_tables(profile: str) -> tuple[str, ...]:
    """Return the sorted managed-table set for one exact build profile."""
    components = EXPECTED_PROFILES.get(profile)
    if components is None:
        return ()
    return tuple(sorted(table for component in components for table in EXPECTED_MANAGED_TABLES[component]))


def _classify_public_object(item: Mapping[str, object], managed_tables: tuple[str, ...], profile: str) -> bool:
    """Return whether one independently addressable public object is profile-owned."""
    object_type = str(item["object_type"])
    name = str(item["name"])
    parent = item.get("parent_table")
    if object_type == "relation":
        kind = str(item["kind"])
        if kind in ("r", "p"):
            return name in managed_tables
        if kind in ("S", "i", "I"):
            return parent in managed_tables
        return False
    if object_type in ("policy", "trigger", "type"):
        return parent in managed_tables
    if object_type == "function":
        return (name, str(item["identity_arguments"])) in _PUBLIC_FUNCTIONS.get(profile, ())
    return False


def _public_scope(cursor: Cursor, profile: str) -> tuple[int, int, tuple[str, ...]]:
    """Totally classify contracted schemas and independently addressable objects."""
    managed_tables = expected_managed_tables(profile)
    objects = _rows(
        cursor,
        """
        SELECT 'relation' AS object_type, c.relname AS name, c.relkind AS kind,
            COALESCE(owned.relname, indexed.relname) AS parent_table,
            NULL::text AS identity_arguments
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        LEFT JOIN pg_catalog.pg_depend AS d
            ON c.relkind = 'S' AND d.objid = c.oid AND d.deptype IN ('a', 'i')
        LEFT JOIN pg_catalog.pg_class AS owned ON owned.oid = d.refobjid
        LEFT JOIN pg_catalog.pg_index AS idx ON idx.indexrelid = c.oid
        LEFT JOIN pg_catalog.pg_class AS indexed ON indexed.oid = idx.indrelid
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f', 'i', 'I')
        UNION ALL
        SELECT 'function', p.proname, NULL, NULL,
            pg_catalog.pg_get_function_identity_arguments(p.oid)
        FROM pg_catalog.pg_proc AS p
        JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
        UNION ALL
        SELECT 'policy', pol.polname, NULL, c.relname, NULL
        FROM pg_catalog.pg_policy AS pol
        JOIN pg_catalog.pg_class AS c ON c.oid = pol.polrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
        UNION ALL
        SELECT 'trigger', t.tgname, NULL, c.relname, NULL
        FROM pg_catalog.pg_trigger AS t
        JOIN pg_catalog.pg_class AS c ON c.oid = t.tgrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND NOT t.tgisinternal
        UNION ALL
        SELECT 'type', typ.typname, NULL, relation.relname, NULL
        FROM pg_catalog.pg_type AS typ
        JOIN pg_catalog.pg_namespace AS n ON n.oid = typ.typnamespace
        LEFT JOIN pg_catalog.pg_class AS relation ON relation.oid = typ.typrelid
        WHERE n.nspname = 'public' AND typ.typtype IN ('c', 'd', 'e')
        ORDER BY 1, 2, 5
        """,
    )
    schemas = _rows(
        cursor,
        """
        SELECT n.nspname AS name,
            n.nspname IN ('pg_catalog', 'information_schema', 'pg_toast')
                OR pg_catalog.pg_is_other_temp_schema(n.oid)
                OR n.oid = pg_catalog.pg_my_temp_schema() AS system_schema
        FROM pg_catalog.pg_namespace AS n
        WHERE n.nspname <> 'public'
        ORDER BY n.nspname
        """,
    )
    extensions = _rows(
        cursor,
        """
        SELECT ext.extname AS name
        FROM pg_catalog.pg_extension AS ext
        ORDER BY ext.extname
        """,
    )
    application_count = sum(_classify_public_object(item, managed_tables, profile) for item in objects)
    unknown = [
        f"{item['object_type']}:{item['name']}"
        for item in objects
        if not _classify_public_object(item, managed_tables, profile)
    ]
    provider_count = 0
    for schema in schemas:
        if bool(schema["system_schema"]) or schema["name"] in _PROVIDER_SCHEMAS:
            provider_count += 1
        else:
            unknown.append(f"schema:{schema['name']}")
    for extension in extensions:
        if extension["name"] in _PROVIDER_EXTENSIONS:
            provider_count += 1
        else:
            unknown.append(f"extension:{extension['name']}")
    return application_count, provider_count, tuple(unknown)


def normalized_managed_catalog(cursor: Cursor, profile: str) -> dict[str, object]:
    """Read and normalize the complete managed portable catalog subset."""
    tables = expected_managed_tables(profile)
    parameters = (list(tables),)
    document: dict[str, object] = {
        "normalization_profile": CATALOG_NORMALIZATION_VERSION,
        "managed_scope_version": MANAGED_SCOPE_VERSION,
        "profile": profile,
        "schemas": _rows(
            cursor,
            """
            SELECT n.nspname AS schema_name,
                COALESCE(ARRAY(SELECT acl::text FROM unnest(n.nspacl) acl ORDER BY acl::text), ARRAY[]::text[]) AS acl
            FROM pg_catalog.pg_namespace AS n
            WHERE n.nspname = 'public'
            ORDER BY n.nspname
            """,
        ),
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
        "types": _rows(
            cursor,
            """
            SELECT typ.typname AS type_name, typ.typtype AS type_kind,
                relation.relname AS relation_name,
                pg_catalog.format_type(typ.typbasetype, typ.typtypmod) AS base_type,
                typ.typnotnull AS not_null,
                typ.typdefault AS default_expression,
                COALESCE(ARRAY(
                    SELECT enum.enumlabel FROM pg_catalog.pg_enum AS enum
                    WHERE enum.enumtypid = typ.oid ORDER BY enum.enumsortorder
                ), ARRAY[]::text[]) AS enum_labels,
                COALESCE(ARRAY(
                    SELECT acl::text FROM unnest(typ.typacl) acl ORDER BY acl::text
                ), ARRAY[]::text[]) AS acl
            FROM pg_catalog.pg_type AS typ
            JOIN pg_catalog.pg_namespace AS n ON n.oid = typ.typnamespace
            LEFT JOIN pg_catalog.pg_class AS relation ON relation.oid = typ.typrelid
            WHERE n.nspname = 'public'
                AND typ.typtype IN ('c', 'd', 'e')
                AND (relation.relname = ANY(%s) OR typ.typtype IN ('d', 'e'))
            ORDER BY typ.typname
            """,
            parameters,
        ),
        "extensions": _rows(
            cursor,
            """
            SELECT ext.extname AS extension_name, ext.extversion AS extension_version,
                namespace.nspname AS schema_name
            FROM pg_catalog.pg_extension AS ext
            JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = ext.extnamespace
            WHERE ext.extname = ANY(%s)
            ORDER BY ext.extname
            """,
            (list(_APPLICATION_EXTENSIONS.get(profile, ())),),
        ),
        "default_privileges": _rows(
            cursor,
            """
            SELECT COALESCE(namespace.nspname, '') AS schema_name, defaults.defaclobjtype AS object_type,
                COALESCE(ARRAY(
                    SELECT pg_catalog.format(
                        '%s=%s%s',
                        CASE WHEN expanded.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END,
                        expanded.privilege_type,
                        CASE WHEN expanded.is_grantable THEN ':grantable' ELSE '' END
                    )
                    FROM pg_catalog.aclexplode(defaults.defaclacl) AS expanded
                    LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = expanded.grantee
                    ORDER BY 1
                ), ARRAY[]::text[]) AS acl
            FROM pg_catalog.pg_default_acl AS defaults
            LEFT JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = defaults.defaclnamespace
            WHERE namespace.nspname = 'public' OR defaults.defaclnamespace = 0
            ORDER BY 1, 2, 3
            """,
        ),
        "functions": _rows(
            cursor,
            """
            SELECT p.proname AS function_name, owner.rolname AS owner_role,
                    pg_catalog.pg_get_function_identity_arguments(p.oid) AS identity_arguments,
                    pg_catalog.pg_get_functiondef(p.oid) AS definition,
                    COALESCE(ARRAY(SELECT acl::text FROM unnest(p.proacl) acl ORDER BY acl::text), ARRAY[]::text[])
                    AS acl
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_catalog.pg_roles owner ON owner.oid = p.proowner
            WHERE n.nspname = 'public' AND p.proname = ANY(%s)
            ORDER BY p.proname, pg_catalog.pg_get_function_identity_arguments(p.oid)
            """,
            ([name for name, _arguments in _PUBLIC_FUNCTIONS.get(profile, ())],),
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
