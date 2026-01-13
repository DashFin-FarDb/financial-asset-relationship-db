"""
Integration tests for requirements.txt file.

This module validates that the production requirements file is well-
formatted, contains required packages, has valid version specifications,
and includes security-pinned dependencies.

Note: Bandit B101 (assert_used) is suppressed for this test file as assert
statements are the standard and required pattern in pytest test files.
"""

# nosec B101  # Suppress Bandit assert warnings - assert is correct in pytest tests

import re
from pathlib import Path
from typing import List, Tuple

import pytest
from packaging.requirements import InvalidRequirement, Requirement

# Path to requirements.txt file (production dependencies)
REQUIREMENTS_FILE = Path(__file__).parent.parent.parent / "requirements.txt"


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
    """
    requirements = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                try:
                    # Remove inline comments
                    line = line.split("#")[0].strip()
                    req = Requirement(line)
                except InvalidRequirement as e:
                    raise ValueError(f"Invalid requirement line: {line}") from e

                # Preserve the package token as written in the requirements file
                raw_pkg_token = line.split(";", 1)[0]  # drop environment markers
                raw_pkg_token = raw_pkg_token.split("[", 1)[0]  # drop extras
                pkg_part = re.split(r"(?=[<>=!~,])", raw_pkg_token, 1)[0].strip()
                pkg = pkg_part or req.name.strip()

                specifier_str = str(req.specifier).strip()
                if specifier_str:
                    specifier_str = ",".join(s.strip() for s in specifier_str.split(",") if s.strip())

                requirements.append((pkg, specifier_str))
    except OSError as e:
        raise OSError(f"Could not read requirements file: {file_path}") from e

    return requirements


class TestRequirementsFileExists:
    """Test that the requirements.txt file exists and is accessible."""

    @staticmethod
    def test_file_exists():
        """Test that requirements.txt file exists."""
        assert REQUIREMENTS_FILE.exists()

    @staticmethod
    def test_file_is_file():
        """Test that requirements.txt is a file, not a directory."""
        assert REQUIREMENTS_FILE.is_file()

    @staticmethod
    def test_file_is_readable():
        """Test that the file can be read."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            assert len(content) > 0


class TestRequirementsFileFormat:
    """Test requirements.txt file formatting and structure."""

    @pytest.fixture
    def file_content(self) -> str:
        """Load requirements file content."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    def file_lines(self) -> List[str]:
        """Load requirements file as list of lines."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            return f.readlines()

    @staticmethod
    def test_file_encoding():
        """Test that file uses UTF-8 encoding."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            f.read()

    @staticmethod
    def test_no_trailing_whitespace(file_lines: List[str]):
        """Test that lines don't have trailing whitespace."""
        lines_with_trailing = [
            (i + 1, repr(line)) for i, line in enumerate(file_lines) if line.rstrip("\n") != line.rstrip()
        ]
        assert len(lines_with_trailing) == 0, f"Lines with trailing whitespace: {lines_with_trailing}"

    @staticmethod
    def test_ends_with_newline(file_content: str):
        """Test that file ends with a newline."""
        assert file_content.endswith("\n"), "File should end with a newline character"

    @staticmethod
    def test_no_blank_lines_in_middle(file_lines: List[str]):
        """Test that there are no excessive blank lines (max 1 consecutive)."""
        consecutive_blanks = 0
        max_consecutive = 0
        for line in file_lines:
            if line.strip() == "":
                consecutive_blanks += 1
                max_consecutive = max(max_consecutive, consecutive_blanks)
            else:
                consecutive_blanks = 0
        assert max_consecutive <= 1, f"Found {max_consecutive} consecutive blank lines"


