#!/bin/bash
echo "🧪 Running tests..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running."
    exit 1
fi
docker compose -f docker-compose.dev.yml exec -T backend pytest tests/ -v --cov=. --cov-report=html
echo ""
echo "✅ Tests complete!"
