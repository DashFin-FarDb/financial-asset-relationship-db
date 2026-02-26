# Docker Deployment Guide

This guide explains how to run the Financial Asset Relationship Database using Docker and Docker Compose.

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Build and start the application
docker-compose up --build

# Access the application at http://localhost:7860
```

### Using Docker Directly

```bash
# Build the image
docker build -t financial-asset-db .

# Run the container
docker run -p 7860:7860 financial-asset-db

# Access the application at http://localhost:7860
```

## Docker Compose Options

### Development Mode

Mount your source code for live development:

```bash
# The docker-compose.yml already includes volume mounts
docker-compose up
```

Changes to `src/` will be reflected immediately (may require app restart).

### Production Mode

Build and run in detached mode:

```bash
# Build and start in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

### With Database (PostgreSQL)

Uncomment the `postgres` service in `docker-compose.yml`:

```bash
# Start with database
docker-compose up -d

# The database will be available at:
# Host: localhost
# Port: 5432
# Database: financial_assets
# User: finuser
# Password: changeme
```

## Environment Variables

Configure the application using environment variables in `docker-compose.yml`:

```yaml
environment:
  - GRADIO_SERVER_NAME=0.0.0.0
  - GRADIO_SERVER_PORT=7860
  - DATABASE_URL=postgresql://finuser:changeme@postgres:5432/financial_assets
```

## Docker Commands

### Build

```bash
# Build the Docker image
docker build -t financial-asset-db .

# Build with no cache
docker build --no-cache -t financial-asset-db .
```

### Run

```bash
# Run container
docker run -p 7860:7860 financial-asset-db

# Run in background
docker run -d -p 7860:7860 --name financial-asset-db financial-asset-db

# Run with environment variables
docker run -p 7860:7860 -e GRADIO_SERVER_NAME=0.0.0.0 financial-asset-db
```

### Manage

```bash
# List running containers
docker ps

# View logs
docker logs financial-asset-db

# Follow logs
docker logs -f financial-asset-db

# Stop container
docker stop financial-asset-db

# Remove container
docker rm financial-asset-db

# Remove image
docker rmi financial-asset-db
```

## Docker Compose Commands

```bash
# Start services
docker-compose up

# Start in background
docker-compose up -d

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# View logs
docker-compose logs

# Follow logs for specific service
docker-compose logs -f app

# Rebuild images
docker-compose build

# Rebuild and start
docker-compose up --build

# Scale services (if needed)
docker-compose up --scale app=3
```

## Health Checks

The application includes health checks:

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' financial-asset-db

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' financial-asset-db
```

## Troubleshooting

### Container Won't Start

Check logs:

```bash
docker-compose logs app
```

### Port Already in Use

Change the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "8080:7860" # Use port 8080 instead
```

### Permission Issues

Ensure the non-root user has permissions:

```bash
# Rebuild with proper permissions
docker-compose build --no-cache
```

### Database Connection Issues

If using PostgreSQL:

1. Ensure the database service is running: `docker-compose ps`
2. Check database logs: `docker-compose logs postgres`
3. Verify connection string in environment variables

## Best Practices

1. **Security**
   - The Dockerfile uses a non-root user (appuser)
   - Change default database passwords in production
   - Use secrets management for sensitive data

2. **Performance**
   - Use `.dockerignore` to exclude unnecessary files
   - Leverage Docker layer caching
   - Use multi-stage builds for smaller images (optional)

3. **Development**
   - Mount source code volumes for live development
   - Use `docker-compose` for easier management
   - Keep development and production configs separate

4. **Production**
   - Use specific image tags (not `latest`)
   - Set resource limits (CPU, memory)
   - Configure proper logging and monitoring
   - Use health checks for auto-recovery

## Multi-Stage Build (Advanced)

For smaller production images, create a multi-stage Dockerfile:

```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "app.py"]
```

## Kubernetes Deployment (Optional)

For Kubernetes deployment, create manifests:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: financial-asset-db
spec:
  replicas: 3
  selector:
    matchLabels:
      app: financial-asset-db
  template:
    metadata:
      labels:
        app: financial-asset-db
    spec:
      containers:
        - name: app
          image: financial-asset-db:latest
          ports:
            - containerPort: 7860
          env:
            - name: GRADIO_SERVER_NAME
              value: "0.0.0.0"
```

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Gradio Docker Guide](https://gradio.app/docs/)
