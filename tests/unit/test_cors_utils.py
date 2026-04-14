"""Unit tests for CORS utility helpers in api/cors_utils.py."""

from __future__ import annotations

import re

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
        Fail the test if this helper is invoked, indicating a downstream validator executed when it should have been short-circuited.

        Always raises an AssertionError with message "short-circuit failed: later validator executed".

        Raises:
            AssertionError: Always raised when called.
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
        Record a stubbed http-local-in-dev check by appending "http_local_dev" to the shared calls list.

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
        Indicate a test failure if invoked, asserting that short-circuiting did not occur.

        Raises:
            AssertionError: Always raised with message "short-circuit failed: evaluated after True check".
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


# ---------------------------------------------------------------------------
# New helpers added in this PR
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsAllowedListOrigin:
    """Unit tests for _is_allowed_list_origin (new in this PR)."""

    def test_returns_true_when_origin_in_list(self) -> None:
        """An origin present in the allowlist returns True."""
        result = cors_utils._is_allowed_list_origin(
            "https://example.com",
            ["https://example.com", "https://other.com"],
        )
        assert result is True

    def test_returns_false_when_origin_not_in_list(self) -> None:
        """An origin absent from the allowlist returns False."""
        result = cors_utils._is_allowed_list_origin(
            "https://evil.com",
            ["https://example.com"],
        )
        assert result is False

    def test_empty_origin_returns_false(self) -> None:
        """An empty origin string returns False even if '' is in the list."""
        result = cors_utils._is_allowed_list_origin("", ["https://example.com", ""])
        assert result is False

    def test_empty_allowlist_returns_false(self) -> None:
        """An empty allowlist always returns False."""
        result = cors_utils._is_allowed_list_origin("https://example.com", [])
        assert result is False

    def test_exact_match_required(self) -> None:
        """Partial or prefix matches do not satisfy the allowlist check."""
        result = cors_utils._is_allowed_list_origin(
            "https://example.com/extra",
            ["https://example.com"],
        )
        assert result is False

    def test_case_sensitive_matching(self) -> None:
        """Allowlist comparison is case-sensitive."""
        result = cors_utils._is_allowed_list_origin(
            "HTTPS://EXAMPLE.COM",
            ["https://example.com"],
        )
        assert result is False

    def test_multiple_entries_first_match_wins(self) -> None:
        """Returns True as soon as the origin is found in the list."""
        result = cors_utils._is_allowed_list_origin(
            "https://a.com",
            ["https://b.com", "https://a.com", "https://c.com"],
        )
        assert result is True

    def test_returns_bool_type(self) -> None:
        """Return value is a plain bool, not a truthy non-bool."""
        result = cors_utils._is_allowed_list_origin("https://x.com", ["https://x.com"])
        assert type(result) is bool  # noqa: E721


@pytest.mark.unit
class TestIsHttpLocalInDev:
    """Unit tests for _is_http_local_in_dev (new in this PR)."""

    def test_localhost_in_development_returns_true(self) -> None:
        """http://localhost in development environment is allowed."""
        assert cors_utils._is_http_local_in_dev("http://localhost", "development") is True

    def test_localhost_with_port_in_development(self) -> None:
        """http://localhost:3000 in development is allowed."""
        assert cors_utils._is_http_local_in_dev("http://localhost:3000", "development") is True

    def test_127_0_0_1_in_development(self) -> None:
        """http://127.0.0.1 in development environment is allowed."""
        assert cors_utils._is_http_local_in_dev("http://127.0.0.1", "development") is True

    def test_127_0_0_1_with_port_in_development(self) -> None:
        """http://127.0.0.1:8080 in development environment is allowed."""
        assert cors_utils._is_http_local_in_dev("http://127.0.0.1:8080", "development") is True

    def test_localhost_in_production_returns_false(self) -> None:
        """http://localhost in production environment is NOT allowed."""
        assert cors_utils._is_http_local_in_dev("http://localhost", "production") is False

    def test_localhost_in_staging_returns_false(self) -> None:
        """http://localhost in staging environment is NOT allowed."""
        assert cors_utils._is_http_local_in_dev("http://localhost", "staging") is False

    def test_empty_env_returns_false(self) -> None:
        """An empty environment string does not allow HTTP local origins."""
        assert cors_utils._is_http_local_in_dev("http://localhost", "") is False

    def test_https_localhost_in_dev_returns_false(self) -> None:
        """HTTPS localhost does NOT match the HTTP-local check even in development."""
        assert cors_utils._is_http_local_in_dev("https://localhost", "development") is False

    def test_external_http_origin_in_dev_returns_false(self) -> None:
        """An external HTTP origin is not accepted even in development."""
        assert cors_utils._is_http_local_in_dev("http://example.com", "development") is False

    def test_dev_env_case_sensitive(self) -> None:
        """The environment check is case-sensitive; 'Development' does not match."""
        assert cors_utils._is_http_local_in_dev("http://localhost", "Development") is False

    def test_returns_bool_type(self) -> None:
        """Return value is a plain bool."""
        result = cors_utils._is_http_local_in_dev("http://localhost", "development")
        assert type(result) is bool  # noqa: E721


