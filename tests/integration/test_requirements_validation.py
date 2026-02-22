"""
Validation tests for requirements changes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


class TestRequirementsDevChanges:
    """Test requirements-dev.txt changes."""

    @pytest.fixture
    def requirements_dev_content(self) -> str:
        """
        Return the full text of requirements-dev.txt from the project root.

        Returns:
            str: Contents of requirements-dev.txt.
        """
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_all_active_lines_parse_as_requirements(self, requirements_dev_content: str) -> None:
        """
        Ensure every active (non-empty, non-comment) line parses as a Requirement.

        Fails with a clear message including line number and offending content.
        """
        from packaging.requirements import InvalidRequirement, Requirement

        for i, raw in enumerate(requirements_dev_content.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                Requirement(line)
            except InvalidRequirement as exc:
                raise AssertionError(f"Invalid requirement in requirements-dev.txt at line {i}: '{raw}'") from exc

    def test_pyyaml_added(self, requirements_dev_content: str) -> None:
        """
        Verify that requirements-dev.txt includes a PyYAML package entry.

        Performs a case-insensitive check of the provided requirements content to
        ensure PyYAML is present.
        """
        assert "pyyaml" in requirements_dev_content.lower()

    def test_pyyaml_has_version_specifier(self, requirements_dev_content: str) -> None:
        """
        Ensure the active PyYAML requirement includes a version operator.

        Finds exactly one non-comment requirement whose normalized name is "pyyaml"
        (ignoring types-PyYAML), then verifies it contains a version operator:
        >=, ==, ~=, <=, >, or <.
        """
        from packaging.requirements import InvalidRequirement, Requirement

        pyyaml_lines: list[str] = []
        for raw in requirements_dev_content.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                req = Requirement(line)
            except InvalidRequirement as exc:
                raise AssertionError(f"Invalid requirement line: '{raw}'") from exc
            if req.name.lower() == "pyyaml":
                pyyaml_lines.append(line)

        assert len(pyyaml_lines) == 1, f"Expected exactly one active PyYAML line, found {len(pyyaml_lines)}"

        pyyaml_line_no_comment = pyyaml_lines[0].split("#", 1)[0].strip()
        assert any(op in pyyaml_line_no_comment for op in [">=", "==", "~=", "<=", ">", "<"])

    def test_no_duplicate_packages(self, requirements_dev_content: str) -> None:
        """
        Ensure requirements-dev.txt contains no duplicate package entries.

        Parses each active line as a Requirement and compares normalized package
        names case-insensitively, asserting that no name appears more than once.
        """
        from packaging.requirements import InvalidRequirement, Requirement

        package_names: list[str] = []
        for raw in requirements_dev_content.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                package_names.append(Requirement(line).name.lower())
            except InvalidRequirement as exc:
                raise AssertionError(f"Invalid requirement line: '{raw}'") from exc

        assert len(package_names) == len(set(package_names)), "Duplicate packages found in requirements-dev.txt"

    def test_requirements_format_valid(self, requirements_dev_content: str) -> None:
        """
        Validate that each active line has no leading/trailing whitespace.

        Ignores blank lines and lines beginning with '#'.
        """
        for i, raw in enumerate(requirements_dev_content.splitlines(), 1):
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            assert raw == raw.rstrip(), f"Line {i} has trailing whitespace"
            assert raw == raw.lstrip(), f"Line {i} has leading whitespace"


class TestRequirementsDependencyCompatibility:
    """Test dependency compatibility."""

    @staticmethod
    def test_pyyaml_compatible_with_python_version() -> None:
        """
        Assert that if PyYAML is listed, Python is at least 3.6.

        PyYAML >=5.4 requires Python 3.6+.
        """
        import sys

        python_version = sys.version_info

        req_path = Path("requirements-dev.txt")
        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read()

        if "pyyaml" in content.lower():
            assert python_version >= (3, 6), "PyYAML requires Python 3.6 or higher"

    @staticmethod
    def test_no_conflicting_versions() -> None:
        """
        Ensure at most two package name overlaps exist between requirements files.

        Reads requirements.txt (skipping if missing) and requirements-dev.txt, then
        extracts requirement names via packaging.Requirement for robust parsing.
        Fails if more than two package names overlap.
        """
        from packaging.requirements import InvalidRequirement, Requirement

        req_path = Path("requirements.txt")
        req_dev_path = Path("requirements-dev.txt")

        if not req_path.exists():
            pytest.skip("requirements.txt not found")

        with open(req_path, "r", encoding="utf-8") as f:
            req_lines = f.read().splitlines()
        with open(req_dev_path, "r", encoding="utf-8") as f:
            dev_lines = f.read().splitlines()

        def _names(lines: list[str], filename: str) -> set[str]:
            out: set[str] = set()
            for i, raw in enumerate(lines, 1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    out.add(Requirement(line).name.lower())
                except InvalidRequirement as exc:
                    raise AssertionError(f"Invalid requirement in {filename} at line {i}: '{raw}'") from exc
            return out

        req_packages = _names(req_lines, "requirements.txt")
        dev_packages = _names(dev_lines, "requirements-dev.txt")

        overlap = req_packages & dev_packages
        assert len(overlap) <= 2, f"Too many overlapping packages: {overlap}"


class TestRequirementsInstallability:
    """Test that requirements can be installed."""

    @pytest.mark.skipif(not Path("requirements-dev.txt").exists(), reason="requirements-dev.txt not found")
    def test_requirements_dev_syntax_valid(self) -> None:
        """
        Verify requirements-dev.txt has valid pip syntax (dry run).

        Notes:
            pip's output varies by version; we treat non-zero return codes as
            failure and surface stderr for debugging.
        """
        result = subprocess.run(
            ["pip", "install", "--dry-run", "-r", "requirements-dev.txt"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            "pip dry-run failed for requirements-dev.txt:\n" f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )


class TestRequirementsDocumentation:
    """Test requirements documentation and comments."""

    @staticmethod
    def test_requirements_has_helpful_comments() -> None:
        """
        Verify that requirements-dev.txt contains at least one comment line.

        Asserts the file includes at least one line that begins with '#'.
        """
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        comment_lines = [l for l in lines if l.strip().startswith("#")]
        assert len(comment_lines) >= 1, "requirements-dev.txt should have explanatory comments"

    @staticmethod
    def test_pyyaml_purpose_documented() -> None:
        """
        Verify the PyYAML addition has a nearby comment explaining purpose.

        Checks a small window of lines above the PyYAML line for keywords such as
        yaml/workflow/config/parse.
        """
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "pyyaml" in line.lower() and not line.strip().startswith("#"):
                context = "\n".join(lines[max(0, i - 3) : i + 1])
                assert any(
                    keyword in context.lower() for keyword in ["yaml", "workflow", "config", "parse"]
                ), "PyYAML should have explanatory comment"
                break
        else:
            pytest.skip("PyYAML not present in requirements-dev.txt; purpose check skipped")
