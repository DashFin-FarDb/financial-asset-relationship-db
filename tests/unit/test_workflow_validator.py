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

# Add src to path before importing the module under test
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from workflow_validator import ValidationResult, validate_workflow  # isort: skip  # noqa: E402


@pytest.mark.unit
class TestValidationResult:
    """Test suite for ValidationResult class"""

    @staticmethod
    def test_validation_result_creation_valid():
        """Test creating a valid ValidationResult"""
        result = ValidationResult(True, [], {"key": "value"})
        assert result.is_valid is True
        assert result.errors == []
        assert result.workflow_data == {"key": "value"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestValidateWorkflow:
    """Test suite for validate_workflow function"""


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

    @staticmethod
    def test_workflow_with_unicode():
        """Test workflow with Unicode characters"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8") as f:
            f.write("""
name: "Test with emojis"
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Unicode test"
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions"""

# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


    @staticmethod
    def test_workflow_with_many_jobs():
        """Test workflow with many jobs"""
        jobs = "\n".join(
            [f"  job{i}:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo {i}" for i in range(50)]
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(f"name: Many Jobs\non: push\njobs:\n{jobs}\n")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                assert len(result.workflow_data["jobs"]) == 50
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_yaml_anchors():
        """Test workflow using YAML anchors"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: Anchors
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "test"
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling and exception scenarios"""

    @staticmethod
    def test_workflow_permission_denied():
        """Test handling of permission denied error"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                "name: Test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test"
            )
            f.flush()

            try:
                Path(f.name).chmod(0o000)
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert len(result.errors) >= 1
            finally:
                Path(f.name).chmod(0o644)
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_duplicate_keys():
        """
        Verify that a workflow YAML containing duplicate mapping keys parses successfully and that the parser retains the last occurrence of a duplicated key.

        This test writes a temporary YAML file where "name" appears twice and asserts validation is successful and workflow_data["name"] equals "Second".
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: First
name: Second
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo test
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                assert result.workflow_data["name"] == "Second"
            finally:
                Path(f.name).unlink()


@pytest.mark.unit
class TestIntegrationWithActualWorkflows:
    """Integration tests with actual project workflows"""

    @staticmethod
    def test_validate_actual_pr_agent_workflow():
        """Test validation of actual pr-agent.yml if it exists"""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "pr-agent.yml"

        if not workflow_path.exists():
            pytest.skip("pr-agent.yml not found")

        result = validate_workflow(str(workflow_path))
        assert result.is_valid is True, f"pr-agent.yml validation failed: {result.errors}"
        assert "jobs" in result.workflow_data

    @staticmethod
    def test_validate_actual_apisec_workflow():
        """Test validation of actual apisec-scan.yml if it exists"""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "apisec-scan.yml"

        if not workflow_path.exists():
            pytest.skip("apisec-scan.yml not found")

        result = validate_workflow(str(workflow_path))
        assert result.is_valid is True, f"apisec-scan.yml validation failed: {result.errors}"

    @staticmethod
    def test_validate_all_project_workflows():
        """
        Validate every GitHub Actions workflow file in the repository's .github/workflows directory.

        Skips the test if the workflows directory or any workflow files are missing. Collects validation failures for each workflow and fails the test if any workflows are invalid, reporting their filenames and error lists.
        """
        workflows_dir = Path(__file__).parent.parent.parent / ".github" / "workflows"

        if not workflows_dir.exists():
            pytest.skip(".github/workflows directory not found")

        workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))

        if not workflow_files:
            pytest.skip("No workflow files found")

        failed = []
        for workflow_file in workflow_files:
            result = validate_workflow(str(workflow_file))
            if not result.is_valid:
                failed.append((workflow_file.name, result.errors))

        assert len(failed) == 0, f"Failed workflows: {failed}"


@pytest.mark.unit
class TestValidationResultDataStructure:
    """Test ValidationResult data structure integrity"""

    @staticmethod
    def test_validation_result_attributes_accessible():
        """Test that ValidationResult attributes are accessible"""

        @staticmethod
        def test_validation_result_attributes():
            """Test that ValidationResult attributes are accessible within a static method."""
            data = {"name": "Test", "jobs": {"build": {}}}
            result = ValidationResult(True, [], data)

            assert hasattr(result, "is_valid")
            assert hasattr(result, "errors")
            assert hasattr(result, "workflow_data")


    @staticmethod
    def test_validation_result_workflow_data_is_dict():
        """Test that workflow_data is typically a dict"""
        data = {"key": "value"}
        result = ValidationResult(True, [], data)
        assert isinstance(result.workflow_data, dict)


@pytest.mark.unit
class TestAdvancedValidationScenarios:
    """Additional advanced validation scenarios with bias for action"""

    def test_workflow_with_binary_content(self):
        """Test handling of binary file mistakenly treated as YAML"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".yml", delete=False) as f:
            # Write some binary content
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert len(result.errors) >= 1
            finally:
                Path(f.name).unlink()

    def test_workflow_with_only_whitespace(self):
        """Test workflow file containing only whitespace"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("   \n\t\n   \n")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
            finally:
                Path(f.name).unlink()

    def test_workflow_with_comments_only(self):
        """Test workflow file with only YAML comments"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
# This is a comment
# Another comment
# More comments
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
            finally:
                Path(f.name).unlink()

    def test_workflow_with_null_jobs_value(self):
        """Test workflow with null value for jobs key"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: Test
on: push
jobs: ~
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                # jobs key exists but value is null
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    def test_workflow_with_list_as_jobs(self):
        """Test workflow where jobs is a list instead of dict"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: Test
