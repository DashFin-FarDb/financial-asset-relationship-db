"""Clean-build proofs for every PostgreSQL ledger profile."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg2
import pytest
import sqlalchemy
from psycopg2 import sql

from api.database import (
    AUTH_RUNTIME_ROLE,
    bind_database_url,
    verify_runtime_access_catalog,
    verify_runtime_authority,
    verify_schema_compatibility,
)
from scripts.postgresql_drift import (
    DRIFT_DETECTED,
    EVALUATION_INCOMPLETE,
    HIGHER_PRIORITY_CHECK_NOT_EVALUATED,
    LEDGER_HISTORY_MISMATCH,
    PASS,
    PROVIDER_SCHEMA_DRIFT,
    RUNTIME_COMPATIBILITY_MISMATCH,
    DriftReport,
    RuntimeCompatibilityMismatch,
    evaluate_profile_drift,
)
from scripts.postgresql_ledger import (
    EXPECTED_MANAGED_TABLES,
    EXPECTED_PROFILES,
    LOGICAL_TARGET_ORDER,
    LedgerManifest,
    PlannedTarget,
    apply_profile_to_database,
    load_and_validate_manifest,
)
from src.data.database import (
    RUNTIME_CAPABILITY_ROLES,
    SchemaCompatibilityError,
    verify_database_schema,
    verify_runtime_database_authority,
)

pytestmark = pytest.mark.integration

_ENABLE_ENV = "FARDB_EPHEMERAL_POSTGRES_LEDGER_TESTS"
_URL_ENV = "FARDB_EPHEMERAL_POSTGRES_URL"
_BOOTSTRAP_PATH = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_database_capability_roles.sql"


def _ephemeral_postgres_url() -> str:
    """Return the explicit disposable PostgreSQL service URL or skip."""
    if os.environ.get(_ENABLE_ENV) != "1":
        pytest.skip(f"set {_ENABLE_ENV}=1 to run disposable PostgreSQL ledger proofs")
    value = os.environ.get(_URL_ENV)
    if not value:
        pytest.fail(f"{_URL_ENV} is required when {_ENABLE_ENV}=1")
    assert value is not None
    return value


def _database_url(base_url: str, database_name: str) -> str:
    """Select a generated database while preserving the disposable service authority."""
    parsed = urlsplit(base_url)
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, parsed.fragment))


def _bootstrap_roles_and_create_database(base_url: str, database_name: str) -> None:
    """Create stable capability roles and one empty disposable database."""
    bootstrap_sql = _BOOTSTRAP_PATH.read_text(encoding="utf-8")
    connection = psycopg2.connect(base_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(bootstrap_sql)
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    finally:
        connection.close()


def _drop_database(base_url: str, database_name: str) -> None:
    """Remove one generated database after terminating only its own sessions."""
    connection = psycopg2.connect(base_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
    finally:
        connection.close()


def _runtime_url(database_url: str, login_name: str, password: str) -> str:
    """Return a runtime-login URL without changing the selected database."""
    return (
        sqlalchemy.engine.make_url(database_url)
        .set(username=login_name, password=password)
        .render_as_string(hide_password=False)
    )


def _create_runtime_login(base_url: str, login_name: str, capability_roles: tuple[str, ...], password: str) -> None:
    """Create one disposable restricted login with only its selected memberships."""
    connection = psycopg2.connect(base_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB " "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
                ).format(sql.Identifier(login_name)),
                (password,),
            )
            for capability_role in capability_roles:
                cursor.execute(
                    sql.SQL("GRANT {} TO {}").format(
                        sql.Identifier(capability_role),
                        sql.Identifier(login_name),
                    )
                )
    finally:
        connection.close()


def _drop_runtime_login(base_url: str, login_name: str) -> None:
    """Drop one disposable cluster login after its database has been removed."""
    connection = psycopg2.connect(base_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(login_name)))
    finally:
        connection.close()


def _set_runtime_schema_create(database_url: str, login_name: str, *, enabled: bool) -> None:
    """Introduce or remove one deliberate direct-authority drift fixture."""
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            action = sql.SQL("GRANT") if enabled else sql.SQL("REVOKE")
            cursor.execute(
                sql.SQL("{} CREATE ON SCHEMA public {} {}").format(
                    action,
                    sql.SQL("TO") if enabled else sql.SQL("FROM"),
                    sql.Identifier(login_name),
                )
            )
    finally:
        connection.close()


def _set_runtime_table_select(database_url: str, login_name: str, table_name: str, *, enabled: bool) -> None:
    """Introduce or remove one direct cross-component table grant."""
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            action = sql.SQL("GRANT") if enabled else sql.SQL("REVOKE")
            cursor.execute(
                sql.SQL("{} SELECT ON TABLE {} {} {}").format(
                    action,
                    sql.Identifier("public", table_name),
                    sql.SQL("TO") if enabled else sql.SQL("FROM"),
                    sql.Identifier(login_name),
                )
            )
    finally:
        connection.close()


def _set_auth_cross_profile_view(database_url: str, login_name: str, *, enabled: bool) -> None:
    """Create or remove a managed-name view directly readable by the auth login."""
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            if enabled:
                cursor.execute("CREATE VIEW public.assets AS SELECT id FROM public.user_credentials")
                cursor.execute(sql.SQL("GRANT SELECT ON TABLE public.assets TO {}").format(sql.Identifier(login_name)))
            else:
                cursor.execute("DROP VIEW IF EXISTS public.assets")
    finally:
        connection.close()


def _expected_tables(profile: str) -> set[str]:
    """Return the exact public table set selected by one profile."""
    return {table_name for component in EXPECTED_PROFILES[profile] for table_name in EXPECTED_MANAGED_TABLES[component]}


def _assert_profile_catalog(engine: sqlalchemy.Engine, manifest: LedgerManifest, profile: str) -> None:
    """Verify exact public tables and one deterministic provider history."""
    with engine.connect() as connection:
        public_tables = set(
            connection.execute(
                sqlalchemy.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
            ).scalars()
        )
        history = connection.execute(
            sqlalchemy.text("SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version")
        ).all()

    selected = manifest.migrations_for_profile(profile)
    assert public_tables == _expected_tables(profile)
    assert history == [(entry.timestamp, entry.filename[15:-4]) for entry in selected]
    assert [version for version, _name in history] == sorted(version for version, _name in history)


def _profile_capabilities(profile: str) -> set[str]:
    """Return graph/coordination capabilities selected by one ledger profile."""
    return set(EXPECTED_PROFILES[profile]).intersection({"graph", "coordination"})


def _verify_operator_contract(engine: sqlalchemy.Engine, target_url: str, profile: str) -> None:
    """Verify the operator-visible schema without mutating it."""
    capabilities = _profile_capabilities(profile)
    if capabilities:
        verify_database_schema(engine, required_capabilities=capabilities)
    if "auth" in EXPECTED_PROFILES[profile]:
        with bind_database_url(target_url):
            verify_schema_compatibility()
            verify_runtime_access_catalog()


def _evaluate_drift(target_url: str, manifest: LedgerManifest, profile: str, runtime_check) -> DriftReport:
    """Run the read-only profile drift gate with an explicit compatibility check."""
    connection = psycopg2.connect(target_url)
    try:
        return evaluate_profile_drift(
            connection,
            manifest,
            profile,
            "fresh-v1",
            "loopback",
            runtime_check=runtime_check,
        )
    finally:
        connection.close()


class _HistoryUnavailableCursor:
    """Proxy one real disposable cursor while denying the required history read."""

    def __init__(self, cursor: object) -> None:
        self._cursor = cursor

    def __enter__(self) -> _HistoryUnavailableCursor:
        self._cursor.__enter__()  # type: ignore[attr-defined]
        return self

    def __exit__(self, *args: object) -> object:
        return self._cursor.__exit__(*args)  # type: ignore[attr-defined,no-any-return]

    def execute(self, query: object, parameters: object = None) -> object:
        """Deny only the provider-history read and delegate every catalog query."""
        if isinstance(query, str) and "supabase_migrations.schema_migrations" in query:
            raise psycopg2.OperationalError("deliberate unavailable history fixture")
        return self._cursor.execute(query, parameters)  # type: ignore[attr-defined,no-any-return]

    def __getattr__(self, name: str) -> object:
        return getattr(self._cursor, name)


class _HistoryUnavailableConnection:
    """Expose a real catalog while proving unavailable history fails closed."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def cursor(self) -> _HistoryUnavailableCursor:
        """Return a cursor that makes the required history check unavailable."""
        return _HistoryUnavailableCursor(self._connection.cursor())  # type: ignore[attr-defined]

    def set_session(self, *, readonly: bool, autocommit: bool) -> None:
        """Delegate the evaluator's read-only transaction posture."""
        self._connection.set_session(readonly=readonly, autocommit=autocommit)  # type: ignore[attr-defined]

    def rollback(self) -> None:
        """Delegate evaluator transaction cleanup."""
        self._connection.rollback()  # type: ignore[attr-defined]


