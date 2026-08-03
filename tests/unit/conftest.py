"""Unit-test isolation fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

_DATABASE_RELOAD_TEST_MODULES = {
    "test_api_database.py",
    "test_database_memory.py",
    "test_postgres_support.py",
}


@pytest.fixture(autouse=True)
def _restore_auth_schema_after_database_reload_tests(
    request: pytest.FixtureRequest,
) -> Iterator[None]:
    """Recreate the SQLite auth schema after tests that reload ``api.database``."""
    yield

    if request.node.path.name not in _DATABASE_RELOAD_TEST_MODULES:
        return

    from api import database

    if database.DATABASE_TYPE == "sqlite":
        database.initialize_schema()
