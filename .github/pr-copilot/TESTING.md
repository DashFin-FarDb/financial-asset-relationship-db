# PR Copilot Testing Guide

This document provides comprehensive testing instructions for the PR Copilot GitHub Actions workflow and associated scripts.

## 🎯 Test Coverage

The PR Copilot test suite includes:

- **Unit Tests**: Test individual functions and components in isolation
- **Integration Tests**: Test complete workflows and script interactions
- **Configuration Tests**: Validate YAML configuration files
- **Documentation Tests**: Ensure documentation exists and is complete

## 🚀 Quick Start

### Prerequisites

```bash
# Install Python 3.8 or higher
python3 --version

# Install pip
pip3 --version
```

### Automated Test Runner (Recommended)

The easiest way to run all tests is using the provided test runner script:

```bash
# Run all tests with automatic virtual environment setup
.github/pr-copilot/scripts/run_tests.sh

# Run with coverage report
.github/pr-copilot/scripts/run_tests.sh --coverage
```

**Benefits:**

- ✅ Automatic virtual environment creation and management
- ✅ Isolated dependency installation
- ✅ Consistent test environment across runs
- ✅ Automatic cleanup on exit
- ✅ Color-coded output for better readability

**What the script does:**

1. Creates a dedicated virtual environment (`.venv-pr-copilot/`) if it doesn't exist
2. Activates the virtual environment
3. Upgrades pip to the latest version
4. Installs test dependencies (pytest, pytest-cov)
5. Installs PR Copilot dependencies from requirements.txt
6. Runs all unit and integration tests
7. Automatically deactivates the virtual environment on exit

The script creates a virtual environment at `.venv-pr-copilot/` in the repository root, which is automatically excluded from version control.

### Manual Test Execution

If you prefer to run tests manually or need more control:

#### 1. Set Up Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv-pr-copilot

# Activate virtual environment
source .venv-pr-copilot/bin/activate  # On Linux/macOS
# OR
.venv-pr-copilot\Scripts\activate  # On Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install pytest pytest-cov
pip install -r .github/pr-copilot/scripts/requirements.txt
```

#### 2. Run Tests

```bash
# Run all PR Copilot unit tests
pytest tests/unit/test_pr_copilot_*.py -v

# Run integration tests
pytest tests/integration/test_pr_copilot_workflow.py -v

# Run all PR Copilot tests
pytest tests/unit/test_pr_copilot_*.py tests/integration/test_pr_copilot_workflow.py -v
```

#### 3. Deactivate Virtual Environment

```bash
deactivate
```

### Run Specific Test Files

```bash
# Test status generation
pytest tests/unit/test_pr_copilot_generate_status.py -v

# Test PR analysis
pytest tests/unit/test_pr_copilot_analyze_pr.py -v

# Test fix suggestions
pytest tests/unit/test_pr_copilot_suggest_fixes.py -v

# Test workflow integration
pytest tests/integration/test_pr_copilot_workflow.py -v
```

### Run Specific Test Functions

```bash
# Test specific functionality
pytest tests/unit/test_pr_copilot_generate_status.py::test_fetch_pr_status -v
pytest tests/unit/test_pr_copilot_analyze_pr.py::test_assess_complexity_high -v
pytest tests/unit/test_pr_copilot_suggest_fixes.py::test_categorize_comment_critical -v
```

### Run with Coverage

```bash
# Generate coverage report
pytest tests/unit/test_pr_copilot_*.py --cov=.github/pr-copilot/scripts --cov-report=html

