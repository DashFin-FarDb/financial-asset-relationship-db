"""
Tests for requirements-dev.txt development dependencies file.

This test suite validates that the development dependencies file is properly
formatted, contains required packages, and has valid version specifications.
"""

import pytest
import re
from pathlib import Path
from typing import List, Tuple
from packaging.specifiers import SpecifierSet


REQUIREMENTS_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


def parse_requirements(file_path: Path) -> List[Tuple[str, str]]:
    """
    Parse a requirements-style file and produce a list of package names with their combined version specifiers.
    
    The parser:
    - ignores empty lines and full-line comments;
    - strips inline comments after `#`;
    - splits comma-separated spec segments and extracts the package name from the first segment;
    - collects all version specifiers (operators such as `>=`, `==`, `<=`, `>`, `<`, `~=`) across segments and joins them with commas;
    - treats an entry with no specifiers as having an empty version specifier.
    
    Parameters:
        file_path (Path): Path to the requirements file to parse.
    
    Returns:
        List[Tuple[str, str]]: A list of (package, version_spec) tuples. `version_spec` is an empty string if no version constraints were found, otherwise specifiers are joined by commas (e.g. ">=1.0,<=2.0").
    
    Raises:
        AssertionError: If a line contains an invalid package name.
    """
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
                # No specifiers found; treat as no-version constraint explicitly
                requirements.append((pkg.strip(), ''))
            else:
                # Normalize by joining with comma
                version_spec = ','.join(specs)
                requirements.append((pkg.strip(), version_spec))
    
    return requirements
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
        """
        Return the parsed list of (package_name, version_spec) pairs from the development requirements file.
        
        Each tuple contains the package name and a single version specifier string; the version spec is an empty string when no specifier is present.
        
        Returns:
            List[Tuple[str, str]]: Parsed requirements as (package_name, version_spec) pairs.
        """
        return parse_requirements(REQUIREMENTS_FILE)

    def test_all_packages_have_versions(self, requirements: List[Tuple[str, str]]):
        """Test that all packages specify version constraints."""
        packages_without_versions = [
            pkg for pkg, ver in requirements
            if not ver
        ]
        assert not packages_without_versions, (
            f"Found unpinned packages: {packages_without_versions}"
        )

    def test_version_format_valid(self, requirements: List[Tuple[str, str]]):
        """
        Validate that each non-empty version specification conforms to PEP 440 using
        packaging.specifiers.SpecifierSet.

        For every (package, version_spec) tuple where `version_spec` is non-empty, this test
        attempts to construct a SpecifierSet from the string. If the specifier is invalid,
        packaging will raise packaging.specifiers.InvalidSpecifier (or a related packaging
        exception), and the test will fail with a message identifying the package and the
        offending specifier.

        Parameters:
            requirements (List[Tuple[str, str]]): Iterable of (package_name, version_spec)
                tuples produced by `parse_requirements`, where `version_spec` may be an empty
                string.
        """
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
        """Test that existing packages are still present."""
        package_names = [pkg for pkg, _ in requirements]
        
        expected_packages = [
            'pytest',
            'pytest-cov',
            'pytest-asyncio',
            'flake8',
            'pylint',
        ]
        
        for expected_pkg in expected_packages:
            assert expected_pkg in package_names

