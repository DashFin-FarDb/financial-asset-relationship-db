# Quick Test Reference - New Unit Tests

## 🎯 What Was Generated

Two comprehensive test files for branch changes:

- `tests/unit/test_auth.py` - 48 tests (25KB)
- `tests/unit/test_real_data_fetcher.py` - 30 tests (23KB)

## 🚀 Quick Commands

### Run All New Tests

```bash
pytest tests/unit/test_auth.py tests/unit/test_real_data_fetcher.py -v
```

### Run with Coverage

```bash
pytest tests/unit/test_auth.py tests/unit/test_real_data_fetcher.py \
  --cov=api.auth --cov=src.data.real_data_fetcher \
  --cov-report=term-missing --cov-report=html
```

### Run Specific Test Classes

```bash
# Auth tests
pytest tests/unit/test_auth.py::TestUserRepository -v
pytest tests/unit/test_auth.py::TestPasswordHashing -v
pytest tests/unit/test_auth.py::TestJWTTokenOperations -v

# RealDataFetcher tests
pytest tests/unit/test_real_data_fetcher.py::TestCacheOperations -v
pytest tests/unit/test_real_data_fetcher.py::TestNetworkFetching -v
```

### Run Single Tests

```bash
pytest tests/unit/test_auth.py::TestUserRepository::test_get_user_returns_user_when_found -v
pytest tests/unit/test_real_data_fetcher.py::TestCacheOperations::test_save_and_load_cache_roundtrip -v
```

### Quick Smoke Test (Run Fast Tests Only)

```bash
pytest tests/unit/test_auth.py::TestIsTruthyHelper -v
pytest tests/unit/test_auth.py::TestPasswordHashing -v
```

## 📊 Test Breakdown

### test_auth.py (48 tests)
