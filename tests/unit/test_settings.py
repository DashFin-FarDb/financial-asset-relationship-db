"""Unit tests for centralized settings configuration.

This module tests the Settings class and configuration loading logic
to ensure environment variables are correctly parsed and cached.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest

from src.config.settings import Settings, _parse_bool_env, _parse_csv_env, get_settings, load_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clear_settings_cache():  # NOSONAR - pytest yield fixture
    """Clear the settings cache before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestParseBoolEnv:
    """Test boolean environment variable parsing."""

    def test_parse_bool_env_true_values(self) -> None:
        """Test that accepted truthy values return True."""
        true_values = ["1", "true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON"]
        for value in true_values:
            assert _parse_bool_env(value) is True, f"Expected {value} to parse as True"

    def test_parse_bool_env_false_values(self) -> None:
        """Test that non-truthy values return False."""
        false_values = ["0", "false", "False", "FALSE", "no", "No", "NO", "off", "Off", "OFF", ""]
        for value in false_values:
            assert _parse_bool_env(value) is False, f"Expected {value} to parse as False"

    def test_parse_bool_env_none(self) -> None:
        """Test that None returns False."""
        assert _parse_bool_env(None) is False

    def test_parse_bool_env_whitespace_handling(self) -> None:
        """Test that whitespace is stripped before parsing."""
        assert _parse_bool_env("  true  ") is True
        assert _parse_bool_env("  1  ") is True
        assert _parse_bool_env("  yes  ") is True

    def test_parse_bool_env_random_string(self) -> None:
        """Test that random strings return False."""
        assert _parse_bool_env("random") is False
        assert _parse_bool_env("maybe") is False


class TestParseCsvEnv:
    """Test CSV environment variable parsing."""

    def test_parse_csv_env_single_value(self) -> None:
        """Test parsing single value."""
        result = _parse_csv_env("value1")
        assert result == ["value1"]

    def test_parse_csv_env_multiple_values(self) -> None:
        """Test parsing multiple comma-separated values."""
        result = _parse_csv_env("value1,value2,value3")
        assert result == ["value1", "value2", "value3"]

    def test_parse_csv_env_whitespace_trimming(self) -> None:
        """Test that whitespace around values is trimmed."""
        result = _parse_csv_env("  value1  ,  value2  ,  value3  ")
        assert result == ["value1", "value2", "value3"]

    def test_parse_csv_env_empty_entries_excluded(self) -> None:
        """Test that empty entries are excluded."""
        result = _parse_csv_env("value1,,value2,  ,value3")
        assert result == ["value1", "value2", "value3"]

    def test_parse_csv_env_empty_string(self) -> None:
        """Test that empty string returns empty list."""
        result = _parse_csv_env("")
        assert result == []

    def test_parse_csv_env_only_commas(self) -> None:
        """Test that string with only commas returns empty list."""
        result = _parse_csv_env(",,,")
        assert result == []


# ---------------------------------------------------------------------------
# Settings model tests
# ---------------------------------------------------------------------------


class TestSettingsModel:
    """Test the Settings dataclass."""

    def test_settings_defaults(self) -> None:
        """Test that Settings has correct default values."""
        settings = Settings()
        assert settings.env == "development"
        assert settings.allowed_origins_raw == ""
        assert settings.secret_key is None
        assert settings.admin_username is None
        assert settings.admin_password is None
        assert settings.admin_email is None
        assert settings.admin_full_name is None
        assert settings.admin_disabled is False
        assert settings.graph_cache_path is None
        assert settings.real_data_cache_path is None
        assert settings.use_real_data_fetcher is False
        assert settings.database_url is None
        assert settings.asset_graph_database_url is None

    def test_settings_with_explicit_values(self) -> None:
        """Test Settings initialization with explicit values."""
        settings = Settings(
            env="production",
            allowed_origins_raw="https://example.com,https://example.org",
            secret_key="secret",
            admin_username="admin",
            admin_password="password",
            admin_email="admin@example.com",
            admin_full_name="Admin User",
            admin_disabled=True,
            graph_cache_path="/path/to/cache",
            real_data_cache_path="/path/to/real/cache",
            use_real_data_fetcher=True,
            database_url="sqlite:///runtime.db",
            asset_graph_database_url="postgresql://user:pass@localhost/db",
        )
        assert settings.env == "production"
        assert settings.allowed_origins_raw == "https://example.com,https://example.org"
        assert settings.secret_key == "secret"
        assert settings.admin_username == "admin"
        assert settings.admin_password == "password"
        assert settings.admin_email == "admin@example.com"
        assert settings.admin_full_name == "Admin User"
        assert settings.admin_disabled is True
        assert settings.graph_cache_path == "/path/to/cache"
        assert settings.real_data_cache_path == "/path/to/real/cache"
        assert settings.use_real_data_fetcher is True
        assert settings.database_url == "sqlite:///runtime.db"
        assert settings.asset_graph_database_url == "postgresql://user:pass@localhost/db"

    def test_settings_allowed_origins_property(self) -> None:
        """Test that allowed_origins property correctly parses CSV."""
        settings = Settings(allowed_origins_raw="https://example.com,https://example.org")
        assert settings.allowed_origins == ["https://example.com", "https://example.org"]

    def test_settings_allowed_origins_empty(self) -> None:
        """Test that empty allowed_origins_raw returns empty list."""
        settings = Settings(allowed_origins_raw="")
        assert settings.allowed_origins == []

    def test_settings_immutable(self) -> None:
        """Test that Settings is immutable (frozen)."""
        settings = Settings()
        with pytest.raises((AttributeError, Exception)):
            settings.env = "test"  # type: ignore

    def test_required_secret_key_returns_secret(self) -> None:
        """Test that required_secret_key returns configured secret."""
        settings = Settings(secret_key="configured-secret")
        assert settings.required_secret_key == "configured-secret"

    def test_required_secret_key_raises_when_missing(self) -> None:
        """Test that required_secret_key raises when SECRET_KEY is missing."""
        settings = Settings(secret_key=None)
        with pytest.raises(ValueError, match="SECRET_KEY environment variable"):
            _ = settings.required_secret_key


