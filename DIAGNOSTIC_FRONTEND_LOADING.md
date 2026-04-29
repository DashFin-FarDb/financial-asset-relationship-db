# Diagnostic Report: Frontend Visualization Data Loading Failure

**Issue:** #1086
**Date:** 2026-04-29
**Branch:** claude/claudediagnose-frontend-visualization-loading

## Problem Statement

The Next.js frontend displays "Failed to load data. Please ensure the API server is running." instead of rendering the 3D visualization when accessing `http://localhost:3000`.

## Root Cause

**Backend requires specific environment variables to start successfully.**

The FastAPI backend (`api/main.py`) imports `api/auth.py` which enforces user credential validation at module import time (line 246). Without the required environment variables, the backend fails to start with:

```
ValueError: No user credentials available. Provide ADMIN_USERNAME and ADMIN_PASSWORD or pre-populate the database.
```

## Required Environment Variables

```bash
DATABASE_URL="sqlite:///:memory:"          # or sqlite:dev.db
SECRET_KEY="<32-char-min-secret-key>"     # JWT signing key
ADMIN_USERNAME="admin"                     # Initial admin username
ADMIN_PASSWORD="<secure-password>"         # Initial admin password
```

## Diagnostic Test Results

### 1. Backend Health Checks ✓

When properly configured with all required environment variables, all backend endpoints work correctly:

| Endpoint | Status | Response |
|----------|--------|----------|
| `/api/health` | ✓ 200 OK | `{"status":"healthy","graph_initialized":true}` |
| `/api/visualization` | ✓ 200 OK | 19 nodes, 57 edges (7917 bytes JSON) |
| `/api/assets` | ✓ 200 OK | 19 items paginated (4648 bytes JSON) |
| `/api/metrics` | ✓ 200 OK | All required metrics fields |

**Test command:**
```bash
export DATABASE_URL="sqlite:///:memory:"
export SECRET_KEY="test-secret-key-for-diagnostics-12345678901234567890"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="testpass123"
python -m uvicorn api.main:app --reload --port 8000
```

### 2. Frontend Configuration ✓

| Component | Status | Details |
|-----------|--------|---------|
| API URL | ✓ | Defaults to `http://localhost:8000` (`frontend/app/lib/api.ts:11`) |
| Build | ✓ | No TypeScript or compilation errors |
| Environment | ✓ | `next.config.js` properly exposes `NEXT_PUBLIC_API_URL` |
| API Client | ✓ | Axios configured with correct base URL and 10s timeout |

### 3. CORS Configuration ✓

The backend CORS policy (`api/cors_policy.py:104-116`) correctly allows `http://localhost:3000` in development mode:

- Development mode includes `localhost:3000` and `127.0.0.1:3000` (both HTTP and HTTPS)
- CORS middleware configured with credentials support
- Standard HTTP methods allowed: GET, POST, PUT, DELETE, OPTIONS

### 4. Error Handling ✓

Frontend error handling in `frontend/app/page.tsx:168-174` works as designed:

```typescript
catch (err) {
  console.error("Error loading data:", err);
  setError("Failed to load data. Please ensure the API server is running.");
}
```

The generic error message intentionally masks internal details for security.

## Data Flow Analysis

### Expected Flow (Working State)

1. Frontend loads at `http://localhost:3000`
2. `useEffect` hook calls `api.getMetrics()` and `api.getVisualizationData()` (page.tsx:161-164)
3. Axios sends GET requests to:
   - `http://localhost:8000/api/metrics`
   - `http://localhost:8000/api/visualization`
4. Backend returns JSON data
5. Frontend state updates: `setMetrics(data)`, `setVizData(data)`
6. NetworkVisualization component renders 3D Plotly graph

### Actual Failure Scenarios

#### Scenario A: Backend Not Running (Most Common)
1. Frontend loads and attempts API calls
2. Backend not running → Connection refused (ECONNREFUSED)
3. Axios throws network error
4. Frontend catches error → displays "Failed to load data"

#### Scenario B: Backend Missing Environment Variables
1. User runs `python -m uvicorn api.main:app`
2. Import fails at `api/auth.py:246` → ValueError raised
3. uvicorn exits, backend never starts
4. Results in Scenario A from frontend perspective

#### Scenario C: Backend Running on Wrong Port
1. Backend running on different port (e.g., 8080 instead of 8000)
2. Frontend calls `http://localhost:8000` → Connection refused
3. Same result as Scenario A

## Failure Classification

From issue #1086 "Likely failure classes":

**✓ Identified: #2 - Backend not actually running**

The backend fails to start without required environment variables. From the frontend's perspective, this manifests as a network connection error.

**Not applicable:**
- ❌ #1 - Frontend calling wrong base URL (verified correct)
- ❌ #3 - CORS rejection (policy allows localhost:3000)
- ❌ #4 - Route mismatch (routes verified correct)
- ❌ #5 - Response shape mismatch (response models match TypeScript types)
- ❌ #6 - Frontend swallowing error (error is logged to console)

## Files Examined

| File | Line(s) | Purpose |
|------|---------|---------|
| `api/main.py` | 19 | FastAPI entry point, imports app_factory |
| `api/auth.py` | 246 | User credential validation (raises ValueError) |
| `api/routers/visualization.py` | 84-98 | Visualization endpoint implementation |
| `api/cors_policy.py` | 104-116 | CORS configuration for development mode |
| `frontend/app/lib/api.ts` | 11 | API_URL configuration |
| `frontend/app/page.tsx` | 156-178 | Data loading logic and error handling |
| `frontend/app/components/NetworkVisualization.tsx` | - | Visualization rendering component |
| `.env.example` | 1-14 | Environment variable template |
| `README.md` | 23-61 | Production setup documentation |

## Validation Results

- ✓ Backend starts successfully with all required env vars
- ✓ All API endpoints return valid data matching response models
- ✓ Frontend builds without errors
- ✓ CORS policy allows localhost:3000 in development mode
- ✓ Documentation in README.md already covers required setup

## Conclusion

**No code changes required.** This is an environmental/operational issue, not a bug in the codebase.

The frontend → backend → visualization data flow works correctly when both services are properly configured and running.

## User Resolution Steps

Users experiencing "Failed to load data" should:

1. **Set all required environment variables** before starting the backend:
   ```bash
   export DATABASE_URL="sqlite:dev.db"
   export SECRET_KEY="your-long-random-secret-key-here"
   export ADMIN_USERNAME="admin"
   export ADMIN_PASSWORD="your-secure-password"
   ```

2. **Verify backend is running** and accessible:
   ```bash
   curl http://localhost:8000/api/health
   # Should return: {"status":"healthy","graph_initialized":true}
   ```

3. **Check browser console** for specific error messages:
   - Open DevTools → Console tab
   - Look for red error messages
   - Network tab shows: connection refused vs CORS vs 404 vs 500 errors

4. **Verify ports**:
   - Backend should be on port 8000
   - Frontend should be on port 3000

## Documentation Assessment

**Existing documentation is adequate.** The `README.md` file already clearly documents all required environment variables in:

- **Lines 23-31:** Quick Start with convenience scripts
- **Lines 47-61:** Manual Setup with step-by-step instructions

No documentation updates required.

## Related Issues

- Addresses diagnostic request: #1086
- Part of master checklist: #1028 (Phase 6 closure prerequisites)
- Relates to: Production architecture declaration (ADR 0001)
