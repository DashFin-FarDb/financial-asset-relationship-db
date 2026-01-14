# Quick Test Reference: workflow_validator.py

## Running the Tests

### Basic Commands

```bash
# Run all tests for workflow_validator
pytest tests/unit/test_workflow_validator.py -v

# Run with coverage
pytest tests/unit/test_workflow_validator.py --cov=src.workflow_validator --cov-report=term-missing

# Run a specific test class
pytest tests/unit/test_workflow_validator.py::TestValidateWorkflow -v

# Run a single test
pytest tests/unit/test_workflow_validator.py::TestValidateWorkflow::test_valid_minimal_workflow_file -v
```

### Quick Test Examples

#### Test 1: Valid Workflow

```python
def test_valid_minimal_workflow_file(self):
    """Test validation of a minimal valid workflow file"""
```

**Validates**: Basic workflow structure with jobs

#### Test 2: Missing Jobs Key

```python
def test_workflow_missing_jobs_key(self):
    """Test detection of missing 'jobs' key"""
```

**Validates**: Error detection for missing required keys

#### Test 3: Invalid YAML

```python
def test_workflow_invalid_yaml_syntax(self):
    """Test handling of invalid YAML syntax"""
```

**Validates**: Proper error handling for malformed YAML

## Test Organization

### Test Classes

1. **TestValidationResult** - ValidationResult class tests
2. **TestValidateWorkflow** - Main validation function tests
3. **TestEdgeCases** - Boundary conditions and edge cases
4. **TestErrorHandling** - Exception and error scenarios
5. **TestIntegrationWithActualWorkflows** - Real project file tests
6. **TestValidationResultDataStructure** - Data structure integrity

## Coverage Report

Generate and view coverage:

```bash
# Generate HTML coverage report
pytest tests/unit/test_workflow_validator.py --cov=src.workflow_validator --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Common Test Patterns

### Creating Test Workflow Files

```python
with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
    f.write(workflow_yaml_content)
    f.flush()
    try:
        result = validate_workflow(f.name)
        # assertions here
    finally:
        Path(f.name).unlink()
```

### Assertion Patterns

```python
# Valid workflow
assert result.is_valid is True
assert len(result.errors) == 0
assert 'jobs' in result.workflow_data

# Invalid workflow
assert result.is_valid is False
assert len(result.errors) >= 1
assert "expected error message" in result.errors[0]
```

## Troubleshooting

### Import Errors

If you see import errors:

```bash
# Ensure src is in Python path
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
pytest tests/unit/test_workflow_validator.py -v
```

### Test Discovery Issues

```bash
# Check test discovery
pytest tests/unit/test_workflow_validator.py --collect-only

# Run with verbose output
pytest tests/unit/test_workflow_validator.py -vv
```

## Expected Test Output
