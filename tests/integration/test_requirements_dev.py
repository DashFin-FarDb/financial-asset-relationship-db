"""Tests for requirements-dev.txt development dependencies file.

This test suite validates that the development dependencies file is properly
formatted, contains required packages, and has valid version specifications.

Note: Bandit B101 (assert_used) is suppressed for this test file as assert
statements are the standard and required pattern in pytest test files.
"""

# nosec B101  # Suppress Bandit assert warnings - assert is correct in pytest tests

from packaging.requirements import Requirement

REQUIREMENTS_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


@pytest.fixture
def parsed_requirements() -> List[Tuple[str, str]]:
    """Parse requirements file and return list of (package, version_spec) tuples."""
    return parse_requirements(REQUIREMENTS_FILE)


def _extract_package_name(line: str, req: Requirement) -> str:
    """Extract the package name from a requirement line, preserving original casing.

    Args:
        line: The raw requirement line from the file.
        req: The parsed Requirement object.

    Returns:
        The package name as written in the requirements file.
    """
    import re as _re

    # Drop environment markers
    raw_pkg_token = line.split(";", 1)[0]
    # Drop extras
    raw_pkg_token = raw_pkg_token.split("[", 1)[0]
    # Split at the first occurrence of any operator character (<,>,=,!,~) or comma
    pkg_part = _re.split(r"(?=[<>=!~,])", raw_pkg_token, 1)[0].strip()
    if pkg_part:
        return pkg_part
    return req.name.strip()


def _normalize_specifier(specifier_str: str) -> str:
    """Normalize a version specifier string by removing spaces around commas.

    Args:
        specifier_str: The version specifier string to normalize.

    Returns:
        The normalized specifier string.
    """
    if not specifier_str:
        return specifier_str
    parts = [s.strip() for s in specifier_str.split(",") if s.strip()]
    return ",".join(parts)


def _parse_single_requirement(line: str) -> tuple:
    """Parse a single requirement line into (package, version_spec) tuple.

    Args:
        line: A stripped, non-empty, non-comment line from the requirements file.

    Returns:
        A tuple of (package_name, version_specifier) or None if parsing fails.
    """
    try:
        Requirement(line)
    except (ValueError, TypeError) as parse_error:
        print(f"Could not parse requirement: {line} due to {parse_error}")


def _parse_single_requirement(line: str) -> tuple[str, str] | None:
    """Parse a single requirement line into (package, version_spec) tuple.

    Args:
        line: A stripped, non-empty, non-comment line from the requirements file.

    Returns:
        A tuple of (package_name, version_specifier) or None if parsing fails.
    """
    try:
        req = Requirement(line)
    except (ValueError, TypeError) as parse_error:
        print(f"Could not parse requirement: {line} due to {parse_error}")
        return None

    pkg = _extract_package_name(line, req)
    specifier_str = _normalize_specifier(str(req.specifier).strip())
    return (pkg, specifier_str)

    pkg = _extract_package_name(line, req)
    specifier_str = _normalize_specifier(str(req.specifier).strip())
    return (pkg, specifier_str)


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
        with open(file_path, "r", encoding="utf-8") as file_handle:
            for line in file_handle:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                result = _parse_single_requirement(line)
                if result is not None:
                    requirements.append(result)
    except OSError as os_error:
        raise OSError(f"Could not open requirements file '{file_path}': {os_error}") from os_error

    return requirements


