"""Unit tests for the bounded database authorization checker."""

from __future__ import annotations

from typing import Any

import pytest

from scripts import check_database_authorization as checker


def _database_url(host: str = "example.invalid") -> str:
    """Return a syntactically valid test PostgreSQL URL without a credential literal."""
    return f"postgresql://operator@{host}/fardb"


@pytest.fixture(autouse=True)
def _clear_database_url_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep configured database boundaries explicit and isolated in each test."""
    for variable_name in checker.SUPPORTED_DATABASE_URL_ENVS:
        monkeypatch.delenv(variable_name, raising=False)


def _snapshot(**overrides: int) -> checker.AuthorizationSnapshot:
    """Return a passing snapshot with selected field overrides."""
    values = {
        "table_count": 4,
        "rls_enabled_count": 4,
        "untrusted_grant_table_count": 0,
        "untrusted_sequence_count": 0,
        "untrusted_function_count": 0,
        "untrusted_view_count": 0,
        "unsafe_policy_count": 0,
    }
    values.update(overrides)
    return checker.AuthorizationSnapshot(**values)


@pytest.mark.unit
def test_evaluate_snapshot_accepts_closed_boundary() -> None:
    """A fully closed aggregate posture should pass."""
    assert checker.evaluate_snapshot(_snapshot()) == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("overrides", "expected_control"),
    [
        ({"rls_enabled_count": 3}, "exposed-schema-rls"),
        ({"untrusted_grant_table_count": 1}, "untrusted-table-access"),
        ({"untrusted_sequence_count": 1}, "untrusted-sequence-access"),
        ({"untrusted_function_count": 1}, "untrusted-function-access"),
        ({"untrusted_view_count": 1}, "untrusted-view-access"),
        ({"unsafe_policy_count": 1}, "policy-claim-safety"),
    ],
)
def test_evaluate_snapshot_reports_only_control_class(overrides: dict[str, int], expected_control: str) -> None:
    """Each failed control should return a bounded finding."""
    findings = checker.evaluate_snapshot(_snapshot(**overrides))
    assert [finding.control for finding in findings] == [expected_control]
    assert all("table_" not in finding.message for finding in findings)


@pytest.mark.unit
def test_evaluate_snapshot_rejects_inconsistent_counts() -> None:
    """Impossible aggregate evidence should fail closed."""
    findings = checker.evaluate_snapshot(_snapshot(rls_enabled_count=5))
    assert findings == [
        checker.Finding(
            "authorization-evidence-integrity",
            "authorization evidence was internally inconsistent",
        )
    ]


class _FakeCursor:
    """Minimal DB-API cursor for aggregate-check tests."""

    description = [
        ("table_count",),
        ("rls_enabled_count",),
        ("untrusted_grant_table_count",),
        ("untrusted_sequence_count",),
        ("untrusted_function_count",),
        ("untrusted_view_count",),
        ("unsafe_policy_count",),
    ]

    def __init__(self, row: tuple[int, ...] | None) -> None:
        self.row = row
        self.query = ""
        self.parameters: dict[str, str] = {}

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, parameters: dict[str, str]) -> None:
        self.query = query
        self.parameters = parameters

    def fetchone(self) -> tuple[int, ...] | None:
        return self.row


class _FakeConnection:
    """Minimal DB-API connection that records safety settings."""

    def __init__(self, row: tuple[int, ...] | None) -> None:
        self.fake_cursor = _FakeCursor(row)
        self.readonly = False
        self.autocommit = True
        self.rolled_back = False
        self.closed = False

    def set_session(self, *, readonly: bool, autocommit: bool) -> None:
        self.readonly = readonly
        self.autocommit = autocommit

    def cursor(self) -> _FakeCursor:
        return self.fake_cursor

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


@pytest.mark.unit
def test_collect_snapshot_uses_read_only_parameterized_query() -> None:
    """The collector should set a read-only transaction and bind the schema."""
    connection = _FakeConnection((4, 4, 0, 0, 0, 0, 0))

    snapshot = checker.collect_snapshot(connection, "public")

    assert snapshot == _snapshot()
    assert connection.readonly is True
    assert connection.autocommit is False
    assert connection.rolled_back is True
    assert connection.fake_cursor.parameters == {"schema": "public"}
    assert "public" not in connection.fake_cursor.query


@pytest.mark.unit
def test_collect_snapshot_rejects_missing_schema_evidence() -> None:
    """A missing schema should fail closed instead of passing with zero counts."""
    connection = _FakeConnection(None)

    with pytest.raises(RuntimeError, match="authorization query returned no evidence"):
        checker.collect_snapshot(connection, "typo_schema")


@pytest.mark.unit
@pytest.mark.parametrize(
    "database_url",
    [
        "https://operator@example.invalid/fardb",
        "postgresql://example.invalid/fardb",
        "postgresql://operator@example.invalid",
        "postgresql://operator@example.invalid/fardb#fragment",
        "postgresql://operator@example.invalid:70000/fardb",
    ],
)
def test_validate_database_url_rejects_untrusted_configuration(database_url: str) -> None:
    """Only complete PostgreSQL URLs should cross the connection trust boundary."""
    assert checker._validate_database_url(database_url) is None


@pytest.mark.unit
def test_configured_database_urls_deduplicate_fixed_allowlist() -> None:
    """Repeated configured boundaries should be checked once without accepting arbitrary keys."""
    database_url = _database_url()
    configured = checker._configured_database_urls(
        {
            "DATABASE_URL": database_url,
            "ASSET_GRAPH_DATABASE_URL": database_url,
            "UNSUPPORTED_DATABASE_URL": _database_url("other.invalid"),
        }
    )

    assert configured == (checker.TrustedDatabaseUrl(database_url),)


@pytest.mark.unit
def test_main_reports_bounded_failure_without_secret_or_topology(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Operator output must not echo connection strings, names or counts."""
    database_url = _database_url()
    connection = _FakeConnection((4, 3, 1, 0, 1, 0, 0))
    monkeypatch.setenv("DATABASE_URL", database_url)

    result = checker.main([], connector=lambda _url: connection)

    captured = capsys.readouterr()
    assert result == checker.CHECK_FAILED
    assert "database authorization gate failed" in captured.out
    assert "exposed-schema-rls" in captured.out
    assert "untrusted-table-access" in captured.out
    assert "untrusted-function-access" in captured.out
    assert database_url not in captured.out
    assert "example.invalid" not in captured.out
    assert "4" not in captured.out
    assert connection.closed is True


