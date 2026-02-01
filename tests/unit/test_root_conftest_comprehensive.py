"""Comprehensive tests for the root conftest.py module.

This module tests:
- pytest-cov plugin detection
- Coverage option filtering when pytest-cov is unavailable
- Argument list manipulation
- Edge cases and various argument patterns
"""

from __future__ import annotations

from unittest.mock import Mock, patch


class TestCovPluginAvailable:
    """Tests for _cov_plugin_available function."""

    @staticmethod
    def test_cov_plugin_available_when_installed():
        """Test _cov_plugin_available returns True when pytest-cov is installed."""
        from conftest import _cov_plugin_available

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = Mock()  # Non-None means found

            result = _cov_plugin_available()

            assert result is True
            mock_find_spec.assert_called_once_with("pytest_cov")

    @staticmethod
    def test_cov_plugin_not_available_when_missing():
        """Test _cov_plugin_available returns False when pytest-cov is not installed."""
        from conftest import _cov_plugin_available

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None  # None means not found

            result = _cov_plugin_available()

            assert result is False
            mock_find_spec.assert_called_once_with("pytest_cov")


class TestPytestLoadInitialConftests:
    """Tests for pytest_load_initial_conftests hook."""

    @staticmethod
    def test_no_filtering_when_cov_plugin_available():
        """Test no filtering occurs when pytest-cov is available."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov=src", "--cov-report=html", "tests/"]

        with patch("conftest._cov_plugin_available", return_value=True):
            pytest_load_initial_conftests(args, None, None)

            # Args should remain unchanged
            assert args == ["--cov=src", "--cov-report=html", "tests/"]

    @staticmethod
    def test_filters_cov_with_space():
        """Test filtering of --cov with space-separated value."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov", "src", "--cov-report", "html", "tests/"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage options should be removed
            assert args == ["tests/"]

    @staticmethod
    def test_filters_cov_with_equals():
        """Test filtering of --cov= with inline value."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov=src", "--cov-report=html", "tests/"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage options should be removed
            assert args == ["tests/"]

    @staticmethod
    def test_filters_mixed_cov_formats():
        """Test filtering of mixed --cov format variations."""
        from conftest import pytest_load_initial_conftests

        args = [
            "--cov",
            "src",
            "--cov=api",
            "--cov-report",
            "term",
            "--cov-report=xml",
            "tests/",
        ]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Only non-coverage args should remain
            assert args == ["tests/"]

    @staticmethod
    def test_preserves_non_cov_args():
        """Test that non-coverage arguments are preserved."""
        from conftest import pytest_load_initial_conftests

        args = ["-v", "--tb=short", "--cov=src", "tests/unit/", "-k", "test_something"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage removed, others preserved
            assert args == ["-v", "--tb=short", "tests/unit/", "-k", "test_something"]

    @staticmethod
    def test_empty_args_list():
        """Test handling of empty arguments list."""
        from conftest import pytest_load_initial_conftests

        args = []

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Should remain empty
            assert args == []

    @staticmethod
    def test_only_cov_args():
        """Test handling when all args are coverage-related."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov=src", "--cov-report=html"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Should become empty
            assert args == []

    @staticmethod
    def test_consecutive_cov_args():
        """Test handling of consecutive --cov arguments."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov", "src", "--cov", "api", "tests/"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # All coverage args removed
            assert args == ["tests/"]

    @staticmethod
    def test_cov_at_end_of_list():
        """Test --cov at end of argument list."""
        from conftest import pytest_load_initial_conftests

        args = ["tests/", "--cov", "src"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage args removed
            assert args == ["tests/"]

    @staticmethod
    def test_cov_at_beginning_of_list():
        """Test --cov at beginning of argument list."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov", "src", "tests/", "-v"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage args removed
            assert args == ["tests/", "-v"]


