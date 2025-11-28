"""
Comprehensive tests for PyYAML dependencies in requirements-dev.txt.
Tests the addition of PyYAML and types-PyYAML dependencies.
"""

import pytest
import re
from pathlib import Path
from typing import List


class TestPyYAMLDependencyAddition:
    """Test that PyYAML dependencies were properly added."""
    
    @pytest.fixture
    def requirements_file(self) -> Path:
        """
        Path to the repository's requirements-dev.txt file.
        
        Returns:
            Path: Path object pointing to requirements-dev.txt in the repository root.
        """
        return Path('requirements-dev.txt')
    
    @pytest.fixture
    def requirements_content(self, requirements_file: Path) -> str:
        """
        Read and return the full contents of the requirements file.
        
        Returns:
            str: The file contents as a single string.
        """
        with open(requirements_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    @pytest.fixture
    def requirements_lines(self, requirements_content: str) -> List[str]:
        """
        Extract non-comment, non-empty lines from the given requirements content.
        
        Parameters:
            requirements_content (str): Full contents of a requirements file.
        
        Returns:
            List[str]: Requirement lines with surrounding whitespace removed, excluding blank lines and lines that start with `#`.
        """
        lines = []
        for line in requirements_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                lines.append(line)
        return lines
    
    def test_pyyaml_present(self, requirements_lines: List[str]):
        """Test that PyYAML is in requirements-dev.txt."""
        pyyaml_lines = [line for line in requirements_lines if line.startswith('PyYAML')]
        assert len(pyyaml_lines) >= 1, \
            "PyYAML should be present in requirements-dev.txt"
    
    def test_types_pyyaml_present(self, requirements_lines: List[str]):
        """Test that types-PyYAML is in requirements-dev.txt."""
        types_lines = [line for line in requirements_lines if line.startswith('types-PyYAML')]
        assert len(types_lines) >= 1, \
            "types-PyYAML should be present in requirements-dev.txt"
    
    def test_pyyaml_version_specified(self, requirements_lines: List[str]):
        """Test that PyYAML has a version specifier."""
        pyyaml_lines = [line for line in requirements_lines if line.startswith('PyYAML')]
        
        for line in pyyaml_lines:
            assert '>=' in line or '==' in line, \
                f"PyYAML should have version specifier: {line}"
    
    def test_pyyaml_version_at_least_6(self, requirements_lines: List[str]):
        """
        Assert that every PyYAML requirement line using a '>=' specifier pins the minimum version to 6.0 or higher.
        
        This only checks PyYAML lines that include a '>=<major>.<minor>' specifier; lines without such a specifier are not validated by this test.
        """
        pyyaml_lines = [line for line in requirements_lines if line.startswith('PyYAML')]
        
        for line in pyyaml_lines:
            version_match = re.search(r'>=(\d+\.\d+)', line)
            if version_match:
                version = float(version_match.group(1))
                assert version >= 6.0, \
                    f"PyYAML version should be >= 6.0, got {version}"
    
    def test_types_pyyaml_matches_pyyaml_version(self, requirements_lines: List[str]):
        """
        Check that the major version specified for `types-PyYAML` matches the major version specified for `PyYAML`.
        
        This inspects lines that start with `PyYAML>=` and `types-PyYAML>=`, extracts the leading integer of the `>=` version specifier, and asserts the two major versions are equal when both are present. If either package is not present with a `>=` specifier, the test is skipped (no assertion is made).
        
        Parameters:
            requirements_lines (List[str]): Non-empty, non-comment lines from requirements-dev.txt.
        """
        pyyaml_version = None
        types_version = None
        
        for line in requirements_lines:
            if line.startswith('PyYAML>='):
                pyyaml_match = re.search(r'>=(\d+)', line)
                if pyyaml_match:
                    pyyaml_version = int(pyyaml_match.group(1))
            
            if line.startswith('types-PyYAML>='):
                types_match = re.search(r'>=(\d+)', line)
                if types_match:
                    types_version = int(types_match.group(1))
        
        if pyyaml_version and types_version:
            assert pyyaml_version == types_version, \
                f"types-PyYAML version {types_version} should match PyYAML version {pyyaml_version}"


class TestRequirementsDevYAMLUsage:
    """Test that PyYAML is needed for workflow validation."""
    
    def test_pyyaml_used_in_workflow_tests(self):
        """
        Check that at least one workflow-related test file imports PyYAML.
        
        Reads tests/integration/test_github_workflows.py and
        tests/integration/test_pr_agent_workflow_specific.py (if they exist)
        and asserts that at least one contains the literal "import yaml".
        """
        workflow_test_files = [
            Path('tests/integration/test_github_workflows.py'),
            Path('tests/integration/test_pr_agent_workflow_specific.py'),
        ]
        
        pyyaml_used = False
        for test_file in workflow_test_files:
            if test_file.exists():
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'import yaml' in content:
                        pyyaml_used = True
                        break
        
        assert pyyaml_used, \
            "PyYAML should be imported in workflow test files"
    
    def test_yaml_files_exist_in_repo(self):
        """Test that YAML files exist that would need PyYAML for testing."""
        yaml_files_exist = False
        workflows_dir = Path('.github/workflows')
        
        if workflows_dir.exists():
            yaml_files = list(workflows_dir.glob('*.yml')) + list(workflows_dir.glob('*.yaml'))
            yaml_files_exist = len(yaml_files) > 0
        
        assert yaml_files_exist, \
            "Repository should have YAML files that need PyYAML for validation"


class TestRequirementsDevCompleteness:
    """Test that requirements-dev.txt is complete and well-formed."""
    
    @pytest.fixture
    def requirements_content(self) -> str:
        """
        Read the contents of requirements-dev.txt.
        
        Returns:
            str: The full contents of requirements-dev.txt decoded as UTF-8.
        """
        with open('requirements-dev.txt', 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_file_ends_with_newline(self, requirements_content: str):
        """Test that requirements-dev.txt ends with a newline."""
        assert requirements_content.endswith('\n'), \
            "requirements-dev.txt should end with a newline"
    
    def test_no_duplicate_packages(self, requirements_content: str):
        """Test that no package is listed multiple times."""
        packages = []
        for line in requirements_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                package = re.split(r'[>=<]', line)[0].strip()
                packages.append(package)
        
        duplicates = [pkg for pkg in set(packages) if packages.count(pkg) > 1]
        assert len(duplicates) == 0, \
            f"Found duplicate packages: {duplicates}"
    
    def test_all_lines_valid_format(self, requirements_content: str):
        """
        Validate each non-empty, non-comment line in the requirements content matches the allowed package/version specifier pattern.
        
        Parameters:
            requirements_content (str): Full text of the requirements file to validate.
        
        Raises:
            AssertionError: If any non-empty, non-comment line does not conform to the expected package specifier regex; the assertion message includes the line number and offending line.
        """
        for line_num, line in enumerate(requirements_content.split('\n'), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            valid_pattern = r'^[a-zA-Z0-9._-]+\[?[a-zA-Z0-9._,-]*\]?((>=|==|<=|>|<|~=)[0-9.]+.*)?$'
            assert re.match(valid_pattern, line), \
                f"Line {line_num} has invalid format: {line}"
    
    def test_has_testing_dependencies(self, requirements_content: str):
        """Test that file includes essential testing dependencies."""
        essential_packages = ['pytest', 'pytest-cov']
        
        for package in essential_packages:
            assert package in requirements_content, \
                f"requirements-dev.txt should include {package}"
    
    def test_has_linting_dependencies(self, requirements_content: str):
        """
        Verify that requirements-dev.txt contains the essential linting and formatting packages.
        
        Checks that the file includes `flake8`, `pylint` and `black`; raises an assertion if any expected package is missing.
        """
        linting_packages = ['flake8', 'pylint', 'black']
        
        for package in linting_packages:
            assert package in requirements_content, \
                f"requirements-dev.txt should include {package}"


class TestPyYAMLCompatibility:
    """Test PyYAML compatibility and best practices."""
    
    def test_pyyaml_safe_load_available(self):
        """Test that PyYAML's safe_load function can be imported."""
        try:
            import yaml
            assert hasattr(yaml, 'safe_load'), \
                "PyYAML should provide safe_load function"
        except ImportError:
            pytest.skip("PyYAML not installed in test environment")
    
    def test_pyyaml_can_parse_workflow_files(self):
        """Test that PyYAML can parse actual workflow files."""
        try:
            import yaml
            workflow_file = Path('.github/workflows/pr-agent.yml')
            
            if workflow_file.exists():
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    content = yaml.safe_load(f)
                
                assert content is not None, \
                    "PyYAML should successfully parse workflow files"
                assert isinstance(content, dict), \
                    "Workflow files should parse to dictionaries"
        except ImportError:
            pytest.skip("PyYAML not installed in test environment")


class TestRequirementsDevVersionPinning:
    """Test version pinning strategy in requirements-dev.txt."""
    
    @pytest.fixture
    def requirements_lines(self) -> List[str]:
        """
        Retrieve non-empty, non-comment lines from requirements-dev.txt.
        
        Returns:
            List[str]: Lines from requirements-dev.txt in file order that are not empty and do not start with '#'.
        """
        with open('requirements-dev.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                lines.append(line)
        return lines
    
    def test_uses_minimum_version_specifiers(self, requirements_lines: List[str]):
        """Test that packages use >= for minimum version."""
        for line in requirements_lines:
            if not line.startswith('types-'):
                assert '>=' in line or '==' in line, \
                    f"Package should have version specifier: {line}"
    
    def test_pyyaml_and_types_both_pinned(self, requirements_lines: List[str]):
        """
        Assert that both PyYAML and types-PyYAML are pinned with minimum-version specifiers in the provided requirement lines.
        
        Checks for the presence of `PyYAML>=` and `types-PyYAML>=` entries in `requirements_lines` and fails the test if either is missing.
        """
        pyyaml_pinned = any(
            'PyYAML>=' in line for line in requirements_lines
        )
        types_pinned = any(
            'types-PyYAML>=' in line for line in requirements_lines
        )
        
        assert pyyaml_pinned, "PyYAML should have version pin"
        assert types_pinned, "types-PyYAML should have version pin"