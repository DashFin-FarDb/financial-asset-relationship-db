"""Unit tests for api/cors_policy.py — CORS/origin policy helpers."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.cors_policy import (
    _has_forbidden_origin_parts,
    _is_http_local_in_dev,
    _is_https_local,
    _is_supported_origin_format,
    _is_valid_https_domain,
    _is_vercel_preview,
    build_allowed_origins,
    configure_cors,
    validate_origin,
)


# ---------------------------------------------------------------------------
# _is_http_local_in_dev
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsHttpLocalInDev:
    """Tests for _is_http_local_in_dev()."""

    def test_localhost_in_development_returns_true(self) -> None:
        assert _is_http_local_in_dev("http://localhost", "development") is True

    def test_localhost_with_port_in_development_returns_true(self) -> None:
        assert _is_http_local_in_dev("http://localhost:3000", "development") is True

    def test_127_0_0_1_in_development_returns_true(self) -> None:
        assert _is_http_local_in_dev("http://127.0.0.1", "development") is True

    def test_127_0_0_1_with_port_in_development_returns_true(self) -> None:
        assert _is_http_local_in_dev("http://127.0.0.1:8080", "development") is True

    def test_localhost_in_production_returns_false(self) -> None:
        assert _is_http_local_in_dev("http://localhost:3000", "production") is False

    def test_localhost_in_staging_returns_false(self) -> None:
        assert _is_http_local_in_dev("http://localhost", "staging") is False

    def test_localhost_in_empty_env_returns_false(self) -> None:
        assert _is_http_local_in_dev("http://localhost", "") is False

    def test_https_localhost_in_dev_returns_false(self) -> None:
        """HTTPS localhost does NOT match the HTTP-local check."""
        assert _is_http_local_in_dev("https://localhost", "development") is False

    def test_external_http_in_dev_returns_false(self) -> None:
        assert _is_http_local_in_dev("http://example.com", "development") is False

    def test_env_check_is_case_sensitive(self) -> None:
        assert _is_http_local_in_dev("http://localhost", "Development") is False
        assert _is_http_local_in_dev("http://localhost", "DEVELOPMENT") is False

    def test_returns_bool_type(self) -> None:
        result = _is_http_local_in_dev("http://localhost", "development")
        assert type(result) is bool  # noqa: E721


# ---------------------------------------------------------------------------
# _is_https_local
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsHttpsLocal:
    """Tests for _is_https_local()."""

    def test_https_localhost_returns_true(self) -> None:
        assert _is_https_local("https://localhost") is True

    def test_https_localhost_with_port_returns_true(self) -> None:
        assert _is_https_local("https://localhost:8443") is True

    def test_https_127_0_0_1_returns_true(self) -> None:
        assert _is_https_local("https://127.0.0.1") is True

    def test_https_127_0_0_1_with_port_returns_true(self) -> None:
        assert _is_https_local("https://127.0.0.1:9000") is True

    def test_http_localhost_returns_false(self) -> None:
        assert _is_https_local("http://localhost") is False

    def test_external_https_domain_returns_false(self) -> None:
        assert _is_https_local("https://example.com") is False

    def test_empty_string_returns_false(self) -> None:
        assert _is_https_local("") is False

    def test_localhostname_variant_returns_false(self) -> None:
        """https://localhostname should not match."""
        assert _is_https_local("https://localhostname") is False

    def test_returns_bool_type(self) -> None:
        result = _is_https_local("https://localhost")
        assert type(result) is bool  # noqa: E721

    def test_port_zero_matches(self) -> None:
        """Port :0 satisfies :\\d+ in the regex."""
        assert _is_https_local("https://localhost:0") is True


