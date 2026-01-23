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

# Ensure src is on path BEFORE imports
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.workflow_validator import WorkflowValidator
from workflow_validator import ValidationResult, validate_workflow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_temp_yaml(content: str) -> Path:
    file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8")
    file.write(content)
    file.flush()
    file.close()
    return Path(file.name)


def assert_invalid(result: ValidationResult) -> None:
    assert result.is_valid is False
    assert result.errors


def assert_valid(result: ValidationResult) -> None:
    assert result.is_valid is True
    assert not result.errors


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_valid_result(self):
        data = {"jobs": {}}
        result = ValidationResult(True, [], data)
        assert result.is_valid
        assert result.errors == []
        assert result.workflow_data == data

    def test_invalid_result(self):
        errors = ["error"]
        result = ValidationResult(False, errors, {})
        assert not result.is_valid
        assert result.errors == errors

    def test_preserves_data_on_failure(self):
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
        path = write_temp_yaml("name: Test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest")
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
        path = write_temp_yaml(content)
        try:
            result = validate_workflow(str(path))
            assert isinstance(result.is_valid, bool)
        finally:
            path.unlink()

    def test_large_workflow(self):
        jobs = "\n".join(
            f"  job{i}:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo {i}" for i in range(100)
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
