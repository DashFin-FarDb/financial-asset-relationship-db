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
from scripts.postgresql_ledger import (
    EXPECTED_MANAGED_TABLES,
    EXPECTED_PROFILES,
    LOGICAL_TARGET_ORDER,
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


def _expected_tables(profile: str) -> set[str]:
    """Return the exact public table set selected by one profile."""
    return {table_name for component in EXPECTED_PROFILES[profile] for table_name in EXPECTED_MANAGED_TABLES[component]}


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
        with operator_engine.connect() as connection:
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

        capabilities = set(EXPECTED_PROFILES[profile]).intersection({"graph", "coordination"})
        if capabilities:
            verify_database_schema(operator_engine, required_capabilities=capabilities)
        if "auth" in EXPECTED_PROFILES[profile]:
            with bind_database_url(target_url):
                verify_schema_compatibility()
                verify_runtime_access_catalog()

        password = f"cq03b-{uuid4().hex}"
        if capabilities:
            graph_login = f"{database_name}_graph_runtime"
            capability_roles = tuple(
                RUNTIME_CAPABILITY_ROLES[capability]
                for capability in ("graph", "coordination")
                if capability in capabilities
            )
            runtime_logins.append(graph_login)
            _create_runtime_login(base_url, graph_login, capability_roles, password)
            runtime_engine = sqlalchemy.create_engine(
                _runtime_url(target_url, graph_login, password),
                future=True,
            )
            runtime_engines.append(runtime_engine)

            verify_database_schema(runtime_engine, required_capabilities=capabilities)
            verify_runtime_database_authority(runtime_engine, required_capabilities=capabilities)
            _set_runtime_schema_create(target_url, graph_login, enabled=True)
            with pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"):
                verify_runtime_database_authority(runtime_engine, required_capabilities=capabilities)
            _set_runtime_schema_create(target_url, graph_login, enabled=False)
            verify_runtime_database_authority(runtime_engine, required_capabilities=capabilities)
            if profile == "combined":
                _set_runtime_table_select(target_url, graph_login, "user_credentials", enabled=True)
                with pytest.raises(SchemaCompatibilityError, match="cross-profile authority"):
                    verify_runtime_database_authority(runtime_engine, required_capabilities=capabilities)
                _set_runtime_table_select(target_url, graph_login, "user_credentials", enabled=False)
                verify_runtime_database_authority(runtime_engine, required_capabilities=capabilities)

        if "auth" in EXPECTED_PROFILES[profile]:
            auth_login = f"{database_name}_auth_runtime"
            runtime_logins.append(auth_login)
            _create_runtime_login(base_url, auth_login, (AUTH_RUNTIME_ROLE,), password)
            auth_runtime_url = _runtime_url(target_url, auth_login, password)

            with bind_database_url(auth_runtime_url):
                verify_schema_compatibility()
                verify_runtime_authority()
            _set_runtime_schema_create(target_url, auth_login, enabled=True)
            with (
                bind_database_url(auth_runtime_url),
                pytest.raises(
                    SchemaCompatibilityError,
                    match="retains schema-migration authority",
                ),
            ):
                verify_runtime_authority()
            _set_runtime_schema_create(target_url, auth_login, enabled=False)
            with bind_database_url(auth_runtime_url):
                verify_runtime_authority()
            if profile == "combined":
                _set_runtime_table_select(target_url, auth_login, "assets", enabled=True)
                with (
                    bind_database_url(auth_runtime_url),
                    pytest.raises(SchemaCompatibilityError, match="cross-profile authority"),
                ):
                    verify_runtime_authority()
                _set_runtime_table_select(target_url, auth_login, "assets", enabled=False)
                with bind_database_url(auth_runtime_url):
                    verify_runtime_authority()
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
