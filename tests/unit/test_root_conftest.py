"""Unit tests for the root conftest.py pytest configuration module.

This module tests the pytest configuration helpers that manage coverage-related
command-line arguments. The root conftest.py strips coverage flags when pytest-cov
is unavailable, allowing tests to run without the plugin installed.
"""

from unittest.mock import MagicMock, patch


class TestCovPluginAvailable:
    """Test cases for the _cov_plugin_available helper function."""

    def test_cov_plugin_available_when_installed(self):
        """Test that _cov_plugin_available returns True when pytest-cov is installed."""
        # Import the function from root conftest
        import conftest

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = MagicMock()  # Non-None means found
            result = conftest._cov_plugin_available()

            assert result is True
            mock_find_spec.assert_called_once_with("pytest_cov")

    def test_cov_plugin_not_available_when_not_installed(self):
        """Test that _cov_plugin_available returns False when pytest-cov is not installed."""
        import conftest

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None  # None means not found
            result = conftest._cov_plugin_available()

            assert result is False
            mock_find_spec.assert_called_once_with("pytest_cov")

    def test_cov_plugin_available_uses_importlib(self):
        """Test that _cov_plugin_available uses importlib.util.find_spec."""
        import conftest

        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None
            conftest._cov_plugin_available()

            # Verify the correct module name is checked
            assert mock_find_spec.call_count == 1
            args = mock_find_spec.call_args[0]
            assert args[0] == "pytest_cov"


