# Docker Guide

> **Note:** These docs use the defaults `FRONTEND_PORT=3000`, `BACKEND_PORT=8000`, and `GRADIO_SERVER_PORT=7860` for simplicity. You can override them via environment variables. Example:
>
> ```bash
> export FRONTEND_PORT=3000
> export BACKEND_PORT=8000
> export GRADIO_SERVER_PORT=7860
> ```

The declared production architecture is the **FastAPI backend + Next.js frontend** (see [docs/adr/0001-production-architecture.md](docs/adr/0001-production-architecture.md) and [DEPLOYMENT.md](DEPLOYMENT.md)).

- **Production containers:** `Dockerfile.api`, `Dockerfile.frontend`, and `docker-compose.production.yml`
- **Non-production Gradio demo containers:** `Dockerfile` and `docker-compose.yml` (`app.py` on port `7860`, for demos and internal testing only)

## Production Stack (FastAPI + Next.js)

### Prerequisites

Set the required backend and frontend runtime environment variables (for example in a local uncommitted `.env` file):

- `DATABASE_URL` (PostgreSQL URL for hosted/production; `sqlite:dev.db` for local dev)
- `ASSET_GRAPH_DATABASE_URL` (durable graph store URL)
- `SECRET_KEY` (strong random JWT signing key)
- `ADMIN_USERNAME` and `ADMIN_PASSWORD` (for initial bootstrap migration only)
- `NEXT_PUBLIC_API_URL` (backend URL reachable by the browser)

### Run Database Migrations (Operator Profile)

FastAPI startup does not auto-create tables. Run migrations first using the `operator` profile (`Dockerfile.api` `migration` target):

```bash
docker compose -f docker-compose.production.yml --profile operator run --rm migrate
```

### Build and Start Production Services

```bash
# Build and start api (port 8000) and frontend (port 3000)
docker compose -f docker-compose.production.yml up -d --build

# Check container status and logs
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs -f

# Stop services
docker compose -f docker-compose.production.yml down
```

### Build Production Images Individually

```bash
# FastAPI backend runtime image (multi-stage python:3.12-slim)
docker build -f Dockerfile.api --target runtime -t fardb-api:local .

# FastAPI migration image
docker build -f Dockerfile.api --target migration -t fardb-migrate:local .

# Next.js frontend image (node:20.19.0-slim)
docker build -f Dockerfile.frontend -t fardb-frontend:local .
```

## Non-Production Gradio Demo Path

The root `Dockerfile` and `docker-compose.yml` start the **Gradio demo UI (`app.py`) on port `7860`**. They are for demos and internal testing only and are not the canonical production deployment path.

### Using Docker Compose (Gradio Demo)

```bash
# Build and start the Gradio demo
docker compose up --build

# Run in background
docker compose up -d --build

# View logs / stop
docker compose logs -f
docker compose down
```

Access the Gradio demo at `http://localhost:${GRADIO_SERVER_PORT:-7860}`.

### Using Docker Directly (Gradio Demo)

```bash
# Build the demo image
docker build -t financial-asset-db:demo .

# Run the demo container
docker run -p ${GRADIO_SERVER_PORT:-7860}:${GRADIO_SERVER_PORT:-7860} financial-asset-db:demo
```

## Health Checks & Troubleshooting

```bash
# Inspect container health status
docker inspect --format='{{.State.Health.Status}}' <container-name>

# View recent health check output
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' <container-name>

# Rebuild cleanly without cache
docker compose -f docker-compose.production.yml build --no-cache
```

- **Backend won't start:** Confirm `DATABASE_URL`, `SECRET_KEY`, and `ADMIN_USERNAME` are set and that `migrate` has been run.
- **Port already in use:** Override `BACKEND_PORT`, `FRONTEND_PORT`, or `GRADIO_SERVER_PORT` in your environment.

## Best Practices

1. **Security:** Production images run as non-root users; inject secrets via environment or secret manager (never bake credentials into images).
2. **Tagging:** Pin explicit image digests or version tags rather than `:latest`.
3. **Migrations:** Always run the `operator` `migrate` target before rolling out new `api` containers.

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [DEPLOYMENT.md](DEPLOYMENT.md)