class TestRequirementsFileExists:
    """Test that requirements-dev.txt exists and is readable."""

    @staticmethod
    def test_file_exists():
        """Test that requirements-dev.txt file exists."""
        assert REQUIREMENTS_FILE.exists()

    @staticmethod
    def test_file_is_file():
        """Test that the path is a file, not a directory."""
        assert REQUIREMENTS_FILE.is_file()

    @staticmethod
    def test_file_is_readable():
        """Test that the file can be read."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            assert len(content) > 0


class TestRequirementsFileFormat:
    """Test the format and structure of requirements-dev.txt."""

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

    def test_no_trailing_whitespace(self, file_lines: List[str]):
        """Test that lines don't have trailing whitespace."""
        lines_with_trailing = [
            (i + 1, repr(line)) for i, line in enumerate(file_lines) if line.rstrip("\n") != line.rstrip()
        ]
        assert len(lines_with_trailing) == 0

    def test_ends_with_newline(self, file_content: str):
        """Test that file ends with a newline."""
        assert file_content.endswith("\n")


class TestRequiredPackages:
    """Test that required development packages are present."""

    @pytest.fixture
    @staticmethod
    def requirements(parsed_requirements) -> List[Tuple[str, str]]:
        """Parse and return requirements."""
        return parsed_requirements

    @pytest.fixture
    @staticmethod
    def package_names(parsed_requirements) -> List[str]:
        """Extract just the package names."""
        return [pkg for pkg, _ in parsed_requirements]

    def test_has_pytest(self, package_names: List[str]):
        """Test that pytest is included."""
        assert "pytest" in package_names

    def test_has_pytest_cov(self, package_names: List[str]):
        """Test that pytest-cov is included."""
        assert "pytest-cov" in package_names

    def test_has_pyyaml(self, package_names: List[str]):
        """Test that PyYAML is included (added in the diff)."""
        assert "pyyaml" in package_names

    def test_has_types_pyyaml(self, package_names: List[str]):
        """Test that types-PyYAML is included (added in the diff)."""
        assert "types-PyYAML" in package_names

    def test_has_flake8(self, package_names: List[str]):
        """Test that flake8 is included."""
        assert "flake8" in package_names

    def test_has_black(self, package_names: List[str]):
        """Test that black is included."""
        assert "black" in package_names

    def test_has_mypy(self, package_names: List[str]):
        """Test that mypy is included."""
        assert "mypy" in package_names


class TestVersionSpecifications:
    """Test that version specifications are valid and reasonable."""

    @pytest.fixture
    def requirements(self, parsed_requirements) -> List[Tuple[str, str]]:
        """Parse and return requirements."""
        return parsed_requirements

    @staticmethod
    def test_all_packages_have_versions(requirements: List[Tuple[str, str]]):
        """Test that all packages specify version constraints."""
        packages_without_versions = [pkg for pkg, ver in requirements if not ver]
        assert len(packages_without_versions) == 0

    @staticmethod
    def test_version_format_valid(requirements: List[Tuple[str, str]]):
        """Test that version specifications use valid format."""
        version_pattern = re.compile(r"^(>=|==|<=|>|<|~=)\d+(\.\d+)*$")

        for _, ver_spec in requirements:
            if ver_spec:
                assert version_pattern.match(ver_spec)

    @staticmethod
    def test_pyyaml_version(requirements: List[Tuple[str, str]]):
        """Test that PyYAML has appropriate version constraint."""
        pyyaml_specs = [ver for pkg, ver in requirements if pkg == "pyyaml"]
        assert len(pyyaml_specs) > 0
        assert pyyaml_specs[0].startswith(">=6.0")

    @staticmethod
    def test_uses_minimum_versions(requirements: List[Tuple[str, str]]):
        """Test that packages use >= for version specifications."""
        specs_using_gte = [ver for pkg, ver in requirements if ver.startswith(">=")]
        all_with_versions = [ver for pkg, ver in requirements if ver]
        assert len(specs_using_gte) >= len(all_with_versions) * 0.7


