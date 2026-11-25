"""Evaluate FarDB PostgreSQL ledger, catalog, and runtime drift read-only."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from scripts.postgresql_ledger import (
    CATALOG_NORMALIZATION_VERSION,
    EXPECTED_MANAGED_TABLES,
    EXPECTED_PROFILES,
    MANAGED_SCOPE_VERSION,
    LedgerManifest,
    MigrationEntry,
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
ADOPTION_MARKER_INVALID = "ADOPTION_MARKER_INVALID"

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
_LEGACY_TABLES = frozenset(
    {
        "financial_data",
        "fundamental_analysis",
        "market_alerts",
        "news_articles",
        "portfolio_holdings",
        "portfolios",
        "transactions",
        "user_preferences",
    }
)
_LEGACY_INDEXES: Mapping[str, tuple[str, bool, bool]] = MappingProxyType(
    {
        "financial_data_pkey": ("financial_data", True, True),
        "idx_financial_data_symbol": ("financial_data", False, False),
        "idx_financial_data_symbol_timestamp": ("financial_data", False, False),
        "idx_financial_data_timestamp": ("financial_data", False, False),
        "fundamental_analysis_pkey": ("fundamental_analysis", True, True),
        "idx_fundamental_analysis_created": ("fundamental_analysis", False, False),
        "idx_fundamental_analysis_symbol": ("fundamental_analysis", False, False),
        "market_alerts_pkey": ("market_alerts", True, True),
        "idx_alerts_user_id": ("market_alerts", False, False),
        "idx_market_alerts_active": ("market_alerts", False, False),
        "idx_market_alerts_user": ("market_alerts", False, False),
        "news_articles_pkey": ("news_articles", True, True),
        "idx_news_articles_published": ("news_articles", False, False),
        "idx_news_articles_source": ("news_articles", False, False),
        "idx_news_articles_url": ("news_articles", True, False),
        "portfolio_holdings_pkey": ("portfolio_holdings", True, True),
        "idx_holdings_portfolio_id": ("portfolio_holdings", False, False),
        "idx_portfolio_holdings_portfolio": ("portfolio_holdings", False, False),
        "portfolios_pkey": ("portfolios", True, True),
        "idx_portfolios_user": ("portfolios", False, False),
        "idx_portfolios_user_id": ("portfolios", False, False),
        "transactions_pkey": ("transactions", True, True),
        "idx_transactions_date": ("transactions", False, False),
        "idx_transactions_portfolio": ("transactions", False, False),
        "idx_transactions_portfolio_id": ("transactions", False, False),
        "user_preferences_pkey": ("user_preferences", True, True),
        "user_preferences_user_id_key": ("user_preferences", True, False),
        "idx_prefs_user_id": ("user_preferences", False, False),
        "idx_user_preferences_user_id": ("user_preferences", False, False),
    }
)
# Values bind the normalized index definition digest, applicable NULL semantics, and ready/valid posture.
# Every baseline is absent until the ratifier supplies approved catalog evidence.
_LEGACY_INDEX_BASELINES: Mapping[str, tuple[str, bool | None, bool, bool] | None] = MappingProxyType(
    {name: None for name in _LEGACY_INDEXES}
)
# The helper is fail-closed until a custodian supplies its approved definition digest and pinned proconfig.
_RESTRICTED_HELPER_DEFINITION_SHA256: str | None = None
_RESTRICTED_HELPER_PROCONFIG: tuple[str, ...] | None = None
_PROVIDER_EXTENSION_IDENTITIES: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "hypopg": ("extensions", "supabase_admin"),
        "index_advisor": ("extensions", "supabase_admin"),
        "pg_graphql": ("graphql", "supabase_admin"),
        "pg_net": ("extensions", "supabase_admin"),
        "pg_stat_statements": ("extensions", "supabase_admin"),
        "pgcrypto": ("extensions", "supabase_admin"),
        "pgmq": ("pgmq", "postgres"),
        "plpgsql": ("pg_catalog", "supabase_admin"),
        "supabase_vault": ("vault", "supabase_admin"),
        "uuid-ossp": ("extensions", "supabase_admin"),
        "wrappers": ("extensions", "supabase_admin"),
    }
)
_RESTRICTED_ROLES = frozenset(
    {
        "anon",
        "authenticated",
        "fardb_runtime_auth",
        "fardb_runtime_graph",
        "fardb_runtime_coordination",
        "fardb_login_auth",
        "fardb_login_graph",
        "fardb_login_coordination",
    }
)
_LEGACY_TABLE_PRIVILEGES = ("DELETE", "INSERT", "REFERENCES", "SELECT", "TRIGGER", "TRUNCATE", "UPDATE")

_SQL_TEXT_COLUMNS = frozenset(
    {"check_expression", "default_expression", "definition", "index_definition", "using_expression"}
)


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
    history: str
    catalog: str
    runtime_compatibility: str
    required_check_count: int
    evaluated_check_count: int
    not_evaluated_count: int
    application_owned_count: int
    provider_owned_count: int
    unknown_count: int
    expected_catalog_digest: str | None
    actual_catalog_digest: str | None
    protected_legacy_count: int = 0
    restricted_helper_count: int = 0

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
            "history": self.history,
            "catalog": self.catalog,
            "runtime_compatibility": self.runtime_compatibility,
            "required_check_count": self.required_check_count,
            "evaluated_check_count": self.evaluated_check_count,
            "not_evaluated_count": self.not_evaluated_count,
            "application_owned_count": self.application_owned_count,
            "provider_owned_count": self.provider_owned_count,
            "unknown_count": self.unknown_count,
            "protected_legacy_count": self.protected_legacy_count,
            "restricted_helper_count": self.restricted_helper_count,
            "expected_catalog_digest": self.expected_catalog_digest,
            "actual_catalog_digest": self.actual_catalog_digest,
        }


def _normalized_text(value: object) -> object:
    """Sort order-insensitive arrays while preserving identifiers exactly."""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        normalized_mapping: dict[str, object] = {}
        for key, item in value.items():
            name = str(key)
            if name == "acl" and isinstance(item, list):
                item = [_acl_without_grantor(str(entry)) for entry in item]
            normalized_mapping[name] = _normalized_text(item)
        return normalized_mapping
    if isinstance(value, list):
        normalized: list[object] = [_normalized_text(item) for item in value]
        strings = [item for item in normalized if isinstance(item, str)]
        if len(strings) == len(normalized):
            return sorted(strings)
        return normalized
    return value


def _acl_without_grantor(value: str) -> str:
    """Remove the environment-specific grantor from one PostgreSQL ACL item."""
    quoted = False
    privileges = False
    index = 0
    while index < len(value):
        if value[index] == '"':
            if quoted and index + 1 < len(value) and value[index + 1] == '"':
                index += 2
                continue
            quoted = not quoted
        elif not quoted and value[index] == "=":
            privileges = True
        elif not quoted and privileges and value[index] == "/":
            return value[:index]
        index += 1
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
    normalized = _normalized_text(document)
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


def _psycopg_error_types() -> tuple[type[BaseException], ...]:
    """Load the optional driver error type only when handling a database failure."""
    try:
        from psycopg2 import Error as PsycopgError
    except ImportError:
        return ()
    return (PsycopgError,)


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


def _legacy_table_posture(cursor: Cursor) -> set[str]:
    """Identify only legacy tables whose live RLS and grants match reviewed evidence."""
    rows = _rows(
        cursor,
        """
        SELECT c.relname AS name, owner.rolname AS owner_role,
            c.relrowsecurity AS row_security, c.relforcerowsecurity AS force_row_security,
            (SELECT count(*) FROM pg_catalog.pg_policy pol WHERE pol.polrelid = c.oid) AS policy_count,
            current_setting('server_version_num')::integer AS server_version_num,
            ARRAY(
                SELECT grantee.rolname || ':' || privilege_type || ':' || is_grantable::text
                FROM pg_catalog.aclexplode(COALESCE(c.relacl, '{}'::aclitem[])) AS acl
                LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = acl.grantee
                ORDER BY 1
            ) AS grants,
            ARRAY(
                SELECT restricted_role.rolname || ':' || privilege.privilege_type
                FROM pg_catalog.pg_roles restricted_role
                JOIN pg_catalog.pg_roles reachable ON reachable.oid = restricted_role.oid OR pg_catalog.pg_has_role(
                    restricted_role.oid, reachable.oid,
                    CASE WHEN current_setting('server_version_num')::integer >= 160000 THEN 'SET' ELSE 'MEMBER' END
                )
                CROSS JOIN LATERAL unnest(
                    ARRAY['DELETE', 'INSERT', 'REFERENCES', 'SELECT', 'TRIGGER', 'TRUNCATE', 'UPDATE']::text[]
                    || CASE
                        WHEN current_setting('server_version_num')::integer >= 170000
                        THEN ARRAY['MAINTAIN']::text[]
                        ELSE ARRAY[]::text[]
                    END
                ) AS privilege(privilege_type)
                WHERE restricted_role.rolname = ANY(%s)
                  AND (
                      pg_catalog.has_table_privilege(reachable.oid, c.oid, privilege.privilege_type)
                      OR (
                          privilege.privilege_type IN ('SELECT', 'INSERT', 'REFERENCES', 'UPDATE')
                          AND pg_catalog.has_any_column_privilege(
                              reachable.oid, c.oid, privilege.privilege_type
                          )
                      )
                  )
                ORDER BY 1
            ) AS restricted_effective_privileges,
            EXISTS (
                SELECT 1 FROM pg_catalog.pg_attribute a
                WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
                  AND cardinality(a.attacl) > 0
            ) AS has_column_acl
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_roles owner ON owner.oid = c.relowner
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname = ANY(%s)
        """,
        (sorted(_RESTRICTED_ROLES), sorted(_LEGACY_TABLES)),
    )
    safe_tables: set[str] = set()
    for row in rows:
        version = row["server_version_num"]
        grants = row["grants"]
        restricted_privileges = row["restricted_effective_privileges"]
        if (
            not isinstance(version, int)
            or not isinstance(grants, (tuple, list))
            or not isinstance(restricted_privileges, (tuple, list))
        ):
            continue
        expected_grants = _legacy_table_grants(version)
        if all(
            (
                row["owner_role"] == "postgres",
                row["row_security"] is True,
                row["force_row_security"] is True,
                row["policy_count"] == 0,
                set(grants) == expected_grants,
                len(grants) == len(expected_grants),
                restricted_privileges == [],
                row["has_column_acl"] is False,
            )
        ):
            safe_tables.add(str(row["name"]))
    return safe_tables


def _legacy_table_grants(server_version_num: int) -> frozenset[str]:
    """Return the exact reviewed legacy ACL entries for the connected PostgreSQL version."""
    privileges = _LEGACY_TABLE_PRIVILEGES + (("MAINTAIN",) if server_version_num >= 170000 else ())
    return frozenset(f"{role}:{privilege}:false" for role in ("postgres", "service_role") for privilege in privileges)


def _restricted_helper_posture(cursor: Cursor) -> bool:
    """Require the reviewed helper definition, configuration, signature and role restrictions."""
    rows = _rows(
        cursor,
        """
        SELECT p.proname AS name, pg_catalog.pg_get_function_identity_arguments(p.oid) AS arguments,
            pg_catalog.format_type(p.prorettype, NULL) AS return_type,
            p.proretset AS returns_set,
            lang.lanname AS language, p.provolatile AS volatility, p.prosecdef AS security_definer,
            owner.rolname AS owner_role,
            CASE WHEN p.prokind = 'f' THEN pg_catalog.pg_get_functiondef(p.oid) END AS definition,
            COALESCE(p.proconfig, ARRAY[]::text[]) AS proconfig,
            COALESCE(
                ARRAY(SELECT acl::text FROM unnest(COALESCE(p.proacl, '{}'::aclitem[])) AS acl ORDER BY acl::text),
                ARRAY[]::text[]
            ) AS acl_entries,
            ARRAY(
                SELECT role.rolname FROM pg_catalog.pg_roles role
                JOIN pg_catalog.pg_roles reachable ON reachable.oid = role.oid OR pg_catalog.pg_has_role(
                    role.oid, reachable.oid,
                    CASE WHEN current_setting('server_version_num')::integer >= 160000 THEN 'SET' ELSE 'MEMBER' END
                )
                WHERE role.rolname = ANY(%s)
                  AND pg_catalog.has_function_privilege(reachable.oid, p.oid, 'EXECUTE')
                ORDER BY role.rolname
            ) AS effective_untrusted_roles
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_catalog.pg_language lang ON lang.oid = p.prolang
        JOIN pg_catalog.pg_roles owner ON owner.oid = p.proowner
        WHERE n.nspname = 'public' AND p.proname = 'is_requester_admin'
        """,
        (sorted(_RESTRICTED_ROLES),),
    )
    if len(rows) != 1 or _RESTRICTED_HELPER_DEFINITION_SHA256 is None or _RESTRICTED_HELPER_PROCONFIG is None:
        return False
    definition = rows[0]["definition"]
    proconfig = rows[0]["proconfig"]
    if not isinstance(definition, str) or not isinstance(proconfig, (tuple, list)):
        return False
    if not all(isinstance(value, str) for value in proconfig):
        return False
    definition_digest = hashlib.sha256(definition.encode("utf-8")).hexdigest()
    normalized_proconfig = tuple(sorted(proconfig))
    return (
        definition_digest == _RESTRICTED_HELPER_DEFINITION_SHA256
        and normalized_proconfig == tuple(sorted(_RESTRICTED_HELPER_PROCONFIG))
        and all(
            (
                rows[0]["arguments"] == "",
                rows[0]["return_type"] == "boolean",
                rows[0]["returns_set"] is False,
                rows[0]["language"] == "sql",
                rows[0]["volatility"] == "v",
                rows[0]["security_definer"] is True,
                rows[0]["owner_role"] == "postgres",
                rows[0]["acl_entries"] == ["postgres=X/postgres", "service_role=X/postgres"],
                rows[0]["effective_untrusted_roles"] == [],
            )
        )
    )


def _classify_legacy_object(item: Mapping[str, object], safe_tables: set[str]) -> bool:
    """Accept a legacy identity only with its reviewed parent and owner."""
    name = item.get("name")
    if item.get("owner_role") != "postgres":
        return False
    if item.get("object_type") == "relation":
        if item.get("kind") == "r":
            return name in safe_tables and item.get("parent_table") is None
        if item.get("kind") == "i":
            expected = _LEGACY_INDEXES.get(str(name))
            baseline = _LEGACY_INDEX_BASELINES.get(str(name))
            definition = item.get("index_definition")
            null_semantics_match = expected is not None and (
                baseline is not None
                and (
                    (baseline[1] is None and (not expected[1] or expected[2]))
                    or (baseline[1] is not None and item.get("nulls_not_distinct") is baseline[1])
                )
            )
            return (
                expected is not None
                and baseline is not None
                and isinstance(definition, str)
                and hashlib.sha256(_normalize_sql_text(definition).encode("utf-8")).hexdigest() == baseline[0]
                and (item.get("parent_table"), item.get("is_unique"), item.get("is_primary")) == expected
                and null_semantics_match
                and baseline[2] is True
                and item.get("is_valid") is baseline[2]
                and baseline[3] is True
                and item.get("is_ready") is baseline[3]
                and expected[0] in safe_tables
            )
    if item.get("object_type") == "type":
        return name in safe_tables and item.get("parent_table") == name and item.get("type_kind") == "c"
    return False


def _is_legacy_inventory_candidate(item: Mapping[str, object]) -> bool:
    """Return whether one identity makes the reviewed legacy inventory present."""
    object_type = item["object_type"]
    name = item["name"]
    kind = item["kind"]
    if object_type == "relation":
        return (kind == "r" and name in _LEGACY_TABLES) or (kind == "i" and name in _LEGACY_INDEXES)
    return object_type == "type" and name in _LEGACY_TABLES


def _legacy_inventory_is_complete(
    objects: Sequence[Mapping[str, object]], *, require_inventory: bool, legacy_present: bool, helper_present: bool
) -> bool:
    """Require each exact legacy identity and the helper when legacy posture applies."""
    expected = (
        {("relation", name, "r") for name in _LEGACY_TABLES}
        | {("relation", name, "i") for name in _LEGACY_INDEXES}
        | {("type", name, None) for name in _LEGACY_TABLES}
    )
    found = {
        (item["object_type"], item["name"], item["kind"]) for item in objects if _is_legacy_inventory_candidate(item)
    }
    inventory_applies = require_inventory or legacy_present or helper_present
    return not inventory_applies or (found == expected and helper_present)


def _is_provider_extension(
    extension: Mapping[str, object], *, allow_loopback_test_owner: bool, legacy_present: bool, helper_present: bool
) -> bool:
    """Match the exact provider extension identity with the narrow loopback exception."""
    name = str(extension["name"])
    expected = _PROVIDER_EXTENSION_IDENTITIES.get(name)
    if expected is None:
        return False
    if (extension.get("schema_name"), extension.get("owner_role")) == expected:
        return True
    loopback_owner = allow_loopback_test_owner and not legacy_present and not helper_present
    return (
        name == "plpgsql"
        and extension.get("schema_name") == "pg_catalog"
        and loopback_owner
        and extension.get("owner_role") in {"postgres", "test"}
    )


def _classify_public_objects(
    objects: Sequence[Mapping[str, object]],
    managed_tables: tuple[str, ...],
    profile: str,
    safe_tables: set[str],
    helper_safe: bool,
) -> tuple[int, int, int, tuple[str, ...]]:
    """Return application, legacy, and helper counts plus unknown object identities."""
    application_count = 0
    legacy_count = 0
    helper_count = 0
    unknown: list[str] = []
    for item in objects:
        if _classify_public_object(item, managed_tables, profile):
            application_count += 1
        elif _classify_legacy_object(item, safe_tables):
            legacy_count += 1
        elif (
            helper_safe
            and item["object_type"] == "function"
            and item["name"] == "is_requester_admin"
            and item["identity_arguments"] == ""
        ):
            helper_count += 1
        else:
            unknown.append(f"{item['object_type']}:{item['name']}")
    return application_count, legacy_count, helper_count, tuple(unknown)


def _provider_scope_counts(
    schemas: Sequence[Mapping[str, object]],
    extensions: Sequence[Mapping[str, object]],
    *,
    inventory_applies: bool,
    allow_loopback_test_owner: bool,
    legacy_present: bool,
    helper_present: bool,
) -> tuple[int, tuple[str, ...]]:
    """Count verified provider schemas/extensions and return unknown identities."""
    provider_count = 0
    unknown: list[str] = []
    for schema in schemas:
        if bool(schema["system_schema"]) or schema["name"] in _PROVIDER_SCHEMAS:
            provider_count += 1
        else:
            unknown.append(f"schema:{schema['name']}")
    if inventory_applies and {str(extension["name"]) for extension in extensions} != set(
        _PROVIDER_EXTENSION_IDENTITIES
    ):
        unknown.append("extension:incomplete")
    for extension in extensions:
        if _is_provider_extension(
            extension,
            allow_loopback_test_owner=allow_loopback_test_owner,
            legacy_present=legacy_present,
            helper_present=helper_present,
        ):
            provider_count += 1
        else:
            unknown.append(f"extension:{str(extension['name'])}")
    return provider_count, tuple(unknown)


def _legacy_posture_state(
    cursor: Cursor, objects: Sequence[Mapping[str, object]], *, require_inventory: bool
) -> tuple[bool, set[str], bool, bool, bool]:
    """Return presence, verified posture, and completeness for restricted legacy identities."""
    legacy_present = any(_is_legacy_inventory_candidate(item) for item in objects)
    safe_tables = _legacy_table_posture(cursor) if legacy_present else set()
    helper_present = any(item["object_type"] == "function" and item["name"] == "is_requester_admin" for item in objects)
    helper_safe = _restricted_helper_posture(cursor) if helper_present else False
    complete = _legacy_inventory_is_complete(
        objects,
        require_inventory=require_inventory,
        legacy_present=legacy_present,
        helper_present=helper_present,
    )
    return legacy_present, safe_tables, helper_present, helper_safe, complete


def _public_scope(
    cursor: Cursor, profile: str, *, allow_loopback_test_owner: bool = False, require_legacy_inventory: bool = False
) -> tuple[int, int, int, int, tuple[str, ...]]:
    """Totally classify contracted schemas and independently addressable objects."""
    managed_tables = expected_managed_tables(profile)
    objects = _rows(
        cursor,
        """
        SELECT 'relation' AS object_type, c.relname AS name, c.relkind AS kind,
            COALESCE(owned.relname, indexed.relname) AS parent_table,
            NULL::text AS identity_arguments, owner.rolname AS owner_role,
            idx.indisunique AS is_unique, idx.indisprimary AS is_primary, idx.indnullsnotdistinct AS nulls_not_distinct,
            CASE WHEN c.relkind IN ('i', 'I') THEN pg_catalog.pg_get_indexdef(c.oid) END AS index_definition,
            idx.indisvalid AS is_valid, idx.indisready AS is_ready, NULL::text AS type_kind
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = c.relowner
        LEFT JOIN pg_catalog.pg_depend AS d
            ON c.relkind = 'S' AND d.objid = c.oid AND d.deptype IN ('a', 'i')
        LEFT JOIN pg_catalog.pg_class AS owned ON owned.oid = d.refobjid
        LEFT JOIN pg_catalog.pg_index AS idx ON idx.indexrelid = c.oid
        LEFT JOIN pg_catalog.pg_class AS indexed ON indexed.oid = idx.indrelid
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f', 'i', 'I')
        UNION ALL
        SELECT 'function', p.proname, NULL, NULL,
            pg_catalog.pg_get_function_identity_arguments(p.oid), owner.rolname, NULL, NULL, NULL, NULL, NULL, NULL, NULL
        FROM pg_catalog.pg_proc AS p
        JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = p.proowner
        WHERE n.nspname = 'public'
        UNION ALL
        SELECT 'policy', pol.polname, NULL, c.relname, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
        FROM pg_catalog.pg_policy AS pol
        JOIN pg_catalog.pg_class AS c ON c.oid = pol.polrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
        UNION ALL
        SELECT 'trigger', t.tgname, NULL, c.relname, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
        FROM pg_catalog.pg_trigger AS t
        JOIN pg_catalog.pg_class AS c ON c.oid = t.tgrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND NOT t.tgisinternal
        UNION ALL
        SELECT 'type', typ.typname, NULL, relation.relname, NULL,
            owner.rolname, NULL, NULL, NULL, NULL, NULL, NULL, typ.typtype::text
        FROM pg_catalog.pg_type AS typ
        JOIN pg_catalog.pg_namespace AS n ON n.oid = typ.typnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = typ.typowner
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
        SELECT ext.extname AS name, n.nspname AS schema_name, owner.rolname AS owner_role
        FROM pg_catalog.pg_extension AS ext
        JOIN pg_catalog.pg_namespace AS n ON n.oid = ext.extnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = ext.extowner
        ORDER BY ext.extname
        """,
    )
    legacy_present, safe_tables, helper_present, helper_safe, legacy_complete = _legacy_posture_state(
        cursor, objects, require_inventory=require_legacy_inventory
    )
    unknown: list[str] = []
    if not legacy_complete:
        unknown.append("legacy:incomplete")
    inventory_applies = require_legacy_inventory or legacy_present or helper_present
    application_count, legacy_count, helper_count, object_unknown = _classify_public_objects(
        objects, managed_tables, profile, safe_tables, helper_safe
    )
    provider_count, provider_unknown = _provider_scope_counts(
        schemas,
        extensions,
        inventory_applies=inventory_applies,
        allow_loopback_test_owner=allow_loopback_test_owner,
        legacy_present=legacy_present,
        helper_present=helper_present,
    )
    unknown.extend(object_unknown)
    unknown.extend(provider_unknown)
    return application_count, provider_count, legacy_count, helper_count, tuple(unknown)


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
            SELECT c.relname AS table_name, owner.rolname AS owner_role, c.relrowsecurity AS row_security,
                    c.relforcerowsecurity AS force_row_security,
                    COALESCE(ARRAY(SELECT acl::text FROM unnest(c.relacl) acl ORDER BY acl::text), ARRAY[]::text[])
                    AS acl
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_roles owner ON owner.oid = c.relowner
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
    table_rows = document["tables"]
    owner_roles = (
        {str(row["owner_role"]) for row in table_rows if isinstance(row, Mapping)}
        if isinstance(table_rows, list)
        else set()
    )
    managed_owner = sorted(owner_roles)[0] if len(owner_roles) == 1 else None
    for section in ("tables", "functions"):
        rows = document[section]
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and "owner_role" in row:
                row["owner_role"] = "managed-owner" if row["owner_role"] == managed_owner else "unexpected-owner"
    return document


def _migration_identity(entry: MigrationEntry) -> tuple[str, str]:
    """Return one validated manifest migration's provider history identity."""
    timestamp = entry.timestamp
    filename = entry.filename
    return timestamp, filename[len(timestamp) + 1 : -4]