def _migration_history(target_url: str) -> tuple[tuple[str, str], ...]:
    """Read the exact disposable provider history for no-mutation comparison."""
    connection = psycopg2.connect(target_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version")
            return tuple((str(version), str(name)) for version, name in cursor.fetchall())
    finally:
        connection.close()


def _execute_operator_sql(target_url: str, statement: object, parameters: tuple[object, ...] = ()) -> None:
    """Apply or restore one deliberate disposable drift fixture."""
    connection = psycopg2.connect(target_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)  # type: ignore[arg-type]
    finally:
        connection.close()


def _verify_profile_drift_contract(
    engine: sqlalchemy.Engine,
    target_url: str,
    manifest: LedgerManifest,
    profile: str,
) -> None:
    """Prove clean, primary-category, incomplete, and no-mutation behavior."""

    def runtime_check() -> None:
        """Convert completed compatibility failures to the drift callback contract."""
        try:
            _verify_operator_contract(engine, target_url, profile)
        except SchemaCompatibilityError as exc:
            raise RuntimeCompatibilityMismatch from exc

    clean_before = _evaluate_drift(target_url, manifest, profile, runtime_check)
    assert clean_before.status == PASS, f"clean catalog digest for {profile}: {clean_before.actual_catalog_digest}"
    history_before = _migration_history(target_url)

    selected = manifest.migrations_for_profile(profile)
    original_version = selected[0].timestamp
    changed_version = "20991231235959"
    _execute_operator_sql(
        target_url,
        "UPDATE supabase_migrations.schema_migrations SET version = %s WHERE version = %s",
        (changed_version, original_version),
    )
    try:
        history_drift = _evaluate_drift(target_url, manifest, profile, runtime_check)
        assert history_drift.status == DRIFT_DETECTED
        assert history_drift.primary_category == LEDGER_HISTORY_MISMATCH
    finally:
        _execute_operator_sql(
            target_url,
            "UPDATE supabase_migrations.schema_migrations SET version = %s WHERE version = %s",
            (original_version, changed_version),
        )

    table_name = sorted(_expected_tables(profile))[0]
    _execute_operator_sql(
        target_url,
        sql.SQL("ALTER TABLE {} ADD COLUMN cq03c_unrecorded INTEGER").format(sql.Identifier("public", table_name)),
    )
    try:
        catalog_drift = _evaluate_drift(target_url, manifest, profile, runtime_check)
        assert catalog_drift.status == DRIFT_DETECTED
        assert catalog_drift.primary_category == PROVIDER_SCHEMA_DRIFT
        connection = psycopg2.connect(target_url)
        try:
            incomplete_history = evaluate_profile_drift(
                _HistoryUnavailableConnection(connection),  # type: ignore[arg-type]
                manifest,
                profile,
                "fresh-v1",
                "loopback",
                runtime_check=runtime_check,
            )
        finally:
            connection.close()
        assert incomplete_history.status == EVALUATION_INCOMPLETE
        assert incomplete_history.primary_category is None
        assert HIGHER_PRIORITY_CHECK_NOT_EVALUATED in incomplete_history.reason_codes
    finally:
        _execute_operator_sql(
            target_url,
            sql.SQL("ALTER TABLE {} DROP COLUMN cq03c_unrecorded").format(sql.Identifier("public", table_name)),
        )

    def incompatible_runtime() -> None:
        """Represent one completed required-invariant mismatch."""
        raise RuntimeCompatibilityMismatch

    runtime_drift = _evaluate_drift(target_url, manifest, profile, incompatible_runtime)
    assert runtime_drift.status == DRIFT_DETECTED
    assert runtime_drift.primary_category == RUNTIME_COMPATIBILITY_MISMATCH

    _execute_operator_sql(target_url, "CREATE TABLE public.cq03c_unknown_scope (id INTEGER PRIMARY KEY)")
    try:
        incomplete = _evaluate_drift(target_url, manifest, profile, runtime_check)
        assert incomplete.status == EVALUATION_INCOMPLETE
        assert incomplete.primary_category is None
        assert incomplete.unknown_count == 3
    finally:
        _execute_operator_sql(target_url, "DROP TABLE public.cq03c_unknown_scope")

    clean_after = _evaluate_drift(target_url, manifest, profile, runtime_check)
    assert clean_after.status == PASS, clean_after.as_public_dict()
    assert clean_after.expected_catalog_digest == clean_before.expected_catalog_digest
    assert clean_after.actual_catalog_digest == clean_before.actual_catalog_digest
    assert _migration_history(target_url) == history_before


def _verify_graph_data_contract(engine: sqlalchemy.Engine, profile: str) -> None:
    """Exercise raw-writer defaults and append-only GRAC guards on ledger-built PostgreSQL."""
    if "graph" not in EXPECTED_PROFILES[profile]:
        return
    with engine.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                "INSERT INTO assets (id, symbol, name, asset_class, sector, price, currency) "
                "VALUES ('RAW_A', 'RA', 'Raw A', 'equity', 'Test', 1.0, 'USD'), "
                "('RAW_B', 'RB', 'Raw B', 'equity', 'Test', 2.0, 'USD')"
            )
        )
        connection.execute(
            sqlalchemy.text(
                "INSERT INTO asset_relationships "
                "(source_asset_id, target_asset_id, relationship_type, strength) "
                "VALUES ('RAW_A', 'RAW_B', 'raw_default', 0.5)"
            )
        )
        assert (
            connection.execute(
                sqlalchemy.text(
                    "SELECT bidirectional FROM asset_relationships "
                    "WHERE source_asset_id = 'RAW_A' AND target_asset_id = 'RAW_B'"
                )
            ).scalar_one()
            is False
        )
        connection.execute(
            sqlalchemy.text(
                "INSERT INTO relationship_evidence "
                "(id, source_ref, content_sha256, media_type, visibility, custody_id, recorded_at) "
                "VALUES ('RAW_EVIDENCE', 'raw', :digest, 'text/plain', 'internal', 'raw', now())"
            ),
            {"digest": "a" * 64},
        )

    immutable_evidence_update = sqlalchemy.text(
        "UPDATE relationship_evidence SET source_ref = 'changed' WHERE id = 'RAW_EVIDENCE'"
    )
    with engine.connect() as connection:
        with pytest.raises(sqlalchemy.exc.DBAPIError):
            connection.execute(immutable_evidence_update)


