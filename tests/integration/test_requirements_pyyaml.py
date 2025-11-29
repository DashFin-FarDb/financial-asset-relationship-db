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
        Get the path to the repository's requirements-dev.txt file.
        
        Returns:
            path (Path): Path to requirements-dev.txt in the repository root.
        """
        return Path('requirements-dev.txt')
    
    @pytest.fixture
    def requirements_content(self, requirements_file: Path) -> str:
        """
        Read and return the contents of the requirements file.
        
        Parameters:
            requirements_file (Path): Path to the requirements-dev.txt file to read.
        
        Returns:
            content (str): The file contents decoded as UTF-8.
        """
        with open(requirements_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    @pytest.fixture
    def requirements_lines(self, requirements_content: str) -> List[str]:
        """
        Extract non-empty, non-comment lines from a requirements file content.
        
        Parameters:
            requirements_content (str): Full text of a requirements file.
        
        Returns:
            List[str]: Lines that are neither empty nor start with `#`, trimmed of surrounding whitespace.
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
        """Test that PyYAML version is at least 6.0."""
        pyyaml_lines = [line for line in requirements_lines if line.startswith('PyYAML')]
        
        for line in pyyaml_lines:
            version_match = re.search(r'>=(\d+\.\d+)', line)
            if version_match:
                version = float(version_match.group(1))
                assert version >= 6.0, \
                    f"PyYAML version should be >= 6.0, got {version}"
    
    def test_types_pyyaml_matches_pyyaml_version(self, requirements_lines: List[str]):
        """Test that types-PyYAML version matches PyYAML major version."""
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
        """Test that PyYAML is imported in workflow test files."""
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
        Read and return the contents of requirements-dev.txt.
        
        Returns:
            requirements (str): The full text of requirements-dev.txt.
        """
        with open('requirements-dev.txt', 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_file_ends_with_newline(self, requirements_content: str):
        """Test that requirements-dev.txt ends with a newline."""
        assert requirements_content.endswith('\n'), \
            "requirements-dev.txt should end with a newline"
    
    def test_no_duplicate_packages(self, requirements_content: str):
        """
        Assert that no package name appears more than once in the provided requirements content.
        
        This test inspects each non-empty, non-comment line in `requirements_content`, extracts the package name before any version specifier (for example, before `>=`, `==`, `<`, `>`), and fails if any package name occurs multiple times.
        
        Parameters:
        	requirements_content (str): Full text of a requirements file (e.g. requirements-dev.txt).
        """
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
        Validate that every non-empty, non-comment line in `requirements_content` is a well-formed requirement specification.
        
        A well-formed line contains a package name (letters, digits, dot, underscore or hyphen), optional extras in square brackets, and an optional version specifier using one of the operators >=, ==, <=, >, <, ~= followed by a version string.
        
        Parameters:
            requirements_content (str): Full text of a requirements file to validate line-by-line.
        """
        for line_num, line in enumerate(requirements_content.split('\n'), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            valid_pattern = r'^[a-zA-Z0-9._-]+\[?[a-zA-Z0-9._,-]*\]?((>=|==|<=|>|<|~=)[0-9.]+.*)?$'
            assert re.match(valid_pattern, line), \
                f"Line {line_num} has invalid format: {line}"
    
    def test_has_testing_dependencies(self, requirements_content: str):
        """
        Verify the requirements-dev.txt content includes essential testing packages.
        
        Checks that the provided requirements file content contains the testing dependencies 'pytest' and 'pytest-cov'.
        
        Parameters:
            requirements_content (str): Full text content of requirements-dev.txt to be checked.
        """
        essential_packages = ['pytest', 'pytest-cov']
        
        for package in essential_packages:
            assert package in requirements_content, \
                f"requirements-dev.txt should include {package}"
    
    def test_has_linting_dependencies(self, requirements_content: str):
        """Test that file includes linting dependencies."""
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
        Return the non-empty, non-comment lines from the repository's requirements-dev.txt.
        
        Returns:
            lines (List[str]): A list of requirement specification lines with leading/trailing whitespace removed; blank lines and lines starting with `#` are excluded.
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
        """
        Assert every non-typed requirement line contains a minimum version specifier.
        
        Lines starting with 'types-' are ignored. Each remaining requirement line must include either '>=' or '==' to indicate a minimum or pinned version respectively.
        
        Parameters:
            requirements_lines (List[str]): Non-empty, non-comment lines from requirements-dev.txt to validate.
        """
        for line in requirements_lines:
            if not line.startswith('types-'):
                assert '>=' in line or '==' in line, \
                    f"Package should have version specifier: {line}"
    
    def test_pyyaml_and_types_both_pinned(self, requirements_lines: List[str]):
        """Test that both PyYAML and types-PyYAML have version pins."""
        pyyaml_pinned = any(
            'PyYAML>=' in line for line in requirements_lines
        )
        types_pinned = any(
            'types-PyYAML>=' in line for line in requirements_lines
        )
        
        assert pyyaml_pinned, "PyYAML should have version pin"
        assert types_pinned, "types-PyYAML should have version pin"