def _fresh_adoption_history(
    migrations: tuple[MigrationEntry, ...], adoption_timestamp: str | None
) -> tuple[tuple[str, str], ...] | None:
    """Return complete fresh history only when no adoption marker is requested."""
    if adoption_timestamp is not None:
        return None
    return tuple(_migration_identity(entry) for entry in migrations)


def _hosted_adoption_history(
    manifest: LedgerManifest,
    migrations: tuple[MigrationEntry, ...],
    adoption_timestamp: str | None,
) -> tuple[tuple[str, str], ...] | None:
    """Return the reviewed hosted receipts plus canonical markers before one marker."""
    if adoption_timestamp is None:
        return None
    selected_timestamps = tuple(entry.timestamp for entry in migrations)
    try:
        marker_index = selected_timestamps.index(adoption_timestamp)
    except ValueError:
        return None
    receipts = manifest.data["lineages"]["hosted-legacy-v1"]["receipts"]
    expected = [(str(receipt["timestamp"]), str(receipt["name"])) for receipt in receipts]
    expected.extend(_migration_identity(entry) for entry in migrations[:marker_index])
    return tuple(sorted(expected))


def expected_adoption_history(
    manifest: LedgerManifest,
    profile: str,
    lineage: str,
    adoption_timestamp: str | None,
) -> tuple[tuple[str, str], ...] | None:
    """Resolve exact fresh history or the strict prefix before one hosted marker."""
    migrations = manifest.migrations_for_profile(profile)
    if lineage == "fresh-v1":
        return _fresh_adoption_history(migrations, adoption_timestamp)
    if lineage == "hosted-legacy-v1":
        return _hosted_adoption_history(manifest, migrations, adoption_timestamp)
    return None


