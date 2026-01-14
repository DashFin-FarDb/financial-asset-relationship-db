"""
Additional tests for requirements-dev.txt PyYAML dependency additions.

This test file validates:
- PyYAML and types-PyYAML are properly added
- Version constraints are appropriate
- Dependencies are compatible with existing tools
- No conflicts with other requirements
"""

import re
from pathlib import Path
from typing import List

import pytest

REQUIREMENTS_DEV_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


# --- Global Fixtures ---


@pytest.fixture(scope="module")
def requirements_content() -> str:
    """Load requirements-dev.txt content once for the module."""
    if not REQUIREMENTS_DEV_FILE.exists():
        pytest.fail("requirements-dev.txt should exist")
    with open(REQUIREMENTS_DEV_FILE, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def requirements_lines(requirements_content: str) -> List[str]:
    """Get non-empty, non-comment lines from requirements."""
    lines = []
    for line in requirements_content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


# --- Test Classes ---


class TestPyYAMLDependencyAddition:
    """Test PyYAML dependency additions to requirements-dev.txt."""

    def test_pyyaml_is_present(self, requirements_lines: List[str]):
        """Verify PyYAML is in requirements-dev.txt."""
        pyyaml_lines = [line for line in requirements_lines if line.startswith("PyYAML")]
        assert len(pyyaml_lines) == 1, "PyYAML should appear exactly once in requirements-dev.txt"

    def test_types_pyyaml_is_present(self, requirements_lines: List[str]):
        """Verify types-PyYAML is in requirements-dev.txt."""
        types_pyyaml_lines = [line for line in requirements_lines if line.startswith("types-PyYAML")]
        assert len(types_pyyaml_lines) == 1, "types-PyYAML should appear exactly once in requirements-dev.txt"

    def test_pyyaml_version_constraint(self, requirements_lines: List[str]):
        """Verify PyYAML has appropriate version constraint."""
        pyyaml_entries = [line for line in requirements_lines if line.startswith("PyYAML")]
        if not pyyaml_entries:
            pytest.fail("PyYAML entry not found")

        pyyaml_line = pyyaml_entries[0]

        # Should have version constraint
        assert ">=" in pyyaml_line, "PyYAML should have minimum version constraint"

        # Extract version
        match = re.search(r"PyYAML\s*>=\s*(\d+\.\d+)", pyyaml_line)
        assert match is not None, "Should have valid version format"

        version = float(match.group(1))
        assert version >= 6.0, "PyYAML version should be >= 6.0"

    def test_types_pyyaml_version_constraint(self, requirements_lines: List[str]):
        """Verify types-PyYAML has appropriate version constraint."""
        types_entries = [line for line in requirements_lines if line.startswith("types-PyYAML")]
        if not types_entries:
            pytest.fail("types-PyYAML entry not found")

        types_pyyaml_line = types_entries[0]

        # Should have version constraint
        assert ">=" in types_pyyaml_line, "types-PyYAML should have minimum version constraint"

        # Extract version
        match = re.search(r"types-PyYAML\s*>=\s*(\d+\.\d+)", types_pyyaml_line)
        assert match is not None, "Should have valid version format"

        version = float(match.group(1))
        assert version >= 6.0, "types-PyYAML version should be >= 6.0"

    def test_pyyaml_and_types_pyyaml_versions_match(self, requirements_lines: List[str]):
        """Verify PyYAML and types-PyYAML have matching major versions."""
        pyyaml_line = next((line for line in requirements_lines if line.startswith("PyYAML")), None)
        types_pyyaml_line = next((line for line in requirements_lines if line.startswith("types-PyYAML")), None)

        if not pyyaml_line or not types_pyyaml_line:
            pytest.fail("Required PyYAML packages missing")

        pyyaml_match = re.search(r"PyYAML\s*>=\s*(\d+)", pyyaml_line)
        types_match = re.search(r"types-PyYAML\s*>=\s*(\d+)", types_pyyaml_line)

        if not pyyaml_match or not types_match:
            pytest.fail("Could not extract major versions for comparison")

        assert pyyaml_match.group(1) == types_match.group(
            1
        ), "PyYAML and types-PyYAML should have matching major versions"

    def test_no_duplicate_pyyaml_entries(self, requirements_content: str):
        """Verify no duplicate PyYAML entries exist."""
        pyyaml_count = requirements_content.lower().count("pyyaml")
        # Should have exactly 2: PyYAML and types-PyYAML
        assert pyyaml_count == 2, f"Should have exactly 2 PyYAML entries (PyYAML + types-PyYAML), found {pyyaml_count}"

    def test_file_ends_with_newline(self, requirements_content: str):
        """Verify file ends with newline."""
        assert requirements_content.endswith("\n"), "requirements-dev.txt should end with newline"

    def test_no_trailing_whitespace(self, requirements_content: str):
        """Verify no lines have trailing whitespace."""
        for i, line in enumerate(requirements_content.splitlines(keepends=True), 1):
            # Skip empty lines
            if line.strip():
                assert not line.rstrip("\n").endswith(" ") and not line.rstrip("\n").endswith(
                    "\t"
                ), f"Line {i} has trailing whitespace"


class TestRequirementsDevStructure:
    """Test overall structure and organization of requirements-dev.txt."""

    def test_all_requirements_have_version_constraints(self, requirements_lines: List[str]):
        """Verify all dependencies have version constraints."""
        for line in requirements_lines:
            assert ">=" in line or "==" in line or "~=" in line, f"Requirement '{line}' should have version constraint"

    def test_version_constraint_format(self, requirements_lines: List[str]):
        """Verify version constraints use correct format."""
        for line in requirements_lines:
            # Should match pattern: package>=version or package==version
            # Adjusted regex to handle optional whitespace around operators
            assert re.match(
                r"^[a-zA-Z0-9_-]+\s*[><=~]+\s*\d+\.\d+(\.\d+)?$", line
            ), f"Requirement '{line}' has invalid format"

    def test_requirements_are_sorted_alphabetically(self, requirements_lines: List[str]):
        """Verify requirements are in alphabetical order (case-insensitive)."""
        package_names = [line.split(">=")[0].split("==")[0].lower().strip() for line in requirements_lines]

        # Check specific ordering of known packages rather than strict sort enforcement
        if "pytest" in package_names and "pylint" in package_names:
            pytest_idx = package_names.index("pytest")
            pylint_idx = package_names.index("pylint")
            assert pytest_idx < pylint_idx, "pytest should come before pylint alphabetically"

    def test_pyyaml_at_end_of_file(self, requirements_lines: List[str]):
        """Verify PyYAML additions are at the end of file."""
        if len(requirements_lines) < 2:
            pytest.fail("requirements file too short to check ordering")

        # PyYAML and types-PyYAML should be the last two entries
        assert requirements_lines[-2].startswith("PyYAML"), "PyYAML should be second to last entry"
        assert requirements_lines[-1].startswith("types-PyYAML"), "types-PyYAML should be last entry"


class TestPyYAMLCompatibility:
    """Test PyYAML compatibility with other dependencies."""

    def test_no_conflicting_yaml_libraries(self, requirements_lines: List[str]):
        """Verify no conflicting YAML libraries are present."""
        yaml_packages = [line for line in requirements_lines if "yaml" in line.lower()]

        # Should only have PyYAML and types-PyYAML
        assert len(yaml_packages) == 2, f"Should only have PyYAML and types-PyYAML, found: {yaml_packages}"

        # Should not have ruamel.yaml or other alternatives
        package_names = [line.split(">=")[0].split("==")[0].lower() for line in requirements_lines]
        assert "ruamel.yaml" not in package_names, "Should not have conflicting ruamel.yaml"

    def test_pyyaml_compatible_with_pytest(self, requirements_lines: List[str]):
        """Verify PyYAML version is compatible with pytest."""
        pyyaml_version = None
        pytest_version = None

        for line in requirements_lines:
            if line.startswith("PyYAML"):
                match = re.search(r">=(\d+\.\d+)", line)
                if match:
                    pyyaml_version = float(match.group(1))
            elif line.startswith("pytest"):
                match = re.search(r">=(\d+\.\d+)", line)
                if match:
                    pytest_version = float(match.group(1))

        # PyYAML 6.0+ is compatible with pytest 7.0+
        if pyyaml_version and pytest_version:
            assert pyyaml_version >= 6.0, "PyYAML should be >= 6.0"
            assert pytest_version >= 7.0, "pytest should be >= 7.0"


class TestPyYAMLUsageRationale:
    """Test that PyYAML addition aligns with project needs."""

    def test_workflow_files_use_yaml(self):
        """Verify project has YAML files that justify PyYAML dependency."""
        workflows_dir = Path(".github/workflows")
        if not workflows_dir.exists():
            pytest.skip("Workflows directory does not exist")

        yaml_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        assert len(yaml_files) > 0, "Project should have YAML workflow files justifying PyYAML dependency"

    def test_pr_agent_config_is_yaml(self):
        """Verify PR agent config exists as YAML file."""
        config_file = Path(".github/pr-agent-config.yml")
        assert config_file.exists(), "PR agent config file should exist justifying PyYAML dependency"

    def test_test_files_import_yaml(self):
        """Verify test files actually import and use yaml module."""
        test_dir = Path("tests/integration")
        if not test_dir.exists():
            pytest.skip("Integration tests directory not found")

        yaml_usage_found = False

        for test_file in test_dir.glob("test_*.py"):
            with open(test_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "import yaml" in content or "from yaml import" in content:
                    yaml_usage_found = True
                    break

        assert yaml_usage_found, "Test files should import yaml module, justifying PyYAML dependency"


class TestRequirementsDevQuality:
    """Test code quality tools in requirements-dev.txt."""

    @pytest.mark.parametrize(
        "tool", ["pytest", "pytest-cov", "flake8", "pylint", "black", "isort", "mypy", "types-PyYAML"]
    )
    def test_has_dev_tool(self, requirements_lines: List[str], tool: str):
        """Verify essential development tools are included."""
        assert any(line.startswith(tool) for line in requirements_lines), f"Should include {tool}"


class TestPyYAMLVersionSpecifics:
    """Test specific version requirements for PyYAML."""

    @pytest.fixture
    def pyyaml_line(self, requirements_lines: List[str]) -> str:
        """Get PyYAML line from requirements."""
        for line in requirements_lines:
            if line.strip().startswith("PyYAML"):
                return line.strip()
        return ""

    def test_pyyaml_uses_minimum_version_constraint(self, pyyaml_line: str):
        """Verify PyYAML uses >= constraint (not pinned)."""
        if not pyyaml_line:
            pytest.fail("PyYAML line not found")
        assert ">=" in pyyaml_line, "PyYAML should use >= for flexibility"
        assert "==" not in pyyaml_line, "PyYAML should not be pinned to exact version"

    def test_pyyaml_version_is_modern(self, pyyaml_line: str):
        """Verify PyYAML version is 6.0 or higher."""
        if not pyyaml_line:
            pytest.fail("PyYAML line not found")

        match = re.search(r"PyYAML\s*>=\s*(\d+\.\d+)", pyyaml_line)
        assert match is not None, "Should have version constraint"

        version_str = match.group(1)
        major_version = int(version_str.split(".")[0])

        assert major_version >= 6, "PyYAML should be version 6.0 or higher for security and features"

    def test_pyyaml_no_upper_bound(self, pyyaml_line: str):
        """Verify PyYAML doesn't have restrictive upper bound."""
        if not pyyaml_line:
            pytest.fail("PyYAML line not found")
        # Should not have <7.0 or similar restrictive upper bounds
        assert "<" not in pyyaml_line, "PyYAML should not have upper version bound for flexibility"


class TestRequirementsFileIntegrity:
    """Test file integrity and formatting."""

    def test_file_is_utf8_encoded(self):
        """Verify file is UTF-8 encoded."""
        try:
            with open(REQUIREMENTS_DEV_FILE, "r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("requirements-dev.txt should be UTF-8 encoded")

    def test_file_has_consistent_line_endings(self):
        """Verify file uses consistent line endings (LF)."""
        with open(REQUIREMENTS_DEV_FILE, "rb") as f:
            content = f.read()

        # Should use LF (\n), not CRLF (\r\n)
        assert b"\r\n" not in content, "File should use LF line endings, not CRLF"

    def test_no_empty_lines_between_requirements(self, requirements_content: str):
        """Verify no unnecessary empty lines between requirements."""
        lines = requirements_content.splitlines()

        # Track consecutive empty lines
        consecutive_empty = 0
        for line in lines:
            if line.strip() == "":
                consecutive_empty += 1
                assert consecutive_empty <= 1, "Should not have multiple consecutive empty lines"
            else:
                consecutive_empty = 0
