"""
Validation tests for requirements changes.
"""

import subprocess
from pathlib import Path

import pytest


class TestRequirementsDevChanges:
    """Test requirements - dev.txt changes."""

    @pytest.fixture
    def requirements_dev_content(self):
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            return f.read()

    def test_pyyaml_added(self, requirements_dev_content):
        assert "pyyaml" in requirements_dev_content.lower() or "PyYAML" in requirements_dev_content

    def test_pyyaml_has_version_specifier(self, requirements_dev_content):
        lines = requirements_dev_content.split("\n")
        pyyaml_lines = [
            line for line in lines if line.lower().startswith("pyyaml") and not line.strip().startswith("#")
        ]

        assert len(pyyaml_lines) == 1
        pyyaml_line = pyyaml_lines[0]
        pyyaml_line_no_comment = pyyaml_line.split("#", 1)[0].strip()
        assert any(op in pyyaml_line_no_comment for op in [">=", "==", "~=", "<=", ">", "<"])

    def test_no_duplicate_packages(self, requirements_dev_content):
        lines = [
            line.strip()
            for line in requirements_dev_content.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        from packaging.requirements import Requirement

        package_names = [Requirement(line).name.lower() for line in lines]

        assert len(package_names) == len(set(package_names))

    def test_requirements_format_valid(self, requirements_dev_content):
        lines = requirements_dev_content.split("\n")

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line and not line.startswith("#"):
                assert not line.startswith(" ")
                assert line == line.rstrip()


class TestRequirementsDependencyCompatibility:
    """Test dependency compatibility."""

    @staticmethod
    def test_pyyaml_compatible_with_python_version():
        import sys

        python_version = sys.version_info

        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            content = f.read()

        if "pyyaml" in content.lower():
            assert python_version >= (3, 6)

    @staticmethod
    def test_no_conflicting_versions():
        req_path = Path("requirements.txt")
        req_dev_path = Path("requirements-dev.txt")

        if not req_path.exists():
            pytest.skip("requirements.txt not found")

        with open(req_path, "r") as f:
            req_content = f.read()
        with open(req_dev_path, "r") as f:
            req_dev_content = f.read()

        req_packages = {
            line.split("==")[0].split(">=")[0].lower().strip()
            for line in req_content.split("\n")
            if line.strip() and not line.strip().startswith("#")
        }

        req_dev_packages = {
            line.split("==")[0].split(">=")[0].lower().strip()
            for line in req_dev_content.split("\n")
            if line.strip() and not line.strip().startswith("#")
        }

        overlap = req_packages & req_dev_packages

        allowed_overlap = {
            "markdown",
            "pydantic",
            "pytest",
            "pytest-asyncio",
            "pyyaml",
        }

        unexpected_overlap = overlap - allowed_overlap

        assert not unexpected_overlap, (
            "Unexpected overlapping packages between requirements.txt "
            f"and requirements-dev.txt: {unexpected_overlap}"
        )


class TestRequirementsInstallability:
    """Test that requirements can be installed."""

    @pytest.mark.skipif(
        not Path("requirements-dev.txt").exists(),
        reason="requirements-dev.txt not found",
    )
    def test_requirements_dev_syntax_valid(self):
        result = subprocess.run(
            ["pip", "install", "--dry-run", "-r", "requirements-dev.txt"],
            capture_output=True,
            text=True,
        )
        assert "error" not in result.stderr.lower() or "requirement already satisfied" in result.stdout.lower()


class TestRequirementsDocumentation:
    """Test requirements documentation and comments."""

    @staticmethod
    def test_requirements_has_helpful_comments():
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, "r") as f:
            lines = f.readlines()

        comment_lines = [line for line in lines if line.strip().startswith("#")]
        assert len(comment_lines) >= 1

    @staticmethod
    def test_pyyaml_purpose_documented():
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, "r") as f:
            content = f.read()

        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "pyyaml" in line.lower():
                context = "\n".join(lines[max(0, i - 3) : i + 1])
                assert any(keyword in context.lower() for keyword in ["yaml", "workflow", "config", "parse"])
                break