class TestRequirementsFileFormatting:
    """Additional tests for requirements-dev.txt file formatting and structure."""
    
    def test_requirements_file_ends_with_newline(self):
        """Test that requirements-dev.txt ends with a newline character (Unix convention)."""
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        with open(REQUIREMENTS_FILE, 'rb') as f:
            content = f.read()
        
        assert len(content) > 0, "requirements-dev.txt is empty"
        assert content.endswith(b'\n'), (
            "requirements-dev.txt should end with a newline character (Unix convention)"
        )
    
    def test_pyyaml_and_types_on_separate_lines(self):
        """
        Ensure PyYAML and types-PyYAML each appear on their own line in the requirements file with >=6.0 version constraints.
        
        Reads the requirements file and builds a list of non-empty, non-comment lines after stripping
        leading and trailing whitespace from each line. Using stripped lines avoids false negatives
        when comments or package entries contain leading spaces. The test then asserts there are
        exactly two lines that begin with the stripped prefixes `PyYAML` or `types-PyYAML`, and that
        one starts with `PyYAML>=` and the other with `types-PyYAML>=`.
        """
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        with open(REQUIREMENTS_FILE, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        # Find lines that start with either PyYAML or types-PyYAML
        pyyaml_lines = [line for line in lines if line.startswith('PyYAML') or line.startswith('types-PyYAML')]
        
        assert len(pyyaml_lines) == 2, (
            f"Should have exactly 2 separate lines for PyYAML dependencies, found {len(pyyaml_lines)}"
        )
        
        # Verify both are present
        has_pyyaml = any(line.startswith('PyYAML>=') for line in pyyaml_lines)
        has_types = any(line.startswith('types-PyYAML>=') for line in pyyaml_lines)
        
        assert has_pyyaml, "Should have PyYAML>=6.0"
        assert has_types, "Should have types-PyYAML>=6.0"
    
    def test_no_trailing_whitespace_in_lines(self):
        """Test that requirements-dev.txt has no trailing whitespace on any line."""
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        with open(REQUIREMENTS_FILE, 'r') as f:
            lines = f.readlines()
        
        lines_with_trailing_space = []
        for i, line in enumerate(lines, 1):
            # Check if line (excluding newline) has trailing whitespace
            if line.rstrip('\r\n') != line.rstrip():
                lines_with_trailing_space.append(i)
        
        assert len(lines_with_trailing_space) == 0, (
            f"Lines with trailing whitespace: {lines_with_trailing_space}. "
            "Remove trailing spaces for clean file formatting."
        )


class TestRequirementsPackageIntegrity:
    """Additional tests for package integrity and consistency in requirements-dev.txt."""
    
    @staticmethod
    def _find_duplicate_packages(requirements: List[Tuple[str, str]]) -> List[str]:
        """
        Find duplicate package names in a requirements list by comparing names case-insensitively.
        
        Parameters:
            requirements (List[Tuple[str, str]]): Sequence of (package_name, version_spec) tuples to inspect.
        
        Returns:
            List[str]: A list of lower-cased package names representing each repeated occurrence
            after the first appearance; duplicates are returned in the order they are encountered
            in the requirements list to match the implementation behaviour.
        """
        package_names = [pkg.lower() for pkg, _ in requirements]
        seen = set()
        duplicates = []
        for pkg in package_names:
            if pkg in seen:
                duplicates.append(pkg)
            seen.add(pkg)
        return duplicates

    def test_no_duplicate_package_names(self):
        """Test that no package appears multiple times in requirements-dev.txt."""
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        requirements = parse_requirements(REQUIREMENTS_FILE)
        duplicates = TestRequirementsPackageIntegrity._find_duplicate_packages(requirements)
        assert len(duplicates) == 0, (
            f"Duplicate packages found in requirements-dev.txt: {duplicates}. "
            "Each package should appear only once."
        )
    
    def test_pyyaml_compatible_versions(self):
        """
        Ensure PyYAML and types-PyYAML specify the same major version in requirements-dev.txt.
        
        Checks that both "PyYAML" and "types-PyYAML" appear with a '>=<version>' constraint and that the integer before the first dot (the major version) is identical for both packages.
        """
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        with open(REQUIREMENTS_FILE, 'r') as f:
            content = f.read()
        
        # Extract versions
        pyyaml_version = None
        types_version = None
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('PyYAML>='):
                pyyaml_version = line.split('>=')[1].strip()
            elif line.startswith('types-PyYAML>='):
                types_version = line.split('>=')[1].strip()
        
        assert pyyaml_version is not None, "PyYAML version constraint not found"
        assert types_version is not None, "types-PyYAML version constraint not found"
        
        # They should have matching major versions for compatibility
        pyyaml_major = pyyaml_version.split('.')[0]
        types_major = types_version.split('.')[0]
        
        assert pyyaml_major == types_major, (
            f"PyYAML (>={pyyaml_version}) and types-PyYAML (>={types_version}) "
            f"should have matching major versions. Found: {pyyaml_major} vs {types_major}"
        )
    
    def test_all_packages_use_consistent_operators(self):
        """
        Ensure the majority of version specifiers in requirements-dev.txt use the '>=' operator.
        
        Parses REQUIREMENTS_FILE, counts comparison operators (`>=`, `==`, `<=`, `>`, `<`, `~=`) found in non-empty version specifications, and asserts that at least 50% of all detected operators are `>=`. On failure, raises an assertion that includes the percentage of `>=` usages and the operator counts.
        """
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        requirements = parse_requirements(REQUIREMENTS_FILE)
        
        # Count operator usage using regex pattern that matches operators followed by version
        # This avoids substring matching issues (e.g., >= being counted as both >= and >)
        operator_counts = {'>=': 0, '==': 0, '<=': 0, '>': 0, '<': 0, '~=': 0}
        
        for pkg, version_spec in requirements:
            if version_spec:
                # Match operators followed by version numbers to avoid overlapping matches
                # Pattern: operator followed by version (digits, dots, etc.)
                for op in ['>=', '==', '<=', '~=', '>', '<']:
                    # Use lookahead to ensure operator is followed by a version number
                    pattern = re.escape(op) + r'(?=\d)'
                    operator_counts[op] += len(re.findall(pattern, version_spec))
        
        # Most packages should use >= (minimum version specifier)
        total_specs = sum(operator_counts.values())
        if total_specs > 0:
            ge_percentage = (operator_counts['>='] / total_specs) * 100
            
            # At least 50% should use >= for flexibility
            assert ge_percentage >= 50, (
                f"Only {ge_percentage:.1f}% of version constraints use '>=' operator. "
                f"Prefer '>=' for minimum version requirements. Operator counts: {operator_counts}"
            )


class TestPyYAMLIntegration:
    """Tests specific to the PyYAML addition in this branch."""
    
    def test_pyyaml_addition_has_both_runtime_and_types(self):
        """
        Assert that the development requirements file contains both runtime and type-stub entries for PyYAML with minimum version 6.0.
        
        Asserts that the requirements-dev.txt file exists, contains entries named 'PyYAML' and 'types-PyYAML', and that each entry's version specifier includes '>=6.0'.
        """
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        requirements = parse_requirements(REQUIREMENTS_FILE)
        package_names = [pkg for pkg, _ in requirements]
        
        assert 'PyYAML' in package_names, (
            "PyYAML should be present in requirements-dev.txt (added in this branch)"
        )
        assert 'types-PyYAML' in package_names, (
            "types-PyYAML should be present in requirements-dev.txt (added in this branch)"
        )
        
        # Both should have version constraints
        pyyaml_entry = next((ver for pkg, ver in requirements if pkg == 'PyYAML'), None)
        types_entry = next((ver for pkg, ver in requirements if pkg == 'types-PyYAML'), None)
        
        assert pyyaml_entry and '>=6.0' in pyyaml_entry, (
            "PyYAML should have version constraint >=6.0"
        )
        assert types_entry and '>=6.0' in types_entry, (
            "types-PyYAML should have version constraint >=6.0"
        )
    
    def test_pyyaml_needed_for_workflow_tests(self):
        """
        Ensure PyYAML is declared in requirements-dev.txt and is usable for workflow validation.
        
        Checks that the requirements-dev.txt file exists and contains a PyYAML entry (case-insensitive). Then attempts to import the yaml module and verifies a basic safe_load operation; if the module is not importable in the current environment the test is skipped.
        """
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        with open(REQUIREMENTS_FILE, 'r') as f:
            content = f.read()
        
        # PyYAML should be present (case-insensitive check)
        assert 'pyyaml' in content.lower(), (
            "PyYAML must be in requirements-dev.txt as it's needed for workflow validation tests"
        )
        
        # Verify we can actually import yaml (validates the requirement works)
        try:
            import yaml
            # Successfully imported - requirement is satisfied
            assert yaml.safe_load("key: value") == {'key': 'value'}, "PyYAML import successful"
        except ImportError:
            pytest.skip("PyYAML not installed in test environment (will be installed from requirements)")