@pytest.mark.unit
def test_main_sanitizes_database_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Raw driver errors must not reach operator output."""
    database_url = _database_url()
    monkeypatch.setenv("DATABASE_URL", database_url)

    def fail_to_connect(_database_url: str) -> Any:
        raise RuntimeError(f"connection failed for {database_url} on restricted_table")

    result = checker.main([], connector=fail_to_connect)

    captured = capsys.readouterr()
    assert result == checker.CHECK_FAILED
    assert captured.err == "database authorization check could not complete\n"
    assert database_url not in captured.err
    assert "restricted_table" not in captured.err


@pytest.mark.unit
def test_main_sanitizes_connection_close_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Connection cleanup failures must fail closed without exposing details."""
    monkeypatch.setenv("DATABASE_URL", _database_url())
    connection = _FakeConnection((0, 0, 0, 0, 0, 0, 0))

    def fail_to_close() -> None:
        raise RuntimeError("restricted cleanup detail")

    connection.close = fail_to_close  # type: ignore[method-assign]

    result = checker.main([], connector=lambda _url: connection)

    captured = capsys.readouterr()
    assert result == checker.CHECK_FAILED
    assert captured.err == "database authorization check could not complete\n"
    assert "restricted cleanup detail" not in captured.err


@pytest.mark.unit
def test_main_rejects_unsafe_schema_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Unsafe schema labels should fail before a database connection is attempted."""
    monkeypatch.setenv("DATABASE_URL", _database_url())

    def unexpected_connect(_database_url: str) -> Any:
        raise AssertionError("connector must not be called")

    result = checker.main(["--exposed-schema", "public;select"], connector=unexpected_connect)

    captured = capsys.readouterr()
    assert result == checker.USAGE_ERROR
    assert captured.err == "database authorization check configuration is invalid\n"


@pytest.mark.unit
def test_main_rejects_invalid_database_url_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Malformed or non-PostgreSQL configuration should fail before connection."""
    monkeypatch.setenv("DATABASE_URL", "https://operator@example.invalid/fardb")

    def unexpected_connect(_database_url: str) -> Any:
        raise AssertionError("connector must not be called")

    result = checker.main([], connector=unexpected_connect)

    captured = capsys.readouterr()
    assert result == checker.USAGE_ERROR
    assert captured.err == "database authorization check configuration is invalid\n"


@pytest.mark.unit
def test_main_fails_closed_when_schema_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-existent exposed schema label must not pass the authorization gate."""
    monkeypatch.setenv("DATABASE_URL", _database_url())
    connection = _FakeConnection(None)

    result = checker.main(["--exposed-schema", "typo_schema"], connector=lambda _url: connection)

    captured = capsys.readouterr()
    assert result == checker.CHECK_FAILED
    assert captured.err == "database authorization check could not complete\n"
