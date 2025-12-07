"""
Comprehensive validation tests for requirements-dev.txt changes.

Tests ensure:
1. Proper dependency specification format
2. Version pinning and security
3. Compatibility with existing dependencies
4. No conflicting versions
"""

import pytest
import re
from pathlib import Path
from typing import List, Tuple, Dict
import subprocess


class TestRequirementsFormat:
    """Test requirements file format and structure."""
    
    @pytest.fixture
    def requirements_lines(self) -> List[str]:
        """
        Read requirements-dev.txt and return its non-empty, stripped lines.
        
        Returns:
            list[str]: Lines from requirements-dev.txt with leading and trailing whitespace removed; blank lines are omitted.
        """
        with open('requirements-dev.txt', 'r') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    
    def test_all_lines_valid_format(self, requirements_lines):
        """Verify each line follows valid pip requirement format."""
        # Valid formats: package, package==version, package>=version, comments
        valid_pattern = re.compile(r'^(#.*|[a-zA-Z0-9\-_]+([<>=~!]+[0-9\.\*]+)?(\s*#.*)?)$')
        
        for i, line in enumerate(requirements_lines, 1):
            assert valid_pattern.match(line), \
                f"Line {i} has invalid format: {line}"
    
    def test_no_http_links(self, requirements_lines):
        """Verify no http:// links (should use https://)."""
        for i, line in enumerate(requirements_lines, 1):
            if not line.startswith('#'):
                assert 'http://' not in line, \
                    f"Line {i}: Use https:// instead of http://"
    
    def test_no_spaces_around_operators(self, requirements_lines):
        """
        Ensure no non-comment line contains spaces around version comparison operators.
        
        If an offending line is found the test fails with an assertion that includes the line number and the line content.
        """
        for i, line in enumerate(requirements_lines, 1):
            if not line.startswith('#'):
                # Check for spaces around version operators
                assert ' == ' not in line and ' >= ' not in line and ' <= ' not in line, \
                    f"Line {i}: Remove spaces around operators: {line}"
    
    def test_lowercase_package_names(self, requirements_lines):
        """
        Ensure each non-comment requirement uses a lowercase package name, allowing hyphenated names and permitting the special-case 'PyYAML'.
        
        Raises:
            AssertionError: if a package name contains uppercase characters (excluding the allowed 'pyyaml') and is not hyphenated; the failure message includes the offending line number and package name.
        """
        for i, line in enumerate(requirements_lines, 1):
            if line and not line.startswith('#'):
                pkg_name = re.split(r'[<>=~!]', line)[0].strip()
                # PyYAML is a special case with capital letters
                if pkg_name.lower() not in ['pyyaml']:
                    assert pkg_name.islower() or '-' in pkg_name, \
                        f"Line {i}: Package name should be lowercase: {pkg_name}"


class TestPyYAMLAddition:
    """Test PyYAML dependency addition."""
    
    def test_pyyaml_present(self):
        """Verify PyYAML is in requirements."""
        with open('requirements-dev.txt', 'r') as f:
            content = f.read().lower()
        
        assert 'pyyaml' in content, "PyYAML must be present in requirements-dev.txt"
    
    def test_pyyaml_version_appropriate(self):
        """
        Ensure requirements-dev.txt contains a PyYAML entry and that any specified version meets the minimum secure version (major >= 5, and if major == 5 then minor >= 4).
        
        Reads requirements-dev.txt, locates the first non-comment line mentioning PyYAML, and asserts the entry exists. If a version specifier is present, asserts the major version is at least 5 and that 5.x versions are >= 5.4.
        """
        with open('requirements-dev.txt', 'r') as f:
            lines = f.readlines()
        
        pyyaml_line = None
        for line in lines:
            if 'pyyaml' in line.lower() and not line.strip().startswith('#'):
                pyyaml_line = line.strip()
                break
        
        assert pyyaml_line, "PyYAML specification not found"
        
        # Extract version if specified
        version_match = re.search(r'[><=~]+(\d+)\.(\d+)', pyyaml_line)
        if version_match:
            major = int(version_match.group(1))
            minor = int(version_match.group(2))
            
            # PyYAML 5.4+ has security fixes for arbitrary code execution
            assert major >= 5, f"PyYAML major version should be >= 5, found {major}"
            if major == 5:
                assert minor >= 4, f"PyYAML 5.x should be >= 5.4 for security, found 5.{minor}"
    
    def test_pyyaml_compatible_with_yaml_workflows(self):
        """
        Verify the installed PyYAML can parse the repository's GitHub workflow and that the parsed object contains job definitions.
        
        Checks that `.github/workflows/pr-agent.yml` can be loaded with `yaml.safe_load`, that the result is a dict-like object and that it contains a top-level 'jobs' key. The test is skipped if PyYAML is not installed and fails if parsing or validation of the workflow file fails.
        """
        try:
            import yaml
            
            # Test parsing a workflow file
            workflow_path = Path(".github/workflows/pr-agent.yml")
            with open(workflow_path, 'r') as f:
                workflow = yaml.safe_load(f)
            
            assert workflow is not None
            assert isinstance(workflow, dict)
            assert 'jobs' in workflow
        except ImportError:
            pytest.skip("PyYAML not installed yet")
        except Exception as e:
            pytest.fail(f"PyYAML failed to parse workflow file: {e}")


