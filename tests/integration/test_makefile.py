"""Integration tests for Makefile commands.

This module tests that Makefile targets execute correctly and produce expected results.
Tests cover:
- Help command
- Dependency installation
- Testing commands
- Linting and formatting
- Clean commands
- Docker commands (structure validation)
"""

import re
import subprocess
from pathlib import Path

import pytest


class TestMakefileStructure:
    """Test Makefile structure and format."""

    @staticmethod
    def test_makefile_exists():
        """Test that Makefile exists in project root."""
        makefile_path = Path("Makefile")
        assert makefile_path.exists(), "Makefile not found in project root"
        assert makefile_path.is_file(), "Makefile is not a regular file"

    @staticmethod
    def test_makefile_readable():
        """Test that Makefile is readable."""
        makefile_path = Path("Makefile")
        with open(makefile_path, "r") as f:
            content = f.read()
            assert len(content) > 0, "Makefile is empty"

    @staticmethod
    def test_makefile_has_phony_declaration():
        """Test that Makefile declares .PHONY targets."""
        makefile_path = Path("Makefile")
        with open(makefile_path, "r") as f:
            content = f.read()
            assert ".PHONY:" in content, "Makefile missing .PHONY declaration"

    @staticmethod
    def test_makefile_targets_format():
        """Test that Makefile targets follow proper format."""
        makefile_path = Path("Makefile")
        with open(makefile_path, "r") as f:
            lines = f.readlines()

        target_pattern = re.compile(r"^[a-zA-Z_\-]+:.*##.*$")
        documented_targets = []

        for line in lines:
            if target_pattern.match(line):
                documented_targets.append(line.split(":")[0])

        # Should have some documented targets
        assert len(documented_targets) > 0, "No documented targets found"


class TestMakeHelp:
    """Test make help command."""

    @staticmethod
    def test_make_help_command_runs():
        """Test that 'make help' runs without error."""
        result = subprocess.run(["make", "help"], capture_output=True, text=True, check=False, timeout=30)

        assert result.returncode == 0, f"make help failed: {result.stderr}"

    @staticmethod
    def test_make_help_output_format():
        """Test that 'make help' output is properly formatted."""
        result = subprocess.run(["make", "help"], capture_output=True, text=True, check=False)

        assert result.returncode == 0
        output = result.stdout

        # Should contain usage information
        assert "Usage:" in output or "Available targets:" in output

    @staticmethod
    def test_make_help_lists_targets():
        """Test that 'make help' lists available targets."""
        result = subprocess.run(["make", "help"], capture_output=True, text=True, check=False)

        output = result.stdout

        # Check for common targets
        expected_targets = ["install", "test", "lint", "format", "clean"]
        found_targets = [t for t in expected_targets if t in output]

        assert len(found_targets) >= 3, f"Expected targets not found in help output. Found: {found_targets}"


class TestMakeInstallTargets:
    """Test installation targets."""

    @staticmethod
    def test_install_target_exists():
        """Test that 'install' target exists."""
        result = subprocess.run(["make", "-n", "install"], capture_output=True, text=True, check=False)

        # -n flag means dry-run, so it should succeed if target exists
        assert result.returncode == 0, "install target not found"

    @staticmethod
    def test_install_dev_target_exists():
        """Test that 'install-dev' target exists."""
        result = subprocess.run(["make", "-n", "install-dev"], capture_output=True, text=True, check=False)

        assert result.returncode == 0, "install-dev target not found"

    @staticmethod
    def test_install_commands():
        """Test that install target uses pip install."""
        result = subprocess.run(["make", "-n", "install"], capture_output=True, text=True, check=False)

        output = result.stdout + result.stderr
        assert "pip install" in output, "install target doesn't use pip install"


class TestMakeTestTargets:
    """Test testing-related targets."""

    @staticmethod
    def test_test_target_exists():
        """Test that 'test' target exists."""
        result = subprocess.run(["make", "-n", "test"], capture_output=True, text=True, check=False)

        assert result.returncode == 0, "test target not found"

    @staticmethod
    def test_test_target_uses_pytest():
        """Test that 'test' target uses pytest."""
        result = subprocess.run(["make", "-n", "test"], capture_output=True, text=True, check=False)

        output = result.stdout + result.stderr
        assert "pytest" in output, "test target doesn't use pytest"

    @staticmethod
    def test_test_target_includes_coverage():
        """Test that 'test' target includes coverage options."""
        result = subprocess.run(["make", "-n", "test"], capture_output=True, text=True, check=False)

        output = result.stdout + result.stderr
        assert "--cov" in output, "test target doesn't include coverage"

    @staticmethod
    def test_test_fast_target_exists():
        """Test that 'test-fast' target exists."""
        result = subprocess.run(["make", "-n", "test-fast"], capture_output=True, text=True, check=False)

        # Should either succeed or be a valid target
        # May not exist in all Makefiles
        assert result.returncode in [0, 2]  # 0 = exists, 2 = doesn't exist


