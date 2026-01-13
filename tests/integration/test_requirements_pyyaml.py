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
        pyyaml_lines = [line for line in requirements_lines if line.startswith("PyYAML")]
        assert len(pyyaml_lines) >= 1, "PyYAML should be present in requirements-dev.txt"

    @staticmethod
    def test_types_pyyaml_present(requirements_lines: List[str]):
        """Test that types-PyYAML is in requirements-dev.txt."""
        types_lines = [line for line in requirements_lines if line.startswith("types-PyYAML")]
        assert len(types_lines) >= 1, "types-PyYAML should be present in requirements-dev.txt"

    @staticmethod
    def test_pyyaml_version_specified(requirements_lines: List[str]):
        """Test that PyYAML has a version specifier."""
        pyyaml_lines = [line for line in requirements_lines if line.startswith("PyYAML")]

        for line in pyyaml_lines:
            assert ">=" in line or "==" in line, f"PyYAML should have version specifier: {line}"

    @staticmethod
    def test_pyyaml_version_at_least_6(requirements_lines: List[str]):
        """
        Ensure any 'PyYAML' entries with a '>=' minimum version in requirements_lines specify version 6.0 or higher.

        Parameters:
                requirements_lines (List[str]): List of non-empty, non-comment lines from requirements-dev.txt.
        """
        pyyaml_lines = [line for line in requirements_lines if line.startswith("PyYAML")]

        for line in pyyaml_lines:
            version_match = re.search(r">=(\d+\.\d+)", line)
            if version_match:
                version = float(version_match.group(1))
                assert version >= 6.0, f"PyYAML version should be >= 6.0, got {version}"

    @staticmethod
    def test_types_pyyaml_matches_pyyaml_version(requirements_lines: List[str]):
        """
        Assert that the major version of types-PyYAML equals the major version of PyYAML when both are specified with '>=' in the given requirements lines.

        Parameters:
            requirements_lines (List[str]): Non-comment, non-empty lines from requirements-dev.txt to inspect for `PyYAML>=` and `types-PyYAML>=` entries.
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
            assert (
                pyyaml_version == types_version
            ), f"types-PyYAML version {types_version} should match PyYAML version {pyyaml_version}"


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
        Check that at least one YAML workflow file exists under .github/workflows.

        Asserts that a file with extension `.yml` or `.yaml` is present in the repository's .github/workflows directory.
        """
        yaml_files_exist = False
        workflows_dir = Path(".github/workflows")

        if workflows_dir.exists():
            yaml_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
            yaml_files_exist = len(yaml_files) > 0

        assert yaml_files_exist, "Repository should have YAML files that need PyYAML for validation"


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

    def test_file_ends_with_newline(self, requirements_content: str):
        """Test that requirements-dev.txt ends with a newline."""
        assert requirements_content.endswith("\n"), "requirements-dev.txt should end with a newline"

    def test_no_duplicate_packages(self, requirements_content: str):
        """
        Verify the requirements content contains no duplicate package entries.

        Ignores blank lines and lines starting with '#'. Package names are taken as the text before any of the characters '>', '<', or '=' on each non-comment line; the test fails if any package name appears more than once.

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

    def test_all_lines_valid_format(self, requirements_content: str):
        """Test that all requirement lines have valid format."""
        for line_num, line in enumerate(requirements_content.split("\n"), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            valid_pattern = r"^[a-zA-Z0-9._-]+\[?[a-zA-Z0-9._,-]*\]?((>=|==|<=|>|<|~=)[0-9.]+.*)?$"
            assert re.match(valid_pattern, line), f"Line {line_num} has invalid format: {line}"

    def test_has_testing_dependencies(self, requirements_content: str):
        """Test that file includes essential testing dependencies."""
        essential_packages = ["pytest", "pytest-cov"]

        for package in essential_packages:
            assert package in requirements_content, f"requirements-dev.txt should include {package}"

    def test_has_linting_dependencies(self, requirements_content: str):
        """Test that file includes linting dependencies."""
        linting_packages = ["flake8", "pylint", "black"]

        for package in linting_packages:
            assert package in requirements_content, f"requirements-dev.txt should include {package}"


class TestPyYAMLCompatibility:
    """Test PyYAML compatibility and best practices."""

    def test_pyyaml_safe_load_available(self):
        """
        Verify that the installed PyYAML package exposes a `safe_load` symbol; skip the test if PyYAML is not installed.

        If the `yaml` module is importable the test asserts `yaml.safe_load` exists. If the module cannot be imported the test is skipped.
        """
        try:
            import yaml

            assert hasattr(yaml, "safe_load"), "PyYAML should provide safe_load function"
        except ImportError:
            pytest.skip("PyYAML not installed in test environment")

    def test_pyyaml_can_parse_workflow_files(self):
        """Test that PyYAML can parse actual workflow files."""
        try:
            import yaml

            workflow_file = Path(".github/workflows/pr-agent.yml")

            if workflow_file.exists():
                with open(workflow_file, "r", encoding="utf-8") as f:
                    content = yaml.safe_load(f)

                assert content is not None, "PyYAML should successfully parse workflow files"
                assert isinstance(content, dict), "Workflow files should parse to dictionaries"
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
        Ensure non-typing packages in the provided requirement lines include a minimum version specifier ('>=' or '==').

        Parameters:
            requirements_lines (List[str]): Non-empty, non-comment requirement lines to validate.
        """
        for line in requirements_lines:
            if not line.startswith("types-"):
                assert ">=" in line or "==" in line, f"Package should have version specifier: {line}"

    @staticmethod
    def test_pyyaml_and_types_both_pinned(requirements_lines: List[str]):
        """Test that both PyYAML and types-PyYAML have version pins."""
        pyyaml_pinned = any("PyYAML>=" in line for line in requirements_lines)
        types_pinned = any("types-PyYAML>=" in line for line in requirements_lines)

        assert pyyaml_pinned, "PyYAML should have version pin"
        assert types_pinned, "types-PyYAML should have version pin"
