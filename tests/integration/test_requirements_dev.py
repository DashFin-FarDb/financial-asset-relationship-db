"""
Tests for requirements-dev.txt development dependencies file.

This test suite validates that the development dependencies file is properly
formatted, contains required packages, and has valid version specifications.
"""

import re
from pathlib import Path
from typing import List, Tuple

import pytest
from packaging.specifiers import SpecifierSet

REQUIREMENTS_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


def parse_requirements(file_path: Path) -> List[Tuple[str, str]]:
    """
    Parse a requirements file into a list of package names with their version specifiers.

    Parameters:
        file_path (Path): Path to a requirements-style text file encoded in UTF-8.

    Returns:
        List[Tuple[str, str]]: A list of (package, version_spec) tuples where `package` is the canonical
        package name (alphanumeric plus . _ -) and `version_spec` is a comma-separated string of
        specifiers (e.g. ">=1.0,<=2.0") or empty string if no constraints present.

    Raises:
        AssertionError: If a requirement line contains a malformed package name.
    """
    requirements = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
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
    except (FileNotFoundError, IOError) as e:
        raise AssertionError(f"Could not read requirements file: {file_path} ({e})")

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
        """
        Load the entire requirements-dev.txt file content.

        Returns:
            content (str): The raw text of the requirements file, including any trailing newline.
        """
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
        """
        Verify the provided file content ends with a newline character.

        Parameters:
            file_content (str): Raw contents of the requirements file to check.
        """
        assert file_content.endswith('\n')