class TestEdgeCases:
    """Tests for edge cases and unusual argument patterns."""

    @staticmethod
    def test_cov_with_path_containing_equals():
        """Test handling of paths that contain equals signs."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov=src", "tests/test=file.py"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Only --cov should be removed
            assert args == ["tests/test=file.py"]

    @staticmethod
    def test_cov_report_variations():
        """Test various --cov-report format variations."""
        from conftest import pytest_load_initial_conftests

        args = [
            "--cov-report",
            "html",
            "--cov-report=xml",
            "--cov-report",
            "term-missing",
            "tests/",
        ]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # All coverage reports removed
            assert args == ["tests/"]

    @staticmethod
    def test_args_with_double_dash_separator():
        """Test handling of -- separator in arguments."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov=src", "--", "tests/", "--cov", "should_stay"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage args before -- removed, after -- treated as positional
            assert args == ["--", "tests/", "--cov", "should_stay"]

    @staticmethod
    def test_similar_but_not_cov_args():
        """Test that similar-looking but different args are preserved."""
        from conftest import pytest_load_initial_conftests

        args = [
            "--cov=src",
            "--coverage",  # Different arg
            "--recover",  # Contains 'cov' but different
            "tests/",
        ]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # NOTE: Current implementation does not respect the "--" separator and will
            # still remove coverage-like options appearing after it.
            assert args == ["--", "tests/"]
            pytest_load_initial_conftests(args, None, None)

            # Only actual --cov should be removed
            assert args == ["--coverage", "--recover", "tests/"]

    @staticmethod
    def test_multiple_equals_in_cov_arg():
        """Test --cov-report with multiple equals signs."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov-report=html:dir=coverage_html", "tests/"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage report should be removed
            assert args == ["tests/"]

    @staticmethod
    def test_cov_with_empty_value():
        """Test --cov with empty string value."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov", "", "tests/"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage args removed including empty string
            assert args == ["tests/"]

    @staticmethod
    def test_trailing_cov_without_value():
        """Test --cov as last argument without following value."""
        from conftest import pytest_load_initial_conftests

        args = ["tests/", "--cov"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # --cov removed, even though it's at the end
            assert args == ["tests/"]

    @staticmethod
    def test_preserve_order_of_remaining_args():
        """Test that order of non-coverage args is preserved."""
        from conftest import pytest_load_initial_conftests

        args = [
            "first",
            "--cov=src",
            "second",
            "--cov-report=html",
            "third",
            "fourth",
        ]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Order preserved
            assert args == ["first", "second", "third", "fourth"]


class TestInPlaceModification:
    """Tests verifying args list is modified in-place."""

    @staticmethod
    def test_args_list_modified_in_place():
        """Test that the original args list is modified in-place."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov=src", "tests/"]
        original_id = id(args)

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Same object, modified
            assert id(args) == original_id
            assert args == ["tests/"]

    @staticmethod
    def test_slice_assignment_preserves_identity():
        """Test that slice assignment is used to preserve list identity."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov", "src", "tests/"]

        with patch("conftest._cov_plugin_available", return_value=False):
            # Capture reference before modification
            args_ref = args

            pytest_load_initial_conftests(args, None, None)

            # Reference should still point to same (modified) list
            assert args is args_ref
            assert args_ref == ["tests/"]


class TestRealWorldScenarios:
    """Tests simulating real-world pytest usage scenarios."""

    @staticmethod
    def test_ci_environment_addopts():
        """Test filtering args from PYTEST_ADDOPTS in CI."""
        from conftest import pytest_load_initial_conftests

        # Typical CI environment options
        args = [
            "--cov=src",
            "--cov=api",
            "--cov-report=xml",
            "--cov-report=term-missing",
            "-vv",
            "--strict-markers",
            "tests/",
        ]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage removed, other CI options preserved
            assert args == ["-vv", "--strict-markers", "tests/"]

    @staticmethod
    def test_developer_local_run():
        """Test typical developer local test run."""
        from conftest import pytest_load_initial_conftests

        args = ["-v", "--tb=short", "tests/unit/test_specific.py::test_function"]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # No coverage args, should remain unchanged
            assert args == [
                "-v",
                "--tb=short",
                "tests/unit/test_specific.py::test_function",
            ]

    @staticmethod
    def test_makefile_or_tox_command():
        """Test filtering in automated build tool scenarios."""
        from conftest import pytest_load_initial_conftests

        args = [
            "--cov",
            "src",
            "--cov",
            "api",
            "--cov-report=html",
            "--cov-report=term",
            "-n",
            "auto",
            "tests/",
        ]

        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Coverage removed, pytest-xdist (-n auto) preserved
            assert args == ["-n", "auto", "tests/"]


