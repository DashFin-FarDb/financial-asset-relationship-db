"""Unit contracts for the profile-aware PostgreSQL drift gate."""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from collections.abc import Sequence
from typing import Any

import psycopg2
import pytest

from scripts.postgresql_drift import (
    CHECK_DRIFT,
    CHECK_PASSED,
    DRIFT_DETECTED,
    EVALUATION_INCOMPLETE,
    HIGHER_PRIORITY_CHECK_NOT_EVALUATED,
    LEDGER_HISTORY_MISMATCH,
    NOT_EVALUATED,
    OUTSIDE_MANAGED_SCOPE,
    PASS,
    PROVIDER_SCHEMA_DRIFT,
    REQUIRED_CHECK_NOT_EVALUATED,
    RUNTIME_COMPATIBILITY_MISMATCH,
    CheckResult,
    RuntimeCheckUnavailable,
    RuntimeCompatibilityMismatch,
    _acl_without_grantor,
    _catalog_check,
    _history_check,
    _normalize_sql_text,
    _public_scope,
    _rows,
    _runtime_check,
    canonical_catalog_bytes,
    catalog_digest,
    evaluate_profile_drift,
    expected_adoption_history,
    expected_managed_tables,
    normalized_managed_catalog,
    select_public_status,
)
from scripts.postgresql_ledger import load_and_validate_manifest

pytestmark = pytest.mark.unit


class StubCursor:
    """Return deterministic DB-API result sets without PostgreSQL."""

    def __init__(self, responses: Sequence[tuple[Sequence[str], Sequence[tuple[Any, ...]]]]) -> None:
        self._responses = deque(responses)
        self.description: Sequence[Sequence[Any]] | None = None
        self._current: list[tuple[Any, ...]] = []

    def execute(self, query: str, parameters: object | None = None) -> object:
        """Advance to the next prepared result set."""
        columns, rows = self._responses.popleft()
        self.description = [(column,) for column in columns]
        self._current = list(rows)
        return None

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Return the current prepared rows."""
        return self._current

    def __enter__(self) -> StubCursor:
        """Enter the fake cursor context."""
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """Exit the fake cursor context."""


class StubConnection:
    """Record evaluator transaction posture around one fake cursor."""

    def __init__(self, cursor: StubCursor) -> None:
        self._cursor = cursor
        self.session: tuple[bool, bool] | None = None
        self.rolled_back = False

    def cursor(self) -> StubCursor:
        """Return the prepared fake cursor."""
        return self._cursor

    def set_session(self, *, readonly: bool, autocommit: bool) -> None:
        """Record the requested transaction posture."""
        self.session = (readonly, autocommit)

    def rollback(self) -> None:
        """Record mandatory evaluator cleanup."""
        self.rolled_back = True


def _check(category: str, state: str, reason: str | None = None) -> CheckResult:
    """Build one concise status-selection fixture."""
    return CheckResult(category.lower(), category, state, reason)


def test_catalog_serialization_is_key_order_and_whitespace_stable() -> None:
    """Equivalent deparsed whitespace and mapping order must produce one digest."""
    left = {"z": _normalize_sql_text("CHECK  ( value > 0 )"), "a": [{"roles": ["b", "a"]}]}
    right = {"a": [{"roles": ["a", "b"]}], "z": _normalize_sql_text("CHECK ( value > 0 )")}

    assert canonical_catalog_bytes(left) == canonical_catalog_bytes(right)
    assert catalog_digest(left) == catalog_digest(right)


def test_catalog_serialization_omits_environment_specific_acl_grantors() -> None:
    """Equivalent grants remain portable across migration-owner role names."""
    assert _acl_without_grantor('"role/with/slash"=r*/"owner/one"') == '"role/with/slash"=r*'
    left = {"acl": ["fardb_runtime_graph=r/test"]}
    right = {"acl": ["fardb_runtime_graph=r/postgres"]}

    assert canonical_catalog_bytes(left) == canonical_catalog_bytes(right)


def test_sql_whitespace_normalization_preserves_quoted_content() -> None:
    """Whitespace inside literals, identifiers, and dollar bodies remains semantic."""
    definition = r"""SELECT  'a  b',  E'c\'d  e',  "quoted  name",  $tag$body  text$tag$"""
    assert _normalize_sql_text(definition) == (r"""SELECT 'a  b', E'c\'d  e', "quoted  name", $tag$body  text$tag$""")


def test_sql_whitespace_normalization_handles_long_unclosed_tokens_without_regex() -> None:
    """Malformed long tokens cannot trigger regex backtracking during evaluation."""
    definition = "SELECT  $tag$" + ("x " * 20_000)

    assert _normalize_sql_text(definition) == "SELECT $tag$" + ("x " * 19_999) + "x"


def test_sql_whitespace_normalization_preserves_unicode_dollar_tags() -> None:
    """PostgreSQL permits identifier letters beyond ASCII in dollar-quote tags."""
    assert _normalize_sql_text("SELECT  $café$body  text$café$") == "SELECT $café$body  text$café$"


def test_catalog_queries_bind_function_owner_without_binding_default_acl_owner() -> None:
    """Ownership drift is evidence while equivalent migration-role names are portable."""

    class RecordingCursor(StubCursor):
        """Record catalog SQL while returning empty result sets."""

        def __init__(self) -> None:
            super().__init__([((), ())] * 12)
            self.queries: list[str] = []

        def execute(self, query: str, parameters: object | None = None) -> object:
            """Record one catalog query before returning its empty result."""
            self.queries.append(query)
            return super().execute(query, parameters)

    cursor = RecordingCursor()
    normalized_managed_catalog(cursor, "graph")
    default_acl_queries = [query for query in cursor.queries if "pg_default_acl" in query]
    function_queries = [query for query in cursor.queries if "pg_proc p" in query]
    table_queries = [query for query in cursor.queries if "c.relrowsecurity" in query]

    assert len(default_acl_queries) == 1
    assert "aclexplode(defaults.defaclacl)" in default_acl_queries[0]
    assert "defaults.defaclrole" not in default_acl_queries[0]
    assert len(function_queries) == 1
    assert "owner.rolname AS owner_role" in function_queries[0]
    assert len(table_queries) == 1
    assert "owner.rolname AS owner_role" in table_queries[0]


def test_expected_managed_tables_are_profile_scoped() -> None:
    """A component target must not silently inherit another component's tables."""
    assert expected_managed_tables("auth") == ("user_credentials",)
    assert "distributed_locks" not in expected_managed_tables("graph")
    assert set(expected_managed_tables("combined")) > set(expected_managed_tables("graph"))
    assert expected_managed_tables("unknown") == ()