# ---------------------------------------------------------------------------
# _is_vercel_preview
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsVercelPreview:
    """Tests for _is_vercel_preview()."""

    def test_simple_subdomain_returns_true(self) -> None:
        assert _is_vercel_preview("https://myapp.vercel.app") is True

    def test_complex_subdomain_returns_true(self) -> None:
        assert _is_vercel_preview("https://myapp-git-main-user.vercel.app") is True

    def test_alphanumeric_subdomain_returns_true(self) -> None:
        assert _is_vercel_preview("https://abc123.vercel.app") is True

    def test_http_vercel_returns_false(self) -> None:
        """HTTP Vercel URLs are rejected."""
        assert _is_vercel_preview("http://myapp.vercel.app") is False

    def test_non_vercel_app_returns_false(self) -> None:
        assert _is_vercel_preview("https://myapp.netlify.app") is False

    def test_vercel_app_without_subdomain_returns_false(self) -> None:
        """https://vercel.app itself (no subdomain) must be rejected."""
        assert _is_vercel_preview("https://vercel.app") is False

    def test_trailing_path_returns_false(self) -> None:
        assert _is_vercel_preview("https://myapp.vercel.app/path") is False

    def test_empty_string_returns_false(self) -> None:
        assert _is_vercel_preview("") is False

    def test_returns_bool_type(self) -> None:
        result = _is_vercel_preview("https://myapp.vercel.app")
        assert type(result) is bool  # noqa: E721


# ---------------------------------------------------------------------------
# _has_forbidden_origin_parts
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHasForbiddenOriginParts:
    """Tests for _has_forbidden_origin_parts()."""

    def test_clean_parsed_result_returns_false(self) -> None:
        """A parsed origin with no forbidden parts returns False."""
        from urllib.parse import urlparse

        parsed = urlparse("https://example.com")
        assert _has_forbidden_origin_parts(parsed) is False

    def test_path_present_returns_true(self) -> None:
        """An origin with a non-empty path is forbidden."""
        obj = SimpleNamespace(path="/path", params="", query="", fragment="", username=None, password=None)
        assert _has_forbidden_origin_parts(obj) is True

    def test_params_present_returns_true(self) -> None:
        obj = SimpleNamespace(path="", params="p=1", query="", fragment="", username=None, password=None)
        assert _has_forbidden_origin_parts(obj) is True

    def test_query_present_returns_true(self) -> None:
        obj = SimpleNamespace(path="", params="", query="foo=bar", fragment="", username=None, password=None)
        assert _has_forbidden_origin_parts(obj) is True

    def test_fragment_present_returns_true(self) -> None:
        obj = SimpleNamespace(path="", params="", query="", fragment="section", username=None, password=None)
        assert _has_forbidden_origin_parts(obj) is True

    def test_username_present_returns_true(self) -> None:
        obj = SimpleNamespace(path="", params="", query="", fragment="", username="user", password=None)
        assert _has_forbidden_origin_parts(obj) is True

    def test_password_present_returns_true(self) -> None:
        obj = SimpleNamespace(path="", params="", query="", fragment="", username=None, password="secret")
        assert _has_forbidden_origin_parts(obj) is True

    def test_all_empty_returns_false(self) -> None:
        obj = SimpleNamespace(path="", params="", query="", fragment="", username=None, password=None)
        assert _has_forbidden_origin_parts(obj) is False

    def test_object_without_attributes_uses_defaults(self) -> None:
        """getattr with defaults handles objects lacking all attributes."""
        obj = object()
        # No attributes -> all default to falsy values -> returns False
        assert _has_forbidden_origin_parts(obj) is False

    def test_https_with_path_returns_true(self) -> None:
        from urllib.parse import urlparse

        parsed = urlparse("https://example.com/path")
        assert _has_forbidden_origin_parts(parsed) is True

    def test_https_with_query_returns_true(self) -> None:
        from urllib.parse import urlparse

        parsed = urlparse("https://example.com?q=1")
        assert _has_forbidden_origin_parts(parsed) is True


