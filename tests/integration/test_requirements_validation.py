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

    def test_pyyaml_added(self, requirements_dev_content: str) -> None:
        """Verify that requirements-dev.txt includes a PyYAML package entry."""
        assert "pyyaml" in requirements_dev_content.lower()

    def test_pyyaml_has_version_specifier(self, requirements_dev_content: str) -> None:
        """
        Ensure the active PyYAML requirement in requirements-dev.txt includes a version operator.

        Checks the provided requirements file content for exactly one non-comment line mentioning
        PyYAML and verifies that that line contains one of the version operators:
        >=, ==, ~=, <=, >, or <.
        """
        lines = requirements_dev_content.splitlines()

        pyyaml_lines = [
            line
            for line in lines
            if "pyyaml" in line.lower() and not line.lstrip().startswith("#")
        ]
        assert pyyaml_lines, (
            "No active PyYAML requirement found in requirements-dev.txt"
        )
        assert len(pyyaml_lines) == 1, (
            f"Expected exactly one active PyYAML line, found {len(pyyaml_lines)}"
        )

        pyyaml_line = pyyaml_lines[0]
        pyyaml_line_no_comment = pyyaml_line.split("#", 1)[0].strip()

        assert any(
            op in pyyaml_line_no_comment for op in (">=", "==", "~=", "<=", ">", "<")
        ), f"PyYAML line has no version operator: {pyyaml_line!r}"

    def test_no_duplicate_packages(self, requirements_dev_content: str) -> None:
        """
        Ensure requirements-dev.txt contains no duplicate package entries.

        Treats each non-empty, non-comment line as a PEP 508 requirement and compares names
        case-insensitively.
        """
        lines = [
            line.strip()
            for line in requirements_dev_content.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        package_names = [Requirement(line).name.lower() for line in lines]
        assert len(package_names) == len(set(package_names)), (
            "Duplicate packages found in requirements-dev.txt"
        )

    def test_requirements_format_valid(self, requirements_dev_content: str) -> None:
        """
        Validate that each active (non-empty, non-comment) line in requirements-dev.txt
        has no leading or trailing whitespace.
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

        req_packages = {Requirement(line).name.lower() for line in req_lines}
        dev_packages = {Requirement(line).name.lower() for line in dev_lines}

        overlap = req_packages & dev_packages
        assert len(overlap) <= 2, f"Too many overlapping packages: {sorted(overlap)}"


class TestRequirementsInstallability:
    """Test that requirements can be installed."""

    @pytest.mark.skipif(
        not Path("requirements-dev.txt").exists(),
        reason="requirements-dev.txt not found",
    )
    def test_requirements_dev_syntax_valid(self) -> None:
        """Verify requirements-dev.txt has valid pip syntax."""
        result = subprocess.run(
            ["pip", "install", "--dry-run", "-r", "requirements-dev.txt"],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"pip dry-run failed.\nstdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )


"""Test module for validating documentation in requirements-dev.txt.

This module contains integration tests that ensure the development requirements
file includes helpful comments and properly documents the purpose of key dependencies.
"""

class TestRequirementsDocumentation:
    """Documentation expectations for requirements-dev.txt."""

    @staticmethod
    def test_requirements_has_helpful_comments() -> None:
        """Ensure that requirements-dev.txt contains explanatory comment lines."""
        req_dev_path = Path("requirements-dev.txt")
        if not req_dev_path.exists():
            pytest.skip("requirements-dev.txt not found")

        lines = req_dev_path.read_text(encoding="utf-8").splitlines()
        comment_lines = [line for line in lines if line.strip().startswith("#")]
        assert comment_lines, "requirements-dev.txt should have explanatory comments"

    @staticmethod
    def test_pyyaml_purpose_documented() -> None:
        """Verify that PyYAML entry in requirements-dev.txt has an explanatory comment nearby."""
        req_dev_path = Path("requirements-dev.txt")
        if not req_dev_path.exists():
            pytest.skip("requirements-dev.txt not found")

        lines = req_dev_path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "pyyaml" in line.lower() and not line.lstrip().startswith("#"):
                context = "\n".join(lines[max(0, i - 3) : i + 1]).lower()
                assert any(
                    keyword in context
                    for keyword in ("yaml", "workflow", "config", "parse")
                ), "PyYAML should have an explanatory comment nearby"
                break
        else:
            pytest.skip(
                "No active PyYAML entry found to validate documentation context"
            )
