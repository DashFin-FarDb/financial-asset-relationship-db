# Security Best Practices

This document outlines security considerations and best practices for the Financial Asset Relationship Database.

## Current Security Status

### ✅ Implemented Security Measures

1. **Code Scanning**
   - CodeQL security scanning (0 alerts)
   - Dependency review on pull requests
   - Trivy Docker image scanning

2. **Input Validation**
   - Price validation (non-negative)
   - Currency code validation (3-letter ISO)
   - Impact score validation (-1 to 1)
   - Date format validation (ISO 8601)

3. **Docker Security**
   - Non-root user (appuser)
   - Minimal base image (Python 3.11-slim)
   - No hardcoded secrets
   - Health checks configured

4. **Dependency Management**
   - Requirements pinned with minimum versions
   - Regular security scanning in CI/CD

## Security Checklist

### Before Production Deployment

- [ ] Change all default passwords
- [ ] Enable HTTPS/TLS
- [ ] Set up API authentication
- [ ] Configure rate limiting
- [ ] Enable CORS with specific origins
- [ ] Set up logging and monitoring
- [ ] Configure backup and recovery
- [ ] Set up secrets management
- [ ] Enable audit logging
- [ ] Configure network policies

### For API Endpoints (Future)

- [ ] Implement JWT authentication
- [ ] Add request validation
- [ ] Rate limit per user/IP
- [ ] Implement CSRF protection
- [ ] Add request signing
- [ ] Enable API versioning
- [ ] Set up WAF (Web Application Firewall)

### For Database (When Added)

- [ ] Use connection pooling
- [ ] Enable encryption at rest
- [ ] Enable encryption in transit
- [ ] Set up user roles and permissions
- [ ] Enable audit logging
- [ ] Regular backups configured
- [ ] SQL injection prevention (use parameterized queries)

## Security Recommendations

### 1. Authentication & Authorization

#### JWT Implementation (for APIs)

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPBearer = Depends(security)):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
```

#### Role-Based Access Control (RBAC)

```python
from enum import Enum

class Role(Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"

def require_role(required_role: Role):
    def decorator(func):
        def wrapper(*args, **kwargs):
            user_role = get_current_user_role()
            if user_role.value < required_role.value:
                raise HTTPException(status_code=403)
            return func(*args, **kwargs)
        return wrapper
    return decorator

@require_role(Role.ADMIN)
def delete_asset(asset_id: str):
    pass
```

### 2. Input Sanitization

#### For User-Generated Content

```python
import bleach
from html import escape

def sanitize_html(content: str) -> str:
    """Sanitize HTML content to prevent XSS."""
    allowed_tags = ['p', 'br', 'strong', 'em', 'u']
    return bleach.clean(content, tags=allowed_tags, strip=True)

def sanitize_text(text: str, max_length: int = 1000) -> str:
    """Sanitize plain text input."""
    # Escape HTML
    text = escape(text)
    # Limit length
    text = text[:max_length]
    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    return text.strip()
```

#### For SQL Queries (when adding database)

```python
from sqlalchemy import text

# BAD - SQL injection vulnerability
query = f"SELECT * FROM assets WHERE id = '{asset_id}'"

# GOOD - Use parameterized queries
query = text("SELECT * FROM assets WHERE id = :asset_id")
result = session.execute(query, {"asset_id": asset_id})
```

### 3. Secrets Management

#### Environment Variables

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from .env file (development only)
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
SECRET_KEY = os.getenv('SECRET_KEY')
API_KEY = os.getenv('API_KEY')

if not all([DATABASE_URL, SECRET_KEY, API_KEY]):
    raise ValueError("Missing required environment variables")
```

#### Using Secret Managers (Production)

```python
# AWS Secrets Manager
import boto3
import json

def get_secret(secret_name: str) -> dict:
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Azure Key Vault
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://myvault.vault.azure.net/", credential=credential)
secret = client.get_secret("database-url").value
```

### 4. Rate Limiting

#### Simple Rate Limiter

```python
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import time
from collections import defaultdict
from threading import Lock

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        self.lock = Lock()

    def is_allowed(self, client_id: str) -> bool:
        with self.lock:
            now = time.time()
            minute_ago = now - 60

            # Clean old requests
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if req_time > minute_ago
            ]

            # Check limit
            if len(self.requests[client_id]) >= self.requests_per_minute:
                return False

            # Add current request
            self.requests[client_id].append(now)
            return True

rate_limiter = RateLimiter(requests_per_minute=60)

async def rate_limit_middleware(request: Request, call_next):
    client_id = request.client.host
    if not rate_limiter.is_allowed(client_id):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests"}
        )
    return await call_next(request)
```

### 5. HTTPS/TLS Configuration

#### For Production Deployment

```python
# Use SSL certificates
import ssl

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain('cert.pem', 'key.pem')

# For Gradio
interface.launch(
    server_name="0.0.0.0",
    server_port=443,
    ssl_keyfile="key.pem",
    ssl_certfile="cert.pem"
)
```

#### Let's Encrypt with Certbot

```bash
# Install certbot
sudo apt-get install certbot

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com

# Certificates will be in /etc/letsencrypt/live/yourdomain.com/
```

### 6. CORS Configuration

#### Secure CORS Setup

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://app.yourdomain.com"
    ],  # Specific origins only, not "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only needed methods
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,
)
```

### 7. Logging Security Events

#### Security Event Logger

```python
import logging
import json
from datetime import datetime

