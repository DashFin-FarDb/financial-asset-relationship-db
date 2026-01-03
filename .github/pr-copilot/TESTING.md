# PR Copilot Testing Guide

Comprehensive testing documentation for the PR Copilot automated PR lifecycle management system.

## 📋 Overview

The PR Copilot system includes comprehensive test coverage for all Python scripts and integration testing for the complete workflow. Tests are organized into unit tests and integration tests following repository best practices.

## 🧪 Test Structure

```
tests/
├── unit/
│   ├── test_pr_copilot_generate_status.py    # Status report generation tests
│   ├── test_pr_copilot_analyze_pr.py         # PR analysis tests
│   └── test_pr_copilot_suggest_fixes.py      # Fix suggestion tests
└── integration/
    └── test_pr_copilot_workflow.py            # End-to-end workflow tests
```

## 🎯 Test Coverage

### Unit Tests

#### 1. **generate_status.py Tests** (`test_pr_copilot_generate_status.py`)

Tests for PR status report generation:

- ✅ CheckRunInfo dataclass creation
- ✅ PRStatus dataclass creation and immutability
- ✅ Fetching PR status from GitHub API
- ✅ Formatting task checklist (complete/incomplete)
- ✅ Formatting CI check sections
- ✅ Generating complete markdown reports
- ✅ Handling draft PRs
- ✅ Writing output to files and GitHub summaries
- ✅ Edge cases (no checks, unknown mergeable state)

**Coverage:** ~95% of generate_status.py

#### 2. **analyze_pr.py Tests** (`test_pr_copilot_analyze_pr.py`)

Tests for PR complexity analysis:

- ✅ File categorization (Python, JavaScript, tests, workflows, etc.)
- ✅ PR file analysis (empty, small, large changes)
- ✅ Complexity scoring and risk assessment
- ✅ Scope issue detection (long titles, multiple changes, too many files)
- ✅ Related issue parsing from PR body
- ✅ Markdown report generation
- ✅ Configuration loading
- ✅ AnalysisData immutability

**Coverage:** ~90% of analyze_pr.py

#### 3. **suggest_fixes.py Tests** (`test_pr_copilot_suggest_fixes.py`)

Tests for review comment parsing and fix suggestions:

- ✅ Code suggestion extraction (blocks and inline)
- ✅ Comment categorization (critical, bug, question, style, improvement)
- ✅ Actionable comment detection
- ✅ Review comment parsing
- ✅ Priority sorting
- ✅ Fix proposal generation
- ✅ Long body truncation
- ✅ Configuration loading with defaults

**Coverage:** ~90% of suggest_fixes.py

### Integration Tests

#### **Workflow Integration** (`test_pr_copilot_workflow.py`)

End-to-end tests for the complete PR Copilot system:

- ✅ Configuration file existence and validity
- ✅ Workflow file existence and validity
- ✅ Script file existence
- ✅ Requirements file validity
- ✅ Complete status generation workflow
- ✅ Complete PR analysis workflow
- ✅ Complete fix suggestion workflow
- ✅ Workflow trigger configuration
- ✅ Workflow job configuration
- ✅ Workflow permissions
- ✅ Agent settings validation
- ✅ Trigger settings validation
- ✅ Scope settings validation
- ✅ Auto-merge settings validation
- ✅ Documentation existence and content

**Coverage:** Complete workflow validation

## 🚀 Running Tests

### Run All PR Copilot Tests

