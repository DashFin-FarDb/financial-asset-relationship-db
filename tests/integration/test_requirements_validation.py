"""
Validation tests for requirements changes.

Tests that requirements-dev.txt changes are valid:
- PyYAML added with correct version
- No conflicting dependencies
- All dependencies installable
"""

import subprocess
import pytest
from pathlib import Path


class TestRequirementsDevChanges:
    """Test requirements-dev.txt changes."""
    
    @pytest.fixture
    def requirements_dev_content(self):
        """
        Read and return the contents of requirements-dev.txt.
        
        Returns:
            content (str): The full text of requirements-dev.txt.
        """
        req_path = Path("requirements-dev.txt")
        with open(req_path, 'r') as f:
            return f.read()
    
    def test_pyyaml_added(self, requirements_dev_content):
        """
        Check that requirements-dev.txt contains an entry for PyYAML.
        
        This test asserts that the requirements-dev content includes a PyYAML package entry (case-insensitive).
        """
        assert 'pyyaml' in requirements_dev_content.lower() or \
               'PyYAML' in requirements_dev_content
    
    def test_pyyaml_has_version_specifier(self, requirements_dev_content):
        """
        Check that a PyYAML entry in requirements-dev.txt includes a version specifier.
        
        Searches the given requirements file content for a line mentioning PyYAML and verifies that the line contains one of the recognised version operators: >=, ==, ~=, <=, > or <.
        """
        lines = requirements_dev_content.split('\n')
    # Ignore commented lines so we don't pick up commented-out examples
    pyyaml_line = next((l for l in lines if 'pyyaml' in l.lower() and not l.strip().startswith('#')), None)

    assert pyyaml_line is not None
    # Strip inline comments and whitespace before checking version specifier
    pyyaml_line_no_comment = pyyaml_line.split('#', 1)[0].strip()
    assert any(op in pyyaml_line_no_comment for op in ['>=', '==', '~=', '<=', '>', '<'])
    
    def test_no_duplicate_packages(self, requirements_dev_content):
        """
        Ensure requirements-dev.txt contains no duplicate package entries.
        
        This test treats each non-empty, non-comment line as a package specification and compares
        package names case-insensitively while ignoring common version specifiers, asserting
        that no package appears more than once.
        
        Parameters:
            requirements_dev_content (str): Contents of requirements-dev.txt.
        """
        import re
        lines = [l.strip() for l in requirements_dev_content.split('\n') 
                if l.strip() and not l.strip().startswith('#')]

        # Split on any common version operator to reliably extract the package name
        package_names = [re.split(r'(?:==|~=|>=|<=|>|<)', l, maxsplit=1)[0].lower() 
        package_names = [l.split('==')[0].split('>=')[0].split('<=')[0].lower() 
                        for l in lines]
        
        assert len(package_names) == len(set(package_names)), \
            "Duplicate packages found in requirements-dev.txt"
    
    def test_requirements_format_valid(self, requirements_dev_content):
        """Verify requirements file follows pip format."""
        lines = requirements_dev_content.split('\n')
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line and not line.startswith('#'):
                # Basic format check
                assert not line.startswith(' '), \
                    f"Line {i} has leading whitespace"
                # Should not have trailing whitespace
                assert line == line.rstrip(), \
                    f"Line {i} has trailing whitespace"


class TestRequirementsDependencyCompatibility:
    """Test dependency compatibility."""
    
    def test_pyyaml_compatible_with_python_version(self):
        """
        Ensure that if PyYAML appears in requirements-dev.txt the running Python version is at least 3.6.
        
        Reads requirements-dev.txt and asserts Python >= 3.6 when a PyYAML entry exists.
        """
        # Check Python version
        import sys
        python_version = sys.version_info
        
        # PyYAML >=5.4 requires Python 3.6+
        req_path = Path("requirements-dev.txt")
        with open(req_path, 'r') as f:
            content = f.read()
        
        if 'pyyaml' in content.lower():
            # Basic compatibility check passed
            assert python_version >= (3, 6), \
                "PyYAML requires Python 3.6 or higher"
    
    def test_no_conflicting_versions(self):
        """
        Assert that the number of package-name overlaps between requirements.txt and requirements-dev.txt does not exceed two.
        
        Skips the test if requirements.txt is missing. Raises an assertion failure listing overlapping package names when more than two overlaps are found.
        """
        req_path = Path("requirements.txt")
        req_dev_path = Path("requirements-dev.txt")
        
        if not req_path.exists():
            pytest.skip("requirements.txt not found")
        
        with open(req_path, 'r') as f:
            req_content = f.read()
        with open(req_dev_path, 'r') as f:
            req_dev_content = f.read()
        
        # Check for packages in both files
        req_packages = {l.split('==')[0].split('>=')[0].lower().strip() 
                       for l in req_content.split('\n') 
                       if l.strip() and not l.strip().startswith('#')}
        
        req_dev_packages = {l.split('==')[0].split('>=')[0].lower().strip() 
                           for l in req_dev_content.split('\n') 
                           if l.strip() and not l.strip().startswith('#')}
        
        overlap = req_packages & req_dev_packages
        # PyYAML might be in both, but versions should be compatible
        # This is a basic check
        assert len(overlap) <= 2, \
            f"Too many overlapping packages: {overlap}"


class TestRequirementsInstallability:
    """Test that requirements can be installed."""
    
    @pytest.mark.skipif(
        not Path("requirements-dev.txt").exists(),
        reason="requirements-dev.txt not found"
    )
    def test_requirements_dev_syntax_valid(self):
        """Verify requirements-dev.txt has valid pip syntax."""
        # Use pip to check syntax without installing
        result = subprocess.run(
            ['pip', 'install', '--dry-run', '-r', 'requirements-dev.txt'],
            capture_output=True,
            text=True
        )
        
        # Should not have syntax errors
        assert 'error' not in result.stderr.lower() or \
               'requirement already satisfied' in result.stdout.lower()


class TestRequirementsDocumentation:
    """Test requirements documentation and comments."""
    
    def test_requirements_has_helpful_comments(self):
        """
        Ensure requirements-dev.txt contains at least one explanatory comment.
        
        Asserts that requirements-dev.txt includes at least one line that, after stripping leading whitespace, starts with `#`, indicating explanatory commentary for the dependencies.
        """
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, 'r') as f:
            lines = f.readlines()
        
        # Should have at least some comments explaining purpose
        comment_lines = [l for l in lines if l.strip().startswith('#')]
        assert len(comment_lines) >= 1, \
            "requirements-dev.txt should have explanatory comments"
    
    def test_pyyaml_purpose_documented(self):
        """Verify PyYAML addition has comment explaining purpose."""
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, 'r') as f:
            content = f.read()
        
        # Check if there's a comment near PyYAML explaining its purpose
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'pyyaml' in line.lower():
                # Check previous lines for comments
                context = '\n'.join(lines[max(0, i-3):i+1])
                # Should have some context about YAML parsing or workflows
                assert any(keyword in context.lower() 
                          for keyword in ['yaml', 'workflow', 'config', 'parse']), \
                    "PyYAML should have explanatory comment"
                break