def _verify_capability_runtime(
    base_url: str,
    target_url: str,
    database_name: str,
    profile: str,
    password: str,
    runtime_engines: list[sqlalchemy.Engine],
    runtime_logins: list[str],
) -> None:
    """Verify selected capability grants and deliberate authority drift."""
    capabilities = _profile_capabilities(profile)
    if not capabilities:
        return
    login_name = f"{database_name}_cap_runtime"
    capability_roles = tuple(
        RUNTIME_CAPABILITY_ROLES[capability] for capability in ("graph", "coordination") if capability in capabilities
    )
    runtime_logins.append(login_name)
    _create_runtime_login(base_url, login_name, capability_roles, password)
    engine = sqlalchemy.create_engine(_runtime_url(target_url, login_name, password), future=True)
    runtime_engines.append(engine)

    verify_database_schema(engine, required_capabilities=capabilities)
    verify_runtime_database_authority(engine, required_capabilities=capabilities)
    _set_runtime_schema_create(target_url, login_name, enabled=True)
    try:
        with pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"):
            verify_runtime_database_authority(engine, required_capabilities=capabilities)
    finally:
        _set_runtime_schema_create(target_url, login_name, enabled=False)
    verify_runtime_database_authority(engine, required_capabilities=capabilities)

    if profile == "combined":
        _set_runtime_table_select(target_url, login_name, "user_credentials", enabled=True)
        try:
            with pytest.raises(SchemaCompatibilityError, match="cross-profile authority"):
                verify_runtime_database_authority(engine, required_capabilities=capabilities)
        finally:
            _set_runtime_table_select(target_url, login_name, "user_credentials", enabled=False)
        verify_runtime_database_authority(engine, required_capabilities=capabilities)


