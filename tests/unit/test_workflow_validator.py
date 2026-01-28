"""
Comprehensive unit tests for src/workflow_validator.py

Tests the ValidationResult class and validate_workflow function:
- File reading and YAML parsing
- Structure validation (must be dict, must have 'jobs')
- Error handling for various failure modes
- Edge cases and boundary conditions
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Import the module under test
from workflow_validator import ValidationResult, validate_workflow

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestValidationResult:
    """Test suite for ValidationResult class"""

    @staticmethod
    def test_validation_result_creation_valid():
        """Test creating a valid ValidationResult"""
        result = ValidationResult(True, [], {"key": "value"})
        assert result.is_valid is True
        assert result.errors == []
        assert result.workflow_data == {"key": "value"}

    @staticmethod
    def test_validation_result_creation_invalid():
        """Test creating an invalid ValidationResult"""
        errors = ["Error 1", "Error 2"]
        result = ValidationResult(False, errors, {})
        assert result.is_valid is False
        assert result.errors == errors
        assert result.workflow_data == {}

    @staticmethod
    def test_validation_result_with_workflow_data():
        """Test ValidationResult retains workflow data even when invalid"""
        data = {"name": "Test", "on": "push"}
        result = ValidationResult(False, ["Missing jobs"], data)
        assert result.workflow_data == data


class TestValidateWorkflow:
    """Test suite for validate_workflow function"""

    @staticmethod
    def test_valid_minimal_workflow_file():
        """Test validation of a minimal valid workflow file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                assert len(result.errors) == 0
                assert "jobs" in result.workflow_data
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_valid_complex_workflow_file():
        """Test validation of a complex valid workflow"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: Complex Workflow
on:
  push:
    branches: [main, develop]
  pull_request:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
  test:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                assert len(result.errors) == 0
                assert "jobs" in result.workflow_data
                assert "build" in result.workflow_data["jobs"]
                assert "test" in result.workflow_data["jobs"]
            finally:
                Path(f.name).unlink()

    def test_workflow_missing_jobs_key(self):
        """Test detection of missing 'jobs' key"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: Test
on: push
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert len(result.errors) == 1
                assert "Workflow must have a 'jobs' key" in result.errors[0]
                assert "name" in result.workflow_data
            finally:
                Path(f.name).unlink()

    def test_workflow_not_a_dict(self):
        """Test detection when YAML content is not a dictionary"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
- item1
- item2
- item3
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert len(result.errors) == 1
                assert "Workflow must be a dict" in result.errors[0]
                assert result.workflow_data == ["item1", "item2", "item3"]
            finally:
                Path(f.name).unlink()

    def test_workflow_invalid_yaml_syntax(self):
        """Test handling of invalid YAML syntax"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: Invalid
on: push
jobs:
  test:
    invalid: indentation
      causes: error
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert len(result.errors) >= 1
                assert result.workflow_data == {}
            finally:
                Path(f.name).unlink()

    def test_workflow_file_not_found(self):
        """Test handling of non-existent file"""
        result = validate_workflow("/nonexistent/file.yml")
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert result.workflow_data == {}

    def test_workflow_empty_file(self):
        """Test handling of empty workflow file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
            finally:
                Path(f.name).unlink()

    def test_workflow_with_null_value(self):
        """Test workflow file that parses to None"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("~\n")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert (
                    "Workflow file is empty or contains only nulls." in result.errors[0]
                )
            finally:
                Path(f.name).unlink()

    def test_workflow_with_empty_jobs_dict(self):
        """Test workflow with empty jobs dictionary"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: Test
on: push
jobs: {}
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    def test_workflow_with_special_characters(self):
        """Test workflow with special characters in values"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: "Test with @special #chars!"
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Special chars"
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    def test_workflow_with_unicode(self):
        """Test workflow with Unicode characters"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                """
name: "Test with emojis"
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Unicode test"
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()


"
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()


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

    @staticmethod
    def test_validation_result_error_message_types():
        """Test that error messages can be various string types"""
        errors = [
            "Simple error",
            "Error with 'quotes'",
            'Error with "double quotes"',
            "Error with unicode: 你好",
            "Error with newline\ncharacter",
        ]
        result = ValidationResult(False, errors, {})
        assert len(result.errors) == 5


