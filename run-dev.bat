@echo off
REM Development startup script - runs both backend and frontend on Windows

echo 🚀 Starting Financial Asset Relationship Database Development Environment
echo.

REM Check required environment variables
echo 🔍 Checking required environment variables...
set missing_vars=
if "%DATABASE_URL%"=="" set missing_vars=%missing_vars% DATABASE_URL
if "%SECRET_KEY%"=="" set missing_vars=%missing_vars% SECRET_KEY
if "%ADMIN_USERNAME%"=="" set missing_vars=%missing_vars% ADMIN_USERNAME
if "%ADMIN_PASSWORD%"=="" set missing_vars=%missing_vars% ADMIN_PASSWORD

if not "%missing_vars%"=="" (
    echo.
    echo ❌ Error: Missing required backend environment variables:
    echo    %missing_vars%
    echo.
    echo Set required variables before running run-dev.bat:
    echo.
    echo   set DATABASE_URL=sqlite:dev.db
    echo   set SECRET_KEY=replace-with-a-long-random-secret
    echo   set ADMIN_USERNAME=admin
    echo   set ADMIN_PASSWORD=replace-with-a-strong-password
    echo.
    echo See README.md and .env.example for more details.
    exit /b 1
)

echo ✓ All required environment variables are set
echo.

REM Check if virtual environment exists
if not exist ".venv\" (
    echo 📦 Creating Python virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo 🐍 Activating Python virtual environment...
call .venv\Scripts\activate.bat

REM Install Python dependencies
echo 📥 Installing Python dependencies...
pip install -r requirements.txt

REM Start backend in background
echo 🔧 Starting FastAPI backend on port 8000...
start /B python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Check if frontend dependencies are installed
if not exist "frontend\node_modules\" (
    echo 📦 Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

REM Start frontend
echo ⚛️  Starting Next.js frontend on port 3000...
cd frontend
start /B npm run dev
cd ..

echo.
echo ✅ Development servers started!
echo.
echo 📍 Frontend: http://localhost:3000
echo 📍 Backend API: http://localhost:8000
echo 📍 API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the servers
echo.

pause
