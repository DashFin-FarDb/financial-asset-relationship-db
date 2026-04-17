"""FastAPI backend for the Financial Asset Relationship Database.

This module assembles the FastAPI application by combining CORS utilities,
graph lifecycle management, authentication, and API routers.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.auth import (ACCESS_TOKEN_EXPIRE_MINUTES, Token, User, authenticate_user, create_access_token,
                      get_current_active_user)
from api.cors_utils import validate_origin
from api.graph_lifecycle import get_graph, reset_graph, set_graph, set_graph_factory
from api.models import AssetResponse, MetricsResponse, RelationshipResponse, VisualizationDataResponse
from api.routers import assets, graph

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """
    Ensure the shared asset relationship graph is initialized before application startup.

    If graph initialization fails, the original exception is re-raised to abort application startup.
    Yields control to FastAPI's lifespan manager for the running application; on shutdown the function logs application shutdown.

    Raises:
        Exception: Propagates any exception raised during graph initialization.
    """
    try:
        get_graph()
        logger.info("Application startup complete - graph initialized")
    except Exception:
        logger.exception("Failed to initialize graph during startup")
        raise

    yield

    logger.info("Application shutdown")


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app with lifespan handler
app = FastAPI(
    title="Financial Asset Relationship API",
    description="REST API for Financial Asset Relationship Database",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Build allowed origins list based on environment
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:7860",
    "https://localhost:3000",
    "https://localhost:7860",
]

# Add origins from ALLOWED_ORIGINS environment variable if set
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    for origin in allowed_origins_env.split(","):
        origin = origin.strip()
        if origin and origin not in allowed_origins:
            allowed_origins.append(origin)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include routers
app.include_router(assets.router)
app.include_router(graph.router)


# Auth endpoints
@app.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request,  # Required by slowapi for rate-limit key extraction.
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """Create a JWT access token for authenticated users."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


@app.get("/api/users/me", response_model=User)
@limiter.limit("10/minute")
async def read_users_me(
    request: Request,  # Required by slowapi for rate-limit key extraction.
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Retrieve the currently authenticated user."""
    return current_user


@app.get("/")
async def root():
    """Return basic API metadata and a listing of available endpoints."""
    return {
        "message": "Financial Asset Relationship API",
        "version": "1.0.0",
        "endpoints": {
            "assets": "/api/assets",
            "asset_detail": "/api/assets/{asset_id}",
            "relationships": "/api/relationships",
            "metrics": "/api/metrics",
            "visualization": "/api/visualization",
        },
    }


@app.get("/api/health")
async def health_check():
    """Return service health status."""
    return {"status": "healthy", "graph_initialized": True}


# Re-export for backward compatibility
__all__ = [
    "app",
    "validate_origin",
    "get_graph",
    "set_graph",
    "set_graph_factory",
    "reset_graph",
    "AssetResponse",
    "MetricsResponse",
    "RelationshipResponse",
    "VisualizationDataResponse",
]