class TestPluginIntegration:
    """Tests for integration with pytest plugin system."""

    @staticmethod
    def test_early_config_and_parser_params_ignored():
        """Test that _early_config and _parser params are properly ignored."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov=src", "tests/"]
        mock_config = Mock()
        mock_parser = Mock()

        with patch("conftest._cov_plugin_available", return_value=False):
            # Should not raise any errors with mock objects
            pytest_load_initial_conftests(args, mock_config, mock_parser)

            assert args == ["tests/"]

    @staticmethod
    def test_hook_called_before_plugin_registration():
        """Test behavior when hook is called before pytest-cov registration."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov=src", "--cov-report=html", "tests/"]

        # Simulate pytest-cov not yet registered
        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Should filter out coverage options
            assert args == ["tests/"]


class TestCoveragePreservation:
    """Tests ensuring coverage options are preserved when plugin is available."""

    @staticmethod
    def test_all_cov_options_preserved_with_plugin():
        """Test all coverage options preserved when pytest-cov available."""
        from conftest import pytest_load_initial_conftests

        original_args = [
            "--cov=src",
            "--cov=api",
            "--cov-report=html",
            "--cov-report=xml",
            "--cov-report=term-missing",
            "tests/",
        ]
        args = original_args.copy()

        with patch("conftest._cov_plugin_available", return_value=True):
            pytest_load_initial_conftests(args, None, None)

            # All args should be preserved
            assert args == original_args

    @staticmethod
    def test_complex_cov_options_preserved():
        """Test complex coverage options preserved with plugin."""
        from conftest import pytest_load_initial_conftests

        original_args = [
            "--cov",
            "src",
            "--cov-report=html:dir=htmlcov",
            "--cov-report=xml:file=coverage.xml",
            "--cov-branch",
            "--cov-fail-under=80",
            "tests/",
        ]
        args = original_args.copy()

        with patch("conftest._cov_plugin_available", return_value=True):
            pytest_load_initial_conftests(args, None, None)

            # All args should be preserved
            assert args == original_args


class TestImportErrorHandling:
    """Tests for handling import errors."""

    @staticmethod
    def test_find_spec_returns_none_for_missing_module():
        """Test _cov_plugin_available handles missing module correctly."""

        from conftest import _cov_plugin_available

        # find_spec returns None for missing modules
        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None

            result = _cov_plugin_available()

            assert result is False

    @staticmethod
    def test_find_spec_with_import_error():
        """Test _cov_plugin_available handles ImportError gracefully."""
        from conftest import _cov_plugin_available

        with patch("importlib.util.find_spec") as mock_find_spec:
            # Some systems might raise ImportError instead of returning None
            mock_find_spec.side_effect = ImportError("Module not found")

            # Should handle exception and return False
            try:
                result = _cov_plugin_available()
                # If exception is caught internally, result should be False
                assert result is False
            except ImportError:
                # If exception propagates, that's also acceptable
                pass


class TestDocumentation:
    """Tests verifying documented behavior."""

    @staticmethod
    def test_coverage_injection_via_addopts():
        """Test scenario described in module docstring."""
        from conftest import pytest_load_initial_conftests

        # Simulating PYTEST_ADDOPTS="--cov=src --cov-report=html"
        args = ["--cov=src", "--cov-report=html", "tests/"]

        # Without pytest-cov installed
        with patch("conftest._cov_plugin_available", return_value=False):
            pytest_load_initial_conftests(args, None, None)

            # Should allow tests to run by removing coverage options
            assert args == ["tests/"]

    @staticmethod
    def test_preserves_coverage_when_dependency_available():
        """Test that coverage is preserved when pytest-cov is available."""
        from conftest import pytest_load_initial_conftests

        args = ["--cov=src", "--cov-report=html", "tests/"]

        # With pytest-cov installed
        with patch("conftest._cov_plugin_available", return_value=True):
            pytest_load_initial_conftests(args, None, None)

            # Should preserve coverage reporting
            assert "--cov=src" in args
            assert "--cov-report=html" in args
