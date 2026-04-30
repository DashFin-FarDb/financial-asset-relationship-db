[![Board Status](https://dev.azure.com/mohavro/2e48cc65-ae36-4c98-98b5-0eb4c1a1b5df/7f564e5b-a967-4110-9d79-7aeaaf540ef4/_apis/work/boardbadge/b59b599b-e6ab-41bd-8d76-d02d17a77a9d)](https://dev.azure.com/mohavro/2e48cc65-ae36-4c98-98b5-0eb4c1a1b5df/_boards/board/t/7f564e5b-a967-4110-9d79-7aeaaf540ef4/Microsoft.RequirementCategory)

# Financial Asset Relationship Database

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

Before using the convenience scripts, set the backend runtime environment required by `api.main:app`. The scripts do not currently load these values from `.env.example`.

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

This will start both the FastAPI backend (port 8000) and Next.js frontend (port 3000).

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
   python -m uvicorn api.main:app --reload --port 8000
   ```

   Windows PowerShell users should activate `.venv\Scripts\Activate.ps1` and set the same environment variables with `$env:NAME="value"` before running the `python -m uvicorn ...` command.

   The backend production entrypoint is `api.main:app`. Production deployments should run the same app object with a command equivalent to `python -m uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"`. See [DEPLOYMENT.md](DEPLOYMENT.md) for runtime environment details.

2. **Start the Next.js frontend (in a new terminal):**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Access the application:**
   - Frontend: `http://localhost:3000`
   - Backend API: `http://localhost:8000`
   - API Documentation: `http://localhost:8000/docs`

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions and Vercel integration.

**Hosted Deployment**: For the hosted deployment and durable persistence decision, see [docs/adr/0002-hosted-deployment-and-persistence.md](docs/adr/0002-hosted-deployment-and-persistence.md).

### Troubleshooting

#### Frontend shows "Failed to load data"

This usually means the FastAPI backend is not running or failed during startup.

Before starting the frontend, verify the backend starts with the required environment variables:

```bash
export DATABASE_URL="sqlite:dev.db"
export SECRET_KEY="change-me-to-a-long-random-secret"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="change-me"
python -m uvicorn api.main:app --reload --port 8000
```

Then verify:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/visualization
```

If `/api/health` fails, fix the backend startup first. If `/api/health` works but the frontend still fails, check `NEXT_PUBLIC_API_URL` and the browser Network tab.

### Demo/Internal UI: Gradio (Non-Production)

The Gradio UI (`app.py`) is available for demos, internal testing, and rapid prototyping. It is **not recommended for production deployment**.
