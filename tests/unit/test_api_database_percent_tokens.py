"""Focused regression coverage for the retired auth capability mutator."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from api.database import ensure_runtime_access
from src.data.database import SchemaCompatibilityError

pytestmark = pytest.mark.unit


@patch("api.database.DATABASE_TYPE", "postgresql")
@patch("api.database.fetch_value")
@patch("api.database.execute")
def test_ensure_runtime_access_emits_no_postgresql_sql(mock_execute, mock_fetch_value) -> None:
    """The legacy helper must fail before any driver token reaches psycopg2."""
    with pytest.raises(SchemaCompatibilityError, match="profile-scoped Supabase ledger"):
        ensure_runtime_access()

    mock_execute.assert_not_called()
    mock_fetch_value.assert_not_called()
