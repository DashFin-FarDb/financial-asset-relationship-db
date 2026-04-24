"""
Pytest configuration and shared fixtures.

This file centralizes:
- Database engine/session fixtures (SQLite file or in-memory)
- Environment isolation for tests
- Coverage flag compatibility when pytest-cov is unavailable
- Common test helpers (e.g., factories) to avoid repeated boilerplate
"""

import importlib.util
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import Any, List, MutableSequence, Optional, Tuple

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
_COV_EQUALS_PREFIXES = (
    "--cov=",
    "--cov-report=",
    "--cov-config=",
    "--cov-context=",
    "--cov-fail-under=",
)


def _cov_plugin_available() -> bool:
    return importlib.util.find_spec("pytest_cov") is not None


def pytest_load_initial_conftests(
    early_config: Any,
    parser: Any,
    args: Optional[MutableSequence[str]],
) -> None:
    del parser

    if _cov_plugin_available():
        return

    target_args = args
    if target_args is None and isinstance(early_config, list):
        target_args = early_config

    if target_args is None:
        return

    target_args[:] = _strip_pytest_cov_args(target_args)


def _strip_pytest_cov_args(args: MutableSequence[str]) -> List[str]:
    filtered_args: List[str] = []
    index = 0

    while index < len(args):
        arg = args[index]
        if arg == "--":
            return filtered_args + list(args[index:])

        should_keep, index = _classify_pytest_cov_arg(args, index)
        if should_keep:
            filtered_args.append(arg)

    return filtered_args


def _classify_pytest_cov_arg(
    args: MutableSequence[str],
    index: int,
) -> Tuple[bool, int]:
    arg = args[index]

    if arg in _COV_FLAGS_WITH_OPTIONAL_VALUE:
        return False, _next_index_after_optional_value(args, index)

    if arg in _COV_VALUE_FLAGS:
        return False, _next_index_after_required_value(args, index)

    if arg in _COV_BOOLEAN_FLAGS or _is_cov_equals_arg(arg):
        return False, index + 1

    return True, index + 1


def _next_index_after_optional_value(
    args: MutableSequence[str],
    index: int,
) -> int:
    next_index = index + 1
    if next_index < len(args) and _looks_like_option_value(args[next_index]):
        return next_index + 1
    return next_index


def _next_index_after_required_value(
    args: MutableSequence[str],
    index: int,
) -> int:
    next_index = index + 1
    if next_index < len(args) and args[next_index] != "--":
        return next_index + 1
    return next_index


def _looks_like_option_value(arg: str) -> bool:
    return arg != "--" and not arg.startswith("-")


def _is_cov_equals_arg(arg: str) -> bool:
    return arg.startswith(_COV_EQUALS_PREFIXES)


def pytest_addoption(parser: Any) -> None:
    if not _cov_plugin_available():
        _register_dummy_cov_options(parser)


def _safe_addoption(group: object, *names: str, **kwargs: object) -> None:
    try:
        group.addoption(*names, **kwargs)
    except ValueError as exc:
        if "already added" not in str(exc):
            raise


def _register_dummy_cov_options(parser: Any) -> None:
    group = parser.getgroup("cov")
    _safe_addoption(group, "--cov", action="append", dest="cov", default=[], metavar="path")
    _safe_addoption(group, "--cov-report", action="append", dest="cov_report", default=[], metavar="type")


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    monkeypatch.delenv("USE_REAL_DATA_FETCHER", raising=False)


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    db_path = tmp_path / "test_asset_graph.db"
    return f"sqlite:///{db_path}"


@pytest.fixture()
def engine(database_url: str) -> Iterator[Engine]:
    eng = create_engine_from_url(database_url)
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture()
def db_session(session_factory: Callable[[], Session]) -> Generator[Session, None, None]:
    with session_scope(session_factory) as session:
        yield session