# View coverage in browser
open htmlcov/index.html
```

## 📊 Test Scenarios

### Scenario 1: Complete PR Status Report

**Test:** `test_generate_status_integration`

Validates:

- PR metadata extraction
- Review status aggregation
- CI check status
- Merge readiness assessment
- Markdown formatting

### Scenario 2: High-Risk PR Analysis

**Test:** `test_assess_complexity_high`

Validates:

- Complexity scoring for large PRs
- Risk level assessment
- File categorization
- Change impact analysis

### Scenario 3: Review Comment Processing

**Test:** `test_parse_review_comments_with_actionable`

Validates:

- Comment extraction from reviews
- Actionable item identification
- Priority categorization
- Code suggestion parsing

### Scenario 4: Configuration Loading

**Test:** `test_config_file_exists`

Validates:

- YAML configuration file existence
- Configuration structure
- Required fields presence
- Default value handling

### Scenario 5: Workflow Trigger Detection

**Test:** `test_workflow_triggers_configuration`

Validates:

- Workflow file structure
- Event trigger configuration
- Job definitions
- Permission settings

## 🧪 Test Structure

### Unit Tests

Located in `tests/unit/`:

- `test_pr_copilot_analyze_pr.py`: Tests for PR analysis functionality
  - File categorization
  - Complexity assessment
  - Scope validation
  - Issue linking

- `test_pr_copilot_generate_status.py`: Tests for status report generation
  - PR data fetching
  - Review aggregation
  - Check run processing
  - Markdown formatting

- `test_pr_copilot_suggest_fixes.py`: Tests for fix suggestion generation
  - Comment categorization
  - Code suggestion extraction
  - Priority assignment
  - Actionable item detection

### Integration Tests

Located in `tests/integration/`:

- `test_pr_copilot_workflow.py`: End-to-end workflow tests
  - Configuration validation
  - Script execution
  - File existence checks
  - Documentation completeness

## 🔍 Test Data

Tests use mock objects and fixtures to simulate:

- GitHub API responses
- PR metadata
- Review comments
- Check run results
- Configuration files

Example mock PR:

```python
mock_pr = Mock()
mock_pr.number = 42
mock_pr.title = "Add new feature"
mock_pr.commits = 5
mock_pr.changed_files = 10
mock_pr.additions = 100
mock_pr.deletions = 50
```

## 📈 Coverage Goals

Target coverage metrics:

- **Overall**: ≥ 80%
- **Critical paths**: ≥ 90%
- **Error handling**: ≥ 85%
- **Configuration loading**: 100%

## 🐛 Debugging Tests

### Verbose Output

```bash
pytest tests/unit/test_pr_copilot_*.py -vv
```

### Show Print Statements

```bash
pytest tests/unit/test_pr_copilot_*.py -s
```

### Run Failed Tests Only

```bash
pytest --lf
```

### Stop on First Failure

```bash
pytest -x
```

### Run Specific Test with Debug Output

```bash
pytest tests/unit/test_pr_copilot_generate_status.py::test_fetch_pr_status -vv -s
```

## 🔧 Troubleshooting

### Import Errors

If you encounter import errors:

```bash
# Ensure you're in the repository root
cd /path/to/repository

# Verify Python path
python3 -c "import sys; print(sys.path)"

# Run tests from repository root
pytest tests/unit/test_pr_copilot_*.py
```

### Missing Dependencies

```bash
# Reinstall dependencies
pip install -r .github/pr-copilot/scripts/requirements.txt

# Verify installation
pip list | grep -E "PyGithub|pyyaml|requests|pytest"
```

### Virtual Environment Issues

```bash
# Remove existing virtual environment
rm -rf .venv-pr-copilot

# Recreate virtual environment
python3 -m venv .venv-pr-copilot
source .venv-pr-copilot/bin/activate
pip install --upgrade pip
pip install pytest pytest-cov
pip install -r .github/pr-copilot/scripts/requirements.txt
```

### Permission Errors

```bash
# Make test runner executable
chmod +x .github/pr-copilot/scripts/run_tests.sh

# Run with explicit bash
bash .github/pr-copilot/scripts/run_tests.sh
```

## 📝 Writing New Tests

### Test Naming Convention

- Test files: `test_pr_copilot_<module>.py`
- Test functions: `test_<functionality>_<scenario>`
- Fixtures: `mock_<object>` or `<object>_fixture`

### Example Test

```python
def test_categorize_filename():
    """Test file categorization logic."""
    assert categorize_filename("src/main.py") == "source"
    assert categorize_filename("tests/test_main.py") == "test"
    assert categorize_filename("README.md") == "docs"
```

### Using Fixtures

```python
@pytest.fixture
def mock_pr():
    """Create a mock PR object."""
    pr = Mock()
    pr.number = 123
    pr.title = "Test PR"
    return pr

def test_with_fixture(mock_pr):
    """Test using fixture."""
    assert mock_pr.number == 123
```

## 🎯 Continuous Integration

Tests run automatically on:

- Pull request creation
- Pull request updates
- Push to main branch

CI configuration in `.github/workflows/pr-copilot.yml`

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [PyGithub Documentation](https://pygithub.readthedocs.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## ✅ Pre-commit Checklist

Before committing changes:

- [ ] All tests pass locally
- [ ] New functionality has tests
- [ ] Coverage remains above 80%
- [ ] No linting errors
- [ ] Documentation updated
- [ ] CHANGELOG updated (if applicable)

## 🤝 Contributing

When adding new tests:

1. Follow existing test structure
2. Use descriptive test names
3. Add docstrings to test functions
4. Mock external dependencies
5. Test both success and failure cases
6. Update this documentation if needed
