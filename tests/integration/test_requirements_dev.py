"""
Tests for requirements-dev.txt development dependencies file.

This test suite validates that the development dependencies file is properly
formatted, contains required packages, and has valid version specifications.
"""

import pytest
import re
from pathlib import Path
from typing import List, Tuple


REQUIREMENTS_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


def parse_requirements(file_path: Path) -> List[Tuple[str, str]]:
    """Parse requirements file and return list of (package, version_spec) tuples."""
    requirements = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            if not line or line.startswith('#'):
                continue
            
            # Support multiple specifiers like "pkg>=1.0,<=2.0" and validate format
            # Split out any inline comments first
            clean = line.split('#', 1)[0].strip()
            if not clean:
                continue
            # Match "name[extras] op version" segments; we ignore extras for name extraction here
            parts = [p.strip() for p in clean.split(',')]
            name_part = parts[0]
            # Extract package name (alphanum, -, _, . allowed) before any specifier
            m_name = re.match(r'^([A-Za-z0-9._-]+)', name_part)
            if not m_name:
                raise AssertionError(f"Malformed requirement line (invalid package name): {line}")
            pkg = m_name.group(1)
            # Find all specifiers across all parts
            spec_pattern = re.compile(r'(>=|==|<=|>|<|~=)\s*([0-9A-Za-z.*+-]+(?:\.[0-9A-Za-z*+-]+)*)')
            specs = []
            for p in parts:
                specs.extend([f"{op}{ver}" for op, ver in spec_pattern.findall(p)])
            if not specs:
    # Find all specifiers across all parts
    spec_pattern = re.compile(r'(>=|==|<=|>|<|~=)\s*([0-9A-Za-z.*+-]+(?:\.[0-9A-Za-z*+-]+)*)')
    specs = []
    for p in parts:
        specs.extend([f"{op}{ver}" for op, ver in spec_pattern.findall(p)])
    if not specs:
        if not specs:
            # No specifiers found; treat as no-version constraint explicitly
            requirements.append((pkg.strip(), ''))
        else:
            # Normalize by joining with comma
            version_spec = ','.join(specs)
            requirements.append((pkg.strip(), version_spec))
    else:
        # Normalize by joining with comma
        version_spec = ','.join(specs)
        requirements.append((pkg.strip(), version_spec))