class TestDependencyConflicts:
    """Test for dependency conflicts and compatibility."""
    
    def test_no_duplicate_packages(self):
        """Verify no package is listed multiple times."""
        with open('requirements-dev.txt', 'r') as f:
            lines = f.readlines()
        
        packages = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                pkg_name = re.split(r'[<>=~!]', line)[0].strip().lower()
                packages.append(pkg_name)
        
        seen = set()
        duplicates = set()
        for pkg in packages:
            if pkg in seen:
                duplicates.add(pkg)
            seen.add(pkg)
        
        assert len(duplicates) == 0, \
            f"Duplicate packages found: {duplicates}"
    
    def test_no_conflicting_versions(self):
        """Verify no obviously conflicting version constraints."""
        with open('requirements-dev.txt', 'r') as f:
            lines = f.readlines()
        
        package_versions: Dict[str, List[str]] = {}
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract package name and version constraint
                match = re.match(r'([a-zA-Z0-9\-_]+)([<>=~!]+.+)', line)
                if match:
                    pkg_name = match.group(1).lower()
                    version_spec = match.group(2)
                    
                    if pkg_name not in package_versions:
                        package_versions[pkg_name] = []
                    package_versions[pkg_name].append(version_spec)
        
        # Check for obviously conflicting constraints (e.g., ==1.0 and ==2.0)
        for pkg, versions in package_versions.items():
            if len(versions) > 1:
                # Check for multiple == constraints
                exact_versions = [v for v in versions if v.startswith('==')]
                if len(exact_versions) > 1:
                    pytest.fail(f"Package {pkg} has conflicting exact versions: {exact_versions}")


class TestRequirementsSecurity:
    """Security-focused tests for requirements."""
    
    def test_no_known_vulnerable_versions(self):
        """Check for known vulnerable package versions."""
        # This is a basic check - in production, use safety or pip-audit
        known_vulnerable = {
            'pyyaml': ['3.', '4.', '5.0', '5.1', '5.2', '5.3'],  # Before 5.4
        }
        
        with open('requirements-dev.txt', 'r') as f:
            content = f.read()
        
        for package, vulnerable_versions in known_vulnerable.items():
            if package in content.lower():
                for vuln_version in vulnerable_versions:
                    assert f'=={vuln_version}' not in content.lower(), \
                        f"Known vulnerable version {package}=={vuln_version} detected"
    
    def test_uses_version_pinning(self):
        """
        Ensure critical packages in requirements-dev.txt have explicit version constraints.
        
        Fails the test if any of the critical packages ('pyyaml', 'pytest') are present in non-comment lines without a version specifier (==, >=, <=, ~=, >, <, !=).
        """
        with open('requirements-dev.txt', 'r') as f:
            lines = f.readlines()
        
        unpinned = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # Check if line has no version specifier
                if not any(op in line for op in ['==', '>=', '<=', '~=', '>', '<', '!=']):
                    pkg_name = line.split()[0]
                    unpinned.append(pkg_name)
        
        # Some flexibility allowed, but critical packages should be pinned
        critical_packages = ['pyyaml', 'pytest']
        for pkg in critical_packages:
            assert pkg.lower() not in [p.lower() for p in unpinned], \
                f"Critical package {pkg} should have version constraint"