class TestPytestLoadInitialConftests:
    """Test cases for pytest_load_initial_conftests hook."""

    def test_does_nothing_when_cov_plugin_available(self):
        """Test that no filtering occurs when pytest-cov is available."""
        import conftest

        original_args = ["--verbose", "--cov=src", "--cov-report=html", "tests/"]
        args = original_args.copy()

        with patch.object(conftest, "_cov_plugin_available", return_value=True):
            conftest.pytest_load_initial_conftests(args, None, None)

            # Args should be unchanged
            assert args == original_args

    def test_removes_cov_flag_with_value(self):
        """Test that --cov with separate value is removed."""
        import conftest

        args = ["--verbose", "--cov", "src", "--strict-markers", "tests/"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # Both --cov and its value should be removed
            assert args == ["--verbose", "--strict-markers", "tests/"]

    def test_removes_cov_report_flag_with_value(self):
        """Test that --cov-report with separate value is removed."""
        import conftest

        args = ["--verbose", "--cov-report", "html", "--strict-markers", "tests/"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # Both --cov-report and its value should be removed
            assert args == ["--verbose", "--strict-markers", "tests/"]

    def test_removes_cov_flag_with_equals_syntax(self):
        """Test that --cov=value is removed."""
        import conftest

        args = ["--verbose", "--cov=src", "--strict-markers", "tests/"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            assert args == ["--verbose", "--strict-markers", "tests/"]

    def test_removes_cov_report_flag_with_equals_syntax(self):
        """Test that --cov-report=type is removed."""
        import conftest

        args = ["--verbose", "--cov-report=html", "--strict-markers", "tests/"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            assert args == ["--verbose", "--strict-markers", "tests/"]

    def test_removes_multiple_coverage_flags(self):
        """Test that multiple coverage flags are all removed."""
        import conftest

        args = [
            "--verbose",
            "--cov=src",
            "--cov-report=html",
            "--cov-report",
            "term-missing",
            "--cov",
            "api",
            "--strict-markers",
        ]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # All coverage flags should be removed
            assert args == ["--verbose", "--strict-markers"]

    def test_preserves_other_flags(self):
        """Test that non-coverage flags are preserved."""
        import conftest

        args = ["-v", "--strict-markers", "--tb=short", "-x", "--maxfail=2", "tests/"]
        original = args.copy()

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # All flags should be preserved
            assert args == original

    def test_handles_empty_args_list(self):
        """Test that empty args list is handled correctly."""
        import conftest

        args: list[str] = []

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            assert args == []

    def test_handles_args_with_only_coverage_flags(self):
        """Test that args with only coverage flags become empty."""
        import conftest

        args = ["--cov=src", "--cov-report=html"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            assert args == []

    def test_modifies_args_in_place(self):
        """Test that the function modifies the args list in place."""
        import conftest

        args = ["--verbose", "--cov=src", "tests/"]
        original_id = id(args)

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # Same list object should be modified
            assert id(args) == original_id
            assert args == ["--verbose", "tests/"]


class TestCoverageFilteringEdgeCases:
    """Test edge cases and boundary conditions for coverage flag filtering."""

    def test_handles_cov_flag_at_end_with_no_value(self):
        """Test that --cov at the end without value doesn't cause index error."""
        import conftest

        args = ["--verbose", "--cov"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # --cov should be removed
            assert args == ["--verbose"]

    def test_handles_cov_report_at_end_with_no_value(self):
        """Test that --cov-report at the end without value doesn't cause index error."""
        import conftest

        args = ["--verbose", "--cov-report"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # --cov-report should be removed
            assert args == ["--verbose"]

    def test_handles_consecutive_coverage_flags(self):
        """Test handling of consecutive coverage flags."""
        import conftest

        args = ["--cov", "src", "--cov-report", "html", "--cov-report", "xml"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            assert args == []

    def test_preserves_similar_but_different_flags(self):
        """Test that flags similar to coverage flags are not removed."""
        import conftest

        args = ["--coverage", "--discover", "--report", "tests/"]  # Different flag  # Different flag  # Different flag
        original = args.copy()

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # These should all be preserved
            assert args == original

    def test_handles_cov_in_test_path(self):
        """Test that 'cov' in test paths doesn't cause issues."""
        import conftest

        args = ["tests/coverage_tests/", "--verbose"]
        original = args.copy()

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # Path should be preserved
            assert args == original

    def test_handles_mixed_equals_and_space_syntax(self):
        """Test handling of mixed --flag=value and --flag value syntax."""
        import conftest

        args = ["--cov=src", "--cov", "api", "--cov-report=html", "--cov-report", "term", "--verbose"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            assert args == ["--verbose"]

    def test_handles_cov_flags_with_complex_values(self):
        """Test handling of coverage flags with complex path values."""
        import conftest

        args = ["--cov=src/module/submodule", "--cov-report=html:reports/coverage", "--verbose"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            assert args == ["--verbose"]

    def test_skip_next_flag_resets_correctly(self):
        """Test that skip_next flag resets after skipping one value."""
        import conftest

        args = ["--cov", "src", "--verbose", "--cov-report", "html", "--strict-markers"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # Only --verbose and --strict-markers should remain
            assert args == ["--verbose", "--strict-markers"]


class TestDocumentationAndCodeQuality:
    """Test documentation and code quality aspects of conftest.py."""

    def test_module_has_docstring(self):
        """Test that the conftest module has a docstring."""
        import conftest

        assert conftest.__doc__ is not None
        assert len(conftest.__doc__.strip()) > 0

    def test_module_docstring_explains_purpose(self):
        """Test that the module docstring explains the purpose."""
        import conftest

        docstring = conftest.__doc__.lower()
        # Should mention coverage and pytest-cov
        assert "coverage" in docstring or "pytest-cov" in docstring or "cov" in docstring

    def test_cov_plugin_available_has_docstring(self):
        """Test that _cov_plugin_available has a docstring."""
        import conftest

        assert conftest._cov_plugin_available.__doc__ is not None
        assert len(conftest._cov_plugin_available.__doc__.strip()) > 0

    def test_pytest_load_initial_conftests_has_docstring(self):
        """Test that pytest_load_initial_conftests has a docstring."""
        import conftest

        assert conftest.pytest_load_initial_conftests.__doc__ is not None
        assert len(conftest.pytest_load_initial_conftests.__doc__.strip()) > 0

    def test_uses_type_hints(self):
        """Test that the module uses type hints appropriately."""
        import inspect

        import conftest

        # Check _cov_plugin_available return annotation
        sig = inspect.signature(conftest._cov_plugin_available)
        assert sig.return_annotation is bool

    def test_imports_are_minimal(self):
        """Test that the module only imports what it needs."""
        import conftest

        # Check that required imports are present
        assert hasattr(conftest, "importlib")

    def test_pragma_no_cover_on_hook(self):
        """Test that pytest hook has pragma no cover comment."""
        import inspect

        import conftest

        source = inspect.getsource(conftest.pytest_load_initial_conftests)
        # The hook should have pragma: no cover since it's tested by pytest itself
        assert "pragma: no cover" in source


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_typical_ci_environment_args(self):
        """Test typical CI environment PYTEST_ADDOPTS scenario."""
        import conftest

        # Typical CI setup with coverage
        args = [
            "-v",
            "--strict-markers",
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "tests/",
        ]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # Coverage flags removed, others preserved
            assert args == ["-v", "--strict-markers", "tests/"]

    def test_local_development_without_cov(self):
        """Test local development scenario without coverage."""
        import conftest

        args = ["-v", "--tb=short", "tests/unit/"]
        original = args.copy()

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            # Nothing should change
            assert args == original

    def test_multiple_coverage_sources(self):
        """Test scenario with multiple --cov flags for different sources."""
        import conftest

        args = ["--cov=src", "--cov=api", "--cov=app.py", "--cov-report=term", "tests/"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            assert args == ["tests/"]

    def test_mixed_short_and_long_flags(self):
        """Test scenario with mixed short and long flags."""
        import conftest

        args = ["-v", "-x", "--cov=src", "-s", "--cov-report=html", "--tb=short", "tests/"]

        with patch.object(conftest, "_cov_plugin_available", return_value=False):
            conftest.pytest_load_initial_conftests(args, None, None)

            assert args == ["-v", "-x", "-s", "--tb=short", "tests/"]