# ---------------------------------------------------------------------------
# _is_valid_https_domain
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsValidHttpsDomain:
    """Tests for _is_valid_https_domain()."""

    def test_simple_https_domain_returns_true(self) -> None:
        assert _is_valid_https_domain("https://example.com") is True

    def test_subdomain_returns_true(self) -> None:
        assert _is_valid_https_domain("https://api.example.com") is True

    def test_deep_subdomain_returns_true(self) -> None:
        assert _is_valid_https_domain("https://a.b.example.co.uk") is True

    def test_with_explicit_port_returns_true(self) -> None:
        assert _is_valid_https_domain("https://example.com:8443") is True

    def test_http_scheme_returns_false(self) -> None:
        assert _is_valid_https_domain("http://example.com") is False

    def test_no_scheme_returns_false(self) -> None:
        assert _is_valid_https_domain("example.com") is False

    def test_empty_string_returns_false(self) -> None:
        assert _is_valid_https_domain("") is False

    def test_url_with_path_returns_false(self) -> None:
        assert _is_valid_https_domain("https://example.com/path") is False

    def test_url_with_query_returns_false(self) -> None:
        assert _is_valid_https_domain("https://example.com?foo=bar") is False

    def test_url_with_fragment_returns_false(self) -> None:
        assert _is_valid_https_domain("https://example.com#section") is False

    def test_url_with_userinfo_returns_false(self) -> None:
        assert _is_valid_https_domain("https://user:pass@example.com") is False

    def test_empty_hostname_returns_false(self) -> None:
        assert _is_valid_https_domain("https://") is False

    def test_space_in_hostname_returns_false(self) -> None:
        assert _is_valid_https_domain("https://invalid domain.com") is False

    def test_idn_domain_returns_true(self) -> None:
        """Internationalized domain names (IDN) are accepted."""
        assert _is_valid_https_domain("https://münchen.de") is True

    def test_returns_false_on_malformed_input(self) -> None:
        assert _is_valid_https_domain("https://[invalid") is False

    def test_single_label_domain_returns_false(self) -> None:
        """A hostname without a dot (TLD) should not pass the regex."""
        assert _is_valid_https_domain("https://localhost") is False

    def test_returns_bool_type(self) -> None:
        result = _is_valid_https_domain("https://example.com")
        assert type(result) is bool  # noqa: E721


# ---------------------------------------------------------------------------
# _is_supported_origin_format
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsSupportedOriginFormat:
    """Tests for _is_supported_origin_format()."""

    def test_http_localhost_in_dev(self) -> None:
        assert _is_supported_origin_format("http://localhost:3000", "development") is True

    def test_http_localhost_in_prod_returns_false(self) -> None:
        assert _is_supported_origin_format("http://localhost:3000", "production") is False

    def test_https_localhost_any_env(self) -> None:
        assert _is_supported_origin_format("https://localhost:3000", "production") is True
        assert _is_supported_origin_format("https://localhost:3000", "development") is True

    def test_vercel_preview(self) -> None:
        assert _is_supported_origin_format("https://myapp.vercel.app", "production") is True

    def test_valid_https_domain(self) -> None:
        assert _is_supported_origin_format("https://example.com", "production") is True

    def test_invalid_origin_returns_false(self) -> None:
        assert _is_supported_origin_format("ftp://example.com", "development") is False

    def test_empty_string_returns_false(self) -> None:
        assert _is_supported_origin_format("", "development") is False

    def test_http_external_in_dev_returns_false(self) -> None:
        assert _is_supported_origin_format("http://external.com", "development") is False


