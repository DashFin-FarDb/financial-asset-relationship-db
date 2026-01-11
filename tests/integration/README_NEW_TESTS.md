# New Validation Tests README

## Overview

This directory contains comprehensive validation tests for configuration and documentation files modified in the current branch.

## New Test Files

### 1. test_documentation_files_validation.py (292 lines)
**Purpose**: Validates all markdown documentation files in the repository

**Test Classes**:
- `TestDocumentationFilesValidation` (10 tests)
  - File existence and readability
  - Non-empty file validation
  - Proper heading structure
  - Code block language identifiers
  - Table formatting consistency
  - Internal link validity
  - Trailing whitespace checks
  - Summary file requirements
  - Reference file examples

- `TestMarkdownContentQuality` (3 tests)
  - Test generation file statistics
  - Comprehensive file size validation
  - Quick reference conciseness

- `TestDocumentationConsistency` (2 tests)
  - Terminology consistency
  - Test file reference validation

**Coverage**: 32 markdown documentation files

### 2. test_modified_config_files_validation.py (297 lines)
**Purpose**: Validates configuration file modifications in the branch

**Test Classes**:
- `TestPRAgentConfigChanges` (8 tests)
  - Version validation (1.0.0)
  - Context chunking removal
  - Fallback strategies removal
  - Essential sections present
  - Token management simplification
  - Quality standards preservation

- `TestWorkflowSimplifications` (4 tests)
  - PR agent workflow simplified
  - APIsec workflow no conditional
  - Label workflow simplified
  - Greetings simple messages

- `TestDeletedFilesImpact` (6 tests)
  - labeler.yml removed
  - context_chunker.py removed
  - scripts/README.md removed
  - codecov.yaml removed
  - .vscode/settings.json removed
  - No references to deleted files

- `TestRequirementsDevChanges` (3 tests)
  - PyYAML added
  - tiktoken removed
  - Essential dependencies present

- `TestGitignoreChanges` (3 tests)
  - codacy instructions ignored
  - Test artifacts configuration
  - Standard patterns present

- `TestCodacyInstructionsChanges` (2 tests)
  - Instructions simplified
  - Critical rules preserved

**Coverage**: 7 configuration files + 5 deleted files

## Running the Tests

### Quick Start
```bash
# Run both new test files
pytest test_documentation_files_validation.py test_modified_config_files_validation.py -v

# Run documentation tests only
pytest test_documentation_files_validation.py -v

# Run configuration tests only
pytest test_modified_config_files_validation.py -v

# With coverage
pytest test_documentation_files_validation.py test_modified_config_files_validation.py --cov
```

### Run Specific Test Classes
```bash
# Documentation validation
pytest test_documentation_files_validation.py::TestDocumentationFilesValidation -v

# Configuration validation
pytest test_modified_config_files_validation.py::TestPRAgentConfigChanges -v

# Deleted files verification
pytest test_modified_config_files_validation.py::TestDeletedFilesImpact -v
```

### Run Specific Tests
```bash
# Check markdown structure
pytest test_documentation_files_validation.py::TestDocumentationFilesValidation::test_markdown_has_proper_headings -v

# Check PR agent version
pytest test_modified_config_files_validation.py::TestPRAgentConfigChanges::test_version_is_correct -v
```

## Test Dependencies

### Required
- pytest (already in requirements.txt)
- PyYAML (already in requirements-dev.txt)

### Optional
- pytest-cov (for coverage reports)

## CI/CD Integration

These tests run automatically in the CI/CD pipeline:
```yaml
# .github/workflows/ci.yml
- name: Run Python Tests
  run: pytest tests/ -v --cov
```

## Test Fixtures

### Common Fixtures
```python
@pytest.fixture
def doc_root(self) -> Path:
    """Get the repository root directory."""
    
@pytest.fixture
def markdown_files(self, doc_root: Path) -> List[Path]:
    """Get all markdown files in repository root."""
    
@pytest.fixture
def config_path(self) -> Path:
    """Get path to PR agent config."""
```

## Writing New Tests

### Add Documentation Test
```python
def test_new_markdown_validation(self, markdown_files: List[Path]):
    """Test for new markdown requirement."""
    for md_file in markdown_files:
        content = md_file.read_text(encoding='utf-8')
        # Add validation logic
        assert some_condition, f"Validation failed for {md_file.name}"
```

### Add Configuration Test
```python
def test_new_config_validation(self, config_path: Path):
    """Test for new config requirement."""
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    # Add validation logic
    assert 'key' in config_data, "Required key missing"
```

## Test Organization

### File Structure