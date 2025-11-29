"""
Comprehensive unit tests for src/workflow_validator.py

Tests the ValidationResult class and validate_workflow function:
- File reading and YAML parsing
- Structure validation (must be dict, must have 'jobs')
- Error handling for various failure modes
- Edge cases and boundary conditions
"""

import pytest
import tempfile
from pathlib import Path

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from workflow_validator import ValidationResult, validate_workflow


class TestValidationResult:
    """Test suite for ValidationResult class"""
    
    def test_validation_result_creation_valid(self):
        """Test creating a valid ValidationResult"""
        result = ValidationResult(True, [], {'key': 'value'})
        assert result.is_valid is True
        assert result.errors == []
        assert result.workflow_data == {'key': 'value'}
    
    def test_validation_result_creation_invalid(self):
        """Test creating an invalid ValidationResult"""
        errors = ["Error 1", "Error 2"]
        result = ValidationResult(False, errors, {})
        assert result.is_valid is False
        assert result.errors == errors
        assert result.workflow_data == {}
    
    def test_validation_result_with_workflow_data(self):
        """Test ValidationResult retains workflow data even when invalid"""
        data = {'name': 'Test', 'on': 'push'}
        result = ValidationResult(False, ["Missing jobs"], data)
        assert result.workflow_data == data


class TestValidateWorkflow:
    """Test suite for validate_workflow function"""
    
    def test_valid_minimal_workflow_file(self):
        """Test validation of a minimal valid workflow file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("""
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                assert len(result.errors) == 0
                assert 'jobs' in result.workflow_data
            finally:
                Path(f.name).unlink()
    
    def test_valid_complex_workflow_file(self):
        """Test validation of a complex valid workflow"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("""
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
""")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                assert len(result.errors) == 0
                assert 'jobs' in result.workflow_data
                assert 'build' in result.workflow_data['jobs']
                assert 'test' in result.workflow_data['jobs']
            finally:
                Path(f.name).unlink()
    
    def test_workflow_missing_jobs_key(self):
        """Test detection of missing 'jobs' key"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("""
name: Test
on: push
""")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert len(result.errors) == 1
                assert "Workflow must have jobs" in result.errors[0]
                assert 'name' in result.workflow_data
            finally:
                Path(f.name).unlink()
    
    def test_workflow_not_a_dict(self):
        """Test detection when YAML content is not a dictionary"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("""
- item1
- item2
- item3
""")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert len(result.errors) == 1
                assert "Workflow must be a dict" in result.errors[0]
                assert result.workflow_data == {}
            finally:
                Path(f.name).unlink()
    
    def test_workflow_invalid_yaml_syntax(self):
        """Test handling of invalid YAML syntax"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("""
name: Invalid
on: push
jobs:
  test:
    invalid: indentation
      causes: error
""")
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
        result = validate_workflow('/nonexistent/file.yml')
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert result.workflow_data == {}
    
    def test_workflow_empty_file(self):
        """Test handling of empty workflow file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
            finally:
                Path(f.name).unlink()
    
    def test_workflow_with_null_value(self):
        """Test workflow file that parses to None"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("~\n")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert "Workflow must be a dict" in result.errors[0]
            finally:
                Path(f.name).unlink()
    
    def test_workflow_with_empty_jobs_dict(self):
        """Test workflow with empty jobs dictionary"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("""
name: Test
on: push
jobs: {}
""")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()
    
    def test_workflow_with_special_characters(self):
        """Test workflow with special characters in values"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("""
name: "Test with @special #chars!"
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Special chars"
""")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()
    
    def test_workflow_with_unicode(self):
        """Test workflow with Unicode characters"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False, encoding='utf-8') as f:
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


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_workflow_with_very_long_name(self):
        """Test workflow with extremely long name"""
        long_name = "A" * 1000
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(f'name: "{long_name}"\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n')
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()
    
    def test_workflow_with_deeply_nested_structure(self):
        """Test workflow with deeply nested YAML structure"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("""
name: Nested
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          level1:
            level2:
              level3:
                deep: value
""")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
            finally:
                Path(f.name).unlink()
    
    def test_workflow_with_many_jobs(self):
        """Test workflow with many jobs"""
        jobs = "\n".join([f"  job{i}:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo {i}" for i in range(50)])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(f"name: Many Jobs\non: push\njobs:\n{jobs}\n")
            f.flush()
            
            try:
                result = validate_workflow(f.name)
                assert result.is_valid is True
                assert len(result.workflow_data['jobs']) == 50
            finally:
                Path(f.name).unlink()
    
    def test_workflow_with_yaml_anchors(self):
        """Test workflow using YAML anchors"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
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


class TestErrorHandling:
    """Test error handling and exception scenarios"""
    
    def test_workflow_permission_denied(self):
        """Test handling of permission denied error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("name: Test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test")
            f.flush()
            
            try:
                Path(f.name).chmod(0o000)
                result = validate_workflow(f.name)
                assert result.is_valid is False
                assert len(result.errors) >= 1
            finally:
                Path(f.name).chmod(0o644)
                Path(f.name).unlink()
    
    def test_workflow_with_duplicate_keys(self):
        """Test workflow with duplicate keys"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
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
                assert result.workflow_data['name'] == 'Second'
            finally:
                Path(f.name).unlink()


class TestIntegrationWithActualWorkflows:
    """Integration tests with actual project workflows"""
    
    def test_validate_actual_pr_agent_workflow(self):
        """Test validation of actual pr-agent.yml if it exists"""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "pr-agent.yml"
        
        if not workflow_path.exists():
            pytest.skip("pr-agent.yml not found")
        
        result = validate_workflow(str(workflow_path))
        assert result.is_valid is True, f"pr-agent.yml validation failed: {result.errors}"
        assert 'jobs' in result.workflow_data
    
    def test_validate_actual_apisec_workflow(self):
        """Test validation of actual apisec-scan.yml if it exists"""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "apisec-scan.yml"
        
        if not workflow_path.exists():
            pytest.skip("apisec-scan.yml not found")
        
        result = validate_workflow(str(workflow_path))
        assert result.is_valid is True, f"apisec-scan.yml validation failed: {result.errors}"
    
    def test_validate_all_project_workflows(self):
        """Test validation of all workflows in the project"""
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


class TestValidationResultDataStructure:
    """Test ValidationResult data structure integrity"""
    
    def test_validation_result_attributes_accessible(self):
        """Test that ValidationResult attributes are accessible"""
        data = {'name': 'Test', 'jobs': {'build': {}}}
        result = ValidationResult(True, [], data)
        
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'workflow_data')
    
    def test_validation_result_errors_is_list(self):
        """Test that errors attribute is a list"""
        result = ValidationResult(False, ["Error 1", "Error 2"], {})
        assert isinstance(result.errors, list)
        assert len(result.errors) == 2
    
    def test_validation_result_workflow_data_is_dict(self):
        """Test that workflow_data is typically a dict"""
        data = {'key': 'value'}
        result = ValidationResult(True, [], data)
        assert isinstance(result.workflow_data, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])