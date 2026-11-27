# Quick Start Guide - Next.js + FastAPI Integration

> **Note:** These docs use the defaults `FRONTEND_PORT=3000`, `BACKEND_PORT=8000`, and `GRADIO_SERVER_PORT=7860` for simplicity. You can override them via environment variables. Example:
> ```bash
> export FRONTEND_PORT=3000
> export BACKEND_PORT=8000
> export GRADIO_SERVER_PORT=7860
> ```


This guide will get you up and running with the new Next.js frontend in under 5 minutes.

## Prerequisites

- Python 3.10+ (3.12+ recommended)
- Node.js 22 LTS (minimum `>=20.19.0`)
- Git

## Option 1: Automated Setup (Recommended)

Export the required backend environment variables and initialize the local database before starting both servers:

### Linux/macOS

```bash
export DATABASE_URL=sqlite:dev.db
export SECRET_KEY=replace-with-a-long-random-secret
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=replace-with-a-strong-password
python -m scripts.migrate_database
unset ADMIN_PASSWORD

# Make the script executable and start backend + frontend
chmod +x run-dev.sh
./run-dev.sh
```

### Windows

```cmd
set DATABASE_URL=sqlite:dev.db
set SECRET_KEY=replace-with-a-long-random-secret
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=replace-with-a-strong-password
python -m scripts.migrate_database
set ADMIN_PASSWORD=
run-dev.bat
```

That's it! The script will:

1. Create a Python virtual environment
2. Install Python dependencies
3. Install Node.js dependencies
4. Start the FastAPI backend on port ${BACKEND_PORT:-8000}
5. Start the Next.js frontend on port ${FRONTEND_PORT:-3000}

**Access the application:**

- Frontend: http://localhost:${FRONTEND_PORT:-3000}
- Backend API: http://localhost:${BACKEND_PORT:-8000}
- API Documentation: http://localhost:${BACKEND_PORT:-8000}/docs

## Option 2: Manual Setup

### Step 1: Backend Setup

```bash
# Create and activate virtual environment
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure required runtime environment variables and run migrations
export DATABASE_URL=sqlite:dev.db
export SECRET_KEY=replace-with-a-long-random-secret
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=replace-with-a-strong-password
python -m scripts.migrate_database
unset ADMIN_PASSWORD

# Start the backend
python -m uvicorn api.main:app --reload --port ${BACKEND_PORT:-8000}
```

### Step 2: Frontend Setup (in a new terminal)

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Copy environment file from project root
# (the .env.example file is located in the project root directory)
cp ../.env.example .env.local

# Start the development server
npm run dev
```

## What You'll See

### Backend (Port 8000)

```text
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

Visit http://localhost:${BACKEND_PORT:-8000}/docs to see the interactive API documentation.

### Frontend (Port 3000)

```text
- ready started server on 0.0.0.0:3000, url: http://localhost:${FRONTEND_PORT:-3000}
- event compiled client and server successfully
```

Visit http://localhost:${FRONTEND_PORT:-3000} to see the application.

## Using the Application

### 1. 3D Visualization Tab

- Interactive 3D network graph
- Rotate: Click and drag
- Zoom: Scroll wheel
- Hover: View asset details

### 2. Metrics & Analytics Tab

- Total assets and relationships
- Network statistics
- Asset class distribution

### 3. Asset Explorer Tab

- Filterable table of all assets
- Filter by asset class or sector
- View detailed asset information

## Testing the API

### Using curl

```bash
# Health check
curl http://localhost:${BACKEND_PORT:-8000}/api/health

# Get all assets
curl http://localhost:${BACKEND_PORT:-8000}/api/assets

# Get graph network metrics
curl http://localhost:${BACKEND_PORT:-8000}/api/graph/metrics
```

### Using pytest

```bash
# Run API unit tests (or run `python run_tests.py` for the full suite)
pytest tests/unit/test_api_main.py -v
```

### Using Browser

Visit http://localhost:${BACKEND_PORT:-8000}/docs for interactive API testing.

## Troubleshooting

### Backend Issues

**Problem: Port 8000 already in use**

```bash
# Find and kill the process
# Linux/macOS
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Problem: Module not found errors**

```bash
# Ensure virtual environment is activated
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Frontend Issues

**Problem: Port 3000 already in use**

```bash
# The frontend will automatically use the next available port
# Or kill the process manually:

# Linux/macOS
lsof -ti:3000 | xargs kill -9

# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

**Problem: API connection errors**

- Check that backend is running on port ${BACKEND_PORT:-8000}
- Verify `NEXT_PUBLIC_API_URL` in `.env.local`
- Check browser console for CORS errors

**Problem: Module not found**

```bash
cd frontend
rm -rf node_modules .next
npm install
npm run dev
```

## Common Commands

### Backend

```bash
# Start backend
python -m uvicorn api.main:app --reload --port ${BACKEND_PORT:-8000}

# Start with custom host
python -m uvicorn api.main:app --host 0.0.0.0 --port ${BACKEND_PORT:-8000}

# Start without auto-reload (production-like)
python -m uvicorn api.main:app --port ${BACKEND_PORT:-8000}
```

### Frontend

```bash
cd frontend

# Development server
npm run dev

# Production build
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

## Next Steps

1. **Explore the code**
   - Backend entrypoint & routers: `api/main.py`, `api/app_factory.py`, `api/routers/`
   - Frontend: `frontend/app/page.tsx`
   - Components: `frontend/app/components/`

2. **Read the documentation**
   - [DEPLOYMENT.md](./DEPLOYMENT.md) - Full deployment guide
   - [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
   - [frontend/README.md](./frontend/README.md) - Frontend specifics

3. **Deploy to Vercel**
   - See [DEPLOYMENT.md](./DEPLOYMENT.md) for instructions

4. **Customize**
   - Modify components in `frontend/app/components/`
   - Add new API endpoints in `api/routers/` (registered in `api/app_factory.py`)
   - Update styles in `frontend/app/globals.css`

## Getting Help

1. Check the error messages in your terminal
2. Review the browser console for frontend errors
3. Visit the API docs at http://localhost:${BACKEND_PORT:-8000}/docs
4. See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed troubleshooting

## Gradio Demo UI (Non-Production)

For local demos and internal testing only, you can also run the non-production Gradio interface:

```bash
python app.py
```

Access at http://localhost:${GRADIO_SERVER_PORT:-7860}.

**Note:** FastAPI + Next.js is the declared production architecture (see [docs/adr/0001-production-architecture.md](docs/adr/0001-production-architecture.md)); Gradio is for local demos and internal testing only.

---

**Happy Coding! 🚀**