# ---------------------------------------------------------------------------
# Settings loading tests
# ---------------------------------------------------------------------------


class TestLoadSettings:
    """Test the load_settings function."""

    @patch.dict(os.environ, {}, clear=True)
    def test_load_settings_with_defaults(self) -> None:
        """Test loading settings with no environment variables set."""
        settings = load_settings()
        assert settings.env == "development"
        assert settings.allowed_origins_raw == ""
        assert settings.secret_key is None
        assert settings.admin_username is None
        assert settings.admin_password is None
        assert settings.admin_email is None
        assert settings.admin_full_name is None
        assert settings.admin_disabled is False
        assert settings.graph_cache_path is None
        assert settings.real_data_cache_path is None
        assert settings.use_real_data_fetcher is False
        assert settings.database_url is None
        assert settings.asset_graph_database_url is None

    @patch.dict(
        os.environ,
        {
            "ENV": "production",
            "ALLOWED_ORIGINS": "https://example.com,https://example.org",
            "SECRET_KEY": "test-secret",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "adminpass",
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_FULL_NAME": "Admin User",
            "ADMIN_DISABLED": "true",
            "GRAPH_CACHE_PATH": "/path/to/cache",
            "REAL_DATA_CACHE_PATH": "/path/to/real/cache",
            "USE_REAL_DATA_FETCHER": "true",
            "DATABASE_URL": "sqlite:///env.db",
            "ASSET_GRAPH_DATABASE_URL": "postgresql://localhost/db",
        },
    )
    def test_load_settings_from_environment(self) -> None:
        """Test loading settings from environment variables."""
        settings = load_settings()
        assert settings.env == "production"
        assert settings.allowed_origins_raw == "https://example.com,https://example.org"
        assert settings.secret_key == "test-secret"
        assert settings.admin_username == "admin"
        assert settings.admin_password == "adminpass"
        assert settings.admin_email == "admin@example.com"
        assert settings.admin_full_name == "Admin User"
        assert settings.admin_disabled is True
        assert settings.graph_cache_path == "/path/to/cache"
        assert settings.real_data_cache_path == "/path/to/real/cache"
        assert settings.use_real_data_fetcher is True
        assert settings.database_url == "sqlite:///env.db"
        assert settings.asset_graph_database_url == "postgresql://localhost/db"

    @patch.dict(os.environ, {"ENV": "PRODUCTION"})
    def test_load_settings_env_lowercase(self) -> None:
        """Test that ENV is converted to lowercase."""
        settings = load_settings()
        assert settings.env == "production"

    @patch.dict(os.environ, {"USE_REAL_DATA_FETCHER": "1"})
    def test_load_settings_use_real_data_fetcher_parsing(self) -> None:
        """Test that USE_REAL_DATA_FETCHER is parsed as boolean."""
        settings = load_settings()
        assert settings.use_real_data_fetcher is True

    @patch.dict(os.environ, {"USE_REAL_DATA_FETCHER": "false"})
    def test_load_settings_use_real_data_fetcher_false(self) -> None:
        """Test that USE_REAL_DATA_FETCHER false value is parsed correctly."""
        settings = load_settings()
        assert settings.use_real_data_fetcher is False


# ---------------------------------------------------------------------------
# Settings caching tests
# ---------------------------------------------------------------------------