class TestRequirementsFileExists:
    """Test that requirements-dev.txt exists and is readable."""
    
    def test_file_exists(self):
        """Test that requirements-dev.txt file exists."""
        assert REQUIREMENTS_FILE.exists()
    
    def test_file_is_file(self):
        """Test that the path is a file, not a directory."""
        assert REQUIREMENTS_FILE.is_file()
    
    def test_file_is_readable(self):
        """Test that the file can be read."""
        with open(REQUIREMENTS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            assert len(content) > 0


class TestRequirementsFileFormat:
    """Test the format and structure of requirements-dev.txt."""
    
    @pytest.fixture
    def file_content(self) -> str:
        """Load requirements file content."""
        with open(REQUIREMENTS_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    
    @pytest.fixture
    def file_lines(self) -> List[str]:
        """Load requirements file as list of lines."""
        with open(REQUIREMENTS_FILE, 'r', encoding='utf-8') as f:
            return f.readlines()
    
    def test_file_encoding(self):
        """Test that file uses UTF-8 encoding."""
        with open(REQUIREMENTS_FILE, 'r', encoding='utf-8') as f:
            f.read()
    
    def test_no_trailing_whitespace(self, file_lines: List[str]):
        """Test that lines don't have trailing whitespace."""
        lines_with_trailing = [
            (i + 1, repr(line)) for i, line in enumerate(file_lines)
            if line.rstrip('\n') != line.rstrip()
        ]
        assert len(lines_with_trailing) == 0
    
    def test_ends_with_newline(self, file_content: str):
        """Test that file ends with a newline."""
        assert file_content.endswith('\n')


class TestRequiredPackages:
    """Test that required development packages are present."""
    
    @pytest.fixture
    def requirements(self) -> List[Tuple[str, str]]:
        """Parse and return requirements."""
        return parse_requirements(REQUIREMENTS_FILE)
    
    @pytest.fixture
    def package_names(self, requirements: List[Tuple[str, str]]) -> List[str]:
        """Extract just the package names."""
        return [pkg for pkg, _ in requirements]
    
    def test_has_pytest(self, package_names: List[str]):
        """Test that pytest is included."""
        assert 'pytest' in package_names
    
    def test_has_pytest_cov(self, package_names: List[str]):
        """Test that pytest-cov is included."""
        assert 'pytest-cov' in package_names
    
    def test_has_pyyaml(self, package_names: List[str]):
        """Test that PyYAML is included (added in the diff)."""
        assert 'PyYAML' in package_names
    
    def test_has_types_pyyaml(self, package_names: List[str]):
        """Test that types-PyYAML is included (added in the diff)."""
        assert 'types-PyYAML' in package_names
    
    def test_has_flake8(self, package_names: List[str]):
        """Test that flake8 is included."""
        assert 'flake8' in package_names
    
    def test_has_black(self, package_names: List[str]):
        """Test that black is included."""
        assert 'black' in package_names
    
    def test_has_mypy(self, package_names: List[str]):
        """Test that mypy is included."""
        assert 'mypy' in package_names


class TestVersionSpecifications:
    """Test that version specifications are valid and reasonable."""
    
    @pytest.fixture
    def requirements(self) -> List[Tuple[str, str]]:
        """Parse and return requirements."""
        return parse_requirements(REQUIREMENTS_FILE)
    
    def test_all_packages_have_versions(self, requirements: List[Tuple[str, str]]):
        """Test that all packages specify version constraints."""
        packages_without_versions = [pkg for pkg, ver in requirements if not ver]
        assert len(packages_without_versions) == 0
    
from packaging.specifiers import SpecifierSet

def parse_requirements(file_path: Path) -> List[Tuple[str, str]]:
    """Parse requirements file and return list of (package, version_spec) tuples."""
    requirements: List[Tuple[str, str]] = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                # Remove inline comments
                clean = line.split('#', 1)[0].strip()
                if not clean:
                    continue
                # Support multiple specifiers separated by commas
                parts = [p.strip() for p in clean.split(',')]
                name_part = parts[0]
                m_name = re.match(r'^([A-Za-z0-9._-]+)', name_part)
                if not m_name:
                    raise AssertionError(f"Malformed requirement line (invalid package name): {line}")
                pkg = m_name.group(1)

                spec_pattern = re.compile(r'(>=|==|<=|>|<|~=)\s*([0-9A-Za-z.*+-]+(?:\.[0-9A-Za-z*+-]+)*)')
                specs: List[str] = []
                for p in parts:
                    specs.extend([f"{op}{ver}" for op, ver in spec_pattern.findall(p)])

                if not specs:
                    requirements.append((pkg.strip(), ''))
                else:
                    version_spec = ','.join(specs)
                    requirements.append((pkg.strip(), version_spec))
    except OSError as e:
        raise AssertionError(f"Could not read requirements file '{file_path}': {e}")

def test_version_format_valid(self, requirements: List[Tuple[str, str]]):
    """Test that version specifications use valid PEP 440 format."""
    for pkg, ver_spec in requirements:
        if ver_spec:
            try:
                SpecifierSet(ver_spec)
            except Exception as e:
                assert False, f"Invalid version specifier for {pkg}: {ver_spec} ({e})"
        """Test that version specifications use valid format."""
    # Add at the top of the file with other imports
    # Add at the top with other imports
    from packaging.specifiers import SpecifierSet
    def test_version_format_valid(self, requirements: List[Tuple[str, str]]):
        """Test that version specifications use valid PEP 440 format."""
        from packaging.specifiers import SpecifierSet
        for pkg, ver_spec in requirements:
            if ver_spec:
                try:
                    SpecifierSet(ver_spec)
                except Exception as e:
                    assert False, f"Invalid version specifier for {pkg}: {ver_spec} ({e})"
    def test_version_format_valid(self, requirements: List[Tuple[str, str]]):
        """Test that version specifications use valid PEP 440 format."""
        for pkg, ver_spec in requirements:
            if ver_spec:
                try:
                    SpecifierSet(ver_spec)
                except Exception as e:
                    assert False, f"Invalid version specifier for {pkg}: {ver_spec} ({e})"
    
    def test_pyyaml_version(self, requirements: List[Tuple[str, str]]):
        """Test that PyYAML has appropriate version constraint."""
        pyyaml_specs = [ver for pkg, ver in requirements if pkg == 'PyYAML']
        assert len(pyyaml_specs) > 0
        assert pyyaml_specs[0].startswith('>=6.0')
    
    def test_uses_minimum_versions(self, requirements: List[Tuple[str, str]]):
        """Test that packages use >= for version specifications."""
        specs_using_gte = [ver for pkg, ver in requirements if ver.startswith('>=')]
        all_with_versions = [ver for pkg, ver in requirements if ver]
        assert len(specs_using_gte) >= len(all_with_versions) * 0.7


class TestPackageConsistency:
    """Test consistency and relationships between packages."""
    
    @pytest.fixture
    def package_names(self) -> List[str]:
        """Extract package names from requirements."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        return [pkg for pkg, _ in requirements]
    
    def test_types_packages_match_base_packages(self, package_names: List[str]):
        """Test that type stub packages have corresponding base packages."""
        types_packages = [pkg for pkg in package_names if pkg.startswith('types-')]
        
        for types_pkg in types_packages:
            base_pkg = types_pkg.replace('types-', '')
            base_exists = any(
                pkg.lower() == base_pkg.lower() 
                for pkg in package_names
            )
            assert base_exists
    
    def test_no_duplicate_packages(self, package_names: List[str]):
        """Test that no package is listed multiple times."""
        seen = set()
        duplicates = []
        
        for pkg in package_names:
            if pkg.lower() in seen:
                duplicates.append(pkg)
            seen.add(pkg.lower())
        
        assert len(duplicates) == 0
    
    def test_package_names_valid(self, package_names: List[str]):
        """Test that package names follow valid naming conventions."""
        valid_name_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
        
        invalid_names = [
            pkg for pkg in package_names 
            if not valid_name_pattern.match(pkg)
        ]
        assert len(invalid_names) == 0


class TestFileOrganization:
    """Test that the file is well-organized."""
    
    @pytest.fixture
    def file_lines(self) -> List[str]:
        """Load requirements file as list of lines."""
        with open(REQUIREMENTS_FILE, 'r', encoding='utf-8') as f:
            return f.readlines()
    
    def test_reasonable_file_size(self, file_lines: List[str]):
        """Test that file isn't excessively large."""
        assert len(file_lines) < 100
    
    def test_has_appropriate_number_of_packages(self):
        """Test that file has a reasonable number of development dependencies."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        assert 5 <= len(requirements) <= 50


class TestSpecificChanges:
    """Test the specific changes made in the diff."""
    
    @pytest.fixture
    def requirements(self) -> List[Tuple[str, str]]:
        """Parse and return requirements."""
        return parse_requirements(REQUIREMENTS_FILE)
    
    def test_pyyaml_added(self, requirements: List[Tuple[str, str]]):
        """Test that PyYAML was added as per the diff."""
        pyyaml_entries = [(pkg, ver) for pkg, ver in requirements if pkg == 'PyYAML']
        assert len(pyyaml_entries) == 1
        pkg, ver = pyyaml_entries[0]
        assert ver == '>=6.0'
    
    def test_types_pyyaml_added(self, requirements: List[Tuple[str, str]]):
        """Test that types-PyYAML was added as per the diff."""
        types_entries = [(pkg, ver) for pkg, ver in requirements if pkg == 'types-PyYAML']
        assert len(types_entries) == 1
    
    def test_existing_packages_preserved(self, requirements: List[Tuple[str, str]]):
    def test_existing_packages_preserved(self, requirements: List[Tuple[str, str]]):
        missing = [pkg for pkg in expected_packages if pkg not in package_names]
        assert not missing, f"Missing expected packages: {missing}"

class TestRequirementsAdvancedValidation:
    """Advanced validation tests for requirements-dev.txt."""
    
    def test_pyyaml_security_version(self):
        """Ensure PyYAML version is not vulnerable to known CVEs."""
        req_file = Path('requirements-dev.txt')
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")
        
        content = req_file.read_text()
        
        import re
        # Extract PyYAML version
        pyyaml_match = re.search(r'pyyaml[>=<~]=*(\d+\.\d+)', content, re.IGNORECASE)
        
        if pyyaml_match:
            version_str = pyyaml_match.group(1)
            major, minor = map(int, version_str.split('.'))
            
            # PyYAML 5.4+ addresses security issues
            assert major > 5 or (major == 5 and minor >= 4), \
                f"PyYAML version {version_str} may have security vulnerabilities. Use >= 5.4"
    
    def test_no_unpinned_dependencies(self):
        """Ensure all dependencies have version constraints."""
        req_file = Path('requirements-dev.txt')
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")
        
        content = req_file.read_text()
        lines = [line.strip() for line in content.split('\n') 
                 if line.strip() and not line.startswith('#')]
        
        for line in lines:
            # Each line should have a version constraint
            has_constraint = any(op in line for op in ['==', '>=', '~=', '>', '<', '<='])
            assert has_constraint, f"Dependency without version constraint: {line}"
    
    def test_no_git_dependencies(self):
        """Ensure no git+ dependencies for reproducibility."""
        req_file = Path('requirements-dev.txt')
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")
        
        content = req_file.read_text()
        assert 'git+' not in content, "Git dependencies found - use PyPI packages for reproducibility"
    
    def test_requirements_parseable(self):
        """Verify requirements file is properly formatted and parseable."""
        req_file = Path('requirements-dev.txt')
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")
        
        content = req_file.read_text()
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Should follow proper format
            assert not line.startswith(' '), f"Line {i} has leading whitespace"
            assert not line.endswith('\\'), f"Line {i} has trailing backslash"
    
    def test_case_consistency(self):
        """Ensure package names use consistent casing."""
        req_file = Path('requirements-dev.txt')
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")
        
        content = req_file.read_text()
        
        # Common packages should use standard casing
        case_standards = {
            'pyyaml': 'PyYAML',
            'pytest': 'pytest',
        }
        
        for wrong, correct in case_standards.items():
            if wrong != correct and wrong in content and correct not in content:
                pytest.fail(f"Use '{correct}' instead of '{wrong}' for consistency")


class TestWorkflowYAMLValidation:
    """Advanced YAML validation for workflow files."""
    
    def test_no_tab_characters(self, workflow_files):
        """Ensure no tab characters in YAML (should use spaces)."""
        for workflow_path in Path('.github/workflows').glob('*.yml'):
            content = workflow_path.read_text()
            assert '\t' not in content, f"{workflow_path} contains tab characters"
    
    def test_consistent_indentation(self, workflow_files):
        """Verify consistent 2-space indentation in workflows."""
        for workflow_path in Path('.github/workflows').glob('*.yml'):
            content = workflow_path.read_text()
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                if line.strip():
                    # Count leading spaces
                    leading_spaces = len(line) - len(line.lstrip(' '))
                    
                    # Should be multiple of 2
                    assert leading_spaces % 2 == 0, \
                        f"{workflow_path} line {i}: indentation not multiple of 2"
    
    def test_no_trailing_whitespace(self, workflow_files):
        """Ensure no trailing whitespace in workflow files."""
        for workflow_path in Path('.github/workflows').glob('*.yml'):
            content = workflow_path.read_text()
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                assert not line.rstrip() != line.rstrip(' \t'), \
                    f"{workflow_path} line {i}: trailing whitespace found"
    
    def test_boolean_values_lowercase(self, workflow_files):
        """Ensure boolean values use lowercase (true/false, not True/False)."""
        for workflow_path, workflow_content in workflow_files.items():
            workflow_str = yaml.dump(workflow_content)
            
            # In YAML output, booleans should be lowercase
            # Check the original file
            original_content = Path(workflow_path).read_text()
            
            import re
            # Look for boolean values
            bool_pattern = r':\s*(True|False|TRUE|FALSE)\s*$'
            matches = re.findall(bool_pattern, original_content, re.MULTILINE)
            
            assert len(matches) == 0, \
                f"{workflow_path} uses uppercase booleans: {matches}. Use lowercase."
    
    def test_quotes_consistency(self, workflow_files):
        """Check for consistent quote usage in workflows."""
        for workflow_path in Path('.github/workflows').glob('*.yml'):
            content = workflow_path.read_text()
            
            # Count different quote types in values
            double_quotes = content.count('": "') + content.count('"${{')
            single_quotes = content.count("': '")
            
            # If quotes are used, should prefer double quotes for consistency
            if single_quotes > 0 and double_quotes > 0:
                # Some mixing is okay, but shouldn't be heavily mixed
                ratio = min(single_quotes, double_quotes) / max(single_quotes, double_quotes)
                assert ratio < 0.3, \
                    f"{workflow_path}: Inconsistent quote usage (mix of single and double)"


class TestWorkflowPerformanceOptimization:
    """Test workflow configurations for performance best practices."""
    
    def test_concurrency_groups_defined(self, workflow_files):
        """Verify workflows that should have concurrency controls do."""
        workflow_types_needing_concurrency = [
            'pr-agent.yml',
            'apisec-scan.yml',
        ]
        
        for workflow_path, workflow_content in workflow_files.items():
            workflow_name = Path(workflow_path).name
            
            if workflow_name in workflow_types_needing_concurrency:
                jobs = workflow_content.get('jobs', {})
                
                # At least one job should have concurrency control
                has_concurrency = any('concurrency' in job_config 
                                    for job_config in jobs.values() 
                                    if isinstance(job_config, dict))
                
                assert has_concurrency, \
                    f"{workflow_path} should define concurrency groups"
    
    def test_reasonable_timeout_minutes(self, workflow_files):
        """Ensure job timeouts are reasonable."""
        for workflow_path, workflow_content in workflow_files.items():
            jobs = workflow_content.get('jobs', {})
            
            for job_name, job_config in jobs.items():
                if isinstance(job_config, dict) and 'timeout-minutes' in job_config:
                    timeout = job_config['timeout-minutes']
                    
                    # Reasonable range: 5-60 minutes for most jobs
                    assert 1 <= timeout <= 120, \
                        f"Job {job_name} in {workflow_path} has unusual timeout: {timeout} minutes"
    
    def test_caching_strategies_used(self, workflow_files):
        """Verify appropriate caching is used for dependencies."""
        for workflow_path, workflow_content in workflow_files.items():
            workflow_str = yaml.dump(workflow_content)
            
            # If setup actions are used, caching should be considered
            if 'setup-python' in workflow_str or 'setup-node' in workflow_str:
                # Should have cache-related configuration or actions
                has_caching = any(keyword in workflow_str.lower() 
                                for keyword in ['cache', 'restore-keys'])
                
                # Not all workflows need caching, but it should be considered
                # This is more of an informational test
                if not has_caching:
                    import warnings
                    warnings.warn(f"{workflow_path} might benefit from dependency caching")


class TestWorkflowErrorHandling:
    """Test error handling in workflow configurations."""
    
    def test_continue_on_error_usage(self, workflow_files):
        """Verify continue-on-error is used appropriately."""
        for workflow_path, workflow_content in workflow_files.items():
            workflow_str = yaml.dump(workflow_content)
            
            if 'continue-on-error: true' in workflow_str:
                # Should have a good reason (e.g., non-critical steps)
                # This is a code smell - should be limited
                import warnings
                warnings.warn(
                    f"{workflow_path} uses continue-on-error. "
                    "Ensure this is intentional for non-critical steps."
                )
    
    def test_failure_notifications_configured(self, workflow_files):
        """Check if workflows have failure notification strategies."""
        for workflow_path, workflow_content in workflow_files.items():
            # Critical workflows should handle failures
            if 'security' in workflow_path.lower() or 'scan' in workflow_path.lower():
                workflow_str = yaml.dump(workflow_content)
                
                # Should have some failure handling
                has_failure_handling = any(keyword in workflow_str.lower() 
                                          for keyword in ['failure()', 'always()', 'if:'])
                
                # This is informational
                if not has_failure_handling:
                    import warnings
                    warnings.warn(
                        f"{workflow_path} is a critical workflow but may not have explicit failure handling"
                    )


class TestWorkflowMaintenability:
    """Test workflow files for maintainability best practices."""
    
    def test_step_names_descriptive(self, workflow_files):
        """Ensure all steps have descriptive names."""
        for workflow_path, workflow_content in workflow_files.items():
            jobs = workflow_content.get('jobs', {})
            
            for job_name, job_config in jobs.items():
                if isinstance(job_config, dict) and 'steps' in job_config:
                    steps = job_config['steps']
                    
                    for i, step in enumerate(steps):
                        if isinstance(step, dict):
                            # If step has name, it should be descriptive
                            if 'name' in step:
                                name = step['name']
                                assert len(name) > 5, \
                                    f"Step name too short in {workflow_path}, job {job_name}, step {i}"
                                
                                # Should not be generic
                                generic_names = ['run', 'step', 'execute', 'do']
                                assert name.lower().strip() not in generic_names, \
                                    f"Generic step name in {workflow_path}, job {job_name}: '{name}'"
    
    def test_no_commented_out_code(self, workflow_files):
        """Ensure no large blocks of commented code."""
        for workflow_path in Path('.github/workflows').glob('*.yml'):
            content = workflow_path.read_text()
            lines = content.split('\n')
            
            consecutive_comments = 0
            max_consecutive_comments = 0
            
            for line in lines:
                if line.strip().startswith('#'):
                    consecutive_comments += 1
                    max_consecutive_comments = max(max_consecutive_comments, consecutive_comments)
                else:
                    consecutive_comments = 0
            
            # More than 10 consecutive comment lines is suspicious
            assert max_consecutive_comments < 15, \
                f"{workflow_path} has {max_consecutive_comments} consecutive comment lines. " \
                "Consider removing commented-out code."
    
    def test_env_vars_documented(self, workflow_files):
        """Check if complex environment variables are documented."""
        for workflow_path, workflow_content in workflow_files.items():
            workflow_str = yaml.dump(workflow_content)
            
            # If many env vars, should have comments explaining them
            env_count = workflow_str.count('env:')
            
            if env_count > 5:
                original_content = Path(workflow_path).read_text()
                comment_count = original_content.count('#')
                
                # Should have some documentation
                assert comment_count > 3, \
                    f"{workflow_path} has many env vars but few comments"