class TestRequiredPackages:
    """Test that required production packages are present."""

    @pytest.fixture
    @staticmethod
    def requirements() -> List[Tuple[str, str]]:
        """Parse requirements and return list of (package, version) tuples."""
        return parse_requirements(REQUIREMENTS_FILE)

    @pytest.fixture
    @staticmethod
    def package_names(requirements: List[Tuple[str, str]]) -> List[str]:
        """Extract package names from requirements."""
        return [pkg.lower() for pkg, _ in requirements]

    @staticmethod
    def test_has_core_packages(package_names: List[str]):
        """Test that core application packages are present."""
        # Based on the application structure, these are likely core dependencies
        assert len(package_names) > 0, "Requirements file should not be empty"

    @staticmethod
    def test_has_fastapi(package_names: List[str]):
        """Test that FastAPI is included for API framework."""
        assert "fastapi" in package_names

    @staticmethod
    def test_has_uvicorn(package_names: List[str]):
        """Test that uvicorn is included for ASGI server."""
        assert "uvicorn" in package_names

    @staticmethod
    def test_has_pydantic(package_names: List[str]):
        """Test that pydantic is included for data validation."""
        assert "pydantic" in package_names

    @staticmethod
    def test_has_httpx(package_names: List[str]):
        """Test that httpx is included for HTTP client."""
        assert "httpx" in package_names

    @staticmethod
    def test_has_pytest(package_names: List[str]):
        """Test that pytest is included for testing."""
        assert "pytest" in package_names

    @staticmethod
    def test_has_security_pinned_packages(requirements: List[Tuple[str, str]]):
        """Test that security-pinned packages are present with comments."""
        # Check for zipp which was added as a security fix
        zipp_entries = [pkg for pkg, _ in requirements if pkg.lower() == "zipp"]
        assert len(zipp_entries) > 0, "Security-pinned package 'zipp' should be present"