def _verify_zero_capability_runtime(
    base_url: str,
    target_url: str,
    database_name: str,
    profile: str,
    password: str,
    runtime_engines: list[sqlalchemy.Engine],
    runtime_logins: list[str],
) -> None:
    """Prove a no-capability login cannot retain direct managed-relation grants."""
    if "graph" not in EXPECTED_PROFILES[profile]:
        return
    login_name = f"{database_name}_zero_runtime"
    runtime_logins.append(login_name)
    _create_runtime_login(base_url, login_name, (), password)
    engine = sqlalchemy.create_engine(_runtime_url(target_url, login_name, password), future=True)
    runtime_engines.append(engine)

    verify_runtime_database_authority(engine)
    _set_runtime_table_select(target_url, login_name, "assets", enabled=True)
    try:
        with pytest.raises(SchemaCompatibilityError, match="runtime login grants are incompatible on assets"):
            verify_runtime_database_authority(engine)
    finally:
        _set_runtime_table_select(target_url, login_name, "assets", enabled=False)
    verify_runtime_database_authority(engine)


def _verify_auth_runtime(
    base_url: str,
    target_url: str,
    database_name: str,
    profile: str,
    password: str,
    runtime_logins: list[str],
) -> None:
    """Verify auth runtime authority, including table and view cross-profile drift."""
    if "auth" not in EXPECTED_PROFILES[profile]:
        return
    login_name = f"{database_name}_auth_runtime"
    runtime_logins.append(login_name)
    _create_runtime_login(base_url, login_name, (AUTH_RUNTIME_ROLE,), password)
    runtime_url = _runtime_url(target_url, login_name, password)

    with bind_database_url(runtime_url):
        verify_schema_compatibility()
        verify_runtime_authority()
    _set_runtime_schema_create(target_url, login_name, enabled=True)
    try:
        with (
            bind_database_url(runtime_url),
            pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"),
        ):
            verify_runtime_authority()
    finally:
        _set_runtime_schema_create(target_url, login_name, enabled=False)
    with bind_database_url(runtime_url):
        verify_runtime_authority()

    if profile == "combined":
        _set_runtime_table_select(target_url, login_name, "assets", enabled=True)
        try:
            with bind_database_url(runtime_url), pytest.raises(SchemaCompatibilityError, match="cross-profile"):
                verify_runtime_authority()
        finally:
            _set_runtime_table_select(target_url, login_name, "assets", enabled=False)
        with bind_database_url(runtime_url):
            verify_runtime_authority()
    elif profile == "auth":
        _set_auth_cross_profile_view(target_url, login_name, enabled=True)
        try:
            with bind_database_url(runtime_url), pytest.raises(SchemaCompatibilityError, match="cross-profile"):
                verify_runtime_authority()
        finally:
            _set_auth_cross_profile_view(target_url, login_name, enabled=False)
        with bind_database_url(runtime_url):
            verify_runtime_authority()