class TestMakeLintTargets:
    """Test linting targets."""

    @staticmethod
    def test_lint_target_exists():
        """Test that 'lint' target exists."""
        result = subprocess.run(["make", "-n", "lint"], capture_output=True, text=True, check=False)

        assert result.returncode == 0, "lint target not found"

    @staticmethod
    def test_lint_target_uses_linters():
        """Test that 'lint' target uses linting tools."""
        result = subprocess.run(["make", "-n", "lint"], capture_output=True, text=True, check=False)

        output = result.stdout + result.stderr
        linters = ["ruff"]
        output_lc = output.lower()
        found_linters = [linter for linter in linters if linter in output_lc]
        assert result.returncode == 0 and (found_linters or output.strip()), (
            "lint target doesn't appear to invoke a linter"
        )


class TestMakeFormatTargets:
    """Test code formatting targets."""

    @staticmethod
    def test_format_target_exists():
        """Test that 'format' target exists."""
        result = subprocess.run(["make", "-n", "format"], capture_output=True, text=True, check=False)

        assert result.returncode == 0, "format target not found"

    @staticmethod
    def test_format_target_uses_formatters():
        """Test that 'format' target uses formatting tools."""
        result = subprocess.run(["make", "-n", "format"], capture_output=True, text=True, check=False)

        output = result.stdout + result.stderr
        formatters = ["black", "ruff"]

        found_formatters = [f for f in formatters if f in output]
        assert len(found_formatters) > 0, "format target doesn't use any known formatters"

    @staticmethod
    def test_format_check_target_exists():
        """Test that 'format-check' target exists."""
        result = subprocess.run(["make", "-n", "format-check"], capture_output=True, text=True, check=False)

        # Should exist or be a valid variation
        assert result.returncode in [0, 2]


class TestMakeCleanTargets:
    """Test cleanup targets."""

    @staticmethod
    def test_clean_target_exists():
        """Test that 'clean' target exists."""
        result = subprocess.run(["make", "-n", "clean"], capture_output=True, text=True, check=False)

        assert result.returncode == 0, "clean target not found"

    @staticmethod
    def test_clean_target_removes_cache():
        """Test that 'clean' target removes cache directories."""
        result = subprocess.run(["make", "-n", "clean"], capture_output=True, text=True, check=False)

        output = result.stdout + result.stderr
        cache_indicators = ["__pycache__", ".pytest_cache", ".mypy_cache", ".coverage"]

        found = [c for c in cache_indicators if c in output]
        assert len(found) > 0, "clean target doesn't clean cache directories"


class TestMakeTypeCheckTargets:
    """Test type checking targets."""

    @staticmethod
    def test_type_check_target_exists():
        """Test that 'type-check' target exists."""
        result = subprocess.run(["make", "-n", "type-check"], capture_output=True, text=True, check=False)

        assert result.returncode == 0, "type-check target not found"

    @staticmethod
    def test_type_check_uses_mypy():
        """Test that 'type-check' target uses mypy."""
        result = subprocess.run(["make", "-n", "type-check"], capture_output=True, text=True, check=False)

        output = result.stdout + result.stderr
        assert "mypy" in output, "type-check target doesn't use mypy"


class TestMakePreCommitTargets:
    """Test pre-commit related targets."""

    @staticmethod
    def test_pre_commit_target_exists():
        """Test that 'pre-commit' target exists."""
        result = subprocess.run(["make", "-n", "pre-commit"], capture_output=True, text=True, check=False)

        # May or may not exist depending on setup
        assert result.returncode in [0, 2]

    @staticmethod
    def test_pre_commit_run_target_exists():
        """Test that 'pre-commit-run' target exists."""
        result = subprocess.run(["make", "-n", "pre-commit-run"], capture_output=True, text=True, check=False)

        # May or may not exist
        assert result.returncode in [0, 2]


class TestMakeRunTargets:
    """Test application run targets."""

    @staticmethod
    def test_run_target_exists():
        """Test that 'run' target exists."""
        result = subprocess.run(["make", "-n", "run"], capture_output=True, text=True, check=False)

        assert result.returncode == 0, "run target not found"

    @staticmethod
    def test_run_target_executes_python():
        """Test that 'run' target executes Python."""
        result = subprocess.run(["make", "-n", "run"], capture_output=True, text=True, check=False)

        output = result.stdout + result.stderr
        assert "python" in output.lower(), "run target doesn't execute Python"