def _history_check(
    cursor: Cursor,
    manifest: LedgerManifest,
    profile: str,
    lineage: str,
    adoption_timestamp: str | None = None,
) -> CheckResult:
    """Compare exact history or the ordered prefix before one hosted marker."""
    expected = expected_adoption_history(manifest, profile, lineage, adoption_timestamp)
    if expected is None:
        reason = ADOPTION_MARKER_INVALID if adoption_timestamp is not None else LINEAGE_NOT_ADOPTED
        return CheckResult("history", LEDGER_HISTORY_MISMATCH, NOT_EVALUATED, reason)
    try:
        cursor.execute("SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version")
        actual = tuple((str(version), str(name)) for version, name in cursor.fetchall())
    except _psycopg_error_types():
        return CheckResult("history", LEDGER_HISTORY_MISMATCH, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)
    expected_digest = hashlib.sha256(canonical_catalog_bytes({"history": expected})).hexdigest()
    actual_digest = hashlib.sha256(canonical_catalog_bytes({"history": actual})).hexdigest()
    state = CHECK_PASSED if actual == expected else CHECK_DRIFT
    return CheckResult("history", LEDGER_HISTORY_MISMATCH, state, None, expected_digest, actual_digest)


def _catalog_check(
    cursor: Cursor,
    manifest: LedgerManifest,
    profile: str,
    *,
    allow_loopback_test_owner: bool = False,
    require_legacy_inventory: bool = False,
) -> tuple[CheckResult, int, int, int, int, int]:
    """Classify scope and compare the normalized profile catalog digest."""
    application_count, provider_count, legacy_count, helper_count, unknown = _public_scope(
        cursor,
        profile,
        allow_loopback_test_owner=allow_loopback_test_owner,
        require_legacy_inventory=require_legacy_inventory,
    )
    if unknown:
        return (
            CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, OUTSIDE_MANAGED_SCOPE),
            application_count,
            provider_count,
            legacy_count,
            helper_count,
            len(unknown),
        )
    expected = manifest.catalog_digest_for_profile(profile)
    actual = catalog_digest(normalized_managed_catalog(cursor, profile))
    state = CHECK_PASSED if actual == expected else CHECK_DRIFT
    return (
        CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, state, None, str(expected), actual),
        application_count,
        provider_count,
        legacy_count,
        helper_count,
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


