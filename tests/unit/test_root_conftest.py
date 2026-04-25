"""Unit tests for the root conftest.py pytest configuration module.

This module tests the pytest configuration helpers that manage coverage-related
command-line arguments. The root conftest.py strips coverage flags when pytest-cov
is unavailable, allowing tests to run without the plugin installed.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestCovPluginAvailable:
    """Test cases for the _cov_plugin_available helper function."""

    @staticmethod
    def test_cov_plugin_available_when_installed():
        """Test that _cov_plugin_available returns True when pytest-cov is installed."""
        # Import the function from root conftest
        import conftest

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = MagicMock()  # Non-None means found
            result = conftest._cov_plugin_available()

            assert result is True
            mock_find_spec.assert_called_once_with("pytest_cov")

    @staticmethod
    def test_cov_plugin_not_available_when_not_installed():
        """Test that _cov_plugin_available returns False when pytest-cov is not installed."""
        import conftest

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None  # None means not found
            result = conftest._cov_plugin_available()

            assert result is False
            mock_find_spec.assert_called_once_with("pytest_cov")

    @staticmethod
    def test_cov_plugin_available_uses_importlib():
        """Test that _cov_plugin_available uses importlib.util.find_spec."""
        import conftest

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None
            conftest._cov_plugin_available()

            # Verify the correct module name is checked
            assert mock_find_spec.call_count == 1
            args = mock_find_spec.call_args[0]
            assert args[0] == "pytest_cov"


@pytest.mark.unit
@pytest.mark.unit
class TestPytestAddoption:
    """Test the pytest_addoption hook and fallback coverage options."""

    @staticmethod
    def test_registers_fallback_options_when_plugin_unavailable():
        """Test that fallback options are registered when pytest-cov is unavailable."""
        import conftest

        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_parser.getgroup.return_value = mock_group

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_addoption(mock_parser)

        # Verify getgroup was called
        mock_parser.getgroup.assert_called_once_with("cov")

        # Verify addoption was called multiple times for coverage flags
        assert mock_group.addoption.call_count >= 8

    @staticmethod
    def test_skips_registration_when_plugin_available():
        """Test that fallback options are not registered when pytest-cov is available."""
        import conftest

        mock_parser = MagicMock()

        with patch.object(conftest, "_cov_plugin_available", return_value=True):
            conftest.pytest_addoption(mock_parser)

        # Verify getgroup was not called
        mock_parser.getgroup.assert_not_called()


@pytest.mark.unit
class TestDocumentationAndCodeQuality:
    """Tests for code documentation and quality standards."""

    @staticmethod
    def test_conftest_has_module_docstring():
        """Verify that conftest.py has a module-level docstring."""
        import conftest

        assert conftest.__doc__ is not None
        assert len(conftest.__doc__) > 50

    @staticmethod
    def test_functions_have_docstrings():
        """Verify that public functions have docstrings."""
        import conftest

        assert conftest._cov_plugin_available.__doc__ is not None
        assert conftest.pytest_addoption.__doc__ is not None


# Note: The following test classes were removed as they tested pytest_load_initial_conftests,
# which was never actually called (pytest doesn't invoke this hook for conftest files):
# - TestPytestLoadInitialConftests
# - TestCoverageFilteringEdgeCases
# - TestRealWorldScenarios
# - TestConftestRobustness
# - TestConftestPerformance
# - TestConftestRegression
#
# The new approach registers fallback coverage options via pytest_addoption instead,
# which doesn't require argument stripping. See TestPytestAddoption above for current tests.
