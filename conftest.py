"""
Pytest configuration and shared fixtures.

This file centralizes:
- Database engine/session fixtures (SQLite file or in-memory)
- Environment isolation for tests
- Coverage flag compatibility when pytest-cov is unavailable
- Common test helpers (e.g., factories) to avoid repeated boilerplate
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Generator, Iterator, MutableSequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.data.database import (
    Base,
    create_engine_from_url,
    create_session_factory,
    session_scope,
)
_COV_FLAGS_WITH_OPTIONAL_VALUE = {"--cov", "--cov-report"}
_COV_VALUE_FLAGS = {"--cov-config", "--cov-context", "--cov-fail-under"}
_COV_BOOLEAN_FLAGS = {
    "--cov-append",
    "--cov-branch",
    "--cov-reset",
}


def _cov_plugin_available() -> bool:
    """Return whether pytest-cov is importable in the current environment."""
    return importlib.util.find_spec("pytest_cov") is not None


def pytest_load_initial_conftests(
    early_config: Any,
    parser: Any,
    args: MutableSequence[str] | None,
) -> None:  # pragma: no cover
    """
    Strip pytest-cov flags before option parsing when pytest-cov is unavailable.

    The hook mutates the provided argument list in place. Some unit tests call
    this helper with the argument list as the first positional argument, while
    pytest itself supplies it as the third argument. Both forms are supported to
    keep the hook testable and compatible with pytest's hook signature.

    Parameters:
        early_config: Pytest early configuration object, or the args list in
            direct unit-test calls.
        parser: Pytest parser object. Unused by this filtering hook.
        args: Mutable pytest argument list supplied by pytest.
    """
    if _cov_plugin_available():
        return

    target_args = args
    if target_args is None and isinstance(early_config, list):
        target_args = early_config

    if target_args is None:
        return

    target_args[:] = _strip_pytest_cov_args(target_args)


def _strip_pytest_cov_args(args: MutableSequence[str]) -> list[str]:
    """Return args with pytest-cov flags removed without dropping test paths."""
    filtered_args: list[str] = []
    index = 0

    while index < len(args):
        arg = args[index]

        if arg == "--":
            filtered_args.extend(args[index:])
            break

        if arg in _COV_FLAGS_WITH_OPTIONAL_VALUE:
            index += 1
            if index < len(args) and _looks_like_option_value(args[index]):
                index += 1
            continue

        if arg in _COV_VALUE_FLAGS:
            index += 1
            if index < len(args) and args[index] != "--":
                index += 1
            continue

        if arg in _COV_BOOLEAN_FLAGS:
            index += 1
            continue

        if _is_cov_equals_arg(arg):
            index += 1
            continue

        filtered_args.append(arg)
        index += 1

    return filtered_args

def _looks_like_option_value(arg: str) -> bool:
    """Return whether arg is a value token rather than another CLI option."""
    return arg != "--" and not arg.startswith("-")


def _is_cov_equals_arg(arg: str) -> bool:
    """Return whether arg is a pytest-cov flag provided as --flag=value."""
    cov_prefixes = (
        "--cov=",
        "--cov-report=",
        "--cov-config=",
        "--cov-context=",
        "--cov-fail-under=",
    )
    return arg.startswith(cov_prefixes)


def pytest_addoption(parser: Any) -> None:
    """
    Register dummy coverage command-line options when pytest-cov is unavailable.

    This is a fallback for environments where option stripping does not run
    early enough. If pytest-cov is available, no dummy options are registered.

    Parameters:
        parser: Pytest argument parser used to add command-line options.
    """
    if not _cov_plugin_available():
        _register_dummy_cov_options(parser)


def _safe_addoption(
    group: object,
    *names: str,
    **kwargs: object,
) -> None:  # pragma: no cover
    """Add a pytest option, ignoring only duplicate-registration errors."""
    try:
        group.addoption(*names, **kwargs)  # type: ignore[attr-defined]
    except ValueError as exc:
        message = str(exc)
        if "already added" not in message:
            raise


def _register_dummy_cov_options(parser: Any) -> None:  # pragma: no cover
    """Register dummy --cov and --cov-report options."""
    group = parser.getgroup("cov")
    _safe_addoption(
        group,
        "--cov",
        action="append",
        dest="cov",
        default=[],
        metavar="path",
        help="Dummy option registered when pytest-cov is unavailable.",
    )
    _safe_addoption(
        group,
        "--cov-report",
        action="append",
        dest="cov_report",
        default=[],
        metavar="type",
        help="Dummy option registered when pytest-cov is unavailable.",
    )


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure tests do not accidentally read developer/prod environment variables.

    You can extend this list as the codebase grows.
    """
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    monkeypatch.delenv("USE_REAL_DATA_FETCHER", raising=False)
    monkeypatch.delenv("GRAPH_CACHE_PATH", raising=False)
    monkeypatch.delenv("REAL_DATA_CACHE_PATH", raising=False)


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    """
    Default test DB URL.

    Uses a temporary on-disk SQLite DB to behave closer to production than :memory:.
    If you want in-memory for speed, replace with:
        "sqlite:///:memory:"
    """
    db_path = tmp_path / "test_asset_graph.db"
    return f"sqlite:///{db_path}"


@pytest.fixture()
def engine(database_url: str) -> Iterator[Engine]:
    """Create a SQLAlchemy Engine for tests and ensure schema exists."""
    eng = create_engine_from_url(database_url)
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the test engine."""
    return create_session_factory(engine)


@pytest.fixture()
def db_session(
    session_factory: Callable[[], Session],
) -> Generator[Session, None, None]:
    """
    Provide a transaction-scoped SQLAlchemy Session.

    Uses the project's session_scope helper to ensure commit/rollback/close semantics.
    """
    with session_scope(session_factory) as session:
        yield session


@pytest.fixture()
def set_env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """
    Return a helper that sets environment variables for a test.

    The returned callable accepts keyword arguments where each key is an
    environment variable name and each value is the value to set;
    invoking it sets those environment variables for the duration of the
    test.

    Returns:
        setter (Callable[..., None]): Callable to set environment variables
            by passing keyword arguments (e.g., `set_env(KEY="value")`).
    """

    def _setter(**kwargs: str) -> None:
        """
        Set environment variables for a test using the captured pytest `monkeypatch`.

        Each keyword argument maps an environment variable name to its string
        value and will be set with `monkeypatch.setenv`.
        Parameters:
            **kwargs (str): Environment variable names and their values to set.
        """
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)

    return _setter


@pytest.fixture()
def unset_env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """
    Provide a fixture that returns a callable to remove environment
    variables from the test environment.

    The returned callable accepts one or more environment variable names
    and ensures each is removed for the duration of the test.

    Returns:
        unsetter (Callable[..., None]): Callable that deletes
            the specified environment variables.
    """

    def _unsetter(*keys: str) -> None:
        """
        Remove the given environment variables from the test environment.

        Parameters:
            *keys (str): One or more environment variable names to remove.
        """
        for key in keys:
            monkeypatch.delenv(key, raising=False)

    return _unsetter