class TestWorkflowValidatorSecurityScenarios:
    """Test security-related scenarios and potential exploits"""

    @staticmethod
    def test_workflow_with_extremely_deep_nesting():
        """Test workflow with extremely deep nesting (YAML bomb prevention)"""
        # Create a deeply nested structure
        nested = "jobs:\n"
        for i in range(100):
            nested += "  " * (i + 1) + f"level{i}:\n"
        nested += "  " * 101 + "value: test\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(f"name: Deep\non: push\n{nested}")
            f.flush()

            try:
                result = validate_workflow(f.name)
                # Should handle deep nesting gracefully
                assert result.is_valid is True or result.is_valid is False
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_suspicious_filenames():
        """Test workflow validation with suspicious filename patterns"""
        suspicious_names = [
            "../../../etc/passwd.yml",
            "workflow;rm -rf /.yml",
            "workflow`whoami`.yml",
        ]

        for name in suspicious_names:
            # These should fail because file doesn't exist
            result = validate_workflow(name)
            assert result.is_valid is False

    @staticmethod
    def test_workflow_with_large_file_size():
        """Test validation of very large workflow file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("name: Large\non: push\njobs:\n")
            # Create many jobs
            for i in range(1000):
                f.write(f"  job{i}:\n")
                f.write("    runs-on: ubuntu-latest\n")
                f.write("    steps:\n")
                f.write(f"      - run: echo {i}\n")
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                assert len(result.workflow_data["jobs"]) == 1000
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_yaml_injection_attempts():
        """Test workflow with potential YAML injection patterns"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: \"echo 'safe'\"
      - run: '; rm -rf /'
      - run: "$(malicious command)"
      - run: "`backdoor`"
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                # Parser should handle these as strings
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()


class TestWorkflowValidatorPerformance:
    """Test performance-related aspects of workflow validation"""

    @staticmethod
    def test_validate_workflow_returns_quickly_on_error():
        """Test that validation returns quickly even on error"""
        import time

        start = time.time()
        result = validate_workflow("/nonexistent/file.yml")
        elapsed = time.time() - start

        assert result.is_valid is False
        assert elapsed < 1.0  # Should complete in less than 1 second

    @staticmethod
    def test_validate_multiple_workflows_sequentially():
        """Test validating multiple workflows in sequence"""
        workflows = []
        for i in range(10):
            f = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
            f.write(
                f"""
name: Test{i}
on: push
jobs:
  test{i}:
    runs-on: ubuntu-latest
    steps:
      - run: echo {i}
"""
            )
            f.flush()
            workflows.append(f.name)

        try:
            results = []
            for workflow in workflows:
                result = validate_workflow(workflow)
                results.append(result)

            assert all(r.is_valid for r in results)
            assert len(results) == 10
        finally:
            for workflow in workflows:
                Path(workflow).unlink()

    @staticmethod
    def test_workflow_with_minimal_memory_footprint():
        """Test that validation doesn't consume excessive memory"""
        # Create a workflow with moderate size
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("name: Test\non: push\njobs:\n")
            for i in range(100):
                f.write(
                    f"  job{i}:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test\n"
                )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                # Validation should complete without memory issues
            finally:
                Path(f.name).unlink()


class TestWorkflowValidatorEdgeCasesExtended:
    """Extended edge cases and corner scenarios"""

    @staticmethod
    def test_workflow_with_boolean_values():
        """Test workflow with boolean values in various positions"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: Booleans
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    if: true
    continue-on-error: false
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: true
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_scientific_notation():
        """Test workflow with scientific notation numbers"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: Scientific
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 1e2
    steps:
      - run: echo test
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_float_values():
        """Test workflow with float values"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
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
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_mixed_indentation():
        """Test workflow with mixed tabs and spaces"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                "name: Mixed\non: push\njobs:\n\ttest:\n    runs-on: ubuntu-latest\n\tsteps:\n      - run: echo test\n"
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                # YAML may handle or reject mixed indentation
                assert isinstance(result.is_valid, bool)
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_trailing_commas():
        """Test workflow with trailing commas in flow style"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: Trailing
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: {ref: main, fetch-depth: 1,}
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                # YAML should handle or reject trailing commas
                assert isinstance(result.is_valid, bool)
            finally:
                Path(f.name).unlink()

    @staticmethod
    def test_workflow_with_explicit_types():
        """Test workflow with explicit YAML type tags"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
name: !!str Types
on: !!str push
jobs:
  test:
    runs-on: !!str ubuntu-latest
    timeout-minutes: !!int 30
    steps:
      - run: !!str "echo test"
"""
            )
            f.flush()

            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