class TestGetSettings:
    """Test the get_settings cached function."""

    @patch.dict(os.environ, {"ENV": "development"}, clear=True)
    def test_get_settings_returns_settings(self) -> None:
        """Test that get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    @patch.dict(os.environ, {"ENV": "test"}, clear=True)
    def test_get_settings_caching(self) -> None:
        """Test that get_settings caches the result."""
        settings1 = get_settings()
        settings2 = get_settings()
        # Should return the same instance due to caching
        assert settings1 is settings2

    @patch.dict(os.environ, {"ENV": "development"}, clear=True)
    def test_get_settings_cache_clear(self, clear_settings_cache: Any) -> None:
        """Test that cache can be cleared."""
        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()
        # After cache clear, should be different instances
        assert settings1 is not settings2


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestSettingsIntegration:
    """Integration tests for Settings usage patterns."""

    @patch.dict(
        os.environ,
        {
            "ENV": "production",
            "ALLOWED_ORIGINS": "https://app.example.com,https://api.example.com",
        },
    )
    def test_settings_cors_integration(self) -> None:
        """Test typical CORS configuration pattern."""
        settings = get_settings()
        assert settings.env == "production"
        assert len(settings.allowed_origins) == 2
        assert set(settings.allowed_origins) == {
            "https://app.example.com",
            "https://api.example.com",
        }

    @patch.dict(
        os.environ,
        {
            "GRAPH_CACHE_PATH": "/var/cache/graph.json",
            "USE_REAL_DATA_FETCHER": "yes",
        },
    )
    def test_settings_graph_initialization_integration(self) -> None:
        """Test typical graph initialization pattern."""
        settings = get_settings()
        assert settings.graph_cache_path == "/var/cache/graph.json"
        assert settings.use_real_data_fetcher is True

    @patch.dict(
        os.environ,
        {
            "ASSET_GRAPH_DATABASE_URL": "postgresql://user:pass@localhost:5432/assets",
        },
    )
    def test_settings_database_integration(self) -> None:
        """Test typical database configuration pattern."""
        settings = get_settings()
        assert settings.asset_graph_database_url == "postgresql://user:pass@localhost:5432/assets"


# ---------------------------------------------------------------------------
# Edge cases and error handling
# ---------------------------------------------------------------------------


class TestSettingsEdgeCases:
    """Test edge cases in settings handling."""

    @patch.dict(os.environ, {"ENV": "  Development  "})
    def test_env_with_whitespace(self) -> None:
        """Test that ENV with whitespace is handled (via .strip().lower())."""
        settings = load_settings()
        # .strip().lower() is called, so whitespace is removed
        assert settings.env == "development"

    @patch.dict(os.environ, {"ALLOWED_ORIGINS": "  ,  ,  "})
    def test_allowed_origins_only_whitespace(self) -> None:
        """Test ALLOWED_ORIGINS with only whitespace and commas."""
        settings = load_settings()
        assert settings.allowed_origins == []

    @patch.dict(os.environ, {"USE_REAL_DATA_FETCHER": "TrUe"})
    def test_use_real_data_fetcher_mixed_case(self) -> None:
        """Test USE_REAL_DATA_FETCHER with mixed case."""
        settings = load_settings()
        assert settings.use_real_data_fetcher is True

    @patch.dict(os.environ, {"ADMIN_DISABLED": " true "})
    def test_load_settings_admin_disabled_normalizes_whitespace(self) -> None:
        """Test that ADMIN_DISABLED whitespace is normalized through settings parsing."""
        settings = load_settings()
        assert settings.admin_disabled is True

    @patch.dict(os.environ, {"ADMIN_DISABLED": "false"})
    def test_load_settings_admin_disabled_false(self) -> None:
        """Test that load_settings returns False for ADMIN_DISABLED=false."""
        settings = load_settings()
        assert settings.admin_disabled is False

    @patch.dict(os.environ, {"ADMIN_DISABLED": "maybe"})
    def test_load_settings_admin_disabled_unknown_value_is_false(self) -> None:
        """Test that unknown ADMIN_DISABLED values load as False."""
        settings = load_settings()
        assert settings.admin_disabled is False

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_optional_vars(self) -> None:
        """Test that missing optional environment variables use defaults."""
        settings = load_settings()
        assert settings.graph_cache_path is None
        assert settings.real_data_cache_path is None
        assert settings.database_url is None
        assert settings.asset_graph_database_url is None


# ---------------------------------------------------------------------------
# Settings validation tests
# ---------------------------------------------------------------------------


class TestSettingsValidation:
    """Test Settings validation via Pydantic."""

    def test_settings_accepts_valid_types(self) -> None:
        """Test that Settings accepts valid types."""
        settings = Settings(
            env="staging",
            allowed_origins_raw="https://example.com",
            graph_cache_path="/path",
            real_data_cache_path="/path2",
            use_real_data_fetcher=True,
            asset_graph_database_url="sqlite:///test.db",
        )
        assert settings.env == "staging"

    def test_settings_field_types(self) -> None:
        """Test that Settings fields have correct types."""
        settings = Settings()
        assert isinstance(settings.env, str)
        assert isinstance(settings.allowed_origins_raw, str)
        assert isinstance(settings.use_real_data_fetcher, bool)
        assert settings.graph_cache_path is None or isinstance(settings.graph_cache_path, str)