security_logger = logging.getLogger('security')
security_logger.setLevel(logging.INFO)

def log_security_event(event_type: str, user_id: str = None, **kwargs):
    """Log security-relevant events."""
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        **kwargs
    }
    security_logger.info(json.dumps(event))

# Usage
log_security_event("login_attempt", user_id="user123", success=True)
log_security_event("unauthorized_access", ip="192.168.1.1", path="/admin")
```

### 8. Error Handling

#### Secure Error Messages

```python
# BAD - Exposes internal details
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}  # Exposes stack trace
    )

# GOOD - Generic message, log details
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
```

### 9. Docker Security

#### Security Best Practices

```dockerfile
# Use specific version, not latest
FROM python:3.11-slim

# Run as non-root
RUN useradd -m -u 1000 appuser
USER appuser

# Don't copy unnecessary files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Use health checks
HEALTHCHECK --interval=30s --timeout=10s \
  CMD python -c "import requests; requests.get('http://localhost:7860')"

# Set security options
LABEL security.no-new-privileges=true
```

#### Docker Compose Security

```yaml
services:
  app:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

### 10. Regular Security Audits

#### Automated Scanning

```bash
# Python dependencies
pip install safety
safety check

# Code security
pip install bandit
bandit -r src/

# Docker images
docker scan financial-asset-db:latest

# Secrets in code
pip install detect-secrets
detect-secrets scan
```

#### Manual Reviews

- Review access logs regularly
- Check for suspicious patterns
- Update dependencies monthly
- Review and rotate credentials quarterly
- Conduct penetration testing annually

## Incident Response Plan

### If Security Issue Discovered

1. **Assess Impact**
   - Identify affected systems
   - Determine data exposure
   - Evaluate severity

2. **Contain**
   - Isolate affected systems
   - Revoke compromised credentials
   - Block suspicious IPs

3. **Investigate**
   - Review logs
   - Identify root cause
   - Document timeline

4. **Remediate**
   - Apply patches
   - Update configurations
   - Rotate credentials

5. **Notify**
   - Inform affected users
   - Report to authorities if required
   - Document lessons learned

## Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

## Contact

For security issues, contact: mohavro@users.noreply.github.com

**Never** publish security vulnerabilities in public issues. Use responsible disclosure.

---

**Last Updated:** October 30, 2025
**Version:** 1.0
**Author:** GitHub Copilot Code Agent
