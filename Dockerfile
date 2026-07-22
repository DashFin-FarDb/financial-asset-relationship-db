# Gradio demo / internal-testing image (NON-PRODUCTION).
# Production architecture uses Dockerfile.api + Dockerfile.frontend.
# See docs/adr/0001-production-architecture.md and production-container.yml.
#
# Use Python 3.12 slim image for smaller size
# Note: Python 3.12 chosen for security and compatibility.
# Application supports Python 3.8-3.12 (see pyproject.toml).
FROM python:3.12-slim-trixie

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GRADIO_SERVER_PORT=7860

# Set working directory
WORKDIR /app

# Install system dependencies including curl for health checks
# and apply latest security fixes available in base repositories.
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    g++ \
    gcc \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose Gradio default port
EXPOSE 7860

# Health check using curl (more reliable than Python imports)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD sh -c 'curl -f http://localhost:${GRADIO_SERVER_PORT}/ || exit 1'

# Run the application
CMD ["python", "app.py"]