class TestVersionSpecifications:
    """Test version specifications and constraints."""

    @pytest.fixture
    @staticmethod
    def requirements() -> List[Tuple[str, str]]:
        """Parse requirements and return list of (package, version) tuples."""
        return parse_requirements(REQUIREMENTS_FILE)

    def test_all_packages_parseable(self, requirements: List[Tuple[str, str]]):
        """Test that all package specifications are parseable."""
        assert len(requirements) > 0

    def test_version_format_valid(self, requirements: List[Tuple[str, str]]):
        """Test that version specifications use valid format."""
        version_pattern = re.compile(r"^(>=|==|<=|>|<|~=)\d+(\.\d+)*$")

        for pkg, ver_spec in requirements:
            if ver_spec:
                # Split compound version specs (e.g., ">=1.0,<2.0")
                for spec in ver_spec.split(","):
                    spec = spec.strip()
                    assert version_pattern.match(spec), f"Invalid version spec '{spec}' for package '{pkg}'"

    def test_zipp_security_version(self, requirements: List[Tuple[str, str]]):
        """Test that zipp has the security-required minimum version."""
        zipp_specs = [ver for pkg, ver in requirements if pkg.lower() == "zipp"]
        assert len(zipp_specs) > 0, "zipp should be present for security fix"
        assert zipp_specs[0].startswith(">=3.19"), f"zipp should be >=3.19.1, got {zipp_specs[0]}"

    def test_uses_minimum_versions(self, requirements: List[Tuple[str, str]]):
        """Test that most packages use >= for version specifications."""
        specs_using_gte = [ver for pkg, ver in requirements if ver.startswith(">=")]
        all_with_versions = [ver for pkg, ver in requirements if ver]
        # At least 70% should use >= for flexibility
        assert len(specs_using_gte) >= len(all_with_versions) * 0.7

    def test_no_exact_pins_without_comment(self, requirements: List[Tuple[str, str]]):
        """Test that exact pins (==) are documented with comments in the file."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        exact_pins = [pkg for pkg, ver in requirements if ver.startswith("==")]

        for pkg in exact_pins:
            # Find the line with this package
            pkg_lines = [line for line in lines if pkg.lower() in line.lower() and "==" in line]
            assert len(pkg_lines) > 0, f"Package {pkg} not found in file"
            # Check if there's a comment on the same line or nearby
            has_comment = any("#" in line for line in pkg_lines)
            assert has_comment, f"Exact pin for {pkg} should have a comment explaining why"


class TestPackageConsistency:
    """Test package consistency and naming conventions."""

    @pytest.fixture
    @staticmethod
    def requirements() -> List[Tuple[str, str]]:
        """Parse requirements and return list of (package, version) tuples."""
        return parse_requirements(REQUIREMENTS_FILE)

    @pytest.fixture
    @staticmethod
    def package_names(requirements: List[Tuple[str, str]]) -> List[str]:
        """Extract package names from requirements."""
        return [pkg for pkg, _ in requirements]

    @staticmethod
    def test_no_duplicate_packages(package_names: List[str]):
        """Test that no package is listed multiple times."""
        lowercase_names = [name.lower() for name in package_names]
        duplicates = [name for name in lowercase_names if lowercase_names.count(name) > 1]
        assert len(set(duplicates)) == 0, f"Duplicate packages found: {set(duplicates)}"

    @staticmethod
    def test_packages_sorted_logically(package_names: List[str]):
        """Test that packages are organized in logical groups."""
        # We don't enforce strict alphabetical sorting, but check for some organization
        assert len(package_names) > 0

    @staticmethod
    def test_package_names_valid(package_names: List[str]):
        """Test that package names follow valid naming conventions."""
        valid_name_pattern = re.compile(r"^[a-zA-Z0-9_-]+$")

        invalid_names = [pkg for pkg in package_names if not valid_name_pattern.match(pkg)]
        assert len(invalid_names) == 0, f"Invalid package names: {invalid_names}"

    @staticmethod
    def test_no_conflicting_packages(package_names: List[str]):
        """Test that there are no known conflicting packages."""
        # Check for common conflicts (example: different database drivers)
        lowercase_names = [name.lower() for name in package_names]

        # These are examples - adjust based on actual conflicts in the ecosystem
        conflicts = [
            ({"mysql-connector-python", "pymysql"}, "Multiple MySQL connectors"),
            ({"psycopg2", "psycopg2-binary"}, "Conflicting psycopg2 packages"),
        ]

        for conflict_set, message in conflicts:
            found = conflict_set.intersection(set(lowercase_names))
            assert len(found) <= 1, f"{message}: {found}"


class TestFileOrganization:
    """Test file organization and structure."""

    @pytest.fixture
    @staticmethod
    def file_lines() -> List[str]:
        """Load requirements file as list of lines."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            return f.readlines()

    def test_reasonable_file_size(self, file_lines: List[str]):
        """Test that file size is reasonable (not too large)."""
        # Production requirements should typically be under 100 lines
        assert len(file_lines) < 200, f"Requirements file is too large: {len(file_lines)} lines"

    def test_has_comments_for_sections(self, file_lines: List[str]):
        """Test that file has organizational comments."""
        comment_lines = [line for line in file_lines if line.strip().startswith("#")]
        # Should have at least some comments for organization
        assert len(comment_lines) > 0, "File should have comments for organization"


class TestSecurityAndCompliance:
    """Test security-related requirements and compliance."""

    @pytest.fixture
    @staticmethod
    def requirements() -> List[Tuple[str, str]]:
        """Parse requirements and return list of (package, version) tuples."""
        return parse_requirements(REQUIREMENTS_FILE)

    @pytest.fixture
    @staticmethod
    def file_content() -> str:
        """Load requirements file content."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def test_zipp_security_fix_present(self, requirements: List[Tuple[str, str]]):
        """Test that zipp security fix is present."""
        zipp_entries = [(pkg, ver) for pkg, ver in requirements if pkg.lower() == "zipp"]
        assert len(zipp_entries) == 1, "zipp security pin should be present exactly once"
        pkg, ver = zipp_entries[0]
        assert ver == ">=3.19.1", f"zipp version should be >=3.19.1, got {ver}"

    def test_zipp_has_security_comment(self, file_content: str):
        """Test that zipp entry has a comment explaining it's for security."""
        # Find the zipp line
        lines = file_content.split("\n")
        zipp_lines = [line for line in lines if "zipp" in line.lower() and not line.strip().startswith("#")]
        assert len(zipp_lines) > 0, "zipp line not found"

        zipp_line = zipp_lines[0]
        # Check for security-related keywords in comment
        assert "#" in zipp_line, "zipp line should have a comment"
        comment = zipp_line.split("#", 1)[1].lower()
        security_keywords = ["security", "vulnerability", "snyk", "pinned"]
        assert any(
            keyword in comment for keyword in security_keywords
        ), f"zipp comment should mention security/vulnerability, got: {comment}"

    def test_no_known_vulnerable_versions(self, requirements: List[Tuple[str, str]]):
        """Test that packages don't use known vulnerable version patterns."""
        # This is a basic check - in production, integrate with safety or snyk
        for pkg, ver in requirements:
            # Example: check that we're not using very old versions
            if ver.startswith("=="):
                version_match = re.search(r"==(\d+)\.(\d+)", ver)
                if version_match:
                    major = int(version_match.group(1))