# ---------------------------------------------------------------------------
# validate_origin
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateOrigin:
    """Tests for validate_origin() directly from api.cors_policy."""

    @staticmethod
    def test_empty_string_returns_false() -> None:
        assert validate_origin("") is False

    @staticmethod
    def test_http_localhost_in_development() -> None:
        from src.config.settings import get_settings

        with patch.dict(os.environ, {"ENV": "development"}):
            get_settings.cache_clear()
            try:
                assert validate_origin("http://localhost:3000") is True
            finally:
                get_settings.cache_clear()

    @staticmethod
    def test_http_localhost_rejected_in_production() -> None:
        from src.config.settings import get_settings

        with patch.dict(os.environ, {"ENV": "production"}):
            get_settings.cache_clear()
            try:
                assert validate_origin("http://localhost:3000") is False
            finally:
                get_settings.cache_clear()

    @staticmethod
    def test_https_localhost_allowed_always() -> None:
        assert validate_origin("https://localhost:3000") is True
        assert validate_origin("https://127.0.0.1:8000") is True

    @staticmethod
    def test_vercel_preview_allowed() -> None:
        assert validate_origin("https://myapp.vercel.app") is True

    @staticmethod
    def test_valid_https_domain_allowed() -> None:
        assert validate_origin("https://example.com") is True

    @staticmethod
    def test_invalid_scheme_rejected() -> None:
        assert validate_origin("ftp://example.com") is False

    @staticmethod
    def test_origin_in_allowed_origins_setting(monkeypatch: pytest.MonkeyPatch) -> None:
        """An origin explicitly listed in ALLOWED_ORIGINS is accepted."""
        from src.config.settings import get_settings

        monkeypatch.setenv("ALLOWED_ORIGINS", "http://special.internal.corp")
        get_settings.cache_clear()
        try:
            assert validate_origin("http://special.internal.corp") is True
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_origin_not_in_allowed_origins_and_invalid_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ALLOWED_ORIGINS", "https://allowed.example.com")
        monkeypatch.setenv("ENV", "production")
        get_settings.cache_clear()
        try:
            assert validate_origin("http://notlisted.example.com") is False
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_returns_bool_type() -> None:
        result = validate_origin("https://example.com")
        assert type(result) is bool  # noqa: E721


