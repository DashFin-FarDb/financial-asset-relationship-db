# Quick Test Run Guide

## Running the New Tests

### Python Backend Tests

```bash
# Run auth refactoring tests
pytest tests/unit/test_auth_refactoring.py -v

# Run database refactoring tests
pytest tests/unit/test_database_refactoring.py -v

# Run both with coverage
pytest tests/unit/test_auth_refactoring.py tests/unit/test_database_refactoring.py --cov=api --cov-report=html

# Run specific test class
pytest tests/unit/test_auth_refactoring.py::TestUserRepositoryInstanceMethods -v

# Run specific test method
pytest tests/unit/test_auth_refactoring.py::TestUserRepositoryInstanceMethods::test_repository_is_instance -v
```

### Frontend TypeScript Tests

```bash
# Navigate to frontend directory
cd frontend

# Run API refactoring tests
npm test -- __tests__/lib/api-refactoring.test.ts

# Run with coverage
npm test -- __tests__/lib/api-refactoring.test.ts --coverage

# Run in watch mode for development
npm test -- __tests__/lib/api-refactoring.test.ts --watch

# Run all tests
npm test
```

### Run All New Tests

```bash
# Python tests
pytest tests/unit/test_auth_refactoring.py tests/unit/test_database_refactoring.py -v

# Then frontend tests
cd frontend && npm test -- __tests__/lib/api-refactoring.test.ts
```

## Test Files Summary

| File | Lines | Tests | Purpose |
|------|-------|-------|---------|
| `tests/unit/test_auth_refactoring.py` | 559 | 52 | Auth module refactoring |
| `tests/unit/test_database_refactoring.py` | 490 | 43 | Database module refactoring |
| `frontend/__tests__/lib/api-refactoring.test.ts` | 394 | 23 | API client refactoring |
| **Total** | **1,443** | **118** | |

## Quick Verification

```bash
# Verify Python syntax
python -m py_compile tests/unit/test_auth_refactoring.py
python -m py_compile tests/unit/test_database_refactoring.py

# Count test methods
grep -c 'def test_' tests/unit/test_auth_refactoring.py
grep -c 'def test_' tests/unit/test_database_refactoring.py
grep -c "it('" frontend/__tests__/lib/api-refactoring.test.ts
```

## Expected Results

All tests should pass as they validate the refactored code behavior:
- ✅ 52 tests in test_auth_refactoring.py
- ✅ 43 tests in test_database_refactoring.py  
- ✅ 23 tests in api-refactoring.test.ts
- ✅ Total: 118 passing tests

## Troubleshooting

If tests fail, check:
1. Environment variables are set (DATABASE_URL, SECRET_KEY)
2. Dependencies are installed (pytest, Jest)
3. Database is accessible
4. Frontend dependencies are installed (`npm install`)

## Integration with CI/CD

These tests will automatically run in your CI pipeline:
- GitHub Actions will execute pytest and npm test
- Coverage reports will be generated
- Pull request checks will validate all tests pass