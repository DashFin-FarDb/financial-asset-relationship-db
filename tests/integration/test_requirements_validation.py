"""Validation tests for requirements changes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement


class TestRequirementsDevChanges:
    """Test requirements-dev.txt changes."""

    @pytest.fixture
    def requirements_dev_content(self) -> str:
        """
        Return the full text of requirements-dev.txt from the project root.

        Returns:
            str: Contents of requirements-dev.txt.
        """
        req_path = Path("requirements-dev.txt")
        return req_path.read_text(encoding="utf-8")

    def test_pyyaml_added(self, requirements_dev_content):
        """
        Verify that requirements-dev.txt includes a PyYAML package entry.

    def test_pyyaml_has_version_specifier(self, requirements_dev_content: str) -> None:
        """
        assert "pyyaml" in requirements_dev_content.lower()

        Checks the provided requirements file content for exactly one non-comment line mentioning
        PyYAML and verifies that that line contains one of the version operators:
        >=, ==, ~=, <=, >, or <.
        """
        Ensure the active PyYAML requirement in requirements-dev.txt includes a version operator.

        Checks the provided requirements file content for exactly one non-comment line mentioning PyYAML and
        verifies that that line contains one of the version operators: >=, ==, ~=, <=, >, or <.

        Parameters:
            requirements_dev_content(str): Full text content of requirements-dev.txt.
        """
        lines = requirements_dev_content.split("\n")
        # Ignore commented lines so we don't pick up commented-out examples
        pyyaml_line = next(
            (l for l in lines if "pyyaml" in l.lower() and not l.strip().startswith("#")),
            None,
        )

        assert pyyaml_line is not None
        from packaging.requirements import Requirement

        def _safe_req_name(line: str) -> str | None:
            """Return the normalised package name, or None for pip directives / malformed lines."""
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("-"):
                return None
            try:
                return Requirement(stripped.split("#")[0].strip()).name.lower()
            except Exception:
                return None

        # Find all non-comment lines explicitly declaring PyYAML (ignore types-PyYAML)
        pyyaml_lines = [l for l in lines if _safe_req_name(l) == "pyyaml"]
        # Assert exactly one active PyYAML requirement exists
        assert len(pyyaml_lines) == 1, f"Expected exactly one active PyYAML line, found {len(pyyaml_lines)}"
        pyyaml_line = pyyaml_lines[0]
        # Strip inline comments and whitespace before checking version specifier
        pyyaml_line_no_comment = pyyaml_line.split("#", 1)[0].strip()
        assert any(op in pyyaml_line_no_comment for op in [">=", "==", "~=", "<=", ">", "<"])

    def test_no_duplicate_packages(self, requirements_dev_content):
        """
        Ensure requirements-dev.txt contains no duplicate package entries.

        This test treats each non-empty, non-comment line as a package specification and compares
        package names case-insensitively while ignoring common version specifiers, asserting
        that no package appears more than once.

        Parameters:
            requirements_dev_content(str): Contents of requirements-dev.txt.
        """
        lines = [
            l.strip()
            for l in requirements_dev_content.split("\n")
            if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("-")
        ]

        # Split on any common version operator to reliably extract the package name
        from packaging.requirements import Requirement

        package_names = [Requirement(l).name.lower() for l in lines]

        assert len(package_names) == len(set(package_names)), "Duplicate packages found in requirements-dev.txt"

        Treats each non-empty, non-comment line as a PEP 508 requirement and compares names
        case-insensitively.
        """
        Validate that each active (non-empty, non-comment) line in requirements-dev.txt has no
        leading or trailing whitespace.

        Ignores blank lines and lines beginning with '#' when performing checks.

        Parameters:
            requirements_dev_content(str): Full text of requirements-dev.txt to validate.
        """
        for line_num, raw_line in enumerate(requirements_dev_content.splitlines(), 1):
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue

            assert raw_line == raw_line.rstrip(), (
                f"Line {line_num} has trailing whitespace"
            )
            assert raw_line == raw_line.lstrip(), (
                f"Line {line_num} has leading whitespace"
            )


class TestRequirementsDependencyCompatibility:
    """Test dependency compatibility."""

    @staticmethod
    def test_pyyaml_compatible_with_python_version() -> None:
        """
        Assert that if PyYAML is listed in requirements-dev.txt the current Python interpreter is at least 3.6.

        Checks requirements-dev.txt case-insensitively and fails the test if PyYAML is present while
        sys.version_info is less than (3, 6).
        """
        req_path = Path("requirements-dev.txt")
        if not req_path.exists():
            pytest.skip("requirements-dev.txt not found")

        content = req_path.read_text(encoding="utf-8")
        if "pyyaml" in content.lower():
            assert sys.version_info >= (3, 6), "PyYAML requires Python 3.6 or higher"

    @staticmethod
    def test_no_conflicting_versions() -> None:
        """
        Ensure at most two package name overlaps exist between requirements.txt and requirements-dev.txt.

        Note: this is a heuristic; a stronger approach would compare specifiers for overlaps,
        but that would change test semantics.
        """
        req_path = Path("requirements.txt")
        req_dev_path = Path("requirements-dev.txt")

        if not req_path.exists():
            pytest.skip("requirements.txt not found")
        if not req_dev_path.exists():
            pytest.skip("requirements-dev.txt not found")

        req_lines = [
            line.strip()
            for line in req_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        dev_lines = [
            line.strip()
            for line in req_dev_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        def _extract_pkg_name(line: str) -> str | None:
            """Return normalised package name from a requirement line, or None to skip."""
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("-"):
                return None
            try:
                from packaging.requirements import Requirement as _Req

                return _Req(stripped.split("#")[0].strip()).name.lower()
            except Exception:
                return None

        # Check for packages in both files
        req_packages = {n for l in req_content.split("\n") if (n := _extract_pkg_name(l)) is not None}

        req_dev_packages = {n for l in req_dev_content.split("\n") if (n := _extract_pkg_name(l)) is not None}

        overlap = req_packages & req_dev_packages
        # PyYAML might be in both, but versions should be compatible
        # This is a basic check
        assert len(overlap) <= 2, f"Too many overlapping packages: {overlap}"


class TestRequirementsInstallability:
    """Test that requirements can be installed."""

    @pytest.mark.skipif(
        not Path("requirements-dev.txt").exists(),
        reason="requirements-dev.txt not found",
    )
    def test_requirements_dev_syntax_valid(self):
        """Verify requirements-dev.txt has valid pip syntax."""
        # Use pip to check syntax without installing
        result = subprocess.run(
            ["pip", "install", "--dry-run", "-r", "requirements-dev.txt"],
            text=True,
            capture_output=True,
            text=True,
        )
        # Check return code - pip should exit with 0 on success
        # Allow benign warnings in stderr (e.g., "WARNING: pip is being invoked")
        assert result.returncode == 0, (
            f"pip install --dry-run failed with exit code {result.returncode}\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )


class TestRequirementsDocumentation:
    """Documentation expectations for requirements-dev.txt."""

    @staticmethod
    def test_requirements_has_helpful_comments():
        """
        Verify that requirements - dev.txt contains at least one comment line.

        Asserts the file has at least one line, which after trimming leading whitespace,
        begins with "#", indicating an explanatory comment for the dependency list.
        """
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, "r") as f:
            lines = f.readlines()

        # Should have at least some comments explaining purpose
        comment_lines = [l for l in lines if l.strip().startswith("#")]
        assert len(comment_lines) >= 1, "requirements-dev.txt should have explanatory comments"

    @staticmethod
    def test_pyyaml_purpose_documented():
        """
        Verify PyYAML addition has comment explaining purpose.
        """
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
                    keyword in context
                    for keyword in ("yaml", "workflow", "config", "parse")
                ), "PyYAML should have an explanatory comment nearby"
                break
        else:
            pytest.skip(
                "No active PyYAML entry found to validate documentation context"
            )
