# Testing Guide

Canonical testing entrypoint for the Financial Asset Relationship Database (FastAPI backend + Next.js frontend).

For full repository orientation, environment variable details, and operational readiness procedures, see [AGENTS.md](AGENTS.md) and [docs/testing/](docs/testing/).

## Python Backend Tests (pytest)

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Running Tests

```bash
# Run the full Python test suite (configured in pyproject.toml)
pytest

# Or use the local wrapper that injects default in-memory DB/auth env vars
python run_tests.py

# Run a single file, class, or pattern
pytest tests/unit/test_api_main.py -v
pytest tests/unit/test_api_main.py::TestValidateOrigin -v
pytest -k "test_assets" -v

# Run with coverage report
pytest --cov=api --cov=src --cov-report=html
```

### Optional Live & Smoke Checks

- **Opt-in Supabase connectivity test** (skipped by default in CI/local runs):

  ```bash
  RUN_SUPABASE_TESTS=1 SUPABASE_URL=... SUPABASE_KEY=... pytest tests/integration/test_supabase.py -v
  ```

- **Manual database module smoke script**:

  ```bash
  python scripts/test_db_module.py
  ```

## Frontend Tests (Jest)

```bash
cd frontend
npm install

# Run all frontend tests
npm test

# Watch mode and coverage
npm run test:watch
npm run test:coverage

# Run a specific test file or directory
npm test -- AssetList.test.tsx
npm test -- api.test.ts
npm test -- __tests__/lib

# Filter by suite or test name
npm test -- -t "Accessibility"
npm test -- -t "Error Handling"
npm test -- --verbose
```

## Lint, Format, Typecheck, and Pre-Commit

```bash
# Run pre-commit hooks on modified files
pre-commit run --files <paths>

# Direct Python checks
flake8 src/ tests/
black --check src/ tests/ app.py
isort --check-only src/ tests/ app.py
mypy src/ --ignore-missing-imports

# Frontend lint and production build
cd frontend && npm run lint && npm run build
```

## Troubleshooting

- **Python import or environment errors:** Activate `.venv`, ensure `requirements.txt` and `requirements-dev.txt` are installed, or run via `python run_tests.py` so required `DATABASE_URL` / `SECRET_KEY` / `ADMIN_*` env vars are populated.
- **SQLite `DATABASE_URL` path errors:** Use `sqlite:///:memory:` or `sqlite:dev.db` rather than `sqlite:///./dev.db` (see [AGENTS.md](AGENTS.md)).
- **Frontend module/mock errors:** Run `npm install` in `frontend/` and verify Jest mock paths match `frontend/app/`.
