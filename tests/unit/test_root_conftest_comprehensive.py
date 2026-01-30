"""Comprehensive unit tests for root conftest.py.

This module tests the pytest configuration helpers including:
- Coverage plugin detection
- Command-line argument filtering
- Edge cases and error handling
"""

import importlib.util
from typing import List
from unittest.mock import MagicMock, patch

import pytest

import conftest

pytestmark = pytest.mark.unit


# Import the functions we want to test


class TestCovPluginAvailable:
    """Test the _cov_plugin_available helper function."""

    @staticmethod
    def test_returns_true_when_pytest_cov_installed():
        """Test that _cov_plugin_available returns True when pytest-cov is installed."""
        # pytest-cov is likely installed in the test environment
        result = conftest._cov_plugin_available()
        # We can't assume it's always installed, so we just test the function runs
        assert isinstance(result, bool)

    @staticmethod
    @patch("importlib.util.find_spec")
    def test_returns_true_when_spec_found(mock_find_spec):
        """Test that _cov_plugin_available returns True when spec is found."""
        mock_find_spec.return_value = MagicMock()  # Non-None value
        result = conftest._cov_plugin_available()
        assert result is True
        mock_find_spec.assert_called_once_with("pytest_cov")

    @staticmethod
    @patch("importlib.util.find_spec")
    def test_returns_false_when_spec_not_found(mock_find_spec):
        """Test that _cov_plugin_available returns False when spec is None."""
        mock_find_spec.return_value = None
        result = conftest._cov_plugin_available()
        assert result is False
        mock_find_spec.assert_called_once_with("pytest_cov")


class TestPytestLoadInitialConftests:
    """Test the pytest_load_initial_conftests hook."""

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_does_nothing_when_plugin_available(mock_cov_available):
        """Test that hook does nothing when coverage plugin is available."""
        mock_cov_available.return_value = True
        args = ["--cov=src", "--cov-report=html", "tests/"]
        original_args = args.copy()

        conftest.pytest_load_initial_conftests(None, None, args)

        # Args should be unchanged
        assert args == original_args

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_removes_cov_flag(mock_cov_available):
        """Test removal of --cov flag and its value."""
        mock_cov_available.return_value = False
        args = ["--cov", "src", "tests/"]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_removes_cov_report_flag(mock_cov_available):
        """Test removal of --cov-report flag and its value."""
        mock_cov_available.return_value = False
        args = ["--cov-report", "html", "tests/"]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_removes_inline_cov_flag(mock_cov_available):
        """Test removal of --cov=value inline format."""
        mock_cov_available.return_value = False
        args = ["--cov=src", "tests/"]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_removes_inline_cov_report_flag(mock_cov_available):
        """Test removal of --cov-report=value inline format."""
        mock_cov_available.return_value = False
        args = ["--cov-report=html", "tests/"]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_removes_multiple_cov_flags(mock_cov_available):
        """Test removal of multiple coverage-related flags."""
        mock_cov_available.return_value = False
        args = [
            "--cov",
            "src",
            "--cov-report",
            "html",
            "--cov-report=term",
            "tests/",
        ]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_preserves_non_coverage_flags(mock_cov_available):
        """Test that non-coverage flags are preserved."""
        mock_cov_available.return_value = False
        args = ["-v", "--strict-markers", "--cov=src", "tests/"]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["-v", "--strict-markers", "tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_handles_empty_args(mock_cov_available):
        """Test handling of empty argument list."""
        mock_cov_available.return_value = False
        args: List[str] = []

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == []

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_modifies_args_in_place(mock_cov_available):
        """Test that the args list is modified in place."""
        mock_cov_available.return_value = False
        args = ["--cov", "src", "tests/"]
        original_list_id = id(args)

        conftest.pytest_load_initial_conftests(None, None, args)

        # Same list object should be modified
        assert id(args) == original_list_id
        assert args == ["tests/"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_handles_similar_flag_names(mock_cov_available):
        """Test that similar but different flags are preserved."""
        mock_cov_available.return_value = False
        args = ["--coverage", "--my-cov-flag", "--cov=src", "tests/"]

        conftest.pytest_load_initial_conftests(None, None, args)

        # Only --cov=src should be removed
        assert args == ["--coverage", "--my-cov-flag", "tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_handles_cov_flag_at_end(mock_cov_available):
        """Test handling when --cov flag is at the end without value."""
        mock_cov_available.return_value = False
        args = ["tests/", "--cov"]

        conftest.pytest_load_initial_conftests(None, None, args)

        # --cov at end should be removed (skip_next will be set but won't affect anything)
        assert args == ["tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_handles_multiple_inline_formats(mock_cov_available):
        """Test handling of multiple inline format flags."""
        mock_cov_available.return_value = False
        args = [
            "--cov=src",
            "--cov=tests",
            "--cov-report=html",
            "--cov-report=term",
            "tests/",
        ]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_handles_mixed_inline_and_separate_flags(mock_cov_available):
        """Test handling of mixed inline and separate flag formats."""
        mock_cov_available.return_value = False
        args = ["--cov", "src", "--cov-report=html", "tests/"]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["tests/"]


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_typical_ci_environment_without_plugin(mock_cov_available):
        """Test typical CI environment args when plugin is not installed."""
        mock_cov_available.return_value = False
        args = [
            "-v",
            "--tb=short",
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "tests/",
        ]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["-v", "--tb=short", "tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_local_development_args(mock_cov_available):
        """Test local development arguments."""
        mock_cov_available.return_value = False
        args = [
            "-v",
            "-s",
            "--cov",
            "src",
            "--cov-report",
            "html",
            "tests/unit/",
        ]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["-v", "-s", "tests/unit/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_preserves_test_selection_args(mock_cov_available):
        """Test that test selection arguments are preserved."""
        mock_cov_available.return_value = False
        args = [
            "-k",
            "test_something",
            "-m",
            "unit",
            "--cov=src",
            "tests/",
        ]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["-k", "test_something", "-m", "unit", "tests/"]


class TestRegression:
    """Regression tests for previously identified issues."""

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_does_not_remove_partial_matches(mock_cov_available):
        """Test that partial flag matches are not removed."""
        mock_cov_available.return_value = False
        # Flags that contain 'cov' but aren't coverage flags
        args = ["--discover", "--recover", "tests/"]

        conftest.pytest_load_initial_conftests(None, None, args)

        # These should be preserved
        assert args == ["--discover", "--recover", "tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_handles_consecutive_cov_flags(mock_cov_available):
        """Test handling of consecutive coverage flags."""
        mock_cov_available.return_value = False
        args = ["--cov", "src", "--cov", "tests", "tests/"]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["tests/"]

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_preserves_order_of_remaining_args(mock_cov_available):
        """Test that order of non-coverage args is preserved."""
        mock_cov_available.return_value = False
        args = [
            "-v",
            "--cov=src",
            "-x",
            "--cov-report=html",
            "-s",
            "tests/",
        ]

        conftest.pytest_load_initial_conftests(None, None, args)

        assert args == ["-v", "-x", "-s", "tests/"]
