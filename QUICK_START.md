# Quick Start Guide - Next.js + FastAPI Integration

This guide will get you up and running with the new Next.js frontend in under 5 minutes.

## Prerequisites

- Python 3.8 or higher
- Node.js 18 or higher
- Git

## Option 1: Automated Setup (Recommended)

### Linux/macOS

```bash
# Make the script executable
chmod +x run-dev.sh

# Run the development environment
./run-dev.sh
```

### Windows

```cmd
# Run the development environment
run-dev.bat
```

That's it! The script will:

1. Create a Python virtual environment
2. Install Python dependencies
3. Install Node.js dependencies
4. Start the FastAPI backend on port 8000
5. Start the Next.js frontend on port 3000

**Access the application:**

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

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

# Start the backend
python -m uvicorn api.main:app --reload --port 8000
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

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

Visit http://localhost:8000/docs to see the interactive API documentation.

### Frontend (Port 3000)

```
- ready started server on 0.0.0.0:3000, url: http://localhost:3000
- event compiled client and server successfully
```

Visit http://localhost:3000 to see the application.

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
curl http://localhost:8000/api/health

# Get all assets
curl http://localhost:8000/api/assets

# Get metrics
curl http://localhost:8000/api/metrics
```

### Using Python

```bash
# Run the test script
python test_api.py
```

### Using Browser

Visit http://localhost:8000/docs for interactive API testing.

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

- Check that backend is running on port 8000
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
python -m uvicorn api.main:app --reload --port 8000

# Start with custom host
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Start without auto-reload (production-like)
python -m uvicorn api.main:app --port 8000
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
   - Backend: `api/main.py`
   - Frontend: `frontend/app/page.tsx`
   - Components: `frontend/app/components/`

2. **Read the documentation**
   - [DEPLOYMENT.md](./DEPLOYMENT.md) - Full deployment guide
   - [INTEGRATION_SUMMARY.md](./INTEGRATION_SUMMARY.md) - Technical details
   - [frontend/README.md](./frontend/README.md) - Frontend specifics

3. **Deploy to Vercel**
   - See [DEPLOYMENT.md](./DEPLOYMENT.md) for instructions

4. **Customize**
   - Modify components in `frontend/app/components/`
   - Add new API endpoints in `api/main.py`
   - Update styles in `frontend/app/globals.css`

## Getting Help

1. Check the error messages in your terminal
2. Review the browser console for frontend errors
3. Visit the API docs at http://localhost:8000/docs
4. See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed troubleshooting

## Compare with Gradio UI

You can still use the original Gradio interface:

```bash
python app.py
```

Access at http://localhost:7860

Both UIs use the same underlying data and logic, so you can use whichever you prefer!

---

**Happy Coding! 🚀**
