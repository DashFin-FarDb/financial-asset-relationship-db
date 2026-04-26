# Active Context

## Current Phase

Development / PR Review

## Current Task

PR #1059 - Centralize auth runtime settings access

## Focus Areas

- Auth settings centralization (Issue #1028 Phase 4)
- Pre-commit compliance
- Test coverage for settings and auth modules

## Recently Modified Files

- `tests/unit/test_auth.py` - Added missing docstrings to fixtures and test classes
- `src/config/settings.py` - Auth fields added (secret_key, admin_*)
- `api/auth.py` - Migrated from os.getenv() to Settings

## Open Questions

- None currently - PR is passing pre-commit checks

## Next Steps

- Monitor CI status on PR #1059
- Address any additional review feedback
- Prepare for merge when approved

## Key Repository Patterns

### Production Architecture
- **Backend**: FastAPI (`api/`) on port 8000
- **Frontend**: Next.js (`frontend/`) on port 3000
- **Non-Production**: Gradio (`app.py`) for demos only

### Required Environment Variables
- `DATABASE_URL` - SQLite connection string
- `SECRET_KEY` - JWT signing key (required)
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` - For user seeding

### Testing Commands
```bash
# Python tests
pytest tests/unit/test_settings.py tests/unit/test_auth.py -v

# Pre-commit checks
pre-commit run --files api/auth.py src/config/settings.py tests/unit/test_auth.py

# Full lint
make lint
```

### PR Scope Requirements
All PRs must include:
1. Primary Objective (single decision)
2. In Scope / Out of Scope
3. Files Expected to Change
4. Validation Commands
5. Merge Criteria
