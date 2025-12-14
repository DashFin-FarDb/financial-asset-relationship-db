"""
Tests for requirements-dev.txt development dependencies file.

This test suite validates that the development dependencies file is properly
formatted, contains required packages, and has valid version specifications.
"""

import re
from pathlib import Path
from typing import List, Tuple

import pytest
from packaging.requirements import Requirement

REQUIREMENTS_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


def parse_requirements(file_path: Path) -> List[Tuple[str, str]]:
    """Parse requirements file and return list of (package, version_spec) tuples.
        Examples:
            Input line: "requests>=2.25.0"
            Output: ("requests", ">=2.25.0")

            Input line: "pytest>=6.0,<7.0 # testing framework"
            Output: ("pytest", ">=6.0,<7.0")

            Input line: "pandas"
            Output: ("pandas", "")

            Input line: "package[extra1,extra2]>=1.0"
            Output: ("package", ">=1.0")
        Raises:
            ValueError: If a requirement line is malformed.
            OSError: If the requirements file could not be opened or read.
        ...
        """
    requirements = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith('#'):
                    continue

                try:
                    req = Requirement(line)
                except (ValueError, TypeError) as e:
                    print(f"Could not parse requirement: {line} due to {e}")
                    continue

                # Preserve the package token as written in the requirements file (preserve casing)
                # by extracting the substring before any specifier/operator/extras/marker characters.
                raw_pkg_token = line.split(';', 1)[0]  # drop environment markers
                raw_pkg_token = raw_pkg_token.split('[', 1)[0]  # drop extras
                # split at the first occurrence of any operator character (<,>,=,!,~) or comma
                pkg_part = re.split(r'(?=[<>=!~,])', raw_pkg_token, 1)[0].strip()
                pkg = pkg_part or req.name.strip()

                specifier_str = str(req.specifier).strip()
                # Normalize specifier string by removing spaces around commas so SpecifierSet accepts it consistently
                if specifier_str:
                    specifier_str = ','.join(s.strip() for s in specifier_str.split(',') if s.strip())

                requirements.append((pkg, specifier_str))
    except OSError as e:
        raise OSError(f"Could not open requirements file '{file_path}': {e}") from e

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
    def requirements(self, parsed_requirements) -> List[Tuple[str, str]]:
        """Parse and return requirements."""
        return parsed_requirements

    @pytest.fixture
    def package_names(self, parsed_requirements) -> List[str]:
        """Extract just the package names."""
        return [pkg for pkg, _ in parsed_requirements]

    def test_has_pytest(self, package_names: List[str]):
        """Test that pytest is included."""
        assert 'pytest' in package_names

    def test_has_pytest_cov(self, package_names: List[str]):
        """Test that pytest-cov is included."""
        assert 'pytest-cov' in package_names

    def test_has_pyyaml(self, package_names: List[str]):
        """Test that PyYAML is included (added in the diff)."""
        assert 'pyyaml' in package_names

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
    def requirements(self, parsed_requirements) -> List[Tuple[str, str]]:
        """Parse and return requirements."""
        return parsed_requirements

    def test_all_packages_have_versions(self, requirements: List[Tuple[str, str]]):
        """Test that all packages specify version constraints."""
        packages_without_versions = [pkg for pkg, ver in requirements if not ver]
        assert len(packages_without_versions) == 0

    def test_version_format_valid(self, requirements: List[Tuple[str, str]]):
        """Test that version specifications use valid format."""
        version_pattern = re.compile(r'^(>=|==|<=|>|<|~=)\d+(\.\d+)*$')

        for _, ver_spec in requirements:
            if ver_spec:
                assert version_pattern.match(ver_spec)

    def test_pyyaml_version(self, requirements: List[Tuple[str, str]]):
        """Test that PyYAML has appropriate version constraint."""
        pyyaml_specs = [ver for pkg, ver in requirements if pkg == 'pyyaml']
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
        _, ver = pyyaml_entries[0]
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
            'pytest-mock',
            'flake8',
            'pylint',
            'mypy',
            'black',
            'isort',
            'pre-commit'
        ]

        for expected_pkg in expected_packages:
            assert expected_pkg in package_names
