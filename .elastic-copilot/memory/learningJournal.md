# Learning Journal

- Initial setup of CRCT system completed.

## 2026-04-26: Auth Settings Centralization PR Review

### PR Context

- **PR #1059**: Centralize auth runtime settings access
- **Branch**: `claude/1028-centralize-auth-settings`
- **Goal**: Move auth runtime configuration reads from direct `os.getenv()` to centralized typed settings layer in `src/config/settings.py`

### Key Technical Learnings

#### 1. Settings Architecture

- `src/config/settings.py` contains centralized typed settings via Pydantic `Settings` class
- Two accessor functions: `load_settings()` (fresh load) and `get_settings()` (cached via `@lru_cache`)
- Auth module (`api/auth.py`) uses `load_settings()` at import time for `_AUTH_SETTINGS` to avoid cache staleness issues
- `required_secret_key` property enforces import-time hard-fail when `SECRET_KEY` missing

#### 2. Code Style Conflicts

- **Black config**: `line-length = 120` in `pyproject.toml`
- **Codacy/Pylint**: Reports 100-character limit warnings
- **Resolution**: Accept black's formatting (120 chars) since it's the pre-commit enforced formatter; Codacy warnings are config mismatch

#### 3. Pre-commit Hooks

- Enforced checks: black, ruff, flake8, mypy, trailing whitespace, end-of-files, merge conflicts
- flake8-docstrings (D101, D102, D103) requires docstrings on all public classes, methods, and functions
- Test fixtures need docstrings even though they're simple

#### 4. Test Fixture Patterns

- `@pytest.fixture(autouse=True)` with `yield` for setup/teardown (e.g., cache clearing)
- Cache clearing: `get_settings.cache_clear()` before and after each test
- Module-level settings (`_AUTH_SETTINGS`) are loaded at import time, so cache clearing doesn't affect them

### PR Review Feedback Patterns

#### Common Issues Found

1. Line length violations (check against project's configured limit, not default)
2. Missing docstrings on test fixtures and helper functions
3. "Method could be a function" warnings in test classes (acceptable for pytest organization)

#### Resolution Workflow

1. Run `pre-commit run --files <affected_files>` to catch all issues
2. Fix issues in order: formatting (black) first, then lint (flake8), then types (mypy)
3. Re-run tests to confirm no regressions
4. Commit and push with clear commit messages

### Backward Compatibility Contracts

- Preserve existing imports: `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` from `api.auth`
- Preserve existing functions: `_seed_credentials_from_env()` as wrapper
- Settings fields use raw strings for `admin_disabled_raw` to preserve `_is_truthy()` semantics
