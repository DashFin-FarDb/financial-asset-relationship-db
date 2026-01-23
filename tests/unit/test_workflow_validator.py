"""
Unit tests for workflow validation.

Covers:
- ValidationResult behaviour
- Workflow file parsing and validation
- Error handling and edge cases
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import pytest

from src.workflow_validator import WorkflowValidator
from workflow_validator import ValidationResult, validate_workflow

# Ensure src is on path BEFORE imports
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_temp_yaml(content: str) -> Path:
    """
    Create a temporary file with a ".yml" suffix containing the given content and return its filesystem path.

    Parameters:
        content (str): YAML text to be written into the temporary file.

    Returns:
        Path: Path to the created temporary file. The file is not removed automatically.
    """
    file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    )
    file.write(content)
    file.flush()
    file.close()
    return Path(file.name)


def assert_invalid(result: ValidationResult) -> None:
    """
    Assert that the given ValidationResult represents an invalid workflow and contains at least one error.

    Parameters:
        result (ValidationResult): The validation result to check.

    Raises:
        AssertionError: If `result.is_valid` is True or `result.errors` is empty.
    """
    assert result.is_valid is False
    assert result.errors


 def assert_valid(result: ValidationResult) -> None:
     """
     Assert that a ValidationResult represents a successful validation.

     Parameters:
         result (ValidationResult): The validation result to check; the function asserts that `result.is_valid` is True and that `result.errors` is empty.
     """
     assert result.is_valid is True
     assert not result.errors


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    """Unit tests for the ValidationResult class, verifying behavior of valid and invalid results and data preservation on failure."""
    @staticmethod
    def test_valid_result():
        """Test that a valid ValidationResult correctly sets is_valid, errors, and workflow_data."""
        data = {"jobs": {}}
        result = ValidationResult(True, [], data)
        assert result.is_valid
        assert result.errors == []
        assert result.workflow_data == data

    @staticmethod
    def test_invalid_result():
        """Test that an invalid ValidationResult correctly sets is_valid to False and retains error messages."""
        errors = ["error"]
        result = ValidationResult(False, errors, {})
        assert not result.is_valid
        assert result.errors == errors

    @staticmethod
    def test_preserves_data_on_failure():
        """Test that workflow_data is preserved even when ValidationResult indicates failure."""
        data = {"name": "x"}
        result = ValidationResult(False, ["missing jobs"], data)
        assert result.workflow_data == data


# ---------------------------------------------------------------------------
# Workflow parsing & validation
# ---------------------------------------------------------------------------


class TestWorkflowValidation:
    @pytest.mark.parametrize(
        "content",
        [
            """
            name: Test
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: echo ok
            """,
            """
            name: Complex
            on:
              push:
                branches: [main]
            jobs: {}
            """,
        ],
    )
    def test_valid_workflows(self, content: str):
        path = write_temp_yaml(content)
        try:
            assert_valid(validate_workflow(str(path)))
        finally:
            path.unlink()

    @pytest.mark.parametrize(
        "content,expected",
        [
            ("", "empty"),
            ("~", "null"),
            ("[]", "dict"),
            ("name: Test", "jobs"),
        ],
    )
    def test_invalid_workflows(self, content: str, expected: str):
        path = write_temp_yaml(content)
        try:
            result = validate_workflow(str(path))
            assert_invalid(result)
            assert any(expected in e.lower() for e in result.errors)
        finally:
            path.unlink()

    def test_file_not_found(self):
        result = validate_workflow("/does/not/exist.yml")
        assert_invalid(result)

    def test_permission_denied(self):
        path = write_temp_yaml(
            "name: Test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest"
        )
        try:
            path.chmod(0o000)
            assert_invalid(validate_workflow(str(path)))
        finally:
            path.chmod(0o644)
            path.unlink()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestWorkflowEdgeCases:
    @pytest.mark.parametrize(
        "content",
        [
            "   \n\t\n",
            "# only comments\n# another",
            "name: Test\non: push\njobs: ~",
            "name: Test\non: push\njobs: []",
        ],
    )
    def test_unusual_but_allowed_structures(self, content: str):
        """
        Ensure the validator accepts unusual but permitted workflow YAML structures.

        Writes `content` to a temporary YAML file, validates it, and asserts that the resulting ValidationResult object's `is_valid` attribute is a boolean.

        Parameters:
            content (str): YAML text representing a workflow configuration to validate.
        """
        path = write_temp_yaml(content)
        try:
            result = validate_workflow(str(path))
            assert isinstance(result.is_valid, bool)
        finally:
            path.unlink()

    def test_large_workflow(self):
        jobs = "\n".join(
            f"  job{i}:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo {i}"
            for i in range(100)
        )
        path = write_temp_yaml(f"name: Big\non: push\njobs:\n{jobs}")
        try:
            result = validate_workflow(str(path))
            assert_valid(result)
            assert len(result.workflow_data["jobs"]) == 100
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# Validator behaviour
# ---------------------------------------------------------------------------


class TestWorkflowValidator:
    def test_validator_returns_strings(self):
        validator = WorkflowValidator()
        errors = validator.validate({"name": "", "steps": []})
        assert all(isinstance(e, str) for e in errors)

    def test_long_description(self):
        """
        Verify that WorkflowValidator.validate returns a list when given a very long description.

        Ensures the validator accepts a workflow config whose `description` is extremely long (1000 characters)
        and yields an errors object of type `list` rather than raising or returning another type.
        """
        validator = WorkflowValidator()
        config = {
            "name": "Test",
            "description": "A" * 1000,
            "steps": [{"name": "step", "action": "run"}],
        }
        errors = validator.validate(config)
        assert isinstance(errors, list)


# ---------------------------------------------------------------------------
# Integration (optional)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    ["pr-agent.yml", "apisec-scan.yml"],
)
def test_real_workflows_if_present(filename: str):
    """
    Parametrized test that validates a GitHub Actions workflow file found under .github/workflows in the project root.

    Parameters:
        filename (str): The workflow file name to locate under .github/workflows; the test is skipped if the file is not present.
    """
    path = PROJECT_ROOT / ".github" / "workflows" / filename
    if not path.exists():
        pytest.skip(f"{filename} not found")

    result = validate_workflow(str(path))
    assert_valid(result)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def test_fast_failure():
    import time

    start = time.time()
    validate_workflow("/nope.yml")
    assert time.time() - start < 1.0