class TestRequirementsCompatibility:
    """Test compatibility with existing project structure."""
    
    def test_compatible_with_main_requirements(self):
        """
        Ensure development requirements do not conflict with main requirements.
        
        Reads requirements.txt and requirements-dev.txt (skipping if requirements.txt is absent), compares packages present in both files, and asserts that any package pinned to an exact version with `==` in both files uses the same version. Raises an assertion error describing the package and differing `==` specifiers if a conflict is found.
        """
        main_req_path = Path('requirements.txt')
        if not main_req_path.exists():
            pytest.skip("requirements.txt not found")
        
        with open('requirements.txt', 'r') as f:
            main_packages = {}
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    match = re.match(r'([a-zA-Z0-9\-_]+)([<>=~!]+.+)?', line)
                    if match:
                        pkg_name = match.group(1).lower()
                        main_packages[pkg_name] = match.group(2) or ''
        
        with open('requirements-dev.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    match = re.match(r'([a-zA-Z0-9\-_]+)([<>=~!]+.+)?', line)
                    if match:
                        pkg_name = match.group(1).lower()
                        dev_version = match.group(2) or ''
                        
                        if pkg_name in main_packages:
                            # Both have the package - check for conflicts
                            main_version = main_packages[pkg_name]
                            if main_version and dev_version:
                                if main_version.startswith('==') and dev_version.startswith('=='):
                                    assert main_version == dev_version, \
                                        f"Version conflict for {pkg_name}: main{main_version} vs dev{dev_version}"
    
    def test_can_be_installed(self):
        """
        Check that pip can parse requirements-dev.txt without syntax errors.
        
        Fails the test if pip reports requirement syntax or lookup errors; skips the test if the pip executable is not available or the subprocess times out.
        """
        try:
            result = subprocess.run(
                ['pip', 'install', '--dry-run', '-r', 'requirements-dev.txt'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Check for syntax errors (exit code 1 with specific error messages)
            if result.returncode != 0:
                error_output = result.stderr.lower()
                syntax_errors = ['invalid requirement', 'could not find', 'error: ']
                
                has_syntax_error = any(err in error_output for err in syntax_errors)
                if has_syntax_error:
                    pytest.fail(f"Requirements file has syntax errors:\n{result.stderr}")
        except FileNotFoundError:
            pytest.skip("pip not available in test environment")
        except subprocess.TimeoutExpired:
            pytest.skip("pip install check timed out")


class TestRequirementsDocumentation:
    """Test documentation and comments in requirements file."""
    
    def test_has_header_comment(self):
        """
        Check that the requirements-dev.txt file contains a header comment.
        
        This test reads the first three lines of requirements-dev.txt and asserts that at least one of them is a comment line (starts with '#'), ensuring the file includes an explanatory header.
        """
        with open('requirements-dev.txt', 'r') as f:
            first_lines = [f.readline().strip() for _ in range(3)]
        
        # At least one of first few lines should be a comment
        has_comment = any(line.startswith('#') for line in first_lines if line)
        assert has_comment, "requirements-dev.txt should have header comment explaining purpose"
    
    def test_pyyaml_has_explanation(self):
        """
        Check that a PyYAML entry in requirements-dev.txt is accompanied by an explanatory comment.
        
        Scans requirements-dev.txt for a non-comment line that mentions "pyyaml" and asserts there is either an inline comment on the same line or a comment on the immediately preceding line.
        """
        with open('requirements-dev.txt', 'r') as f:
            lines = f.readlines()
        
        found_pyyaml = False
        has_explanation = False
        
        for i, line in enumerate(lines):
            if 'pyyaml' in line.lower() and not line.strip().startswith('#'):
                found_pyyaml = True
                
                # Check previous line or inline comment for explanation
                if i > 0 and '#' in lines[i-1]:
                    has_explanation = True
                if '#' in line:
                    has_explanation = True
                break
        
        if found_pyyaml:
            assert has_explanation, \
                "PyYAML addition should have comment explaining its purpose"


class TestRequirementsEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_file_ends_with_newline(self):
        """Verify file ends with newline (POSIX requirement)."""
        with open('requirements-dev.txt', 'rb') as f:
            content = f.read()
        
        assert content.endswith(b'\n'), \
            "requirements-dev.txt should end with newline"
    
    def test_no_trailing_whitespace(self):
        """
        Fail the test if any non-empty line in requirements-dev.txt contains trailing whitespace.
        
        The assertion reports the 1-based line number when trailing whitespace is found.
        """
        with open('requirements-dev.txt', 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            # Remove newline, then check for trailing whitespace
            line_content = line.rstrip('\n\r')
            if line_content:
                assert line_content == line_content.rstrip(), \
                    f"Line {i} has trailing whitespace"
    
    def test_no_empty_lines_between_related_packages(self):
        """
        Ensure requirements-dev.txt does not contain more than one consecutive empty line.
        
        Reads the file, counts consecutive empty lines and fails the test if more than one empty line appears in a row.
        """
        with open('requirements-dev.txt', 'r') as f:
            lines = [line.strip() for line in f.readlines()]
        
        # Count consecutive empty lines
        max_consecutive_empty = 0
        current_empty = 0
        
        for line in lines:
            if not line:
                current_empty += 1
                max_consecutive_empty = max(max_consecutive_empty, current_empty)
            else:
                current_empty = 0
        
        assert max_consecutive_empty <= 1, \
            "Should not have multiple consecutive empty lines"
    
    def test_file_not_too_large(self):
        """
        Ensure requirements-dev.txt is smaller than 10,000 bytes.
        
        Asserts the file size is less than 10,000 bytes and fails showing the actual byte count if it exceeds the limit.
        """
        import os
        file_size = os.path.getsize('requirements-dev.txt')
        
        # Development requirements shouldn't be enormous
        assert file_size < 10000, \
            f"requirements-dev.txt is unexpectedly large: {file_size} bytes"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])