# ---------------------------------------------------------------------------
# build_allowed_origins
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildAllowedOrigins:
    """Tests for build_allowed_origins()."""

    @staticmethod
    def test_development_includes_http_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            origins = build_allowed_origins()
            assert "http://localhost:3000" in origins
            assert "http://localhost:7860" in origins
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_development_includes_https_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            origins = build_allowed_origins()
            assert "https://localhost:3000" in origins
            assert "https://localhost:7860" in origins
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_production_excludes_http_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            origins = build_allowed_origins()
            assert "http://localhost:3000" not in origins
            assert "http://localhost:7860" not in origins
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_production_includes_https_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            origins = build_allowed_origins()
            assert "https://localhost:3000" in origins
            assert "https://localhost:7860" in origins
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_valid_configured_origins_are_included(monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://myapp.example.com")
        get_settings.cache_clear()
        try:
            origins = build_allowed_origins()
            assert "https://myapp.example.com" in origins
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_invalid_configured_origins_are_excluded(
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "not-a-valid-origin")
        get_settings.cache_clear()
        try:
            import logging

            with caplog.at_level(logging.WARNING, logger="api.cors_policy"):
                origins = build_allowed_origins()
            assert "not-a-valid-origin" not in origins
            assert any("not-a-valid-origin" in record.message for record in caplog.records)
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_returns_list_type(monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            result = build_allowed_origins()
            assert isinstance(result, list)
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_multiple_valid_configured_origins(monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://app1.example.com,https://app2.example.com")
        get_settings.cache_clear()
        try:
            origins = build_allowed_origins()
            assert "https://app1.example.com" in origins
            assert "https://app2.example.com" in origins
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_vercel_preview_in_configured_origins(monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://myapp-preview.vercel.app")
        get_settings.cache_clear()
        try:
            origins = build_allowed_origins()
            assert "https://myapp-preview.vercel.app" in origins
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_no_duplicates_from_default_plus_configured(monkeypatch: pytest.MonkeyPatch) -> None:
        """If a configured origin duplicates a default one, it appears twice (list behaviour)."""
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://localhost:3000")
        get_settings.cache_clear()
        try:
            origins = build_allowed_origins()
            # The https://localhost:3000 is added as default AND from configured origins
            assert origins.count("https://localhost:3000") >= 1
        finally:
            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# configure_cors
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConfigureCors:
    """Tests for configure_cors()."""

    @staticmethod
    def test_adds_cors_middleware_to_app(monkeypatch: pytest.MonkeyPatch) -> None:
        """configure_cors() should add CORSMiddleware to the FastAPI app."""
        from fastapi import FastAPI
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            test_app = FastAPI()
            test_app.add_middleware = MagicMock()
            configure_cors(test_app)
            assert test_app.add_middleware.called
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_middleware_uses_cors_middleware_class(monkeypatch: pytest.MonkeyPatch) -> None:
        """The middleware added must be CORSMiddleware."""
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            test_app = FastAPI()
            calls = []

            def record_middleware(cls, **kwargs):  # type: ignore[no-untyped-def]
                calls.append((cls, kwargs))

            test_app.add_middleware = record_middleware
            configure_cors(test_app)
            assert len(calls) == 1
            assert calls[0][0] is CORSMiddleware
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_middleware_allows_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import FastAPI
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            test_app = FastAPI()
            captured_kwargs: dict = {}

            def record_middleware(cls, **kwargs):  # type: ignore[no-untyped-def]
                captured_kwargs.update(kwargs)

            test_app.add_middleware = record_middleware
            configure_cors(test_app)
            assert captured_kwargs.get("allow_credentials") is True
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_middleware_includes_required_methods(monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import FastAPI
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            test_app = FastAPI()
            captured_kwargs: dict = {}

            def record_middleware(cls, **kwargs):  # type: ignore[no-untyped-def]
                captured_kwargs.update(kwargs)

            test_app.add_middleware = record_middleware
            configure_cors(test_app)
            methods = captured_kwargs.get("allow_methods", [])
            for required in ("GET", "POST", "PUT", "DELETE", "OPTIONS"):
                assert required in methods, f"Method {required} missing from allow_methods"
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_middleware_includes_required_headers(monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import FastAPI
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            test_app = FastAPI()
            captured_kwargs: dict = {}

            def record_middleware(cls, **kwargs):  # type: ignore[no-untyped-def]
                captured_kwargs.update(kwargs)

            test_app.add_middleware = record_middleware
            configure_cors(test_app)
            headers = captured_kwargs.get("allow_headers", [])
            assert "Content-Type" in headers
            assert "Authorization" in headers
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_configure_cors_called_once(monkeypatch: pytest.MonkeyPatch) -> None:
        """configure_cors must call add_middleware exactly once."""
        from fastapi import FastAPI
        from src.config.settings import get_settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        get_settings.cache_clear()
        try:
            test_app = FastAPI()
            test_app.add_middleware = MagicMock()
            configure_cors(test_app)
            assert test_app.add_middleware.call_count == 1
        finally:
            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# validate_origin — additional boundary/regression tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateOriginBoundary:
    """Boundary and regression tests for validate_origin()."""

    @staticmethod
    def test_url_with_path_rejected() -> None:
        assert validate_origin("https://example.com/path") is False

    @staticmethod
    def test_url_with_query_rejected() -> None:
        assert validate_origin("https://example.com?foo=bar") is False

    @staticmethod
    def test_url_with_fragment_rejected() -> None:
        assert validate_origin("https://example.com#frag") is False

    @staticmethod
    def test_url_with_userinfo_rejected() -> None:
        assert validate_origin("https://user:pass@example.com") is False

    @staticmethod
    def test_none_like_empty_string_rejected() -> None:
        """Empty string short-circuits to False before any settings lookup."""
        assert validate_origin("") is False

    @staticmethod
    def test_explicit_allowlist_entry_bypasses_format_checks(monkeypatch: pytest.MonkeyPatch) -> None:
        """An entry in ALLOWED_ORIGINS is accepted regardless of format rules."""
        from src.config.settings import get_settings

        # This is an HTTP URL that would otherwise fail _is_supported_origin_format in production
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://internal.corp.example")
        get_settings.cache_clear()
        try:
            assert validate_origin("http://internal.corp.example") is True
        finally:
            get_settings.cache_clear()

    @staticmethod
    def test_http_vercel_rejected() -> None:
        assert validate_origin("http://myapp.vercel.app") is False

    @staticmethod
    def test_ws_scheme_rejected() -> None:
        assert validate_origin("ws://example.com") is False

    @staticmethod
    def test_ftp_scheme_rejected() -> None:
        assert validate_origin("ftp://example.com") is False