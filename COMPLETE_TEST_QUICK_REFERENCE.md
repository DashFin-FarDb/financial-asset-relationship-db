# Complete Test Quick Reference

## All Tests in Current Branch

### Python Integration Tests (tests/integration/)
```bash
# Run ALL integration tests
pytest tests/integration/ -v

# With coverage report
pytest tests/integration/ --cov --cov-report=html

# Run specific test file
pytest tests/integration/test_documentation_files_validation.py -v
pytest tests/integration/test_modified_config_files_validation.py -v
pytest tests/integration/test_github_workflows.py -v
pytest tests/integration/test_pr_agent_config_validation.py -v
pytest tests/integration/test_branch_integration.py -v

# Run specific test class
pytest tests/integration/test_documentation_files_validation.py::TestDocumentationFilesValidation -v
pytest tests/integration/test_modified_config_files_validation.py::TestPRAgentConfigChanges -v

# Run tests matching pattern
pytest -k "validation" tests/integration/ -v
pytest -k "config" tests/integration/ -v
pytest -k "documentation" tests/integration/ -v
```

### Frontend Tests (frontend/__tests__/)
```bash
cd frontend

# Run ALL frontend tests
npm test

# Run with coverage
npm test -- --coverage

# Run specific test file
npm test -- app/page.test.tsx
npm test -- components/NetworkVisualization.test.tsx
npm test -- lib/api.test.ts
npm test -- test-utils.test.ts

# Watch mode for development
npm test -- --watch

# Update snapshots if needed
npm test -- --updateSnapshot
```

### Quick Validation Commands

```bash
# Validate ALL Python code (linting + tests)
pytest tests/ --cov && \
python -m flake8 src/ api/ tests/ && \
python -m black --check src/ api/ tests/

# Validate ALL Frontend code (linting + tests + type check)
cd frontend && \
npm run lint && \
npm run type-check && \
npm test -- --coverage

# Full project validation (Python + Frontend)
pytest tests/ --cov && cd frontend && npm test -- --coverage
```

## Test Coverage by Category

### Documentation Tests (15 tests)
```bash
pytest tests/integration/test_documentation_files_validation.py -v
```
Validates:
- Markdown file structure
- Code block formatting
- Table consistency
- Link validity
- Content quality

### Configuration Tests (26 tests)
```bash
pytest tests/integration/test_modified_config_files_validation.py -v
```
Validates:
- PR Agent config changes
- Workflow simplifications
- Deleted files impact
- Requirements updates
- .gitignore changes

### Workflow Tests (50+ tests)
```bash
pytest tests/integration/test_github_workflows.py -v
```
Validates:
- All GitHub Actions workflows
- YAML syntax and structure
- Security best practices
- Action versions

### Integration Tests (16 tests)
```bash
pytest tests/integration/test_branch_integration.py -v
```
Validates:
- Cross-workflow consistency
- Dependency-workflow integration
- Branch coherence

### Frontend Component Tests (100+ tests)
```bash
cd frontend && npm test
```
Validates:
- React components
- API client
- Test utilities
- Integration scenarios

## CI/CD Commands

### GitHub Actions (Automated)
These run automatically on push/PR:
```yaml
- pytest tests/ -v --cov
- cd frontend && npm test -- --coverage
```

### Pre-commit Validation
Before committing:
```bash
# Python
python -m pytest tests/ --cov
python -m flake8 src/ api/ tests/
python -m black src/ api/ tests/

# Frontend
cd frontend
npm run lint
npm run type-check
npm test -- --coverage
```

## Useful Test Flags

### pytest flags
```bash
-v              # Verbose output
--cov           # Coverage report
--cov-report=html  # HTML coverage report
-k PATTERN      # Run tests matching pattern
-m MARKER       # Run tests with marker
-x              # Stop on first failure
--maxfail=N     # Stop after N failures
--tb=short      # Short traceback format
--collect-only  # Show tests without running
```

### Jest/npm test flags
```bash
--coverage      # Coverage report
--watch         # Watch mode
--watchAll      # Watch all files
--verbose       # Verbose output
--silent        # Suppress output
--updateSnapshot  # Update snapshots
--testNamePattern  # Run tests matching pattern
--onlyChanged   # Only test changed files
```

## Test File Locations