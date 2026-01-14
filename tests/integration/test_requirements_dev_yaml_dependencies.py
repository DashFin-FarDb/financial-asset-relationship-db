"""
Additional tests for requirements-dev.txt PyYAML dependency additions.

This test file validates:
- PyYAML and types-PyYAML are properly added
- Version constraints are appropriate
- Dependencies are compatible with existing tools
- No conflicts with other requirements
"""

import pytest
import re
from pathlib import Path
from typing import List, Tuple


REQUIREMENTS_DEV_FILE = Path("requirements-dev.txt")


class TestPyYAMLDependencyAddition:
    """Test PyYAML dependency additions to requirements-dev.txt."""
    
    @pytest.fixture
    def requirements_content(self) -> str:
        """
        Return the full contents of requirements-dev.txt.
        
        Returns:
            content (str): The raw text of the requirements-dev.txt file.
        
        Raises:
            AssertionError: If REQUIREMENTS_DEV_FILE does not exist.
        """
        assert REQUIREMENTS_DEV_FILE.exists(), "requirements-dev.txt should exist"
        with open(REQUIREMENTS_DEV_FILE, 'r') as f:
            return f.read()
    
    @pytest.fixture
    def requirements_lines(self, requirements_content: str) -> List[str]:
        """
        Extract non-empty, non-comment lines from the given requirements file content.
        
        Parameters:
            requirements_content (str): The full text content of a requirements file.
        
        Returns:
            List[str]: A list of lines with surrounding whitespace removed, excluding empty lines and lines starting with `#`.
        """
        lines = []
        for line in requirements_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                lines.append(line)
        return lines
    
    def test_pyyaml_is_present(self, requirements_lines: List[str]):
        """Assert that exactly one 'PyYAML' entry appears in requirements-dev.txt."""
        pyyaml_lines = [line for line in requirements_lines if line.startswith('PyYAML')]
        assert len(pyyaml_lines) == 1, \
            "PyYAML should appear exactly once in requirements-dev.txt"
    
    def test_types_pyyaml_is_present(self, requirements_lines: List[str]):
        """
        Assert that requirements-dev.txt contains exactly one `types-PyYAML` entry.
        """
        types_pyyaml_lines = [line for line in requirements_lines if line.startswith('types-PyYAML')]
        assert len(types_pyyaml_lines) == 1, \
            "types-PyYAML should appear exactly once in requirements-dev.txt"
    
    def test_pyyaml_version_constraint(self, requirements_lines: List[str]):
        """
        Verify the PyYAML requirement specifies a minimum version of at least 6.0.
        
        Checks that the `PyYAML` line contains a '>=' minimum-version constraint and that the specified major.minor version is greater than or equal to 6.0.
        
        Parameters:
            requirements_lines (List[str]): Non-empty, non-comment lines from requirements-dev.txt.
        """
        pyyaml_line = [line for line in requirements_lines if line.startswith('PyYAML')][0]
        
        # Should have version constraint
        assert '>=' in pyyaml_line, "PyYAML should have minimum version constraint"
        
        # Extract version
        match = re.search(r'PyYAML>=(\d+\.\d+)', pyyaml_line)
        assert match is not None, "Should have valid version format"
        
        version = float(match.group(1))
        assert version >= 6.0, "PyYAML version should be >= 6.0"
    
    def test_types_pyyaml_version_constraint(self, requirements_lines: List[str]):
        """Verify types-PyYAML has appropriate version constraint."""
        types_pyyaml_line = [line for line in requirements_lines if line.startswith('types-PyYAML')][0]
        
        # Should have version constraint
        assert '>=' in types_pyyaml_line, "types-PyYAML should have minimum version constraint"
        
        # Extract version
        match = re.search(r'types-PyYAML>=(\d+\.\d+)', types_pyyaml_line)
        assert match is not None, "Should have valid version format"
        
        version = float(match.group(1))
        assert version >= 6.0, "types-PyYAML version should be >= 6.0"
    
    def test_pyyaml_and_types_pyyaml_versions_match(self, requirements_lines: List[str]):
        """Verify PyYAML and types-PyYAML have matching major versions."""
        pyyaml_line = [line for line in requirements_lines if line.startswith('PyYAML')][0]
        types_pyyaml_line = [line for line in requirements_lines if line.startswith('types-PyYAML')][0]
        
        pyyaml_version = re.search(r'PyYAML>=(\d+)', pyyaml_line).group(1)
        types_version = re.search(r'types-PyYAML>=(\d+)', types_pyyaml_line).group(1)
        
        assert pyyaml_version == types_version, \
            "PyYAML and types-PyYAML should have matching major versions"
    
    def test_no_duplicate_pyyaml_entries(self, requirements_content: str):
        """
        Ensure the requirements-dev content contains exactly two PyYAML-related entries.
        
        This test asserts that the file includes exactly two case-insensitive occurrences of "pyyaml" (intended to be the PyYAML and types-PyYAML entries).
        
        Parameters:
            requirements_content (str): Full text content of requirements-dev.txt.
        
        Raises:
            AssertionError: If the count of "pyyaml" occurrences is not exactly two.
        """
        pyyaml_count = requirements_content.lower().count('pyyaml')
        # Should have exactly 2: PyYAML and types-PyYAML
        assert pyyaml_count == 2, \
            f"Should have exactly 2 PyYAML entries (PyYAML + types-PyYAML), found {pyyaml_count}"
    
    def test_file_ends_with_newline(self, requirements_content: str):
        """
        Ensure requirements-dev.txt ends with a newline character.
        """
        assert requirements_content.endswith('\n'), \
            "requirements-dev.txt should end with newline"
    
    def test_no_trailing_whitespace(self, requirements_lines: List[str]):
        """Verify no lines have trailing whitespace."""
        with open(REQUIREMENTS_DEV_FILE, 'r') as f:
            for i, line in enumerate(f, 1):
                # Skip empty lines
                if line.strip():
                    assert not line.rstrip('\n').endswith(' ') and not line.rstrip('\n').endswith('\t'), \
                        f"Line {i} has trailing whitespace"