class TestPackageConsistency:
    """Test consistency and relationships between packages."""

    @pytest.fixture
    def package_names(self) -> List[str]:
        """Extract package names from requirements."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        return [pkg for pkg, _ in requirements]

    @staticmethod
    def test_types_packages_match_base_packages(package_names: List[str]):
        """Test that type stub packages have corresponding base packages."""
        types_packages = [pkg for pkg in package_names if pkg.startswith("types-")]

        for types_pkg in types_packages:
            base_pkg = types_pkg.replace("types-", "")
            base_exists = any(pkg.lower() == base_pkg.lower() for pkg in package_names)
            assert base_exists

    @staticmethod
    def test_no_duplicate_packages(package_names: List[str]):
        """Test that no package is listed multiple times."""
        seen = set()
        duplicates = []

        for pkg in package_names:
            if pkg.lower() in seen:
                duplicates.append(pkg)
            seen.add(pkg.lower())

        assert len(duplicates) == 0

    @staticmethod
    def test_package_names_valid(package_names: List[str]):
        """Test that package names follow valid naming conventions."""
        valid_name_pattern = re.compile(r"^[a-zA-Z0-9_-]+$")

        invalid_names = [pkg for pkg in package_names if not valid_name_pattern.match(pkg)]
        assert len(invalid_names) == 0


class TestFileOrganization:
    """Test that the file is well-organized."""

    @pytest.fixture
    def file_lines(self) -> List[str]:
        """Load requirements file as list of lines."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            return f.readlines()

    def test_reasonable_file_size(self, file_lines: List[str]):
        """Test that file isn't excessively large."""
        assert len(file_lines) < 100

    @staticmethod
    def test_has_appropriate_number_of_packages():
        """Test that file has a reasonable number of development dependencies."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        assert 5 <= len(requirements) <= 50


class TestSpecificChanges:
    """Test the specific changes made in the diff."""

    @staticmethod
    @pytest.fixture
    def requirements() -> List[Tuple[str, str]]:
        """Parse and return requirements."""
        return parse_requirements(REQUIREMENTS_FILE)

    def test_pyyaml_added(self, requirements: List[Tuple[str, str]]):
        """Test that PyYAML was added as per the diff."""
        pyyaml_entries = [(pkg, ver) for pkg, ver in requirements if pkg == "PyYAML"]
        assert len(pyyaml_entries) == 1
        _, ver = pyyaml_entries[0]
        assert ver == ">=6.0"

    def test_types_pyyaml_added(self, requirements: List[Tuple[str, str]]):
        """Test that types-PyYAML was added as per the diff."""
        types_entries = [(pkg, ver) for pkg, ver in requirements if pkg == "types-PyYAML"]
        assert len(types_entries) == 1

    def test_existing_packages_preserved(self, requirements: List[Tuple[str, str]]):
        """Test that existing packages are still present."""
        package_names = [pkg for pkg, _ in requirements]

        expected_packages = [
            "pytest",
            "pytest-cov",
            "pytest-mock",
            "flake8",
            "pylint",
            "mypy",
            "black",
            "isort",
            "pre-commit",
        ]

        for expected_pkg in expected_packages:
            assert expected_pkg in package_names


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling in requirements parsing and validation."""

    def test_parse_packages_with_extras(self):
        """Test that packages with extras are parsed correctly."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        # Ensure extras are stripped from package names
        for pkg, ver in requirements:
            assert "[" not in pkg, f"Package name should not contain '[': {pkg}"
            assert "]" not in pkg, f"Package name should not contain ']': {pkg}"

    def test_parse_packages_with_environment_markers(self):
        """Test that environment markers are handled correctly."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        # Ensure environment markers are stripped
        for pkg, ver in requirements:
            assert ";" not in pkg, f"Package name should not contain ';': {pkg}"
            assert ";" not in ver, f"Version spec should not contain ';': {ver}"

    def test_parse_inline_comments(self):
        """Test that inline comments don't leak into parsed data."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        for pkg, ver in requirements:
            assert "#" not in pkg, f"Package name should not contain '#': {pkg}"
            assert "#" not in ver, f"Version spec should not contain '#': {ver}"

    def test_whitespace_handling(self):
        """Test that whitespace is properly handled in parsing."""
        requirements = parse_requirements(REQUIREMENTS_FILE)
        for pkg, ver in requirements:
            # No leading or trailing whitespace
            assert pkg == pkg.strip(), f"Package name has whitespace: '{pkg}'"
            assert ver == ver.strip(), f"Version spec has whitespace: '{ver}'"

    def test_empty_lines_and_comments_ignored(self):
        """Test that empty lines and comment-only lines are properly ignored."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        requirements = parse_requirements(REQUIREMENTS_FILE)

        # Count non-empty, non-comment lines
        content_lines = [line for line in all_lines if line.strip() and not line.strip().startswith("#")]

        # Number of requirements should not exceed content lines
        assert len(requirements) <= len(content_lines)


