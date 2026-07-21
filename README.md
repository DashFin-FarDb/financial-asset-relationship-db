[![Board Status](https://dev.azure.com/mohavro/2e48cc65-ae36-4c98-98b5-0eb4c1a1b5df/7f564e5b-a967-4110-9d79-7aeaaf540ef4/_apis/work/boardbadge/b59b599b-e6ab-41bd-8d76-d02d17a77a9d)](https://dev.azu[...]
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/DashFin-FarDb/financial-asset-relationship-db?utm_source=badge)

# Financial Asset Relationship Database

> **Note:** These docs use the defaults `FRONTEND_PORT=3000`, `BACKEND_PORT=8000`, and `GRADIO_SERVER_PORT=7860` for simplicity. You can override them via environment variables. Example:
> ```bash
> export FRONTEND_PORT=3000
> export BACKEND_PORT=8000
> export GRADIO_SERVER_PORT=7860
> ```


A comprehensive 3D visualization system for interconnected financial assets across all major classes: **Equities, Bonds, Commodities, Currencies, and Regulatory Events**.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for production frontend)
- Virtual environment (recommended)

### Production Setup: Next.js Frontend + FastAPI Backend

**This is the recommended production path for deployment and development.**

For the modern web frontend with REST API:

**Quick Start (Both Servers):**

Configuration is now centralized through `src/config/settings.py` via `pydantic-settings`. Note that configuration settings are validated and cached at import-time. You must set these environment variables before launching the application or running the test suite. While reasonable defaults are provided for local development, you can set the backend runtime environment variables required by `api.main:app` as shown below. Note that auth keys like `SECRET_KEY` are deterministic in testing environments.

```bash
# Linux/macOS
export DATABASE_URL=sqlite:dev.db
export SECRET_KEY=replace-with-a-long-random-secret
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=replace-with-a-strong-password
./run-dev.sh
```

```cmd
REM Windows CMD
set DATABASE_URL=sqlite:dev.db
set SECRET_KEY=replace-with-a-long-random-secret
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=replace-with-a-strong-password
run-dev.bat
```

This will start both the FastAPI backend (port ${BACKEND_PORT:-8000}) and Next.js frontend (port ${FRONTEND_PORT:-3000}).

**Manual Setup:**

1. **Start the FastAPI backend:**

   Linux/macOS:

   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   export DATABASE_URL=sqlite:dev.db
   export SECRET_KEY=replace-with-a-long-random-secret
   export ADMIN_USERNAME=admin
   export ADMIN_PASSWORD=replace-with-a-strong-password
   python -m uvicorn api.main:app --reload --port ${BACKEND_PORT:-8000}
   ```

   Windows PowerShell users should activate `.venv\\Scripts\\Activate.ps1` and set the same environment variables with `$env:NAME="value"` before running the `python -m uvicorn ...` command.

   The backend production entrypoint is `api.main:app`. Production deployments should run the same app object with a command equivalent to the following; set the PORT environment variable as needed (example shown):

   ```bash
   # set a PORT env var (example)
   export PORT=8000
   python -m uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
   ```

2. **Start the Next.js frontend (in a new terminal):**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Access the application:**
   - Frontend: `http://localhost:${FRONTEND_PORT:-3000}`
   - Backend API: `http://localhost:${BACKEND_PORT:-8000}`
   - API Documentation: `http://localhost:${BACKEND_PORT:-8000}/docs`

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions and Vercel integration.

**Hosted Deployment**: For the hosted deployment and durable persistence decision, see [docs/adr/0002-hosted-deployment-and-persistence.md](docs/adr/0002-hosted-deployment-and-persistence.md).

For the full enterprise-readiness package, see [docs/enterprise-readiness-index.md](./docs/enterprise-readiness-index.md).

For dated product strategy, current-versus-target claims, and the long-range FarDB platform direction, see
[docs/strategy/README.md](./docs/strategy/README.md). Strategy material is subordinate to code, accepted ADRs, and
release evidence.

### Hosted Readiness Smoke Check

You can verify a hosted deployment's liveness and readiness endpoints:

```bash
python scripts/check_hosted_readiness.py <base_url> [--timeout SECONDS] [--require-persistence] [--assets-smoke]
```

The `--require-persistence` option enforces that the deployment has successfully loaded its asset graph from the configured database (meaning `persistence_enabled` is true, `persistence_loaded` is true, and the startup source is `"persisted"`). It also enables `--assets-smoke`, which proves bounded `GET /api/assets?per_page=1` returns at least one asset. Both are mandatory for staging and production promotions.


### Troubleshooting

#### Frontend shows "Failed to load data"

This usually means the FastAPI backend is not running or failed during startup.

Before starting the frontend, verify the backend starts with the required environment variables:

```bash
export DATABASE_URL="sqlite:dev.db"
export SECRET_KEY="change-me-to-a-long-random-secret"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="change-me"
python -m uvicorn api.main:app --reload --port ${BACKEND_PORT:-8000}
```

Then verify:

```bash
curl http://localhost:${BACKEND_PORT:-8000}/api/health
curl http://localhost:${BACKEND_PORT:-8000}/api/visualization
```

If `/api/health` fails, fix the backend startup first. If `/api/health` works but the frontend still fails, check `NEXT_PUBLIC_API_URL` and the browser Network tab.

#### Backend fails with `sqlite3.OperationalError: unable to open database file`

The API startup path (`api/database.py`) resolves SQLite file paths using a custom resolver, not SQLAlchemy URL path semantics. A URL like `sqlite:///./dev.db` can resolve to `/dev.db`, which is often unwritable in local environments.

Use one of these known-good `DATABASE_URL` values instead:

```bash
# repo-relative file in the current working directory
export DATABASE_URL="sqlite:dev.db"

# in-memory SQLite
export DATABASE_URL="sqlite:///:memory:"

# explicit writable absolute path
export DATABASE_URL="sqlite:////absolute/path/dev.db"
```

Then restart the backend:

```bash
python -m uvicorn api.main:app --reload --port ${BACKEND_PORT:-8000}
```

#### `python: command not found` in Linux cloud/dev containers

Some Linux environments provide `python3` but not `python` on `PATH`.

- Use `python3 -m venv .venv` to create the virtual environment.
- Activate it (`source .venv/bin/activate`) so `python` resolves from the venv, or run commands with `python3`.

Note: the application creates a startup trace context (trace_id/span_id) during lifespan-based state initialization, so observability events emitted during startup (reconciliation, get_graph, etc.) include trace metadata.

For implementation details, see the code and tests:

- [api/app_factory.py](api/app_factory.py)
- [tests/unit/test_app_factory.py](tests/unit/test_app_factory.py)
- [tests/unit/api/observability/](tests/unit/api/observability/)

Format: trace_id is the full uuid4().hex (32 lowercase hex chars); span_id is the first 16 hex characters of uuid4().hex (16 lowercase hex chars).

### Demo/Internal UI: Gradio (Non-Production)

The Gradio UI (`app.py`) is decoupled from production configuration and acts strictly as a non-production demo endpoint. It explicitly bounds its host to localhost (`127.0.0.1`) unless specified otherwise. It is **not recommended for production deployment**.
