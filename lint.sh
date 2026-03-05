#!/bin/bash
echo "🔍 Running linting checks..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running."
    exit 1
fi
echo "📝 Running ruff..."
docker compose -f docker-compose.dev.yml exec -T backend ruff check .
echo ""
echo "🎨 Checking black formatting..."
docker compose -f docker-compose.dev.yml exec -T backend black --check .
echo ""
echo "✅ Lint checks complete!"