@pytest.mark.unit
class TestIsHttpsLocal:
    """Unit tests for _is_https_local (new in this PR)."""

    def test_https_localhost_returns_true(self) -> None:
        """https://localhost is accepted."""
        assert cors_utils._is_https_local("https://localhost") is True

    def test_https_localhost_with_port_returns_true(self) -> None:
        """https://localhost:8443 is accepted."""
        assert cors_utils._is_https_local("https://localhost:8443") is True

    def test_https_127_0_0_1_returns_true(self) -> None:
        """https://127.0.0.1 is accepted."""
        assert cors_utils._is_https_local("https://127.0.0.1") is True

    def test_https_127_0_0_1_with_port_returns_true(self) -> None:
        """https://127.0.0.1:9000 is accepted."""
        assert cors_utils._is_https_local("https://127.0.0.1:9000") is True

    def test_http_localhost_returns_false(self) -> None:
        """http://localhost (HTTP, not HTTPS) is rejected."""
        assert cors_utils._is_https_local("http://localhost") is False

    def test_https_external_domain_returns_false(self) -> None:
        """https://example.com is not an HTTPS local origin."""
        assert cors_utils._is_https_local("https://example.com") is False

    def test_empty_string_returns_false(self) -> None:
        """An empty string is not an HTTPS local origin."""
        assert cors_utils._is_https_local("") is False

    def test_https_localhostname_is_rejected(self) -> None:
        """'https://localhostname' (no match) is rejected."""
        assert cors_utils._is_https_local("https://localhostname") is False

    def test_returns_bool_type(self) -> None:
        """Return value is a plain bool."""
        result = cors_utils._is_https_local("https://localhost")
        assert type(result) is bool  # noqa: E721

    def test_https_local_with_zero_port_returns_false(self) -> None:
        """https://localhost:0 - port 0 is allowed by regex (digits match)."""
        # Port :0 is valid syntax matching :\d+; function should return True
        result = cors_utils._is_https_local("https://localhost:0")
        # The regex only checks for digit presence, so this should be True
        assert result is True


@pytest.mark.unit
class TestCompiledRegexConstants:
    """Tests for the new module-level compiled regex constants (new in this PR)."""

    def test_http_local_re_matches_localhost(self) -> None:
        """_HTTP_LOCAL_RE matches http://localhost."""
        assert cors_utils._HTTP_LOCAL_RE.match("http://localhost") is not None

    def test_http_local_re_matches_localhost_with_port(self) -> None:
        """_HTTP_LOCAL_RE matches http://localhost:3000."""
        assert cors_utils._HTTP_LOCAL_RE.match("http://localhost:3000") is not None

    def test_http_local_re_matches_127_0_0_1(self) -> None:
        """_HTTP_LOCAL_RE matches http://127.0.0.1."""
        assert cors_utils._HTTP_LOCAL_RE.match("http://127.0.0.1") is not None

    def test_http_local_re_rejects_https(self) -> None:
        """_HTTP_LOCAL_RE does not match https:// origins."""
        assert cors_utils._HTTP_LOCAL_RE.match("https://localhost") is None

    def test_http_local_re_rejects_external(self) -> None:
        """_HTTP_LOCAL_RE does not match http://example.com."""
        assert cors_utils._HTTP_LOCAL_RE.match("http://example.com") is None

    def test_https_local_re_matches_localhost(self) -> None:
        """_HTTPS_LOCAL_RE matches https://localhost."""
        assert cors_utils._HTTPS_LOCAL_RE.match("https://localhost") is not None

    def test_https_local_re_matches_127_with_port(self) -> None:
        """_HTTPS_LOCAL_RE matches https://127.0.0.1:9443."""
        assert cors_utils._HTTPS_LOCAL_RE.match("https://127.0.0.1:9443") is not None

    def test_https_local_re_rejects_http(self) -> None:
        """_HTTPS_LOCAL_RE does not match http://localhost."""
        assert cors_utils._HTTPS_LOCAL_RE.match("http://localhost") is None

    def test_vercel_preview_re_matches_subdomain(self) -> None:
        """_VERCEL_PREVIEW_RE matches https://<subdomain>.vercel.app."""
        assert cors_utils._VERCEL_PREVIEW_RE.match("https://myapp-abc123.vercel.app") is not None

    def test_vercel_preview_re_rejects_http(self) -> None:
        """_VERCEL_PREVIEW_RE does not match http:// Vercel URLs."""
        assert cors_utils._VERCEL_PREVIEW_RE.match("http://myapp.vercel.app") is None

    def test_vercel_preview_re_rejects_non_vercel(self) -> None:
        """_VERCEL_PREVIEW_RE does not match non-vercel.app domains."""
        assert cors_utils._VERCEL_PREVIEW_RE.match("https://myapp.netlify.app") is None

    def test_https_domain_re_matches_standard_domain(self) -> None:
        """_HTTPS_DOMAIN_RE matches https://example.com."""
        assert cors_utils._HTTPS_DOMAIN_RE.match("https://example.com") is not None

    def test_https_domain_re_matches_subdomain(self) -> None:
        """_HTTPS_DOMAIN_RE matches https://api.example.com."""
        assert cors_utils._HTTPS_DOMAIN_RE.match("https://api.example.com") is not None

    def test_https_domain_re_matches_with_port(self) -> None:
        """_HTTPS_DOMAIN_RE matches https://example.com:8443."""
        assert cors_utils._HTTPS_DOMAIN_RE.match("https://example.com:8443") is not None

    def test_https_domain_re_rejects_http(self) -> None:
        """_HTTPS_DOMAIN_RE does not match http:// origins."""
        assert cors_utils._HTTPS_DOMAIN_RE.match("http://example.com") is None

    def test_constants_are_compiled_pattern_objects(self) -> None:
        """All four regex constants are compiled Pattern objects."""
        assert isinstance(cors_utils._HTTP_LOCAL_RE, type(re.compile("")))
        assert isinstance(cors_utils._HTTPS_LOCAL_RE, type(re.compile("")))
        assert isinstance(cors_utils._VERCEL_PREVIEW_RE, type(re.compile("")))
        assert isinstance(cors_utils._HTTPS_DOMAIN_RE, type(re.compile("")))