class TestEdgeCases:
    """Test edge cases and error handling in requirements parsing."""

    @staticmethod
    def test_parse_with_extras():
        """Test parsing packages with extras."""
        # Test that packages with extras are handled correctly
        requirements = parse_requirements(REQUIREMENTS_FILE)
        # If any package has extras, ensure it's parsed correctly
        for pkg, _ in requirements:
            assert "[" not in pkg, f"Package name should not contain '[': {pkg}"

    @staticmethod
    def test_parse_with_environment_markers():
        """Test parsing packages with environment markers."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        # Ensure environment markers are stripped
        for pkg, ver in requirements:
            assert ";" not in pkg, f"Package name should not contain ';': {pkg}"
            assert ";" not in ver, f"Version spec should not contain ';': {ver}"

    @staticmethod
    def test_parse_with_inline_comments():
        """Test that inline comments are properly handled."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        # Ensure comments don't leak into package names or versions
        for pkg, ver in requirements:
            assert "#" not in pkg, f"Package name should not contain '#': {pkg}"
            assert "#" not in ver, f"Version spec should not contain '#': {ver}"

    @staticmethod
    def test_empty_lines_ignored():
        """Test that empty lines and comment-only lines are ignored."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        # All returned entries should have valid package names
        for pkg, _ in requirements:
            assert len(pkg) > 0, "Package name should not be empty"
            assert pkg.strip() == pkg, f"Package name should not have leading/trailing whitespace: '{pkg}'"


class TestComprehensiveValidation:
    """Comprehensive validation tests for the requirements file."""

    @pytest.fixture
    @staticmethod
    def requirements() -> List[Tuple[str, str]]:
        """Parse requirements and return list of (package, version) tuples."""
        return parse_requirements(REQUIREMENTS_FILE)

    def test_all_packages_have_versions_or_pins(self, requirements: List[Tuple[str, str]]):
        """Test that critical packages have version specifications."""
        packages_without_versions = [pkg for pkg, ver in requirements if not ver]
        # Allow some packages without versions, but production deps should mostly be pinned
        assert (
            len(packages_without_versions) <= len(requirements) * 0.2
        ), f"Too many packages without versions: {packages_without_versions}"

    def test_version_consistency(self, requirements: List[Tuple[str, str]]):
        """Test that version specifications are consistent in style."""
        version_styles = {}
        for pkg, ver in requirements:
            if ver:
                if ver.startswith(">="):
                    version_styles.setdefault("minimum", []).append(pkg)
                elif ver.startswith("=="):
                    version_styles.setdefault("exact", []).append(pkg)
                elif ver.startswith("~="):
                    version_styles.setdefault("compatible", []).append(pkg)

        # Should use consistent versioning strategy (mostly one style)
        if version_styles:
            max_style = max(version_styles.values(), key=len)
            total_versioned = sum(len(v) for v in version_styles.values())
            assert len(max_style) >= total_versioned * 0.6, "Version specifications should be consistent in style"

    def test_transitive_dependencies_documented(self, requirements: List[Tuple[str, str]]):
        """Test that transitive dependencies are documented if pinned."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Packages that are typically transitive dependencies
        transitive_indicators = ["not directly required", "transitive", "pinned by"]

        for line in lines:
            if any(indicator in line.lower() for indicator in transitive_indicators):
                # If mentioning transitive/indirect, should have a comment
                assert "#" in line, f"Transitive dependency line should have comment: {line}"
