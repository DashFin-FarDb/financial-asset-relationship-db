"""
Integration test for Supabase connectivity.

Opt-in only: requires real credentials and network access.

Enable explicitly by setting:
  RUN_SUPABASE_TESTS=1
and providing:
  SUPABASE_URL
  SUPABASE_KEY

Notes:
- This test should not run in standard CI unless you explicitly configure
  secrets.
- We do not print secrets or raw URLs beyond a minimal redaction.
"""

from __future__ import annotations

import os
from typing import Any, Final, Optional

import pytest

pytest.importorskip("supabase")

# pylint: disable=wrong-import-position
from supabase import (  # noqa: E402  # pyright: ignore[reportMissingImports]; type: ignore[import-not-found]
    Client,
    create_client,
)

# pylint: enable=wrong-import-position

PLACEHOLDER_TOKENS: Final[tuple[str, ...]] = (
    "[YOUR-KEY]",
    "<KEY>",
    "YOUR_KEY",
    "SUPABASE_KEY_HERE",
)


def _get_env(name: str) -> Optional[str]:
    """Return the environment variable value for name, or None if unset."""
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _redact(value: str) -> str:
    """
    Redact a secret value for logs, preserving first/last 4 chars.
    """
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"


def _ensure_live_test_enabled() -> None:
    """Skip test unless live Supabase integration tests are enabled."""
    if os.getenv("RUN_SUPABASE_TESTS") == "1":
        return
    pytest.skip("Set RUN_SUPABASE_TESTS=1 to enable live Supabase connectivity test")


def _maybe_load_dotenv() -> None:
    """Load .env only when explicitly requested."""
    if os.getenv("LOAD_DOTENV") != "1":
        return
    dotenv = pytest.importorskip("dotenv")
    dotenv.load_dotenv()


def _read_supabase_credentials() -> tuple[str, str]:
    """Read and validate SUPABASE_URL and SUPABASE_KEY from environment."""
    supabase_url = _get_env("SUPABASE_URL")
    supabase_key = _get_env("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        pytest.skip("Missing SUPABASE_URL and/or SUPABASE_KEY")
    if any(tok in supabase_key for tok in PLACEHOLDER_TOKENS):
        pytest.skip("SUPABASE_KEY appears to be a placeholder")
    return supabase_url, supabase_key


def _create_supabase_client(url: str, key: str) -> Client:
    """Create Supabase client or fail the test with a redacted message."""
    try:
        return create_client(url, key)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Failed to initialize Supabase client (url={_redact(url)}): {exc}")


def _execute_smoke_query(client: Client, url: str) -> Any:
    """Execute a lightweight query and return response payload."""
    try:
        return client.table("assets").select("id").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Supabase query failed (url={_redact(url)}): {exc}")


@pytest.mark.integration
def test_supabase_connection_smoke() -> None:
    """
    Smoke-test Supabase connection by querying a small number of records.

    Expectations:
    - Client initializes
    - Query executes without raising
    - Response contains a 'data' attribute (list-like)
    """
    _ensure_live_test_enabled()
    _maybe_load_dotenv()
    supabase_url, supabase_key = _read_supabase_credentials()
    supabase = _create_supabase_client(supabase_url, supabase_key)
    response = _execute_smoke_query(supabase, supabase_url)

    # Validate response shape
    assert response is not None  # nosec B101
    assert hasattr(response, "data")  # nosec B101
    assert isinstance(response.data, list)  # nosec B101
