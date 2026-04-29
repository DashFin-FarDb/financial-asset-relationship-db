#!/bin/bash
# Development startup script - runs both backend and frontend

set -e

echo "🚀 Starting Financial Asset Relationship Database Development Environment"
echo ""

# Check required environment variables
echo "🔍 Checking required environment variables..."
required_vars=(DATABASE_URL SECRET_KEY ADMIN_USERNAME ADMIN_PASSWORD)
missing_vars=()

for var in "${required_vars[@]}"; do
  if [ -z "${!var:-}" ]; then
    missing_vars+=("$var")
  fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
  echo ""
  echo "❌ Error: Missing required backend environment variables:"
  for var in "${missing_vars[@]}"; do
    echo "   - $var"
  done
  echo ""
  echo "Set required variables before running ./run-dev.sh:"
  echo ""
  echo "  export DATABASE_URL=sqlite:dev.db"
  echo "  export SECRET_KEY=replace-with-a-long-random-secret"
  echo "  export ADMIN_USERNAME=admin"
  echo "  export ADMIN_PASSWORD=replace-with-a-strong-password"
  echo ""
  echo "See README.md and .env.example for more details."
  exit 1
fi

echo "✓ All required environment variables are set"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
echo "🐍 Activating Python virtual environment..."
source .venv/bin/activate

# Install Python dependencies
echo "📥 Installing Python dependencies..."
pip install -r requirements.txt

# Start backend in background
echo "🔧 Starting FastAPI backend on port 8000..."
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if frontend directory exists
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Start frontend
echo "⚛️  Starting Next.js frontend on port 3000..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Development servers started!"
echo ""
echo "📍 Frontend: http://localhost:3000"
echo "📍 Backend API: http://localhost:8000"
echo "📍 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for Ctrl+C
trap "echo ''; echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