```bash
# Run all PR Copilot unit tests
pytest tests/unit/test_pr_copilot_*.py -v

# Run integration tests
pytest tests/integration/test_pr_copilot_workflow.py -v

# Run all PR Copilot tests
pytest tests/unit/test_pr_copilot_*.py tests/integration/test_pr_copilot_workflow.py -v
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
- Large file detection
- Scope issue identification

### Scenario 3: Critical Review Feedback

**Test:** `test_categorize_comment_critical`

Validates:
- Security issue detection
- Priority assignment
- Actionable item extraction
- Fix proposal generation

### Scenario 4: Workflow Configuration

**Test:** `test_workflow_triggers_configuration`

Validates:
- All required triggers present
- Correct event types
- Proper job dependencies
- Permission settings

## 🔍 Test Data

### Mock PR Data

Tests use realistic mock data:

```python
mock_pr = {
    "number": 42,
    "title": "Add new feature for user authentication",
    "author": "contributor",
    "commits": 8,
    "files_changed": 12,
    "additions": 250,
    "deletions": 75,
    "labels": ["enhancement", "security"],
    "mergeable": True,
    "reviews": [{"state": "APPROVED"}],
    "checks": [{"name": "CI", "conclusion": "success"}]
}
```

### Mock Review Comments

```python
mock_comment = {
    "author": "reviewer",
    "body": "Please fix this security vulnerability",
    "category": "critical",
    "priority": 1,
    "file": "auth.py",
    "line": 42
}
```

## 🛠️ Test Utilities

### Fixtures

Common fixtures used across tests:

- `mock_github_client`: Mock GitHub API client
- `mock_pr`: Complete PR object with all data
- `mock_reviews`: Review objects with various states
- `mock_check_runs`: CI check run objects
- `mock_env_vars`: Environment variables for scripts

### Mocking Strategy

Tests use `unittest.mock` for:
- GitHub API calls
- File system operations
- Environment variables
- External dependencies

## ✅ Test Checklist

Before deploying PR Copilot changes:

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Coverage > 85% for all scripts
- [ ] No test warnings or errors
- [ ] Configuration files validated
- [ ] Workflow file validated
- [ ] Documentation updated
- [ ] Edge cases covered

## 🐛 Debugging Tests

### Enable Verbose Output

```bash
pytest tests/unit/test_pr_copilot_*.py -vv
```

### Show Print Statements

```bash
pytest tests/unit/test_pr_copilot_*.py -s
```

### Run Failed Tests Only

```bash
pytest tests/unit/test_pr_copilot_*.py --lf
```

### Debug with PDB

```bash
pytest tests/unit/test_pr_copilot_*.py --pdb
```

## 📈 Continuous Integration

Tests run automatically in CI/CD:

```yaml
# .github/workflows/ci.yml
- name: Run PR Copilot Tests
  run: |
    pytest tests/unit/test_pr_copilot_*.py -v
    pytest tests/integration/test_pr_copilot_workflow.py -v
```

## 🔄 Test Maintenance

### Adding New Tests

When adding new functionality:

1. Create test file in appropriate directory
2. Follow naming convention: `test_pr_copilot_<module>.py`
3. Include docstrings for all test functions
4. Use fixtures for common setup
5. Test both success and failure cases
6. Update this documentation

### Updating Existing Tests

When modifying functionality:

1. Update affected test cases
2. Ensure backward compatibility
3. Add tests for new edge cases
4. Verify coverage remains high
5. Update test documentation

## 📚 Best Practices

### Test Organization

- **One test per function**: Each test validates one specific behavior
- **Clear naming**: Test names describe what they validate
- **Arrange-Act-Assert**: Follow AAA pattern
- **Minimal mocking**: Mock only external dependencies
- **Realistic data**: Use data similar to production

### Test Quality

- **Fast execution**: Tests should run quickly
- **Isolated**: Tests don't depend on each other
- **Deterministic**: Same input always produces same output
- **Comprehensive**: Cover happy path and edge cases
- **Maintainable**: Easy to understand and update

## 🔗 Related Documentation

- [PR Copilot README](README.md) - User guide and features
- [Setup Guide](SETUP.md) - Installation and configuration
- [Configuration Reference](../.github/pr-copilot-config.yml) - All settings
- [Workflow File](../.github/workflows/pr-copilot.yml) - GitHub Actions workflow

## 💡 Tips

- Run tests before committing changes
- Use coverage reports to find untested code
- Add tests for bug fixes to prevent regression
- Keep tests simple and focused
- Update tests when requirements change

## 🤝 Contributing

To contribute test improvements:

1. Write tests for new features
2. Ensure all tests pass
3. Maintain or improve coverage
4. Follow existing patterns
5. Document test scenarios
6. Submit PR with test changes

## 📞 Support

For test-related issues:

- Check test output for specific errors
- Review mock data and fixtures
- Verify environment setup
- Consult existing test examples
- Open issue with test failure details

---

**Questions about testing?** Open an issue or refer to the main [TESTING.md](../../TESTING.md) guide!