class TestRequiredPackages:
    """Test that required development packages are present."""

    @pytest.fixture
    def requirements(self) -> List[Tuple[str, str]]:
        """
        Load and parse the development requirements file into package/version tuples.

        Returns:
            List[Tuple[str, str]]: A list of (package, version_spec) tuples parsed from requirements-dev.txt; `version_spec` is an empty string when no constraints are present.
        """
        return parse_requirements(REQUIREMENTS_FILE)

    @pytest.fixture
    def package_names(self, requirements: List[Tuple[str, str]]) -> List[str]:
        """
        Extract package names from parsed requirements.

        Parameters:
            requirements (List[Tuple[str, str]]): Iterable of (package, version_spec) tuples as returned by parse_requirements.

        Returns:
            List[str]: Package names in the same order as provided.
        """
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
        Parse the development requirements file into a list of (package, version_spec) tuples.

        Returns:
            List[Tuple[str, str]]: Each tuple contains the package name and its version specifier; the version specifier is an empty string when no constraint is present.
        """
        return parse_requirements(REQUIREMENTS_FILE)

    def test_all_packages_have_versions(self, requirements: List[Tuple[str, str]]):
        """
        Verify every parsed requirement includes a version specifier.

        Parameters:
            requirements (List[Tuple[str, str]]): List of (package_name, version_spec) tuples where `version_spec` is an empty string if no constraint was provided.

        Raises:
            AssertionError: If any package has an empty version specifier.
        """
        packages_without_versions = [pkg for pkg, ver in requirements if not ver]
        assert len(packages_without_versions) == 0

    def test_version_format_valid(self, requirements: List[Tuple[str, str]]):
        """
        Verify that every non-empty version specifier in the provided requirements conforms to PEP 440.

        Parameters:
            requirements (List[Tuple[str, str]]): List of (package_name, version_spec) tuples produced by parse_requirements; `version_spec` may be an empty string and will be skipped.
        """
        for pkg, ver_spec in requirements:
            if ver_spec:
                try:
                    SpecifierSet(ver_spec)
                except Exception as e:
                    assert False, f"Invalid version specifier for {pkg}: {ver_spec} ({e})"

    def test_pyyaml_version(self, requirements: List[Tuple[str, str]]):
        """
        Verify that PyYAML is required with a minimum version of 6.0.

        Asserts a PyYAML entry is present in the parsed requirements and its version specifier starts with ">=6.0".
        """
        pyyaml_specs = [ver for pkg, ver in requirements if pkg == 'PyYAML']
        assert len(pyyaml_specs) > 0
        assert pyyaml_specs[0].startswith('>=6.0')

    def test_uses_minimum_versions(self, requirements: List[Tuple[str, str]]):
        """
        Assert that a large majority of package version specifications use the ">=" operator.

        Parameters:
            requirements (List[Tuple[str, str]]): Parsed requirements as (package_name, version_spec) tuples; version_spec is an empty string when no constraint is present.

        Raises:
            AssertionError: if fewer than 70% of entries that include a version specification start with ">=".
        """
        specs_using_gte = [ver for pkg, ver in requirements if ver.startswith('>=')]
        all_with_versions = [ver for pkg, ver in requirements if ver]
        assert len(specs_using_gte) >= len(all_with_versions) * 0.7


class TestPackageConsistency:
    """Test consistency and relationships between packages."""

    @pytest.fixture
    def package_names(self) -> List[str]:
        """
        Extracts package names from the parsed development requirements file.

        Returns:
            List[str]: Package names in the same order they appear in REQUIREMENTS_FILE.
        """
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
        """
        Load and parse the development requirements file into package/version tuples.

        Returns:
            List[Tuple[str, str]]: A list of (package, version_spec) tuples parsed from requirements-dev.txt; `version_spec` is an empty string when no constraints are present.
        """
        return parse_requirements(REQUIREMENTS_FILE)

    def test_pyyaml_added(self, requirements: List[Tuple[str, str]]):
        """
        Verify that exactly one `PyYAML` entry exists in the parsed requirements and that its version specifier is `>=6.0`.

        Parameters:
                requirements (List[Tuple[str, str]]): Parsed requirements as (package, version_spec) tuples.
        """
        pyyaml_entries = [(pkg, ver) for pkg, ver in requirements if pkg == 'PyYAML']
        assert len(pyyaml_entries) == 1
        pkg, ver = pyyaml_entries[0]
        assert ver == '>=6.0'

    def test_types_pyyaml_added(self, requirements: List[Tuple[str, str]]):
        """
        Assert that exactly one 'types-PyYAML' entry exists in the parsed requirements.

        Parameters:
            requirements (List[Tuple[str, str]]): Parsed requirements as (package, version_spec) tuples.
        """
        types_entries = [(pkg, ver) for pkg, ver in requirements if pkg == 'types-PyYAML']
        assert len(types_entries) == 1

    def test_existing_packages_preserved(self, requirements: List[Tuple[str, str]]):
        # Ensure expected baseline packages are still present after changes
        package_names = [pkg for pkg, _ in requirements]

        expected_packages = [
            'pytest',
            'pytest-cov',
            'flake8',
            'black',
            'mypy',
            'PyYAML',
            'types-PyYAML',
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
        Verify that PyYAML and types-PyYAML each appear on their own line in requirements-dev.txt with a >=6.0 version constraint.

        Checks that the requirements file exists, collects non-empty non-comment lines, asserts there are exactly two lines that begin with either `PyYAML` or `types-PyYAML`, and requires one line to start with `PyYAML>=` and the other with `types-PyYAML>=`.
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
        Finds duplicate package names in a requirements list using case-insensitive comparison.

        Parameters:
            requirements (List[Tuple[str, str]]): Sequence of (package_name, version_spec) pairs as returned by parse_requirements.

        Returns:
            List[str]: Lowercased package names that appear more than once. Each additional occurrence after the first is included once (so a package present three times yields two entries).
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
        Ensure PyYAML and types-PyYAML declare matching major-version constraints in requirements-dev.txt.

        Asserts that both packages appear with a '>=' version specifier and that their major version components are equal.
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
        Verify requirements-dev.txt contains both PyYAML and types-PyYAML entries constrained to >=6.0.

        Asserts that the requirements file exists, contains 'PyYAML' and 'types-PyYAML', and that each package's version spec includes '>=6.0'.
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
        Verify PyYAML is declared in the development requirements and is importable for workflow validation tests.

        Checks that requirements-dev.txt contains "PyYAML" (case-insensitive) and that the `yaml` module can be imported and used via `yaml.safe_load`; skips the test if PyYAML is not installed in the current environment.
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
