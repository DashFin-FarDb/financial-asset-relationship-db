"""
Integration test for Supabase connectivity.

Opt-in only: requires real credentials and network access.

Enable explicitly by setting:
  RUN_SUPABASE_TESTS=1
and providing:
  SUPABASE_URL
  SUPABASE_KEY

Notes:
- This test should not run in standard CI unless you explicitly configure secrets.
- We do not print secrets or raw URLs beyond a minimal redaction.
"""

from __future__ import annotations

import os
from typing import Final, Optional

import pytest

pytest.importorskip("supabase")

from supabase import Client, create_client  # noqa: E402  # pylint: disable=wrong-import-position

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
    """Redact a secret value for logs, preserving only the first/last 4 chars."""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"


@pytest.mark.integration
def test_supabase_connection_smoke() -> None:
    """
    Smoke-test Supabase connection by querying a small number of records.

    Expectations:
    - Client initializes
    - Query executes without raising
    - Response contains a 'data' attribute (list-like)
    """
    if os.getenv("RUN_SUPABASE_TESTS") != "1":
        pytest.skip("Set RUN_SUPABASE_TESTS=1 to enable live Supabase connectivity test")

    # If you *really* want local .env loading, do it only when explicitly enabled.
    if os.getenv("LOAD_DOTENV") == "1":
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass  # dotenv not installed; proceed without it

    supabase_url = _get_env("SUPABASE_URL")
    supabase_key = _get_env("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        pytest.skip("Missing SUPABASE_URL and/or SUPABASE_KEY")

    if any(tok in supabase_key for tok in PLACEHOLDER_TOKENS):
        pytest.skip("SUPABASE_KEY appears to be a placeholder")

    # Build client
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Failed to initialize Supabase client (url={_redact(supabase_url)}): {exc}")

    # Execute a safe, low-cost query.
    # Assumes 'assets' table exists as per your domain; if not, adjust to a known table.
    try:
        response = supabase.table("assets").select("id").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Supabase query failed (url={_redact(supabase_url)}): {exc}")

    # Validate response shape
    assert response is not None  # nosec B101
    assert hasattr(response, "data")  # nosec B101
    assert isinstance(response.data, list)  # nosec B101