@pytest.mark.parametrize("profile", ["auth", "graph", "coordination", "combined"])
def test_clean_profile_build_and_history(profile: str) -> None:
    """Each profile builds exactly its tables and ordered history from empty PostgreSQL."""
    base_url = _ephemeral_postgres_url()
    database_name = f"cq03b_{profile}_{uuid4().hex[:12]}"
    target_url = _database_url(base_url, database_name)
    manifest = load_and_validate_manifest()
    logical_targets = LOGICAL_TARGET_ORDER if profile == "combined" else (profile,)
    target = PlannedTarget(
        logical_targets=logical_targets,
        profile=profile,
        lineage="fresh-v1",
        execution_class="loopback",
        fingerprint="0" * 64,
        database_url=target_url,
    )

    _bootstrap_roles_and_create_database(base_url, database_name)
    operator_engine = None
    runtime_engines: list[sqlalchemy.Engine] = []
    runtime_logins: list[str] = []
    try:
        apply_profile_to_database(target, manifest)
        # A second projection must be an exact no-op, not a second history identity.
        apply_profile_to_database(target, manifest)

        operator_engine = sqlalchemy.create_engine(target_url, future=True)
        _assert_profile_catalog(operator_engine, manifest, profile)
        _verify_operator_contract(operator_engine, target_url, profile)
        _verify_profile_drift_contract(operator_engine, target_url, manifest, profile)
        _verify_graph_data_contract(operator_engine, profile)
        password = f"cq03b-{uuid4().hex}"
        _verify_capability_runtime(
            base_url,
            target_url,
            database_name,
            profile,
            password,
            runtime_engines,
            runtime_logins,
        )
        _verify_zero_capability_runtime(
            base_url,
            target_url,
            database_name,
            profile,
            password,
            runtime_engines,
            runtime_logins,
        )
        _verify_auth_runtime(base_url, target_url, database_name, profile, password, runtime_logins)
    finally:
        for runtime_engine in runtime_engines:
            runtime_engine.dispose()
        if operator_engine is not None:
            operator_engine.dispose()
        try:
            _drop_database(base_url, database_name)
        finally:
            for runtime_login in runtime_logins:
                _drop_runtime_login(base_url, runtime_login)
