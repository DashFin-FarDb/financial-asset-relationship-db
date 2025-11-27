# Quick Test Execution Guide

## New Tests Added for This Branch

This branch includes comprehensive additional tests for:
- ✅ GitHub workflow modifications
- ✅ Requirements file updates
- ✅ Documentation quality

## Running All New Tests

### Complete Integration Test Suite
```bash
pytest tests/integration/ -v
```

### Requirements Validation Tests
```bash
pytest tests/integration/test_requirements_dev.py -v
```

### Documentation Quality Tests
```bash
pytest tests/integration/test_documentation_validation.py -v
```

## Running Specific Test Categories

### Security and Version Validation
```bash
pytest tests/integration/test_requirements_dev.py::TestRequirementsAdvancedValidation -v
```

### YAML Structure and Formatting
```bash
pytest tests/integration/test_requirements_dev.py::TestWorkflowYAMLValidation -v
```

### Performance Best Practices
```bash
pytest tests/integration/test_requirements_dev.py::TestWorkflowPerformanceOptimization -v
```

### Markdown Quality Checks
```bash
pytest tests/integration/test_documentation_validation.py::TestDocumentationMarkdownQuality -v
```

### Documentation Completeness
```bash
pytest tests/integration/test_documentation_validation.py::TestTestSummaryCompleteness -v
```

## Coverage Reports

### Generate HTML Coverage Report
```bash
pytest tests/integration/ --cov --cov-report=html
open htmlcov/index.html  # View in browser
```

### Terminal Coverage Report
```bash
pytest tests/integration/ --cov --cov-report=term-missing
```

## Troubleshooting

### Install Test Dependencies
```bash
pip install -r requirements-dev.txt
```

### Verify Test Discovery
```bash
pytest --collect-only tests/integration/
```

### Run with Extra Verbosity
```bash
pytest tests/integration/ -vv -s
```

### Run Specific Test Method
```bash
pytest tests/integration/test_requirements_dev.py::TestRequirementsAdvancedValidation::test_pyyaml_security_version -vv
```

## Quick Test Stats

| Category | Test Count |
|----------|-----------|
| **Requirements Validation** | 5 tests |
| **YAML Validation** | 5 tests |
| **Performance** | 3 tests |
| **Error Handling** | 2 tests |
| **Maintainability** | 3 tests |
| **Documentation Quality** | 6 tests |
| **Summary Completeness** | 4 tests |
| **Workflow Documentation** | 2 tests |
| **Total New Tests** | 40+ tests |

## Test Files Modified

1. `tests/integration/test_requirements_dev.py` - Enhanced with 18 new tests
2. `tests/integration/test_documentation_validation.py` - Enhanced with 12 new tests

## What These Tests Validate

### Security
- ✅ PyYAML version is not vulnerable to known CVEs
- ✅ All dependencies have version constraints
- ✅ No insecure git+ dependencies

### Quality
- ✅ YAML files are properly formatted
- ✅ Documentation links are not broken
- ✅ Code blocks have language identifiers
- ✅ Markdown follows best practices

### Best Practices
- ✅ Workflows have concurrency controls
- ✅ Timeouts are reasonable
- ✅ Step names are descriptive
- ✅ No commented-out code blocks

---

**Quick Reference for**: codex/fix-high-priority-bugs-in-tests
**Generated**: 2025-11-22
**Total Tests Added**: 40+
**Test Files Enhanced**: 2