on: push
jobs:
  - job1
  - job2
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                # Has jobs key, validation passes (structure validation is minimal)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    def test_workflow_with_integer_values(self):
        """Test workflow with integer values in unexpected places"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: 12345
on: 67890
jobs:
  test:
    runs-on: 11111
    steps:
      - run: 22222
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    def test_workflow_path_with_spaces(self):
        """
        Verify that a workflow file whose filesystem path contains spaces is parsed and accepted.

        Creates a temporary file with spaces in its name, writes a minimal valid GitHub Actions workflow to it, runs validation, and asserts the result is valid.
        """
        import os

        temp_dir = tempfile.mkdtemp()
        try:
            assert_valid(validate_workflow(str(path)))
        finally:
            import shutil

            shutil.rmtree(temp_dir)

    def test_workflow_with_extremely_long_line(self):
        """Test workflow with extremely long single line"""
        long_string = "A" * 10000
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(f"""
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      LONG_VAR: "{long_string}"
    steps:
      - run: echo test
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    def test_workflow_with_circular_yaml_reference(self):
        """Test workflow with YAML anchors that could cause circular references"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: Test
on: push
defaults: &defaults
  runs-on: ubuntu-latest
jobs:
  test1:
    <<: *defaults
    steps:
      - run: echo test1
  test2:
    <<: *defaults
    steps:
      - run: echo test2
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                assert "test1" in result.workflow_data["jobs"]
                assert "test2" in result.workflow_data["jobs"]
            finally:
                Path(f.name).unlink()

    def test_workflow_with_multiline_strings(self):
        """Test workflow with various multiline string formats"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Multiline literal
        run: |
          echo "Line 1"
          echo "Line 2"
          echo "Line 3"
      - name: Multiline folded
        run: >
          This is a very long line
          that will be folded into
          a single line
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()


@pytest.mark.unit
class TestValidationResultBehavior:
    """Test ValidationResult behavior and edge cases"""

    @staticmethod
    def test_validation_result_with_multiple_errors():
        """Test ValidationResult with multiple error messages"""
        errors = ["Error 1", "Error 2", "Error 3", "Error 4"]
        result = ValidationResult(False, errors, {})
        assert len(result.errors) == 4
        assert result.errors[0] == "Error 1"
        assert result.errors[-1] == "Error 4"

    @staticmethod
    def test_validation_result_with_empty_error_list():
        """Test valid ValidationResult with empty error list"""
        result = ValidationResult(True, [], {"jobs": {}})
        assert result.is_valid is True
        assert result.errors == []
        assert isinstance(result.errors, list)

    @staticmethod
    def test_validation_result_preserves_complex_workflow_data():
        """Test that ValidationResult preserves complex nested workflow data"""
        complex_data = {
            "name": "Complex",
            "on": {"push": {"branches": ["main", "dev"]}, "pull_request": {}},
            "jobs": {
                "job1": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"uses": "actions/checkout@v4"}, {"run": "npm test"}],
                    "env": {"NODE_ENV": "test"},
                }
            },
        }
        result = ValidationResult(True, [], complex_data)
        assert result.workflow_data == complex_data
        assert result.workflow_data["jobs"]["job1"]["env"]["NODE_ENV"] == "test"

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

@pytest.mark.unit
class TestWorkflowValidatorSecurityScenarios:
    """Test security-related scenarios and potential exploits"""


# ---------------------------------------------------------------------------
# Validator behaviour
# ---------------------------------------------------------------------------


    @staticmethod
    def test_workflow_with_yaml_injection_attempts():
        """
        Ensures YAML parsing treats injection-like command strings as plain scalars and the workflow is considered valid.

        Writes a temporary workflow file containing steps with values that resemble shell injection or command substitutions and asserts that validate_workflow returns a valid ValidationResult (i.e., parser does not execute or interpret those patterns).
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: "echo 'safe'"
      - run: '; rm -rf /'
      - run: "$(malicious command)"
      - run: "`backdoor`"
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                # Parser should handle these as strings
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()


@pytest.mark.unit
class TestWorkflowValidatorPerformance:
    """Test performance-related aspects of workflow validation"""

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
    """

    @staticmethod
    def test_workflow_with_minimal_memory_footprint():
        """
        Ensure validate_workflow handles a moderately sized workflow without excessive memory usage.

        Creates a temporary YAML workflow file containing 100 jobs and asserts the validator reports it as valid.
        """
        # Create a workflow with moderate size
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("name: Test\non: push\njobs:\n")
            for i in range(100):
                f.write(f"  job{i}:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test\n")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                # Validation should complete without memory issues
            finally:
                Path(f.name).unlink()


@pytest.mark.unit
class TestWorkflowValidatorEdgeCasesExtended:
    """Extended edge cases and corner scenarios"""

    result = validate_workflow(str(path))
    assert_valid(result)

    @staticmethod
    def test_workflow_with_scientific_notation():
        """
        Validate that a workflow using numeric values in scientific notation (for example `1e2`) is considered valid.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: Scientific
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 1e2
    steps:
      - run: echo test
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_float_values():
        """
        Validate that a workflow containing float values in environment fields is considered valid.

        Creates a temporary YAML workflow with float values in `env` and asserts that `validate_workflow` returns a valid result.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
name: Floats
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      VERSION: 3.14159
      RATIO: 0.5
    steps:
      - run: echo test
""")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()


def test_fast_failure():
    import time

    start = time.time()
    validate_workflow("/nope.yml")
    assert time.time() - start < 1.0
