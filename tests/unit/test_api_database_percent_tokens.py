"""Focused regression coverage for PostgreSQL auth capability DDL tokens."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from api.database import ensure_runtime_access

pytestmark = pytest.mark.unit


@patch("api.database.DATABASE_TYPE", "postgresql")
@patch("api.database.fetch_value", side_effect=[None, 2])
@patch("api.database.execute")
def test_ensure_runtime_access_escapes_driver_percent_tokens(mock_execute, _mock_fetch_value) -> None:
    """Server-side format tokens must be escaped before psycopg2 sees them."""
    ensure_runtime_access()

    emitted_statements = [call.args[0] for call in mock_execute.call_args_list]
    for statement in emitted_statements:
        assert re.search(r"(?<!%)%(?!%)", statement) is None

    statements = "\n".join(emitted_statements)
    assert "CREATE ROLE fardb_runtime_auth NOLOGIN" in statements
    assert "GRANT SELECT ON TABLE user_credentials TO fardb_runtime_auth" in statements
    assert "FOR SELECT TO fardb_runtime_auth USING (true)" in statements
    assert "GRANT INSERT" not in statements
    assert "GRANT UPDATE" not in statements
    assert "GRANT DELETE" not in statements
