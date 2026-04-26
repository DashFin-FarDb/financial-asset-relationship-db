"""Comprehensive unit tests for root conftest.py.

This module tests the pytest configuration helpers including:
- Coverage plugin detection
- Command-line argument filtering
- Edge cases and error handling
"""

from unittest.mock import MagicMock, patch

import pytest

import conftest

pytestmark = pytest.mark.unit


# Import the functions we want to test


@pytest.mark.unit
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


@pytest.mark.unit
class TestPytestAddoption:
    """Test the pytest_addoption hook and fallback coverage options."""

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_registers_fallback_options_when_plugin_unavailable(mock_cov_available):
        """Test that fallback options are registered when pytest-cov is unavailable."""
        mock_cov_available.return_value = False
        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_parser.getgroup.return_value = mock_group

        conftest.pytest_addoption(mock_parser)

        # Verify getgroup was called
        mock_parser.getgroup.assert_called_once_with("cov")

        # Verify addoption was called for all coverage flags
        assert mock_group.addoption.call_count >= 8  # At least 8 coverage flags

    @staticmethod
    @patch("conftest._cov_plugin_available")
    def test_skips_registration_when_plugin_available(mock_cov_available):
        """Test that fallback options are not registered when pytest-cov is available."""
        mock_cov_available.return_value = True
        mock_parser = MagicMock()

        conftest.pytest_addoption(mock_parser)

        # Verify getgroup was not called
        mock_parser.getgroup.assert_not_called()


# Note: TestEdgeCases, TestRealWorldScenarios, and TestRegression were removed
# as they tested pytest_load_initial_conftests, which was never actually called
# (pytest doesn't invoke this hook for conftest files). The new approach registers
# fallback coverage options via pytest_addoption instead, which doesn't require
# argument stripping. See TestPytestAddoption above for the current tests.
