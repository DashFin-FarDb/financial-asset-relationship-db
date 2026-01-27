"""
Comprehensive tests for PyYAML dependencies in requirements-dev.txt.
Tests the addition of PyYAML and types-PyYAML dependencies.
"""

import re
from pathlib import Path
from typing import List

import pytest


class TestPyYAMLDependencyAddition:
    """Test that PyYAML dependencies were properly added."""

    @pytest.fixture
    def requirements_file(self) -> Path:
        """Return the Path to the repository's requirements-dev.txt file."""
        return Path("requirements-dev.txt")

    @pytest.fixture
    def requirements_content(self, requirements_file: Path) -> str:
        """Get the UTF-8 text contents of the requirements-dev.txt file."""
        return requirements_file.read_text(encoding="utf-8")

    @pytest.fixture
    def requirements_lines(self, requirements_content: str) -> List[str]:
        """
        Extract non-empty, non-comment lines from a requirements file.
        """
        return [
            line.strip()
            for line in requirements_content.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def test_pyyaml_present(self, requirements_lines: List[str]) -> None:
        """Test that PyYAML is in requirements-dev.txt."""
        assert any(
            line.startswith("PyYAML") for line in requirements_lines
        ), "PyYAML should be present in requirements-dev.txt"

    def test_types_pyyaml_present(self, requirements_lines: List[str]) -> None:
        """Test that types-PyYAML is in requirements-dev.txt."""
        assert any(
            line.startswith("types-PyYAML") for line in requirements_lines
        ), "types-PyYAML should be present in requirements-dev.txt"

    def test_pyyaml_version_specified(self, requirements_lines: List[str]) -> None:
        """Test that PyYAML has a version specifier."""
        for line in requirements_lines:
            if line.startswith("PyYAML"):
                assert ">=" in line or "==" in line, (
                    f"PyYAML should have version specifier: {line}"
                )

    def test_pyyaml_version_at_least_6(self, requirements_lines: List[str]) -> None:
        """Ensure PyYAML minimum version is >= 6.0 when specified."""
        for line in requirements_lines:
            if line.startswith("PyYAML"):
                match = re.search(r">=(\d+\.\d+)", line)
                if match:
                    assert float(match.group(1)) >= 6.0

    def test_types_pyyaml_matches_pyyaml_version(
        self, requirements_lines: List[str]
    ) -> None:
        """Ensure types-PyYAML major version matches PyYAML major version."""
        pyyaml_major = None
        types_major = None

        for line in requirements_lines:
            if line.startswith("PyYAML>="):
                match = re.search(r">=(\d+)", line)
                if match:
                    pyyaml_major = int(match.group(1))

            if line.startswith("types-PyYAML>="):
                match = re.search(r">=(\d+)", line)
                if match:
                    types_major = int(match.group(1))

        if pyyaml_major is not None and types_major is not None:
            assert pyyaml_major == types_major, (
                f"types-PyYAML version {types_major} should match PyYAML version {pyyaml_major}"
            )


class TestRequirementsDevYAMLUsage:
    """Test that PyYAML is actually used."""

    def test_pyyaml_used_in_workflow_tests(self) -> None:
        """Test that PyYAML is imported in workflow test files."""
        workflow_tests = [
            Path("tests/integration/test_github_workflows.py"),
            Path("tests/integration/test_pr_agent_workflow_specific.py"),
        ]

        for test_file in workflow_tests:
            if test_file.exists():
                if "import yaml" in test_file.read_text(encoding="utf-8"):
                    return

        pytest.fail("PyYAML should be imported in workflow test files")

    def test_yaml_files_exist_in_repo(self) -> None:
        """Ensure YAML workflow files exist in .github/workflows."""
        workflows_dir = Path(".github/workflows")

        if not workflows_dir.exists():
            pytest.fail(".github/workflows directory does not exist")

        yaml_files = list(workflows_dir.glob("*.yml")) + list(
            workflows_dir.glob("*.yaml")
        )

        assert yaml_files, (
            "Repository should contain YAML workflow files requiring PyYAML"
        )


class TestRequirementsDevCompleteness:
    """Test completeness and formatting of requirements-dev.txt."""

    def test_all_lines_valid_format(self, requirements_content: str):
        """
        Test that all requirement lines follow a valid PEP 440–compatible format.

        Allowed forms:
        - package
        - package>=x.y
        - package==x.y.z
        - package[extra1,extra2]>=x.y
        """
        pattern = re.compile(
            r"""
            ^                                   # start of line
            [A-Za-z0-9._-]+                     # package name
            (\[[A-Za-z0-9._,-]+\])?             # optional extras
            (                                   # optional version specifier
                (==|>=)                         # allowed operators
                [0-9]+(\.[0-9]+)*               # version number
            )?                                  # version optional
            $                                   # end of line
            """,
            re.VERBOSE,
        )

        for line_num, line in enumerate(requirements_content.splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("#"):
            continue

        assert pattern.match(line), (
            f"Invalid requirement format on line {line_num}: {line}"
        )

    @pytest.fixture
    def requirements_content(self) -> str:
        """Read requirements-dev.txt."""
        return Path("requirements-dev.txt").read_text(encoding="utf-8")

    def test_file_ends_with_newline(self, requirements_content: str) -> None:
        """Ensure requirements-dev.txt ends with a newline."""
        assert requirements_content.endswith("\n")

    def test_no_duplicate_packages(self, requirements_content: str) -> None:
        """Ensure no duplicate package entries exist."""
        packages: list[str] = []

        for line in requirements_content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                package = re.split(r"[<>=]", stripped)[0].strip()
                packages.append(package)

        duplicates = {pkg for pkg in packages if packages.count(pkg) > 1}
        assert not duplicates, f"Duplicate packages found: {sorted(duplicates)}"


class TestRequirementsDevVersionPinning:
    """Test version pinning strategy."""

    @pytest.fixture
    def requirements_lines(self) -> List[str]:
        """Return cleaned requirement lines."""
        content = Path("requirements-dev.txt").read_text(encoding="utf-8")
        return [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def test_uses_minimum_version_specifiers(
        self, requirements_lines: List[str]
    ) -> None:
        """Ensure non-types packages include a version specifier."""
        for line in requirements_lines:
            if not line.startswith("types-"):
                assert ">=" in line or "==" in line, (
                    f"Package should have version specifier: {line}"
                )

    def test_pyyaml_and_types_both_pinned(
        self, requirements_lines: List[str]
    ) -> None:
        """Ensure PyYAML and types-PyYAML are both pinned."""
        assert any("PyYAML>=" in line for line in requirements_lines)
        assert any("types-PyYAML>=" in line for line in requirements_lines)
