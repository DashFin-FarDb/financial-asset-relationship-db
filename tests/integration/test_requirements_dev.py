"""
Comprehensive tests for the requirements-dev.txt development dependencies file.
Validates correctness of development dependencies and their version constraints.
"""

import re
from pathlib import Path
from typing import List, Tuple

import pytest
from packaging.requirements import Requirement


def parse_requirements(file_path: Path) -> List[Tuple[str, str]]:
    """
    Parse a pip requirements file into package names and version specifiers.

    Reads a requirements file line by line, ignoring comments and empty lines,
    and parses each requirement into its package name and version specifiers.

    Parameters:
        file_path (Path): Path to the requirements file to parse.

    Returns:
        List[Tuple[str, str]]: A list of ``(package_name, version_spec)`` tuples where
        ``version_spec`` is a comma-separated string of specifiers (e.g. ``">=1.0,<=2.0"``)
        or an empty string when no specifiers are present.

    Raises:
        AssertionError: If a requirement line is malformed.
        OSError: If the requirements file cannot be opened or read (e.g., FileNotFoundError,
        PermissionError).
    """

    requirements: List[Tuple[str, str]] = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            clean = stripped.split("#", 1)[0].strip()
            if not clean:
                continue

            try:
                req = Requirement(clean)
            except Exception as exc:  # pragma: no cover - defensive guard
                raise AssertionError(f"Malformed requirement line: {line.rstrip()} ({exc})") from exc

            extras = f"[{','.join(sorted(req.extras))}]" if req.extras else ""
            pkg = f"{req.name}{extras}"
            version_spec = ",".join(sorted({str(spec) for spec in req.specifier})) if req.specifier else ""
            requirements.append((pkg, version_spec))

    return requirements