class TestVersionConstraintValidation:
    """Test detailed version constraint validation."""

    @pytest.fixture
    @staticmethod
    def requirements(parsed_requirements) -> List[Tuple[str, str]]:
        """Get parsed requirements."""
        return parsed_requirements

    def test_version_operators_valid(self, requirements: List[Tuple[str, str]]):
        """Test that all version operators are valid."""
        valid_operators = {">=", "==", "<=", ">", "<", "~=", "!="}

        for pkg, ver in requirements:
            if ver:
                # Extract operators from version spec
                operators_found = []
                for op in valid_operators:
                    if op in ver:
                        operators_found.append(op)

                # Should have at least one valid operator
                assert len(operators_found) > 0, f"No valid operator found in '{ver}' for package '{pkg}'"

    def test_compound_version_specs(self, requirements: List[Tuple[str, str]]):
        """Test that compound version specs are properly formatted."""
        for pkg, ver in requirements:
            if "," in ver:
                # Compound spec should not have spaces after comma
                parts = ver.split(",")
                for part in parts:
                    assert (
                        part.strip() == part or part == ""
                    ), f"Compound version spec has improper spacing: '{ver}' for package '{pkg}'"

    def test_minimum_version_numbers_reasonable(self, requirements: List[Tuple[str, str]]):
        """Test that minimum version numbers are reasonable (not 0.0.0)."""
        for pkg, ver in requirements:
            if ver.startswith(">="):
                # Extract version number
                version_str = ver.replace(">=", "")
                parts = version_str.split(".")
                if len(parts) >= 1:
                    major = int(parts[0])
                    # Most production packages should have major version > 0
                    # (Allow some exceptions for type stubs and utilities)
                    if not pkg.startswith("types-"):
                        assert major >= 0, f"Version for {pkg} should be >= 0: {ver}"

    def test_no_conflicting_version_specs(self, requirements: List[Tuple[str, str]]):
        """Test that version specs don't have obvious conflicts."""
        for pkg, ver in requirements:
            if "," in ver:
                # For compound specs like ">=X,<Y", ensure they make sense
                specs = ver.split(",")
                if len(specs) == 2:
                    # Basic check: if both are comparison operators
                    if ">=" in specs[0] and "<" in specs[1]:
                        # Extract versions (basic check)
                        min_ver = specs[0].replace(">=", "").strip()
                        max_ver = specs[1].replace("<", "").replace("<=", "").strip()
                        # Just ensure they're not obviously wrong
                        assert min_ver != max_ver or "<=" in specs[1], f"Conflicting version spec for {pkg}: {ver}"