def test_rows_and_public_scope_classify_without_a_live_database() -> None:
    """Cursor mapping and scope classification handle managed and unknown objects."""
    row_cursor = StubCursor([(("name", "kind"), (("user_credentials", "r"),))])
    assert _rows(row_cursor, "SELECT") == [{"name": "user_credentials", "kind": "r"}]

    scope_cursor = StubCursor(
        [
            (
                (
                    "object_type",
                    "name",
                    "kind",
                    "parent_table",
                    "identity_arguments",
                    "owner_role",
                    "is_unique",
                    "is_primary",
                    "nulls_not_distinct",
                    "index_definition",
                    "is_valid",
                    "is_ready",
                    "type_kind",
                ),
                (
                    (
                        "relation",
                        "user_credentials",
                        "r",
                        None,
                        None,
                        "postgres",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                    (
                        "relation",
                        "user_credentials_id_seq",
                        "S",
                        "user_credentials",
                        None,
                        "postgres",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                    (
                        "relation",
                        "unmanaged_view",
                        "v",
                        None,
                        None,
                        "postgres",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                    (
                        "policy",
                        "idx_news_articles_url",
                        None,
                        "user_credentials",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                ),
            ),
            (("name", "system_schema"), (("pg_catalog", True), ("supabase_migrations", False))),
            (("name", "schema_name", "owner_role"), (("plpgsql", "pg_catalog", "postgres"),)),
        ]
    )
    application, provider, legacy, helper, unknown = _public_scope(scope_cursor, "auth", allow_loopback_test_owner=True)
    assert (application, provider, legacy, helper) == (3, 3, 0, 0)
    assert len(unknown) == 1


def test_public_scope_requires_exact_function_identity_and_known_schema() -> None:
    """An overload or unclassified namespace makes the total scope incomplete."""
    cursor = StubCursor(
        [
            (
                (
                    "object_type",
                    "name",
                    "kind",
                    "parent_table",
                    "identity_arguments",
                    "owner_role",
                    "is_unique",
                    "is_primary",
                    "nulls_not_distinct",
                    "index_definition",
                    "is_valid",
                    "is_ready",
                    "type_kind",
                ),
                (
                    (
                        "function",
                        "grac_v1_reject_mutation",
                        None,
                        None,
                        "",
                        "postgres",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                    (
                        "function",
                        "grac_v1_reject_mutation",
                        None,
                        None,
                        "integer",
                        "postgres",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                ),
            ),
            (("name", "system_schema"), (("private_extension", False),)),
            (("name", "schema_name", "owner_role"), (("plpgsql", "pg_catalog", "postgres"),)),
        ]
    )
    application, provider, legacy, helper, unknown = _public_scope(cursor, "graph", allow_loopback_test_owner=True)
    assert (application, provider, legacy, helper) == (1, 1, 0, 0)
    assert len(unknown) == 2


def test_history_and_catalog_helpers_cover_pass_and_unknown_scope(monkeypatch) -> None:
    """Core checks compare exact history and stop catalog comparison on unknown scope."""
    manifest = load_and_validate_manifest()
    migration = manifest.migrations_for_profile("auth")[0]
    migration_name = migration.filename[len(migration.timestamp) + 1 : -4]
    history_cursor = StubCursor([(("version", "name"), ((migration.timestamp, migration_name),))])
    assert _history_check(history_cursor, manifest, "auth", "fresh-v1").state == CHECK_PASSED

    expected = manifest.catalog_digest_for_profile("auth")
    monkeypatch.setattr("scripts.postgresql_drift._public_scope", lambda cursor, profile, **kwargs: (1, 0, 0, 0, ()))
    monkeypatch.setattr(
        "scripts.postgresql_drift.normalized_managed_catalog", lambda cursor, profile: {"profile": profile}
    )
    monkeypatch.setattr("scripts.postgresql_drift.catalog_digest", lambda document: expected)
    catalog, application, provider, legacy, helper, unknown = _catalog_check(StubCursor([]), manifest, "auth")
    assert catalog.state == CHECK_PASSED
    assert (application, provider, legacy, helper, unknown) == (1, 0, 0, 0, 0)

    monkeypatch.setattr(
        "scripts.postgresql_drift._public_scope", lambda cursor, profile, **kwargs: (1, 0, 0, 0, ("restricted-name",))
    )
    monkeypatch.setattr(
        "scripts.postgresql_drift.normalized_managed_catalog",
        lambda cursor, profile: (_ for _ in ()).throw(AssertionError("unknown scope must not be compared")),
    )
    incomplete, _application, _provider, _legacy, _helper, unknown = _catalog_check(StubCursor([]), manifest, "auth")
    assert incomplete.state == NOT_EVALUATED
    assert incomplete.reason_code == OUTSIDE_MANAGED_SCOPE
    assert unknown == 1


def test_hosted_adoption_history_requires_the_next_profile_marker() -> None:
    """Each permit must bind the exact legacy-plus-canonical prefix before its marker."""
    manifest = load_and_validate_manifest()
    migrations = manifest.migrations_for_profile("combined")
    receipts = tuple(
        (str(receipt["timestamp"]), str(receipt["name"]))
        for receipt in manifest.data["lineages"]["hosted-legacy-v1"]["receipts"]
    )

    first = expected_adoption_history(manifest, "combined", "hosted-legacy-v1", migrations[0].timestamp)
    second = expected_adoption_history(manifest, "combined", "hosted-legacy-v1", migrations[1].timestamp)

    assert first == receipts
    assert second == receipts + ((migrations[0].timestamp, migrations[0].filename[15:-4]),)
    assert expected_adoption_history(manifest, "combined", "hosted-legacy-v1", "0" * 14) is None


def test_evaluator_enforces_read_only_transaction_and_rollback(monkeypatch) -> None:
    """Known-profile evaluation must force read-only access and clean up its snapshot."""
    monkeypatch.setattr(
        "scripts.postgresql_drift._history_check",
        lambda cursor, manifest, profile, lineage: _check(LEDGER_HISTORY_MISMATCH, CHECK_PASSED),
    )
    monkeypatch.setattr(
        "scripts.postgresql_drift._catalog_check",
        lambda cursor, manifest, profile, **kwargs: (_check(PROVIDER_SCHEMA_DRIFT, CHECK_PASSED), 1, 0, 0, 0, 0),
    )
    connection = StubConnection(StubCursor([]))
    report = evaluate_profile_drift(
        connection,
        load_and_validate_manifest(),
        "auth",
        "fresh-v1",
        "loopback",
        runtime_check=lambda: None,
    )
    assert report.status == PASS
    assert connection.session == (True, False)
    assert connection.rolled_back is True


def test_evaluator_fails_closed_when_transaction_cleanup_is_unavailable(monkeypatch) -> None:
    """A failed rollback cannot leave a successful public evaluation."""

    class CleanupUnavailable(StubConnection):
        """Simulate a connection failure while releasing the read-only snapshot."""

        def rollback(self) -> None:
            """Record cleanup and then make its completion unknowable."""
            super().rollback()
            raise psycopg2.OperationalError("cleanup unavailable")

    monkeypatch.setattr(
        "scripts.postgresql_drift._history_check",
        lambda cursor, manifest, profile, lineage: _check(LEDGER_HISTORY_MISMATCH, CHECK_PASSED),
    )
    monkeypatch.setattr(
        "scripts.postgresql_drift._catalog_check",
        lambda cursor, manifest, profile, **kwargs: (_check(PROVIDER_SCHEMA_DRIFT, CHECK_PASSED), 1, 0, 0, 0, 0),
    )
    connection = CleanupUnavailable(StubCursor([]))
    report = evaluate_profile_drift(
        connection,
        load_and_validate_manifest(),
        "auth",
        "fresh-v1",
        "loopback",
        runtime_check=lambda: None,
    )
    assert report.status == EVALUATION_INCOMPLETE
    assert report.primary_category is None
    assert report.history == NOT_EVALUATED
    assert report.catalog == NOT_EVALUATED
    assert (
        report.application_owned_count,
        report.provider_owned_count,
        report.unknown_count,
        report.protected_legacy_count,
        report.restricted_helper_count,
    ) == (0, 0, 0, 0, 0)
    assert connection.rolled_back is True


def test_evaluator_preserves_completed_history_drift_when_catalog_fails(monkeypatch) -> None:
    """A lower-priority catalog error must not erase a completed history finding."""
    monkeypatch.setattr(
        "scripts.postgresql_drift._history_check",
        lambda cursor, manifest, profile, lineage: _check(LEDGER_HISTORY_MISMATCH, CHECK_DRIFT),
    )

    def catalog_unavailable(*_args, **_kwargs):
        """Simulate catalog failure after migration history was checked."""
        raise psycopg2.OperationalError("catalog unavailable")

    monkeypatch.setattr("scripts.postgresql_drift._catalog_check", catalog_unavailable)
    connection = StubConnection(StubCursor([]))
    report = evaluate_profile_drift(
        connection,
        load_and_validate_manifest(),
        "auth",
        "fresh-v1",
        "loopback",
        runtime_check=lambda: None,
    )

    assert report.status == DRIFT_DETECTED
    assert report.primary_category == LEDGER_HISTORY_MISMATCH
    assert report.history == CHECK_DRIFT
    assert report.catalog == NOT_EVALUATED
    assert connection.rolled_back is True


def test_evaluator_does_not_hide_catalog_programming_errors(monkeypatch) -> None:
    """Unexpected evaluator bugs propagate instead of masquerading as database outages."""
    monkeypatch.setattr(
        "scripts.postgresql_drift._history_check",
        lambda cursor, manifest, profile, lineage: _check(LEDGER_HISTORY_MISMATCH, CHECK_PASSED),
    )

    def catalog_bug(*_args, **_kwargs):
        """Simulate a programmer error in the catalog evaluator."""
        raise TypeError("unexpected catalog result shape")

    monkeypatch.setattr("scripts.postgresql_drift._catalog_check", catalog_bug)
    connection = StubConnection(StubCursor([]))
    with pytest.raises(TypeError, match="unexpected catalog result shape"):
        evaluate_profile_drift(
            connection,
            load_and_validate_manifest(),
            "auth",
            "fresh-v1",
            "loopback",
            runtime_check=lambda: None,
        )
    assert connection.rolled_back is True


def test_clean_required_checks_pass() -> None:
    """PASS requires every required check to complete without drift."""
    checks = tuple(
        _check(category, CHECK_PASSED)
        for category in (
            LEDGER_HISTORY_MISMATCH,
            PROVIDER_SCHEMA_DRIFT,
            RUNTIME_COMPATIBILITY_MISMATCH,
        )
    )
    assert select_public_status(checks) == (PASS, None, ())


def test_primary_category_uses_ratified_precedence() -> None:
    """Combined drift must publish only the earliest completed category."""
    checks = (
        _check(LEDGER_HISTORY_MISMATCH, CHECK_PASSED),
        _check(PROVIDER_SCHEMA_DRIFT, CHECK_DRIFT),
        _check(RUNTIME_COMPATIBILITY_MISMATCH, CHECK_DRIFT),
    )
    assert select_public_status(checks) == (DRIFT_DETECTED, PROVIDER_SCHEMA_DRIFT, ())


def test_unavailable_higher_priority_check_cannot_be_masked() -> None:
    """A detected lower category cannot replace unknown higher-priority state."""
    checks = (
        _check(LEDGER_HISTORY_MISMATCH, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED),
        _check(PROVIDER_SCHEMA_DRIFT, CHECK_DRIFT),
        _check(RUNTIME_COMPATIBILITY_MISMATCH, CHECK_PASSED),
    )
    status, primary, reasons = select_public_status(checks)
    assert status == EVALUATION_INCOMPLETE
    assert primary is None
    assert reasons == (HIGHER_PRIORITY_CHECK_NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)


def test_unavailable_lower_priority_check_does_not_hide_primary() -> None:
    """Checks downstream of a publishable primary may remain unavailable."""
    checks = (
        _check(LEDGER_HISTORY_MISMATCH, CHECK_DRIFT),
        _check(PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED),
        _check(RUNTIME_COMPATIBILITY_MISMATCH, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED),
    )
    assert select_public_status(checks) == (
        DRIFT_DETECTED,
        LEDGER_HISTORY_MISMATCH,
        (REQUIRED_CHECK_NOT_EVALUATED,),
    )


def test_unknown_profile_fails_closed_without_connecting() -> None:
    """Unknown profile selection must produce bounded incomplete diagnostics."""

    class NoConnection:
        """Reject accidental database access for invalid selectors."""

        def cursor(self) -> object:
            """Fail if selector validation does not short-circuit."""
            raise AssertionError("unknown profile must fail before database access")

    report = evaluate_profile_drift(
        NoConnection(),  # type: ignore[arg-type]
        load_and_validate_manifest(),
        "unknown",
        "fresh-v1",
        "loopback",
        runtime_check=lambda: None,
    )
    assert report.status == EVALUATION_INCOMPLETE
    assert report.primary_category is None
    assert report.not_evaluated_count == 3
    assert report.reason_codes == (REQUIRED_CHECK_NOT_EVALUATED,)


def test_public_report_contains_no_restricted_details() -> None:
    """Public JSON must expose counts and digests, never object names or raw errors."""
    report = evaluate_profile_drift(
        object(),  # type: ignore[arg-type]
        load_and_validate_manifest(),
        "unknown",
        "hosted-legacy-v1",
        "hosted",
        runtime_check=None,
    )
    payload = json.dumps(report.as_public_dict(), sort_keys=True)
    assert "database_url" not in payload
    assert "raw_error" not in payload
    assert "object_names" not in payload


def test_manifest_records_versioned_profile_catalog_digests() -> None:
    """The immutable profile manifest must bind every expected catalog digest."""
    manifest = load_and_validate_manifest()
    digests: dict[str, str] = {}
    for profile in ("auth", "graph", "coordination", "combined"):
        digest = manifest.catalog_digest_for_profile(profile)
        assert re.fullmatch(r"[0-9a-f]{64}", digest), profile
        assert digest != "0" * 64, f"{profile} catalog digest is not calibrated"
        digests[profile] = digest
    assert len(set(digests.values())) == len(digests), "profile catalog digests are not distinct"


def test_runtime_check_distinguishes_mismatch_from_unavailable() -> None:
    """Only an explicit completed compatibility failure is runtime drift."""

    def mismatch() -> None:
        """Signal a completed invariant mismatch."""
        raise RuntimeCompatibilityMismatch

    def unavailable() -> None:
        """Signal explicit evaluator unavailability."""
        raise RuntimeCheckUnavailable

    assert _runtime_check(mismatch).state == CHECK_DRIFT
    unavailable_result = _runtime_check(unavailable)
    assert unavailable_result.state == NOT_EVALUATED
    assert unavailable_result.reason_code == REQUIRED_CHECK_NOT_EVALUATED


def test_unknown_runtime_callback_failure_is_unavailable() -> None:
    """Driver-like callback failures must not be mislabeled as proven drift."""

    def driver_failure() -> None:
        """Represent an unexpected driver failure."""
        raise ConnectionError("database unavailable")

    result = _runtime_check(driver_failure)
    assert result.state == NOT_EVALUATED
    assert result.reason_code == REQUIRED_CHECK_NOT_EVALUATED


def test_exact_legacy_inventory_requires_parent_owner_index_flags_and_access() -> None:
    """All reviewed identities pass; a changed or added identity remains unknown."""
    from scripts.postgresql_drift import (
        _LEGACY_INDEXES,
        _LEGACY_TABLES,
        _PROVIDER_EXTENSION_IDENTITIES,
        _legacy_table_grants,
    )

    with pytest.raises(TypeError):
        _LEGACY_INDEXES["unexpected"] = ("financial_data", False, False)  # type: ignore[index]
    with pytest.raises(TypeError):
        _PROVIDER_EXTENSION_IDENTITIES["unexpected"] = ("extensions", "supabase_admin")  # type: ignore[index]

    columns = (
        "object_type",
        "name",
        "kind",
        "parent_table",
        "identity_arguments",
        "owner_role",
        "is_unique",
        "is_primary",
        "nulls_not_distinct",
        "index_definition",
        "is_valid",
        "is_ready",
        "type_kind",
    )
    objects = (
        [
            ("relation", name, "r", None, None, "postgres", None, None, None, None, None, None, None)
            for name in sorted(_LEGACY_TABLES)
        ]
        + [
            (
                "relation",
                name,
                "i",
                parent,
                None,
                "postgres",
                unique,
                primary,
                False,
                f"CREATE INDEX {name} ON public.{parent} USING btree (id)",
                True,
                True,
                None,
            )
            for name, (parent, unique, primary) in sorted(_LEGACY_INDEXES.items())
        ]
        + [
            ("type", name, None, name, None, "postgres", None, None, None, None, None, None, "c")
            for name in sorted(_LEGACY_TABLES)
        ]
        + [("function", "is_requester_admin", None, None, "", "postgres", None, None, None, None, None, None, None)]
    )
    extensions = [(name, schema, owner) for name, (schema, owner) in sorted(_PROVIDER_EXTENSION_IDENTITIES.items())]
    grants = sorted(_legacy_table_grants(170000))
    legacy_table_columns = (
        "name",
        "owner_role",
        "row_security",
        "force_row_security",
        "policy_count",
        "server_version_num",
        "grants",
    )
    helper_columns = (
        "name",
        "arguments",
        "return_type",
        "returns_set",
        "language",
        "volatility",
        "security_definer",
        "owner_role",
        "definition",
        "proconfig",
        "acl_entries",
        "effective_untrusted_roles",
    )

    def classify(rows, *, require_legacy_inventory=False, owner="postgres"):
        """Evaluate one catalog fixture with the requested legacy posture."""
        legacy_tables = [(name, owner, True, True, 0, 170000, grants) for name in sorted(_LEGACY_TABLES)]
        helper = (
            "is_requester_admin",
            "",
            "boolean",
            False,
            "sql",
            "v",
            True,
            "postgres",
            "CREATE FUNCTION public.is_requester_admin() RETURNS boolean LANGUAGE sql SECURITY DEFINER",
            [],
            ["postgres=X/postgres", "service_role=X/postgres"],
            [],
        )
        cursor = StubCursor(
            [
                (columns, rows),
                (("name", "system_schema"), ()),
                (("name", "schema_name", "owner_role"), extensions),
                (legacy_table_columns, legacy_tables),
                (helper_columns, [helper]),
            ]
        )
        return _public_scope(cursor, "combined", require_legacy_inventory=require_legacy_inventory)

    all_objects = classify(objects)
    assert all_objects[:4] == (0, 11, 16, 0)
    assert "function:is_requester_admin" in all_objects[4]
    assert "relation:financial_data_pkey" in all_objects[4]
    assert "relation:idx_financial_data_symbol" in all_objects[4]
    assert "legacy:incomplete" in classify(objects[:-2])[4]
    assert "legacy:incomplete" in classify((), require_legacy_inventory=True)[4]
    assert "relation:financial_data" in classify(objects, owner="unexpected_owner")[4]
    colliding_name = list(objects) + [
        (
            "policy",
            "idx_news_articles_url",
            None,
            "financial_data",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    ]
    collision_result = classify(colliding_name)
    assert "legacy:incomplete" not in collision_result[4]
    assert "policy:idx_news_articles_url" in collision_result[4]
    altered = list(objects)
    indices = [i for i, row in enumerate(altered) if row[1] == "idx_news_articles_url"]
    assert len(indices) == 1
    altered[indices[0]] = (*altered[indices[0]][:6], False, False, False, *altered[indices[0]][9:])
    assert "relation:idx_news_articles_url" in classify(altered)[4]
    altered = list(objects)
    indices = [i for i, row in enumerate(altered) if row[1] == "idx_financial_data_symbol"]
    assert len(indices) == 1
    altered[indices[0]] = (*altered[indices[0]][:8], True, *altered[indices[0]][9:])
    assert "relation:idx_financial_data_symbol" in classify(altered)[4]
    altered = list(objects) + [
        (
            "relation",
            "idx_unreviewed",
            "i",
            "financial_data",
            None,
            "postgres",
            False,
            False,
            False,
            "CREATE INDEX idx_unreviewed ON public.financial_data USING btree (id)",
            True,
            True,
            None,
        )
    ]
    assert "relation:idx_unreviewed" in classify(altered)[4]
    extensions[0] = (extensions[0][0], "public", extensions[0][2])
    assert any(value.startswith("extension:") for value in classify(objects)[4])


def test_partitioned_legacy_index_is_not_an_inventory_candidate() -> None:
    """Partitioned-index catalog identities remain unknown rather than masquerading as legacy indexes."""
    from scripts.postgresql_drift import _classify_legacy_object, _is_legacy_inventory_candidate

    item = {
        "object_type": "relation",
        "name": "financial_data_pkey",
        "kind": "I",
        "parent_table": "financial_data",
        "owner_role": "postgres",
        "is_unique": True,
        "is_primary": True,
        "nulls_not_distinct": False,
        "index_definition": "CREATE UNIQUE INDEX financial_data_pkey ON public.financial_data USING btree (id)",
        "is_valid": True,
        "is_ready": True,
    }
    assert not _is_legacy_inventory_candidate(item)
    assert not _classify_legacy_object(item, {"financial_data"})


def test_legacy_index_requires_matching_approved_definition_and_posture(monkeypatch) -> None:
    """A ratified index passes only with its exact definition, NULL mode and usable flags."""
    from scripts.postgresql_drift import _classify_legacy_object

    name = "idx_news_articles_url"
    definition = "CREATE UNIQUE INDEX idx_news_articles_url ON public.news_articles USING btree (url)"
    digest = hashlib.sha256(_normalize_sql_text(definition).encode("utf-8")).hexdigest()
    monkeypatch.setattr("scripts.postgresql_drift._LEGACY_INDEX_BASELINES", {name: (digest, False, True, True)})
    item = {
        "object_type": "relation",
        "name": name,
        "kind": "i",
        "parent_table": "news_articles",
        "owner_role": "postgres",
        "is_unique": True,
        "is_primary": False,
        "nulls_not_distinct": False,
        "index_definition": definition,
        "is_valid": True,
        "is_ready": True,
    }
    assert _classify_legacy_object(item, {"news_articles"})
    assert not _classify_legacy_object({**item, "index_definition": "CREATE INDEX changed"}, {"news_articles"})
    assert not _classify_legacy_object({**item, "nulls_not_distinct": True}, {"news_articles"})
    assert not _classify_legacy_object({**item, "is_valid": False}, {"news_articles"})
    assert not _classify_legacy_object({**item, "is_ready": False}, {"news_articles"})


def test_legacy_table_access_posture_fails_closed() -> None:
    """An extra grant or disabled RLS must not protect a legacy table."""
    from scripts.postgresql_drift import _legacy_table_grants, _legacy_table_posture

    pg15_16_grants = frozenset(
        {
            "postgres:DELETE:false",
            "postgres:INSERT:false",
            "postgres:REFERENCES:false",
            "postgres:SELECT:false",
            "postgres:TRIGGER:false",
            "postgres:TRUNCATE:false",
            "postgres:UPDATE:false",
            "service_role:DELETE:false",
            "service_role:INSERT:false",
            "service_role:REFERENCES:false",
            "service_role:SELECT:false",
            "service_role:TRIGGER:false",
            "service_role:TRUNCATE:false",
            "service_role:UPDATE:false",
        }
    )
    pg17_grants = pg15_16_grants | {"postgres:MAINTAIN:false", "service_role:MAINTAIN:false"}
    assert _legacy_table_grants(150000) == pg15_16_grants
    assert _legacy_table_grants(160000) == pg15_16_grants
    assert _legacy_table_grants(170000) == pg17_grants

    columns = (
        "name",
        "owner_role",
        "row_security",
        "force_row_security",
        "policy_count",
        "server_version_num",
        "grants",
    )

    def classify(rows):
        """Evaluate the supplied legacy ACL posture rows."""
        return _legacy_table_posture(StubCursor([(columns, rows)]))

    for version in (150000, 160000):
        grants = sorted(pg15_16_grants)
        valid = ("financial_data", "postgres", True, True, 0, version, grants)
        assert "financial_data" in classify([valid])
        assert not classify([(*valid[:6], None)])
        assert not classify([(*valid[:6], grants + ["anon:SELECT:false"])])
        assert not classify([(*valid[:2], False, *valid[3:])])
        assert not classify([(*valid[:4], 1, *valid[5:])])

    pg17_valid = ("financial_data", "postgres", True, True, 0, 170000, sorted(pg17_grants))
    assert "financial_data" in classify([pg17_valid])
    assert not classify([(*pg17_valid[:6], sorted(pg17_grants)[:-1])])


def test_restricted_helper_requires_ratified_definition_and_exact_posture(monkeypatch) -> None:
    """A grant or changed function metadata leaves the helper outside scope."""
    from scripts.postgresql_drift import _restricted_helper_posture

    columns = (
        "name",
        "arguments",
        "return_type",
        "returns_set",
        "language",
        "volatility",
        "security_definer",
        "owner_role",
        "definition",
        "proconfig",
        "acl_entries",
        "effective_untrusted_roles",
    )
    valid: tuple[Any, ...] = (
        "is_requester_admin",
        "",
        "boolean",
        False,
        "sql",
        "v",
        True,
        "postgres",
        "CREATE FUNCTION public.is_requester_admin() RETURNS boolean LANGUAGE sql SECURITY DEFINER",
        [],
        ["postgres=X/postgres", "service_role=X/postgres"],
        [],
    )
    assert not _restricted_helper_posture(StubCursor([(columns, [valid])]))
    definition_digest = hashlib.sha256(valid[8].encode("utf-8")).hexdigest()
    monkeypatch.setattr("scripts.postgresql_drift._RESTRICTED_HELPER_DEFINITION_SHA256", definition_digest)
    monkeypatch.setattr("scripts.postgresql_drift._RESTRICTED_HELPER_PROCONFIG", ())
    assert _restricted_helper_posture(StubCursor([(columns, [valid])]))
    assert not _restricted_helper_posture(StubCursor([(columns, [(*valid[:3], True, *valid[4:])])]))
    assert not _restricted_helper_posture(StubCursor([(columns, [(*valid[:-1], ["anon"])])]))
    assert not _restricted_helper_posture(StubCursor([(columns, [(*valid[:6], False, *valid[7:])])]))
    assert not _restricted_helper_posture(
        StubCursor([(columns, [(*valid[:8], "CREATE FUNCTION altered", *valid[9:])])])
    )
    assert not _restricted_helper_posture(StubCursor([(columns, [(*valid[:9], ["search_path=public"], *valid[10:])])]))


def test_public_report_separates_protected_legacy_and_helper_counts(monkeypatch) -> None:
    """Restricted legacy identities never inflate provider-owned counts."""
    monkeypatch.setattr(
        "scripts.postgresql_drift._history_check",
        lambda cursor, manifest, profile, lineage: _check(LEDGER_HISTORY_MISMATCH, CHECK_PASSED),
    )
    monkeypatch.setattr(
        "scripts.postgresql_drift._catalog_check",
        lambda cursor, manifest, profile, **kwargs: (_check(PROVIDER_SCHEMA_DRIFT, CHECK_PASSED), 1, 11, 45, 1, 0),
    )
    report = evaluate_profile_drift(
        StubConnection(StubCursor([])),
        load_and_validate_manifest(),
        "combined",
        "fresh-v1",
        "loopback",
        runtime_check=lambda: None,
    )
    public = report.as_public_dict()
    assert report.status == PASS
    assert public["application_owned_count"] == 1
    assert public["provider_owned_count"] == 11
    assert public["protected_legacy_count"] == 45
    assert public["restricted_helper_count"] == 1


def test_plpgsql_test_owner_requires_explicit_local_scope() -> None:
    """The disposable test role cannot be accepted on a hosted scope."""
    responses = [
        (("object_type", "name", "kind", "parent_table", "identity_arguments"), ()),
        (("name", "system_schema"), ()),
        (("name", "schema_name", "owner_role"), (("plpgsql", "pg_catalog", "test"),)),
    ]
    default = _public_scope(StubCursor(responses), "auth")
    local = _public_scope(StubCursor(responses), "auth", allow_loopback_test_owner=True)
    assert default[4] == ("extension:plpgsql",)
    assert local == (0, 1, 0, 0, ())
