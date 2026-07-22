# Gradio demo / internal-testing image (NON-PRODUCTION).
# Production architecture uses Dockerfile.api + Dockerfile.frontend.
# See docs/adr/0001-production-architecture.md and
# .github/workflows/production-container.yml.
#
# Multi-stage: compile native deps in the builder, keep the runtime image free of
# gcc/g++/make/binutils and apt extras like curl (reduces Snyk Container noise).
#
# Use Python 3.12 slim image for smaller size
# Note: Python 3.12 chosen for security and compatibility.
# Application supports Python 3.8-3.12 (see pyproject.toml).
FROM python:3.12-slim-trixie AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# hadolint ignore=DL3008
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    g++ \
    gcc \
    make \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim-trixie AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GRADIO_SERVER_PORT=7860 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# No apt packages in the runtime stage: compilers stay in the builder, and a
# pure-Python HEALTHCHECK avoids curl (and its gnutls/krb5/openldap deps).
COPY --from=builder /opt/venv /opt/venv
COPY . .

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

# Pure-Python healthcheck avoids a curl apt dependency in the runtime image.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('GRADIO_SERVER_PORT','7860')+'/')" || exit 1

CMD ["python", "app.py"]
