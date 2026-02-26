# Testing Guide

Comprehensive testing guide for the Financial Asset Relationship Database.

## Python Backend Tests

### Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run API tests only
pytest tests/unit/test_api_main.py -v

# Run with coverage
pytest --cov=api --cov=src --cov-report=html
```

### Test Coverage

**test_api_main.py** provides 609 lines of comprehensive tests covering:

1. **CORS Validation** - HTTP/HTTPS localhost, Vercel URLs, domain validation
2. **Graph Initialization** - Thread-safe singleton pattern
3. **Pydantic Models** - All response model validation
4. **API Endpoints** - All REST endpoints with filters
5. **Error Handling** - 404, 500, invalid methods
6. **Integration Scenarios** - Full workflow tests

## Frontend TypeScript Tests

### Running Tests

```bash
cd frontend
npm install
npm test
```

### Test Files

- `api.test.ts` - API client tests with mocking
- `jest.config.js` - Jest configuration
- `jest.setup.js` - Test environment setup

## Quick Test Commands

```bash
# Backend only
pytest tests/unit/test_api_main.py -v

# Frontend only
cd frontend && npm test

# Both with coverage
pytest --cov && cd frontend && npm run test:coverage
```

For detailed instructions, see the test files themselves.