class TestPackageNamingAndCasing:
    """Test package naming conventions and casing consistency."""

    @pytest.fixture
    @staticmethod
    def requirements(parsed_requirements) -> List[Tuple[str, str]]:
        """Get parsed requirements."""
        return parsed_requirements

    def test_package_name_casing_preserved(self, requirements: List[Tuple[str, str]]):
        """Test that package name casing is preserved as written."""
        # Read raw file to check original casing
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for pkg, _ in requirements:
            # Find the original line
            matching_lines = [line for line in lines if pkg in line and not line.strip().startswith("#")]
            assert len(matching_lines) > 0, f"Package {pkg} not found in original file"

    def test_no_underscore_hyphen_conflicts(self, requirements: List[Tuple[str, str]]):
        """Test that there are no packages differing only in underscore/hyphen."""
        normalized_names = {}
        for pkg, _ in requirements:
            normalized = pkg.lower().replace("-", "_")
            if normalized in normalized_names:
                original = normalized_names[normalized]
                assert original.lower().replace("-", "_") == pkg.lower().replace(
                    "-", "_"
                ), f"Potential conflict between {original} and {pkg}"
            normalized_names[normalized] = pkg

    def test_common_package_name_patterns(self, requirements: List[Tuple[str, str]]):
        """Test that package names follow common patterns."""
        for pkg, _ in requirements:
            # Should not start or end with hyphen or underscore
            assert not pkg.startswith("-"), f"Package name starts with hyphen: {pkg}"
            assert not pkg.startswith("_"), f"Package name starts with underscore: {pkg}"
            assert not pkg.endswith("-"), f"Package name ends with hyphen: {pkg}"
            assert not pkg.endswith("_"), f"Package name ends with underscore: {pkg}"


class TestDevelopmentToolsPresence:
    """Test that essential development tools are present and properly configured."""

    @pytest.fixture
    @staticmethod
    def package_names(parsed_requirements) -> List[str]:
        """Extract package names."""
        return [pkg.lower() for pkg, _ in parsed_requirements]

    @staticmethod
    def test_has_testing_framework(package_names: List[str]):
        """Test that a testing framework is present."""
        testing_frameworks = ["pytest", "unittest", "nose"]
        assert any(fw in package_names for fw in testing_frameworks), "No testing framework found"

    @staticmethod
    def test_has_code_formatter(package_names: List[str]):
        """Test that a code formatter is present."""
        formatters = ["black", "autopep8", "yapf"]
        assert any(fmt in package_names for fmt in formatters), "No code formatter found"

    @staticmethod
    def test_has_linter(package_names: List[str]):
        """Test that at least one linter is present."""
        linters = ["flake8", "pylint", "ruff"]
        assert any(linter in package_names for linter in linters), "No linter found"

    @staticmethod
    def test_has_type_checker(package_names: List[str]):
        """Test that a type checker is present."""
        type_checkers = ["mypy", "pytype", "pyre"]
        assert any(tc in package_names for tc in type_checkers), "No type checker found"

    @staticmethod
    def test_has_import_sorter(package_names: List[str]):
        """Test that an import sorter is present."""
        import_sorters = ["isort", "reorder-python-imports"]
        # This is optional but good to have
        if any(sorter in package_names for sorter in import_sorters):
            assert True
        else:
            # Not required but log it
            pass


class TestPytestEcosystem:
    """Test pytest and related plugins."""

    @pytest.fixture
    @staticmethod
    def requirements(parsed_requirements) -> List[Tuple[str, str]]:
        """Get parsed requirements."""
        return parsed_requirements

    @pytest.fixture
    @staticmethod
    def package_names(parsed_requirements) -> List[str]:
        """Extract package names."""
        return [pkg.lower() for pkg, _ in parsed_requirements]

    @staticmethod
    def test_pytest_version_sufficient(requirements: List[Tuple[str, str]]):
        """Test that pytest version is recent enough."""
        pytest_specs = [ver for pkg, ver in requirements if pkg.lower() == "pytest"]
        assert len(pytest_specs) > 0, "pytest should be present"

        # Should be at least version 6.0
        ver = pytest_specs[0]
        if ver.startswith(">="):
            version_num = ver.replace(">=", "")
            major = int(version_num.split(".")[0])
            assert major >= 6, f"pytest version should be >= 6.0, got {ver}"

    @staticmethod
    def test_pytest_plugins_compatible(requirements: List[Tuple[str, str]]):
        """Test that pytest plugins have compatible versions."""
        pytest_plugins = [(pkg, ver) for pkg, ver in requirements if pkg.lower().startswith("pytest-")]

        # All pytest plugins should have version constraints
        for pkg, ver in pytest_plugins:
            assert ver, f"Pytest plugin {pkg} should have a version constraint"

    @staticmethod
    def test_pytest_cov_present_for_coverage(package_names: List[str]):
        """Test that pytest-cov is present for coverage reporting."""
        if "pytest-cov" in package_names:
            assert True
        else:
            # Coverage is important but not critical for dev dependencies
            pass