class TestRequirementsDevFormat:
    """Test that requirements-dev.txt is correctly formatted."""

    @pytest.fixture
    def requirements_file(self) -> Path:
        """
        Path to the project's requirements-dev.txt file.

        Returns:
            path (Path): Path to requirements-dev.txt located at the repository root.
        """
        return Path("requirements-dev.txt")

    @pytest.fixture
    def requirements_content(self, requirements_file: Path) -> str:
        """
        Read and return the contents of the requirements-dev.txt file.

        Parameters:
            requirements_file (Path): Path to the requirements-dev.txt file to read.

        Returns:
            str: The file contents as a UTF-8 decoded string.
        """
        with open(requirements_file, "r", encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    def parsed_requirements(self, requirements_file: Path) -> List[Tuple[str, str]]:
        """
        Parse the requirements-dev.txt file into package names and version specifiers.

        Parameters:
            requirements_file (Path): Path to the requirements-dev.txt file to parse.

        Returns:
            List[Tuple[str, str]]: A list of (package_name, version_spec) tuples.
        """
        return parse_requirements(requirements_file)

    def test_file_encoding_utf8(self, requirements_content: str):
        """Test that requirements-dev.txt is UTF-8 encoded."""
        # If we can read it as UTF-8 in the fixture, this test passes implicitly
        assert isinstance(requirements_content, str)

    def test_no_trailing_whitespace(self, requirements_content: str):
        """Test that no line in requirements-dev.txt has trailing whitespace."""
        for i, line in enumerate(requirements_content.splitlines(), start=1):
            assert line == line.rstrip(), f"Line {i} has trailing whitespace"

    def test_newline_end_of_file(self, requirements_content: str):
        """Test that requirements-dev.txt ends with a newline."""
        assert requirements_content.endswith("\n"), "File must end with a newline"

    def test_single_newline_end_of_file(self, requirements_content: str):
        """Test that requirements-dev.txt ends with exactly one newline."""
        assert not requirements_content.endswith("\n\n"), "File must end with exactly one newline"


class TestRequirementsDevDependencies:
    """Test that requirements-dev.txt contains the expected dependencies."""

    # Constants for expected tool sets
    EXPECTED_LINTING_TOOLS = {"flake8", "pylint"}
    EXPECTED_FORMATTING_TOOLS = {"black", "isort"}
    EXPECTED_TYPE_CHECKING_TOOLS = {"mypy"}

    @pytest.fixture
    def requirements_file(self) -> Path:
        """
        Path to the project's requirements-dev.txt file.

        Returns:
            path (Path): Path to requirements-dev.txt located at the repository root.
        """
        return Path("requirements-dev.txt")

    @pytest.fixture
    def parsed_requirements(self, requirements_file: Path) -> List[Tuple[str, str]]:
        """
        Parse the requirements-dev.txt file into package names and version specifiers.

        Parameters:
            requirements_file (Path): Path to the requirements-dev.txt file to parse.

        Returns:
            List[Tuple[str, str]]: A list of (package_name, version_spec) tuples.
        """
        return parse_requirements(requirements_file)

    def test_pytest_present(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that pytest is in requirements-dev.txt."""
        pytest_packages = [pkg for pkg, _ in parsed_requirements if pkg.startswith("pytest")]
        assert pytest_packages, "pytest should be present in requirements-dev.txt"

    def test_linting_tools_present(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that linting tools are in requirements-dev.txt."""
        installed_tools = {pkg for pkg, _ in parsed_requirements}
        missing_tools = self.EXPECTED_LINTING_TOOLS - installed_tools
        assert not missing_tools, f"Linting tools {missing_tools} are missing"

    def test_formatting_tools_present(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that formatting tools are in requirements-dev.txt."""
        installed_tools = {pkg for pkg, _ in parsed_requirements}
        missing_tools = self.EXPECTED_FORMATTING_TOOLS - installed_tools
        assert not missing_tools, f"Formatting tools {missing_tools} are missing"

    def test_type_checking_tools_present(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that type checking tools are in requirements-dev.txt."""
        installed_tools = {pkg for pkg, _ in parsed_requirements}
        missing_tools = self.EXPECTED_TYPE_CHECKING_TOOLS - installed_tools
        assert not missing_tools, f"Type checking tools {missing_tools} are missing"

    def test_pre_commit_present(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that pre-commit is in requirements-dev.txt."""
        pre_commit_found = any(pkg == "pre-commit" for pkg, _ in parsed_requirements)
        assert pre_commit_found, "pre-commit should be present in requirements-dev.txt"

    def test_pyyaml_present(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that PyYAML is in requirements-dev.txt."""
        pyyaml_found = any(pkg == "PyYAML" for pkg, _ in parsed_requirements)
        assert pyyaml_found, "PyYAML should be present in requirements-dev.txt"

    def test_types_pyyaml_present(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that types-PyYAML is in requirements-dev.txt."""
        types_pyyaml_found = any(pkg == "types-PyYAML" for pkg, _ in parsed_requirements)
        assert types_pyyaml_found, "types-PyYAML should be present in requirements-dev.txt"


class TestRequirementsDevVersionSpecs:
    """Test that version specifiers in requirements-dev.txt are correctly formatted."""

    @pytest.fixture
    def requirements_file(self) -> Path:
        """
        Path to the project's requirements-dev.txt file.

        Returns:
            path (Path): Path to requirements-dev.txt located at the repository root.
        """
        return Path("requirements-dev.txt")

    @pytest.fixture
    def parsed_requirements(self, requirements_file: Path) -> List[Tuple[str, str]]:
        """
        Parse the requirements-dev.txt file into package names and version specifiers.

        Parameters:
            requirements_file (Path): Path to the requirements-dev.txt file to parse.

        Returns:
            List[Tuple[str, str]]: A list of (package_name, version_spec) tuples.
        """
        return parse_requirements(requirements_file)

    def test_all_requirements_have_version_specs(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that all requirements have version specifiers."""
        missing_versions = [pkg for pkg, spec in parsed_requirements if not spec and not pkg.startswith("pytest")]
        # pytest is allowed to not have version specifiers as it's often used with plugins
        if missing_versions:
            assert False, f"Requirements missing version specifiers: {', '.join(missing_versions)}"

    def test_version_specs_use_caret_or_tilde(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that version specifiers use >= rather than ==, <=, >, or <."""
        for pkg, spec in parsed_requirements:
            if spec:
                # Check that we're using >= for version pinning
                assert "==" not in spec, f"{pkg} should not use strict pinning (==)"
                assert "<" not in spec, f"{pkg} should not use less-than constraints (<)"

    def test_pytest_version_specified(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that pytest has a version specifier."""
        pytest_lines = [(pkg, spec) for pkg, spec in parsed_requirements if pkg.startswith("pytest")]

        for pkg, spec in pytest_lines:
            assert ">=" in spec or "==" in spec, f"{pkg} should have version specifier: {pkg}{spec}"

    def test_pytest_version_at_least_7(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that pytest version is at least 7.0."""
        pytest_lines = [(pkg, spec) for pkg, spec in parsed_requirements if pkg == "pytest"]

        for pkg, spec in pytest_lines:
            version_match = re.search(r">=(\d+\.\d+)", spec)
            if version_match:
                version = float(version_match.group(1))
                assert version >= 7.0, f"{pkg} version should be >= 7.0, got {version}"

    def test_pyyaml_version_specified(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that PyYAML has a version specifier."""
        pyyaml_lines = [(pkg, spec) for pkg, spec in parsed_requirements if pkg == "PyYAML"]

        for pkg, spec in pyyaml_lines:
            assert ">=" in spec or "==" in spec, f"{pkg} should have version specifier: {pkg}{spec}"

    def test_pyyaml_version_at_least_6(self, parsed_requirements: List[Tuple[str, str]]):
        """Test that PyYAML version is at least 6.0."""
        pyyaml_lines = [(pkg, spec) for pkg, spec in parsed_requirements if pkg == "PyYAML"]

        for pkg, spec in pyyaml_lines:
            version_match = re.search(r">=(\d+\.\d+)", spec)
            if version_match:
                version = float(version_match.group(1))
                assert version >= 6.0, f"{pkg} version should be >= 6.0, got {version}"

    def test_types_pyyaml_matches_pyyaml_version(self, parsed_requirements: List[Tuple[str, str]]):
        """
        Assert that the major version of types-PyYAML matches the major version of PyYAML.

        Parameters:
            parsed_requirements (List[Tuple[str, str]]): Parsed requirements from requirements-dev.txt.

        Raises:
            AssertionError: If both packages are pinned with '>=' but their major versions differ.
        """
        pyyaml_version = None
        types_version = None

        for pkg, spec in parsed_requirements:
            if pkg == "PyYAML" and spec.startswith(">="):
                pyyaml_match = re.search(r">=(\d+)", spec)
                if pyyaml_match:
                    pyyaml_version = int(pyyaml_match.group(1))

            if pkg == "types-PyYAML" and spec.startswith(">="):
                types_match = re.search(r">=(\d+)", spec)
                if types_match:
                    types_version = int(types_match.group(1))

        if pyyaml_version and types_version:
            assert (
                pyyaml_version == types_version
            ), f"types-PyYAML version {types_version} should match PyYAML version {pyyaml_version}"