def _incomplete_profile_report(target_class: str, profile: str, lineage: str) -> DriftReport:
    """Return the bounded result for an unknown profile or lineage contract."""
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
        NOT_EVALUATED,
        NOT_EVALUATED,
        NOT_EVALUATED,
        3,
        0,
        3,
        0,
        0,
        0,
        None,
        None,
    )


def _profile_catalog_checks(
    connection: Connection,
    manifest: LedgerManifest,
    profile: str,
    lineage: str,
    adoption_timestamp: str | None,
    target_class: str,
) -> tuple[CheckResult, CheckResult, int, int, int, int, int]:
    """Evaluate history and catalog in one always-rolled-back read-only snapshot."""
    history = CheckResult("history", LEDGER_HISTORY_MISMATCH, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)
    catalog = CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)
    application_count = provider_count = legacy_count = helper_count = unknown_count = 0
    try:
        with _read_only_cursor(connection) as cursor:
            if adoption_timestamp is None:
                history = _history_check(cursor, manifest, profile, lineage)
            else:
                history = _history_check(cursor, manifest, profile, lineage, adoption_timestamp)
            try:
                catalog, application_count, provider_count, legacy_count, helper_count, unknown_count = _catalog_check(
                    cursor,
                    manifest,
                    profile,
                    allow_loopback_test_owner=lineage == "fresh-v1" and target_class == "loopback",
                    require_legacy_inventory=lineage == "hosted-legacy-v1",
                )
            except _psycopg_error_types():
                catalog = CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)
                application_count = provider_count = legacy_count = helper_count = unknown_count = 0
    except _psycopg_error_types():
        catalog = CheckResult("catalog", PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)
        application_count = provider_count = legacy_count = helper_count = unknown_count = 0
    return history, catalog, application_count, provider_count, legacy_count, helper_count, unknown_count


def evaluate_profile_drift(
    connection: Connection,
    manifest: LedgerManifest,
    profile: str,
    lineage: str,
    target_class: str,
    *,
    runtime_check: Callable[[], None] | None,
    adoption_timestamp: str | None = None,
) -> DriftReport:
    """Evaluate all safe required checks and return only bounded public diagnostics."""
    if profile not in EXPECTED_PROFILES or lineage not in ("fresh-v1", "hosted-legacy-v1"):
        return _incomplete_profile_report(target_class, profile, lineage)

    history, catalog, application_count, provider_count, legacy_count, helper_count, unknown_count = (
        _profile_catalog_checks(connection, manifest, profile, lineage, adoption_timestamp, target_class)
    )
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
        history.state,
        catalog.state,
        runtime.state,
        len(checks),
        len(checks) - not_evaluated,
        not_evaluated,
        application_count,
        provider_count,
        unknown_count,
        catalog.expected_digest,
        catalog.actual_digest,
        legacy_count,
        helper_count,
    )