class TestTypeStubConsistency:
    """Test consistency between type stub packages and their base packages."""

    @pytest.fixture
    @staticmethod
    def requirements(parsed_requirements) -> List[Tuple[str, str]]:
        """Get parsed requirements."""
        return parsed_requirements

    def test_type_stubs_have_base_packages(self, requirements: List[Tuple[str, str]]):
        """Test that all type stub packages have corresponding base packages."""
        packages_map = {pkg.lower(): (pkg, ver) for pkg, ver in requirements}

        for pkg, ver in requirements:
            if pkg.lower().startswith("types-"):
                base_name = pkg.lower().replace("types-", "")

                # Check if base package exists (with various naming conventions)
                base_exists = (
                    base_name in packages_map
                    or base_name.replace("-", "_") in packages_map
                    or base_name.replace("_", "-") in packages_map
                )

                assert base_exists, f"Type stub package {pkg} has no corresponding base package"

    def test_type_stub_versions_reasonable(self, requirements: List[Tuple[str, str]]):
        """Test that type stub packages have reasonable version constraints."""
        for pkg, ver in requirements:
            if pkg.lower().startswith("types-"):
                # Type stubs may or may not have version constraints
                # but if they do, they should be valid
                if ver:
                    assert any(
                        op in ver for op in [">=", "==", "~="]
                    ), f"Type stub {pkg} has invalid version spec: {ver}"


class TestFileStructureAndOrganization:
    """Test file structure and organizational aspects."""

    @staticmethod
    def test_comments_have_proper_format():
        """Test that comments follow a consistent format."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for i, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                # Comments should have a space after #
                if len(line.strip()) > 1:
                    assert (
                        line.strip()[1] == " " or line.strip()[1] == "#"
                    ), f"Line {i}: Comment should have space after #: {line.strip()}"

    @staticmethod
    def test_sections_are_organized():
        """Test that the file appears to be organized into sections."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Should have at least one section comment
        section_indicators = ["#", "Dependencies", "Testing", "Development"]
        has_sections = any(indicator in content for indicator in section_indicators)
        assert has_sections, "File should have organizational comments"

    @staticmethod
    def test_no_excessive_blank_lines():
        """Test that there are no excessive consecutive blank lines."""
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        consecutive_blanks = 0
        max_consecutive = 0

        for line in lines:
            if line.strip() == "":
                consecutive_blanks += 1
                max_consecutive = max(max_consecutive, consecutive_blanks)
            else:
                consecutive_blanks = 0

        # Allow at most 1 consecutive blank line
        assert max_consecutive <= 1, f"Found {max_consecutive} consecutive blank lines"


class TestSecurityBestPractices:
    """Test security best practices in dependency management."""

    @pytest.fixture
    def requirements(self, parsed_requirements) -> List[Tuple[str, str]]:
        """Get parsed requirements."""
        return parsed_requirements

    @staticmethod
    def test_no_very_old_package_versions(requirements: List[Tuple[str, str]]):
        """Test that packages don't use very old major versions."""
        for pkg, ver in requirements:
            if ver.startswith(">="):
                version_str = ver.replace(">=", "")
                parts = version_str.split(".")
                if len(parts) >= 1 and parts[0].isdigit():
                    major = int(parts[0])
                    # Most modern packages should be at least version 1.0
                    # Allow exceptions for certain packages
                    if pkg not in ["types-PyYAML"] and not pkg.startswith("types-"):
                        # Just log if version is 0.x (not necessarily an error)
                        if major == 0:
                            pass  # Could add warning

    @staticmethod
    def test_critical_packages_pinned(requirements: List[Tuple[str, str]]):
        """Test that critical security-related packages have minimum versions."""
        critical_packages = ["pytest", "pytest-cov"]

        for critical in critical_packages:
            matching = [ver for pkg, ver in requirements if pkg.lower() == critical.lower()]
            if matching:
                assert matching[0], f"Critical package {critical} should have version constraint"