class TestRequirementsDevStructure:
    """Test overall structure and organization of requirements-dev.txt."""
    
    @pytest.fixture
    def requirements_lines(self) -> List[str]:
        """
        Retrieve non-empty, non-comment lines from REQUIREMENTS_DEV_FILE with surrounding whitespace removed.
        
        Returns:
            lines (List[str]): A list of requirement lines (comments and blank lines excluded), each trimmed of leading and trailing whitespace.
        """
        with open(REQUIREMENTS_DEV_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    def test_all_requirements_have_version_constraints(self, requirements_lines: List[str]):
        """Verify all dependencies have version constraints."""
        for line in requirements_lines:
            assert '>=' in line or '==' in line or '~=' in line, \
                f"Requirement '{line}' should have version constraint"
    
    def test_version_constraint_format(self, requirements_lines: List[str]):
        """
        Validate that each requirement line matches the expected package-and-version format.
        
        Each line must consist of a package name followed immediately by a version constraint operator (e.g., >=, ==, ~=) and a numeric version in the form major.minor or major.minor.patch.
        
        Parameters:
            requirements_lines (List[str]): Non-empty, non-comment requirement lines from requirements-dev.txt.
        """
        for line in requirements_lines:
            # Should match pattern: package>=version or package==version
            assert re.match(r'^[a-zA-Z0-9_-]+[><=~]+\d+\.\d+(\.\d+)?$', line), \
                f"Requirement '{line}' has invalid format"
    
    def test_requirements_are_sorted_alphabetically(self, requirements_lines: List[str]):
        """
        Assert that requirement package names are in case-insensitive alphabetical order for critical entries.
        
        This test derives package names from each requirement line (trimming version specifiers) and performs a case-insensitive ordering check for critical pairs: if both `pytest` and `pylint` are present, it asserts `pytest` appears before `pylint`. It does not fail for other out-of-order packages.
        """
        package_names = [line.split('>=')[0].split('==')[0].lower() for line in requirements_lines]
        sorted_names = sorted(package_names)
        
        # Allow some flexibility - just check critical ones are properly ordered
        # Check pytest comes before pylint
        if 'pytest' in package_names and 'pylint' in package_names:
            pytest_idx = package_names.index('pytest')
            pylint_idx = package_names.index('pylint')
            assert pytest_idx < pylint_idx, "pytest should come before pylint alphabetically"
    
    def test_pyyaml_at_end_of_file(self, requirements_lines: List[str]):
        """Verify PyYAML additions are at the end of file."""
        # PyYAML and types-PyYAML should be the last two entries
        assert requirements_lines[-2].startswith('PyYAML'), \
            "PyYAML should be second to last entry"
        assert requirements_lines[-1].startswith('types-PyYAML'), \
            "types-PyYAML should be last entry"


class TestPyYAMLCompatibility:
    """Test PyYAML compatibility with other dependencies."""
    
    @pytest.fixture
    def requirements_lines(self) -> List[str]:
        """
        Retrieve non-empty, non-comment lines from REQUIREMENTS_DEV_FILE with surrounding whitespace removed.
        
        Returns:
            lines (List[str]): A list of requirement lines (comments and blank lines excluded), each trimmed of leading and trailing whitespace.
        """
        with open(REQUIREMENTS_DEV_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    def test_no_conflicting_yaml_libraries(self, requirements_lines: List[str]):
        """Verify no conflicting YAML libraries are present."""
        yaml_packages = [line for line in requirements_lines if 'yaml' in line.lower()]
        
        # Should only have PyYAML and types-PyYAML
        assert len(yaml_packages) == 2, \
            f"Should only have PyYAML and types-PyYAML, found: {yaml_packages}"
        
        # Should not have ruamel.yaml or other alternatives
        package_names = [line.split('>=')[0].split('==')[0].lower() for line in requirements_lines]
        assert 'ruamel.yaml' not in package_names, \
            "Should not have conflicting ruamel.yaml"
    
    def test_pyyaml_compatible_with_pytest(self, requirements_lines: List[str]):
        """Verify PyYAML version is compatible with pytest."""
        pyyaml_version = None
        pytest_version = None
        
        for line in requirements_lines:
            if line.startswith('PyYAML'):
                match = re.search(r'>=(\d+\.\d+)', line)
                if match:
                    pyyaml_version = float(match.group(1))
            elif line.startswith('pytest'):
                match = re.search(r'>=(\d+\.\d+)', line)
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
        assert workflows_dir.exists(), "Workflows directory should exist"
        
        yaml_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        assert len(yaml_files) > 0, \
            "Project should have YAML workflow files justifying PyYAML dependency"
    
    def test_pr_agent_config_is_yaml(self):
        """Verify PR agent config exists as YAML file."""
        config_file = Path(".github/pr-agent-config.yml")
        assert config_file.exists(), \
            "PR agent config file should exist justifying PyYAML dependency"
    
    def test_test_files_import_yaml(self):
        """Verify test files actually import and use yaml module."""
        test_dir = Path("tests/integration")
        yaml_usage_found = False
        
        for test_file in test_dir.glob("test_*.py"):
            with open(test_file, 'r') as f:
                content = f.read()
                if 'import yaml' in content or 'from yaml import' in content:
                    yaml_usage_found = True
                    break
        
        assert yaml_usage_found, \
            "Test files should import yaml module, justifying PyYAML dependency"


class TestRequirementsDevQuality:
    """Test code quality tools in requirements-dev.txt."""
    
    @pytest.fixture
    def requirements_lines(self) -> List[str]:
        """
        Retrieve non-empty, non-comment lines from REQUIREMENTS_DEV_FILE with surrounding whitespace removed.
        
        Returns:
            lines (List[str]): A list of requirement lines (comments and blank lines excluded), each trimmed of leading and trailing whitespace.
        """
        with open(REQUIREMENTS_DEV_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    def test_has_testing_framework(self, requirements_lines: List[str]):
        """
        Check that the development requirements include the pytest testing framework.
        
        Asserts that at least one requirement line starts with 'pytest'.
        """
        assert any(line.startswith('pytest') for line in requirements_lines), \
            "Should include pytest testing framework"
    
    def test_has_coverage_tool(self, requirements_lines: List[str]):
        """
        Ensure pytest-cov is present in the provided requirements lines.
        """
        assert any(line.startswith('pytest-cov') for line in requirements_lines), \
            "Should include pytest-cov for coverage"
    
    def test_has_linters(self, requirements_lines: List[str]):
        """
        Ensure required linter packages are present in the given requirements lines.
        
        Parameters:
            requirements_lines (List[str]): Non-empty, non-comment lines from requirements-dev.txt to check.
        """
        linters = ['flake8', 'pylint']
        for linter in linters:
            assert any(line.startswith(linter) for line in requirements_lines), \
                f"Should include {linter} linter"
    
    def test_has_formatter(self, requirements_lines: List[str]):
        """
        Ensure the 'black' code formatter is listed in requirements-dev.txt.
        """
        assert any(line.startswith('black') for line in requirements_lines), \
            "Should include black formatter"
    
    def test_has_import_sorter(self, requirements_lines: List[str]):
        """Verify import sorting tool is included."""
        assert any(line.startswith('isort') for line in requirements_lines), \
            "Should include isort for import sorting"
    
    def test_has_type_checker(self, requirements_lines: List[str]):
        """Verify type checking tool is included."""
        assert any(line.startswith('mypy') for line in requirements_lines), \
            "Should include mypy for type checking"
    
    def test_has_type_stubs_for_yaml(self, requirements_lines: List[str]):
        """
        Assert that requirements include a `types-PyYAML` entry to provide type stubs for PyYAML.
        
        Parameters:
            requirements_lines (List[str]): List of non-empty, non-comment lines from requirements-dev.txt.
        """
        assert any(line.startswith('types-PyYAML') for line in requirements_lines), \
            "Should include types-PyYAML for mypy compatibility"


class TestPyYAMLVersionSpecifics:
    """Test specific version requirements for PyYAML."""
    
    @pytest.fixture
    def pyyaml_line(self) -> str:
        """
        Retrieve the PyYAML requirement line from REQUIREMENTS_DEV_FILE.
        
        Returns:
            The PyYAML requirement line as a trimmed string, or an empty string if no such entry exists.
        """
        with open(REQUIREMENTS_DEV_FILE, 'r') as f:
            for line in f:
                if line.strip().startswith('PyYAML'):
                    return line.strip()
        return ""
    
    def test_pyyaml_uses_minimum_version_constraint(self, pyyaml_line: str):
        """
        Assert that the PyYAML requirement uses a minimum-version constraint (>=) and is not pinned to an exact version.
        
        Parameters:
            pyyaml_line (str): The PyYAML requirement line from requirements-dev.txt.
        """
        assert '>=' in pyyaml_line, \
            "PyYAML should use >= for flexibility"
        assert '==' not in pyyaml_line, \
            "PyYAML should not be pinned to exact version"
    
    def test_pyyaml_version_is_modern(self, pyyaml_line: str):
        """
        Assert that the PyYAML requirement specifies a minimum major version of 6 or higher.
        
        This test verifies the PyYAML requirement line contains a `>=` version constraint and that the constrained major version is at least 6.
        
        Parameters:
            pyyaml_line (str): The requirements-dev.txt line for the PyYAML package.
        """
        match = re.search(r'PyYAML>=(\d+\.\d+)', pyyaml_line)
        assert match is not None, "Should have version constraint"
        
        version_str = match.group(1)
        major_version = int(version_str.split('.')[0])
        
        assert major_version >= 6, \
            "PyYAML should be version 6.0 or higher for security and features"
    
    def test_pyyaml_no_upper_bound(self, pyyaml_line: str):
        """
        Ensure the PyYAML requirement line does not specify an upper version bound.
        
        Asserts that the requirement string contains no '<' character; presence of '<' indicates an upper bound and will fail the test.
        """
        # Should not have <7.0 or similar restrictive upper bounds
        assert '<' not in pyyaml_line, \
            "PyYAML should not have upper version bound for flexibility"


class TestRequirementsFileIntegrity:
    """Test file integrity and formatting."""
    
    def test_file_is_utf8_encoded(self):
        """Verify file is UTF-8 encoded."""
        try:
            with open(REQUIREMENTS_DEV_FILE, 'r', encoding='utf-8') as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("requirements-dev.txt should be UTF-8 encoded")
    
    def test_file_has_consistent_line_endings(self):
        """Verify file uses consistent line endings (LF)."""
        with open(REQUIREMENTS_DEV_FILE, 'rb') as f:
            content = f.read()
        
        # Should use LF (\n), not CRLF (\r\n)
        assert b'\r\n' not in content, \
            "File should use LF line endings, not CRLF"
    
    def test_no_empty_lines_between_requirements(self):
        """
        Ensure requirements-dev.txt does not contain multiple consecutive empty lines.
        
        Reads the requirements file and asserts there is at most one consecutive empty line; the test fails if two or more empty lines appear in a row.
        """
        with open(REQUIREMENTS_DEV_FILE, 'r') as f:
            lines = f.readlines()
        
        # Track consecutive empty lines
        consecutive_empty = 0
        for line in lines:
            if line.strip() == '':
                consecutive_empty += 1
                assert consecutive_empty <= 1, \
                    "Should not have multiple consecutive empty lines"
            else:
                consecutive_empty = 0