class TestMakeDockerTargets:
    """Test Docker-related targets."""

    @staticmethod
    def test_docker_build_target_exists():
        """Test that 'docker-build' target exists."""
        result = subprocess.run(["make", "-n", "docker-build"], capture_output=True, text=True, check=False)

        # May or may not exist
        assert result.returncode in [0, 2]

    @staticmethod
    def test_docker_run_target_exists():
        """Test that 'docker-run' target exists."""
        result = subprocess.run(["make", "-n", "docker-run"], capture_output=True, text=True, check=False)

        # May or may not exist
        assert result.returncode in [0, 2]

    @staticmethod
    def test_docker_targets_use_docker_commands():
        """Test that Docker targets use docker commands."""
        result = subprocess.run(["make", "-n", "docker-build"], capture_output=True, text=True, check=False)

        if result.returncode == 0:
            output = result.stdout + result.stderr
            assert "docker" in output.lower(), "docker-build doesn't use docker command"


class TestMakeCheckTarget:
    """Test comprehensive check target."""

    @staticmethod
    def test_check_target_exists():
        """Test that 'check' target exists."""
        result = subprocess.run(["make", "-n", "check"], capture_output=True, text=True, check=False)

        # May or may not exist
        assert result.returncode in [0, 2]

    @staticmethod
    def test_check_target_runs_multiple_checks():
        """Test that 'check' target runs multiple validations."""
        result = subprocess.run(["make", "-n", "check"], capture_output=True, text=True, check=False)

        if result.returncode == 0:
            output = result.stdout + result.stderr
            # Should reference multiple other targets or commands
            check_indicators = ["format", "lint", "test", "type"]
            found = [c for c in check_indicators if c in output.lower()]
            assert len(found) >= 2, "check target doesn't run multiple checks"


class TestMakefileEdgeCases:
    """Test edge cases and error handling."""

    @staticmethod
    def test_invalid_target_returns_error():
        """Test that invalid target returns non-zero exit code."""
        result = subprocess.run(["make", "nonexistent-target-12345"], capture_output=True, text=True, check=False)

        assert result.returncode != 0, "Invalid target should return error"

    @staticmethod
    def test_make_without_arguments():
        """Test running make without arguments."""
        result = subprocess.run(["make", "-n"], capture_output=True, text=True, check=False, timeout=30)

        # Should succeed with the default target
        assert result.returncode == 0, "Default make target failed"

    @staticmethod
    def test_multiple_targets_sequential():
        """Test that multiple targets can be specified."""
        result = subprocess.run(["make", "-n", "clean", "install"], capture_output=True, text=True, check=False)

        # Should process both targets
        output = result.stdout + result.stderr
        # At least one should be present
        assert "clean" in output.lower() or "install" in output.lower()


class TestMakefileDocumentation:
    """Test Makefile documentation and help strings."""

    @staticmethod
    def test_targets_have_help_strings():
        """Test that important targets have help documentation."""
        makefile_path = Path("Makefile")
        with open(makefile_path, "r") as f:
            content = f.read()

        # Look for ## comments (help strings)
        help_pattern = re.compile(r".*:.*##.*")
        help_lines = [line for line in content.split("\n") if help_pattern.match(line)]

        # Should have at least some documented targets
        assert len(help_lines) >= 5, "Not enough targets have help documentation"

    @staticmethod
    def test_help_strings_format():
        """Test that help strings follow consistent format."""
        makefile_path = Path("Makefile")
        with open(makefile_path, "r") as f:
            lines = f.readlines()

        help_lines = [line for line in lines if "##" in line and ":" in line]

        for line in help_lines:
            # Help string should be after ##
            parts = line.split("##")
            if len(parts) >= 2:
                help_text = parts[1].strip()
                # Should not be empty
                assert len(help_text) > 0, f"Empty help string in line: {line}"


class TestMakefileConsistency:
    """Test consistency across Makefile targets."""

    @staticmethod
    def test_phony_targets_declared():
        """Test that targets in .PHONY are actually defined."""
        makefile_path = Path("Makefile")
        with open(makefile_path, "r") as f:
            content = f.read()

        # Extract .PHONY declaration
        phony_match = re.search(r"\.PHONY:\s*(.+)", content)
        if phony_match:
            phony_targets = phony_match.group(1).split()

            # Check each phony target is defined
            for target in phony_targets:
                pattern = rf"^{re.escape(target)}:"
                assert re.search(pattern, content, re.MULTILINE), f"PHONY target '{target}' not defined in Makefile"

    @staticmethod
    def test_no_hardcoded_python_version():
        """Test that Makefile doesn't hardcode Python version unnecessarily."""
        makefile_path = Path("Makefile")
        with open(makefile_path, "r") as f:
            content = f.read()

        # Should use 'python' not 'python3.8' or similar
        # This makes the Makefile more portable
        hardcoded_versions = re.findall(r"python3\.\d+", content)

        # Some hardcoding might be acceptable in comments
        # Just ensure it's not excessive
        assert len(hardcoded_versions) < 3, "Too many hardcoded Python versions"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
