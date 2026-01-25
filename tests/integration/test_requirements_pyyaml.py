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
        """
        Return the Path to the repository's requirements-dev.txt file.

        Returns:
            Path: Path object pointing to 'requirements-dev.txt' at the repository root.
        """
        return Path("requirements-dev.txt")

    @pytest.fixture
    def requirements_content(self, requirements_file: Path) -> str:
        """
        Get the UTF-8 text contents of the requirements-dev.txt file.

        Parameters:
            requirements_file (Path): Path to the requirements-dev.txt file to read.


        Returns:
            str: File contents decoded as UTF-8.
        """
        with open(requirements_file, "r", encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    @staticmethod
    def requirements_lines(requirements_content: str) -> List[str]:
        """
        Extracts the non-empty, non-comment lines from the contents of a requirements file.

        Parameters:
            requirements_content (str): Full text of a requirements file.

        Returns:
            List[str]: Lines from the file with surrounding whitespace removed, excluding blank lines and lines beginning with `#`.
        """
        lines = []
        for line in requirements_content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        return lines

    @staticmethod
    def test_pyyaml_present(requirements_lines: List[str]):
        """Test that PyYAML is in requirements-dev.txt."""
        pyyaml_lines = [
            line for line in requirements_lines if line.startswith("PyYAML")
        ]
        assert len(pyyaml_lines) >= 1, (
            "PyYAML should be present in requirements-dev.txt"
        )

    @staticmethod
    def test_types_pyyaml_present(requirements_lines: List[str]):
        """
        Ensure types-PyYAML is listed in requirements-dev.txt.

        Asserts that at least one non-empty, non-comment requirement line begins with "types-PyYAML".
        """
        types_lines = [
            line for line in requirements_lines if line.startswith("types-PyYAML")
        ]
        assert len(types_lines) >= 1, (
            "types-PyYAML should be present in requirements-dev.txt"
        )

    @staticmethod
    def test_pyyaml_version_specified(requirements_lines: List[str]):
        """
        Verify PyYAML entries include a version specifier.

        Asserts that every non-comment requirements line starting with "PyYAML" contains either '>=' or '=='.
        """
        pyyaml_lines = [
            line for line in requirements_lines if line.startswith("PyYAML")
        ]

        for line in pyyaml_lines:
            assert ">=" in line or "==" in line, (
                f"PyYAML should have version specifier: {line}"
            )

    @staticmethod
    def test_pyyaml_version_at_least_6(requirements_lines: List[str]):
        """
        Assert that every `PyYAML` requirement with a "greater than or equal" version specifier requires version 6.0 or higher.

        Parameters:
            requirements_lines (List[str]): Non-empty, non-comment lines from requirements-dev.txt to inspect.
        """
        pyyaml_lines = [
            line for line in requirements_lines if line.startswith("PyYAML")
        ]

        for line in pyyaml_lines:
            version_match = re.search(r">=(\d+\.\d+)", line)
            if version_match:
                version = float(version_match.group(1))
                assert version >= 6.0, f"PyYAML version should be >= 6.0, got {version}"

    @staticmethod
    def test_types_pyyaml_matches_pyyaml_version(requirements_lines: List[str]):
        """
        Ensure the major version number of `types-PyYAML` equals the major version number of `PyYAML` when both are specified with '>=' in the given requirements lines.

        Parameters:
            requirements_lines (List[str]): Non-comment, non-empty lines from requirements-dev.txt to inspect for 'PyYAML>=' and 'types-PyYAML>=' entries.
        """
        pyyaml_version = None
        types_version = None

        for line in requirements_lines:
            if line.startswith("PyYAML>="):
                pyyaml_match = re.search(r">=(\d+)", line)
                if pyyaml_match:
                    pyyaml_version = int(pyyaml_match.group(1))

            if line.startswith("types-PyYAML>="):
                types_match = re.search(r">=(\d+)", line)
                if types_match:
                    types_version = int(types_match.group(1))

        if pyyaml_version and types_version:
            assert pyyaml_version == types_version, (
                f"types-PyYAML version {types_version} should match PyYAML version {pyyaml_version}"
            )


class TestRequirementsDevYAMLUsage:
    """Test that PyYAML is needed for workflow validation."""

    @staticmethod
    def test_pyyaml_used_in_workflow_tests():
        """Test that PyYAML is imported in workflow test files."""
        workflow_test_files = [
            Path("tests/integration/test_github_workflows.py"),
            Path("tests/integration/test_pr_agent_workflow_specific.py"),
        ]

        pyyaml_used = False
        for test_file in workflow_test_files:
            if test_file.exists():
                with open(test_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "import yaml" in content:
                        pyyaml_used = True
                        break

        assert pyyaml_used, "PyYAML should be imported in workflow test files"

    @staticmethod
    def test_yaml_files_exist_in_repo():
        """
        Verify that at least one YAML workflow file exists in .github/workflows.

        Checks for files with `.yml` or `.yaml` extensions and fails the test if none are found.
        """
        yaml_files_exist = False
        workflows_dir = Path(".github/workflows")

        if workflows_dir.exists():
            yaml_files = list(workflows_dir.glob("*.yml")) + list(
                workflows_dir.glob("*.yaml")
            )
            yaml_files_exist = len(yaml_files) > 0

        assert yaml_files_exist, (
            "Repository should have YAML files that need PyYAML for validation"
        )


class TestRequirementsDevCompleteness:
    """Test that requirements-dev.txt is complete and well-formed."""

    @pytest.fixture
    def requirements_content(self) -> str:
        """
        Read the repository's requirements-dev.txt as UTF-8 text.

        Returns:
            str: The full contents of requirements-dev.txt.
        """
        with open("requirements-dev.txt", "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def test_file_ends_with_newline(requirements_content: str):
        """
        Assert that the requirements-dev.txt content ends with a newline.

        Parameters:
            requirements_content (str): UTF-8 decoded contents of requirements-dev.txt.
        """
        assert requirements_content.endswith("\n"), (
            "requirements-dev.txt should end with a newline"
        )

    @staticmethod
    def test_no_duplicate_packages(requirements_content: str):
        """
        Ensure the requirements text contains no duplicate package names.

        Ignores blank lines and comment lines (starting with '#'). For each remaining line, the package name is taken as the substring before any of '>', '<', or '='; the test fails if any package appears more than once.

        Parameters:
            requirements_content (str): Full text of the requirements file to inspect.
        """
        packages = []
        for line in requirements_content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                package = re.split(r"[>=<]", line)[0].strip()
                packages.append(package)

        duplicates = [pkg for pkg in set(packages) if packages.count(pkg) > 1]
        assert len(duplicates) == 0, f"Found duplicate packages: {duplicates}"

    @staticmethod
    def test_all_lines_valid_format(requirements_content: str):
        """
        Ensure each non-empty, non-comment line in requirements_content matches the package/version pattern.

        Empty lines and lines starting with '#' are ignored. Raises an AssertionError identifying the offending line number and text if any remaining line does not match the expected package name, optional extras, and optional version specifier (e.g., `==1.2.3`, `>=1.0`, `~=1.4`).

        Parameters:
            requirements_content (str): Full text of requirements-dev.txt to validate.
        """
        for line_num, line in enumerate(requirements_content.split("\n"), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            valid_pattern = (
                r"^[a-zA-Z0-9._-]+\[?[a-zA-Z0-9._,-]*\]?((>=|==|<=|>|<|~=)[0-9.]+.*)?$"
            )
            assert re.match(valid_pattern, line), (
                f"Line {line_num} has invalid format: {line}"
            )

    @staticmethod
    def test_has_testing_dependencies(requirements_content: str):
        """
        Verify that requirements-dev.txt contains essential testing packages.

        Parameters:
            requirements_content (str): Full text contents of requirements-dev.txt to check.
        """
        essential_packages = ["pytest", "pytest-cov"]

        for package in essential_packages:
            assert package in requirements_content, (
                f"requirements-dev.txt should include {package}"
            )

    @staticmethod
    def test_has_linting_dependencies(requirements_content: str):
        """
        Ensure the requirements-dev.txt content includes the linting packages flake8, pylint, and black.

        Parameters:
            requirements_content (str): Full text of requirements-dev.txt to inspect for the presence of the listed packages.
        """
        linting_packages = ["flake8", "pylint", "black"]

        for package in linting_packages:
            assert package in requirements_content, (
                f"requirements-dev.txt should include {package}"
            )


class TestPyYAMLCompatibility:
    """Test PyYAML compatibility and best practices."""

    @staticmethod
    def test_pyyaml_safe_load_available():
        """
        Check that the installed PyYAML package exposes a `safe_load` symbol.

        If the `yaml` module cannot be imported, the test is skipped. Otherwise the test fails if `yaml.safe_load` is missing.
        """
        try:
            import yaml

            assert hasattr(yaml, "safe_load"), (
                "PyYAML should provide safe_load function"
            )
        except ImportError:
            pytest.skip("PyYAML not installed in test environment")

    @staticmethod
    def test_pyyaml_can_parse_workflow_files():
        """Test that PyYAML can parse actual workflow files."""
        try:
            import yaml

            workflow_file = Path(".github/workflows/pr-agent.yml")

            if workflow_file.exists():
                with open(workflow_file, "r", encoding="utf-8") as f:
                    content = yaml.safe_load(f)

                assert content is not None, (
                    "PyYAML should successfully parse workflow files"
                )
                assert isinstance(content, dict), (
                    "Workflow files should parse to dictionaries"
                )
        except ImportError:
            pytest.skip("PyYAML not installed in test environment")


class TestRequirementsDevVersionPinning:
    """Test version pinning strategy in requirements-dev.txt."""

    @pytest.fixture
    @staticmethod
    def requirements_lines() -> List[str]:
        """
        Get the non-comment, non-empty lines from requirements-dev.txt.

        Returns:
            List[str]: Cleaned requirement lines (whitespace trimmed) in file order.
        """
        with open("requirements-dev.txt", "r", encoding="utf-8") as f:
            content = f.read()

        lines = []
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        return lines

    @staticmethod
    def test_uses_minimum_version_specifiers(requirements_lines: List[str]):
        """
        Assert that each non-typing package entry includes a minimum version specifier ('>=' or '==').

        Parameters:
            requirements_lines (List[str]): Non-empty, non-comment requirement lines to validate.
        """
        for line in requirements_lines:
            if not line.startswith("types-"):
                assert ">=" in line or "==" in line, (
                    f"Package should have version specifier: {line}"
                )

    @staticmethod
    def test_pyyaml_and_types_both_pinned(requirements_lines: List[str]):
        """Test that both PyYAML and types-PyYAML have version pins."""
        pyyaml_pinned = any("PyYAML>=" in line for line in requirements_lines)
        types_pinned = any("types-PyYAML>=" in line for line in requirements_lines)

        assert pyyaml_pinned, "PyYAML should have version pin"
        assert types_pinned, "types-PyYAML should have version pin"