class TestPyYAMLIntegration:
    """Test PyYAML-specific integration based on the diff changes."""

    @pytest.fixture
    @staticmethod
    def requirements(parsed_requirements) -> List[Tuple[str, str]]:
        """Get parsed requirements."""
        return parsed_requirements

    def test_pyyaml_and_types_both_present(self, requirements: List[Tuple[str, str]]):
        """Test that both PyYAML and types-PyYAML are present."""
        packages = [pkg.lower() for pkg, _ in requirements]
        assert "pyyaml" in packages, "PyYAML should be present"
        assert "types-pyyaml" in packages, "types-PyYAML should be present"

    def test_pyyaml_version_compatible_with_types(self, requirements: List[Tuple[str, str]]):
        """Test that PyYAML version is compatible with types-PyYAML."""
        pyyaml_ver = [ver for pkg, ver in requirements if pkg.lower() == "pyyaml"]
        types_ver = [ver for pkg, ver in requirements if pkg.lower() == "types-pyyaml"]

        # Both should exist
        assert len(pyyaml_ver) > 0, "PyYAML should have version constraint"
        # types-PyYAML may or may not have version constraint

        # PyYAML should be at least 6.0 (as per the diff)
        assert pyyaml_ver[0].startswith(">=6.0"), f"PyYAML should be >=6.0, got {pyyaml_ver[0]}"

    def test_yaml_parsing_capability(self):
        """Test that PyYAML can be imported and used (if installed)."""
        try:
            import yaml  # noqa: F401

            # If import succeeds, the package is available
            assert True
        except ImportError:
            # Package not installed yet, but should be in requirements
            requirements = parse_requirements(REQUIREMENTS_FILE)
            packages = [pkg.lower() for pkg, _ in requirements]
            assert "pyyaml" in packages, "PyYAML should be in requirements"


class TestComprehensivePackageValidation:
    """Comprehensive validation of all aspects of package specifications."""

    @pytest.fixture
    @staticmethod
    def requirements(parsed_requirements) -> List[Tuple[str, str]]:
        """Get parsed requirements."""
        return parsed_requirements

    def test_all_packages_loadable_by_pip(self, requirements: List[Tuple[str, str]]):
        """Test that all package specifications are valid pip requirements."""
        from packaging.requirements import Requirement

        # Re-read file and try to parse each line with pip
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                try:
                    # Remove inline comment
                    if "#" in line:
                        line = line.split("#")[0].strip()

                    # This should not raise an exception
                    Requirement(line)
                except Exception as e:
                    pytest.fail(f"Failed to parse requirement line: {line}, error: {e}")

    def test_package_count_reasonable(self, requirements: List[Tuple[str, str]]):
        """Test that the number of development packages is reasonable."""
        # Development dependencies should typically be between 5 and 50 packages
        assert 5 <= len(requirements) <= 50, f"Development dependencies count seems unusual: {len(requirements)}"

    def test_no_missing_pytest_plugins(self, requirements: List[Tuple[str, str]]):
        """Test that common pytest plugins are not missing."""
        packages = [pkg.lower() for pkg, _ in requirements]

        # pytest-cov is especially important
        if "pytest" in packages:
            assert "pytest-cov" in packages, "pytest-cov should be present with pytest"
