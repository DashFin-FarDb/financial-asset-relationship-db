#!/bin/bash
echo "🐛 Starting debug environment..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running."
    exit 1
fi
docker compose -f docker-compose.debug.yml down 2>/dev/null
echo "📦 Starting debug containers..."
docker compose -f docker-compose.debug.yml up -d
echo ""
echo "✅ Debug environment ready!"
echo "📍 Debug URLs:"
echo "   Debugger:  localhost:5678"
echo "   Gradio:    http://localhost:7860"
echo "   FastAPI:   http://localhost:8000"
