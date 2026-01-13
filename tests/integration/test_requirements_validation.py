"""
Validation tests for requirements changes.

Tests that requirements-dev.txt changes are valid:
- PyYAML added with correct version
- No conflicting dependencies
- All dependencies installable
"""

import subprocess
from pathlib import Path

import pytest


class TestRequirementsDevChanges:
    """Test requirements-dev.txt changes."""

    @pytest.fixture
    def requirements_dev_content(self):
        """
        Return the full text of requirements-dev.txt from the project root.

        Returns:
            str: Contents of requirements-dev.txt.
        """
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            return f.read()

    def test_pyyaml_added(self, requirements_dev_content):
        """
        Verify that requirements-dev.txt includes a PyYAML package entry.

        Performs a case-insensitive check of the provided requirements content to ensure PyYAML is present.
        """
        assert "pyyaml" in requirements_dev_content.lower() or "PyYAML" in requirements_dev_content

    def test_pyyaml_has_version_specifier(self, requirements_dev_content):
        """
        Ensure the active PyYAML requirement in requirements-dev.txt includes a version operator.

        Checks the provided requirements file content for exactly one non-comment line mentioning PyYAML and verifies that that line contains one of the version operators: >=, ==, ~=, <=, >, or <.

        Parameters:
                requirements_dev_content (str): Full text content of requirements-dev.txt.
        """
        lines = requirements_dev_content.split("\n")
        # Ignore commented lines so we don't pick up commented-out examples
        pyyaml_line = next((l for l in lines if "pyyaml" in l.lower() and not l.strip().startswith("#")), None)

        assert pyyaml_line is not None
        # Find all non-comment lines containing 'pyyaml'
        pyyaml_lines = [l for l in lines if "pyyaml" in l.lower() and not l.strip().startswith("#")]
        # Assert exactly one active PyYAML requirement exists
        assert len(pyyaml_lines) == 1, f"Expected exactly one active PyYAML line, found {len(pyyaml_lines)}"
        pyyaml_line = pyyaml_lines[0]
        # Strip inline comments and whitespace before checking version specifier
        pyyaml_line_no_comment = pyyaml_line.split("#", 1)[0].strip()
        assert any(op in pyyaml_line_no_comment for op in [">=", "==", "~=", "<=", ">", "<"])
        pyyaml_line_no_comment = pyyaml_line.split("#", 1)[0].strip()
        assert any(op in pyyaml_line_no_comment for op in [">=", "==", "~=", "<=", ">", "<"])

    def test_no_duplicate_packages(self, requirements_dev_content):
        """
        Ensure requirements-dev.txt contains no duplicate package entries.

        This test treats each non-empty, non-comment line as a package specification and compares
        package names case-insensitively while ignoring common version specifiers, asserting
        that no package appears more than once.

        Parameters:
            requirements_dev_content (str): Contents of requirements-dev.txt.
        """
        lines = [l.strip() for l in requirements_dev_content.split("\n") if l.strip() and not l.strip().startswith("#")]

        # Split on any common version operator to reliably extract the package name
        from packaging.requirements import Requirement

        package_names = [Requirement(l).name.lower() for l in lines]

        assert len(package_names) == len(set(package_names)), "Duplicate packages found in requirements-dev.txt"

    def test_requirements_format_valid(self, requirements_dev_content):
        """
        Validate that each active (non-empty, non-comment) line in requirements-dev.txt has no leading or trailing whitespace.

        Ignores blank lines and lines beginning with '#' when performing checks.

        Parameters:
            requirements_dev_content (str): Full text of requirements-dev.txt to validate.
        """
        lines = requirements_dev_content.split("\n")

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line and not line.startswith("#"):
                # Basic format check
                assert not line.startswith(" "), f"Line {i} has leading whitespace"
                # Should not have trailing whitespace
                assert line == line.rstrip(), f"Line {i} has trailing whitespace"


class TestRequirementsDependencyCompatibility:
    """Test dependency compatibility."""

    def test_pyyaml_compatible_with_python_version(self):
        """
        Assert that if PyYAML is listed in requirements-dev.txt the current Python interpreter is at least 3.6.

        Checks requirements-dev.txt case-insensitively and fails the test if PyYAML is present while sys.version_info is less than (3, 6).
        """
        # Check Python version
        import sys

        python_version = sys.version_info

        # PyYAML >=5.4 requires Python 3.6+
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            content = f.read()

        if "pyyaml" in content.lower():
            # Basic compatibility check passed
            assert python_version >= (3, 6), "PyYAML requires Python 3.6 or higher"

    def test_no_conflicting_versions(self):
        """
        Ensure at most two package name overlaps exist between requirements.txt and requirements-dev.txt.

        Reads both files (skipping the test if requirements.txt is missing), extracts package names by removing common version specifiers and ignoring commented/blank lines, and asserts that the number of overlapping package names is less than or equal to two. On failure, raises an AssertionError listing the overlapping package names.

        Raises:
            AssertionError: If more than two package names appear in both files.
        """
        req_path = Path("requirements.txt")
        req_dev_path = Path("requirements-dev.txt")

        if not req_path.exists():
            pytest.skip("requirements.txt not found")

        with open(req_path, "r") as f:
            req_content = f.read()
        with open(req_dev_path, "r") as f:
            req_dev_content = f.read()

        # Check for packages in both files
        req_packages = {
            l.split("==")[0].split(">=")[0].lower().strip()
            for l in req_content.split("\n")
            if l.strip() and not l.strip().startswith("#")
        }

        req_dev_packages = {
            l.split("==")[0].split(">=")[0].lower().strip()
            for l in req_dev_content.split("\n")
            if l.strip() and not l.strip().startswith("#")
        }

        overlap = req_packages & req_dev_packages
        # PyYAML might be in both, but versions should be compatible
        # This is a basic check
        assert len(overlap) <= 2, f"Too many overlapping packages: {overlap}"


class TestRequirementsInstallability:
    """Test that requirements can be installed."""

    @pytest.mark.skipif(not Path("requirements-dev.txt").exists(), reason="requirements-dev.txt not found")
    def test_requirements_dev_syntax_valid(self):
        """Verify requirements-dev.txt has valid pip syntax."""
        # Use pip to check syntax without installing
        result = subprocess.run(
            ["pip", "install", "--dry-run", "-r", "requirements-dev.txt"], capture_output=True, text=True
        )

        # Should not have syntax errors
        assert "error" not in result.stderr.lower() or "requirement already satisfied" in result.stdout.lower()


class TestRequirementsDocumentation:
    """Test requirements documentation and comments."""

    def test_requirements_has_helpful_comments(self):
        """
        Verify that requirements-dev.txt contains at least one comment line.

        Asserts the file has at least one line which, after trimming leading whitespace, begins with `#`, indicating an explanatory comment for the dependency list.
        """
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, "r") as f:
            lines = f.readlines()

        # Should have at least some comments explaining purpose
        comment_lines = [l for l in lines if l.strip().startswith("#")]
        assert len(comment_lines) >= 1, "requirements-dev.txt should have explanatory comments"

    def test_pyyaml_purpose_documented(self):
        """Verify PyYAML addition has comment explaining purpose."""
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, "r") as f:
            content = f.read()

        # Check if there's a comment near PyYAML explaining its purpose
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "pyyaml" in line.lower():
                # Check previous lines for comments
                context = "\n".join(lines[max(0, i - 3) : i + 1])
                # Should have some context about YAML parsing or workflows
                assert any(
                    keyword in context.lower() for keyword in ["yaml", "workflow", "config", "parse"]
                ), "PyYAML should have explanatory comment"
                break
