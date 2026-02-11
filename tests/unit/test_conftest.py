# ruff: noqa: S101
"""Unit tests for conftest.py pytest configuration helpers.

This module contains comprehensive unit tests for the conftest module including:
- Testing pytest_load_initial_conftests function behavior
- Testing coverage argument filtering with pytest-cov available
- Testing coverage argument filtering without pytest-cov
- Testing various coverage option formats (--cov, --cov=, --cov-report, etc.)
- Testing edge cases and argument preservation

Note: This test file uses assert statements which is the standard and recommended
approach for pytest. The S101 rule is suppressed because tests are not run with
Python optimization flags that would remove assert statements.
"""

import sys
from typing import List
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestConftestHelpers:
    """Test cases for conftest.py pytest configuration helpers."""

    @staticmethod
    def test_pytest_load_initial_conftests_with_cov_plugin_available():
        """Test that coverage args are preserved when pytest-cov is available."""
        # Import after mocking to ensure the mock is in place
        with patch("conftest.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = MagicMock()  # Simulate plugin found

            # Import the function under test
            from conftest import pytest_load_initial_conftests

            args = ["tests/", "--cov=src", "--cov-report=html"]
            original_args = args.copy()

            pytest_load_initial_conftests(args)

            # Args should be unchanged when plugin is available
            assert args == original_args

    @staticmethod
    def test_pytest_load_initial_conftests_without_cov_plugin():
        """Test that coverage args are removed when pytest-cov is not available."""
        with patch("conftest.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None  # Simulate plugin not found

            from conftest import pytest_load_initial_conftests

            args = ["tests/", "--cov=src", "--cov-report=html", "-v"]
            pytest_load_initial_conftests(args)

            # Coverage args should be removed, other args preserved
            assert "--cov=src" not in args
            assert "--cov-report=html" not in args
            assert "tests/" in args
            assert "-v" in args

    @staticmethod
    def test_pytest_load_initial_conftests_removes_standalone_cov_arg():
        """Test removal of standalone --cov argument with separate value."""
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args = ["tests/", "--cov", "src", "--verbose"]
            pytest_load_initial_conftests(args)

            # Both --cov and its value should be removed
            assert "--cov" not in args
            assert "src" not in args  # The value following --cov
            assert "tests/" in args
            assert "--verbose" in args

    @staticmethod
    def test_pytest_load_initial_conftests_removes_standalone_cov_report():
        """Test removal of standalone --cov-report argument with separate value."""
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args = ["--cov-report", "term-missing", "tests/"]
            pytest_load_initial_conftests(args)

            # Both --cov-report and its value should be removed
            assert "--cov-report" not in args
            assert "term-missing" not in args
            assert "tests/" in args

    @staticmethod
    def test_pytest_load_initial_conftests_handles_inline_cov_args():
        """Test handling of inline --cov= and --cov-report= arguments."""
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args = [
                "--cov=src",
                "--cov-report=html",
                "--cov-report=term",
                "tests/",
            ]
            pytest_load_initial_conftests(args)

            # All inline coverage args should be removed
            assert not any(arg.startswith("--cov") for arg in args)
            assert "tests/" in args

    @staticmethod
    def test_pytest_load_initial_conftests_preserves_non_cov_args():
        """Test that non-coverage arguments are preserved."""
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args = [
                "tests/",
                "-v",
                "--tb=short",
                "--cov=src",
                "-s",
                "--cov-report=html",
                "--maxfail=5",
            ]
            pytest_load_initial_conftests(args)

            # Non-coverage args should be preserved
            assert "tests/" in args
            assert "-v" in args
            assert "--tb=short" in args
            assert "-s" in args
            assert "--maxfail=5" in args

            # Coverage args should be removed
            assert "--cov=src" not in args
            assert "--cov-report=html" not in args

    @staticmethod
    def test_pytest_load_initial_conftests_empty_args():
        """Test handling of empty argument list."""
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args: List[str] = []
            pytest_load_initial_conftests(args)

            # Should not raise error and list should remain empty
            assert args == []

    @staticmethod
    def test_pytest_load_initial_conftests_only_cov_args():
        """Test handling when only coverage arguments are present."""
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args = ["--cov=src", "--cov-report=html"]
            pytest_load_initial_conftests(args)

            # All args should be removed
            assert args == []

    @staticmethod
    def test_pytest_load_initial_conftests_modifies_in_place():
        """Test that the function modifies the argument list in place."""
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            original_list = ["--cov=src", "tests/"]
            args = original_list

            pytest_load_initial_conftests(args)

            # The same list object should be modified
            assert args is original_list
            assert args == ["tests/"]

    @staticmethod
    def test_pytest_load_initial_conftests_consecutive_skip_args():
        """
        Ensure consecutive coverage-related arguments and their values are removed when pytest-cov is unavailable.

        Verifies the provided `args` list is modified in place to strip `--cov`, `--cov-report` and their following values, preserving non-coverage arguments.
        """
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args = [
                "--cov",
                "src",
                "--cov-report",
                "html",
                "tests/",
            ]
            pytest_load_initial_conftests(args)

            # All coverage args and their values should be removed
            assert args == ["tests/"]

    @staticmethod
    def test_pytest_load_initial_conftests_mixed_formats():
        """Test handling of mixed inline and standalone coverage arguments."""
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args = [
                "--cov",
                "src",
                "--cov-report=html",
                "tests/",
                "--cov=api",
            ]
            pytest_load_initial_conftests(args)

            # All coverage args should be removed regardless of format
            assert args == ["tests/"]

    @staticmethod
    def test_cov_plugin_available_helper():
        """Test the _cov_plugin_available helper function."""
        with patch("conftest.importlib.util.find_spec") as mock_find_spec:
            from conftest import _cov_plugin_available

            # Test when plugin is available
            mock_find_spec.return_value = MagicMock()
            assert _cov_plugin_available() is True

            # Test when plugin is not available
            mock_find_spec.return_value = None
            assert _cov_plugin_available() is False

    @staticmethod
    def test_pytest_load_initial_conftests_args_with_equals_in_value():
        """
        Ensures pytest_load_initial_conftests removes pytest-cov related arguments whose values contain equals signs while preserving other arguments.

        Verifies that an inline `--cov-report=...` argument with a value containing `=` is removed from the provided args list and that unrelated args remain unchanged.
        """
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args = [
                "tests/",
                "--cov-report=html:dir=coverage_html",
                "-v",
            ]
            pytest_load_initial_conftests(args)

            # Coverage arg with complex value should be removed
            assert not any("--cov-report" in arg for arg in args)
            assert "tests/" in args
            assert "-v" in args

    @staticmethod
    def test_pytest_load_initial_conftests_similar_arg_names():
        """Test that only coverage args are removed, not similar named args."""
        with patch("conftest.importlib.util.find_spec", return_value=None):
            from conftest import pytest_load_initial_conftests

            args = [
                "tests/",
                "--coverage-data",  # Not a pytest-cov arg
                "--cov=src",
                "--discover",  # Contains 'cov' but not a coverage arg
            ]
            pytest_load_initial_conftests(args)

            # Only actual coverage args should be removed
            assert "--cov=src" not in args
            assert "--coverage-data" in args  # Should be preserved
            assert "--discover" in args  # Should be preserved
            assert "tests/" in args

    @staticmethod
    def test_pytest_load_initial_conftests_no_modification_when_plugin_present():
        """Test that no modification occurs when pytest-cov plugin is present."""
        with patch("conftest.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = MagicMock()

            from conftest import pytest_load_initial_conftests

            original_args = [
                "tests/",
                "--cov=src",
                "--cov-report=html",
                "--cov",
                "api",
            ]
            args = original_args.copy()

            pytest_load_initial_conftests(args)

            # Args should remain completely unchanged
            assert args == original_args

    @staticmethod
    def test_conftest_module_docstring_exists():
        """Test that conftest module has proper documentation."""
        import conftest

        assert conftest.__doc__ is not None
        assert "pytest configuration helpers" in conftest.__doc__.lower()

    @staticmethod
    def test_pytest_load_initial_conftests_function_signature():
        """
        Verify that `pytest_load_initial_conftests` is callable and has a single parameter named `args`.
        """
        from conftest import pytest_load_initial_conftests

        # Check function exists and is callable
        assert callable(pytest_load_initial_conftests)

        # Check function accepts a list argument
        import inspect

        sig = inspect.signature(pytest_load_initial_conftests)
        assert len(sig.parameters) == 1
        param = list(sig.parameters.values())[0]
        assert param.name == "args"
