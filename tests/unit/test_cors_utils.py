"""Unit tests for CORS utility helpers in api/cors_utils.py."""

from __future__ import annotations

import pytest

from api import cors_utils


@pytest.mark.unit
def test_validate_origin_short_circuits_on_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allowlist match should return before any later validators execute."""
    origin = "https://allowed.example"
    monkeypatch.setenv("ALLOWED_ORIGINS", origin)
    monkeypatch.setenv("ENV", "production")

    def _must_not_run(*_args: object, **_kwargs: object) -> bool:
        """
        Fail the test if an unexpected downstream validator is invoked.

        This helper always raises an AssertionError to signal that a code path which should have been short-circuited was executed.

        Raises:
            AssertionError: Always raised with message "short-circuit failed: later validator executed".
        """
        raise AssertionError("short-circuit failed: later validator executed")

    monkeypatch.setattr(cors_utils, "_is_http_local_in_dev", _must_not_run)
    monkeypatch.setattr(cors_utils, "_is_https_local", _must_not_run)
    monkeypatch.setattr(cors_utils, "_is_vercel_preview", _must_not_run)
    monkeypatch.setattr(cors_utils, "_is_valid_https_domain", _must_not_run)
    monkeypatch.setattr(cors_utils, "_is_valid_https_idn", _must_not_run)

    assert cors_utils.validate_origin(origin) is True


@pytest.mark.unit
def test_validate_origin_stops_after_first_true_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validation should stop at the first True check in order."""
    calls: list[str] = []

    def _allowlist_false(origin: str, allowed_origins: list[str]) -> bool:
        """
        Test double that records an allowlist check invocation and always returns False.

        Appends the string "allowlist" to the surrounding `calls` list as a side effect. The `origin` and `allowed_origins` parameters are accepted but ignored.

        Returns:
            False to indicate the origin is not allowed by the allowlist.
        """
        del origin, allowed_origins
        calls.append("allowlist")
        return False

    def _http_local_true(origin: str, current_env: str) -> bool:
        """
        Record the stubbed http-local-in-dev check by appending "http_local_dev" to the shared calls list and return True.

        Parameters:
            origin (str): Unused; present for signature compatibility.
            current_env (str): Unused; present for signature compatibility.

        Returns:
            bool: Always True.
        """
        del origin, current_env
        calls.append("http_local_dev")
        return True

    def _must_not_run(*_args: object, **_kwargs: object) -> bool:
        """
        Fail the test if called, indicating a later validator was invoked despite an earlier successful check.

        Raises:
            AssertionError: always raised with message "short-circuit failed: evaluated after True check".
        """
        raise AssertionError("short-circuit failed: evaluated after True check")

    monkeypatch.setattr(cors_utils, "_is_allowed_list_origin", _allowlist_false)
    monkeypatch.setattr(cors_utils, "_is_http_local_in_dev", _http_local_true)
    monkeypatch.setattr(cors_utils, "_is_https_local", _must_not_run)
    monkeypatch.setattr(cors_utils, "_is_vercel_preview", _must_not_run)
    monkeypatch.setattr(cors_utils, "_is_valid_https_domain", _must_not_run)
    monkeypatch.setattr(cors_utils, "_is_valid_https_idn", _must_not_run)

    assert cors_utils.validate_origin("http://localhost:3000") is True
    assert calls == ["allowlist", "http_local_dev"]
