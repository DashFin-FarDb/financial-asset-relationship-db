#!/bin/bash
echo "🚀 Starting Financial Asset Relationship DB Dev Environment..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running."
    exit 1
fi
echo "📦 Building development images..."
docker compose -f docker-compose.dev.yml build
echo ""
echo "🎬 Starting services..."
docker compose -f docker-compose.dev.yml up -d
echo ""
echo "✅ Development environment started!"
echo "📍 Service URLs:"
echo "   Backend (FastAPI):  http://localhost:8000"
echo "   Gradio UI:         http://localhost:7860"
echo "   Database:          postgres://finuser:changeme@localhost:5432/financial_assets"
