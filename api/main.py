# Comprehensive test coverage available in tests/unit/test_api_main.py
"""FastAPI backend for Financial Asset Relationship Database"""

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

import api.graph_lifecycle as _graph_lifecycle

# Import from new modules
from api.cors_utils import validate_origin
from api.graph_lifecycle import get_graph, reset_graph, set_graph, set_graph_factory
from api.models import (
    AssetResponse,
    MetricsResponse,
    RelationshipResponse,
    VisualizationDataResponse,
)
from api.routers import assets, graph

from .auth import (
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Authentication settings
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Export public API for backward compatibility
__all__ = [
    "app",
    "get_graph",
    "set_graph",
    "set_graph_factory",
    "reset_graph",
    "validate_origin",
    "AssetResponse",
    "MetricsResponse",
    "RelationshipResponse",
    "VisualizationDataResponse",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the application's lifespan by initialising the global graph on startup and logging shutdown.

    Initialises the global asset relationship graph before the application begins handling requests; if initialisation fails the exception is re-raised to abort startup. Yields control for the application's running lifetime and logs on shutdown.

    Parameters:
        app (FastAPI): The FastAPI application instance.
    """
    # Startup
    try:
        get_graph()
        logger.info("Application startup complete - graph initialized")
    except Exception:
        logger.exception("Failed to initialize graph during startup")
        raise

    yield

    # Shutdown (cleanup if needed)
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

# Add rate limiting exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS for Next.js frontend
# Note: Update allowed origins for production deployment

# Determine environment (default to 'development' if not set)
ENV = os.getenv("ENV", "development").lower()

# Set allowed_origins based on environment
allowed_origins = []
if ENV == "development":
    allowed_origins.extend(
        [
            "http://localhost:3000",
            "http://localhost:7860",
            "https://localhost:3000",
            "https://localhost:7860",
        ]
    )
else:
    # In production, only allow HTTPS localhost (if needed for testing)
    allowed_origins.extend(
        [
            "https://localhost:3000",
            "https://localhost:7860",
        ]
    )

# Add production origins from environment variable if set
if os.getenv("ALLOWED_ORIGINS"):
    additional_origins = os.getenv("ALLOWED_ORIGINS").split(",")
    for origin in additional_origins:
        stripped_origin = origin.strip()
        if validate_origin(stripped_origin):
            allowed_origins.append(stripped_origin)
        else:
            logger.warning(f"Skipping invalid CORS origin: {stripped_origin}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(assets.router)
app.include_router(graph.router)


@app.post("/token", response_model=Token)
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    # The `request` parameter is required by slowapi's limiter for dependency injection.
    # The `request` parameter is required by slowapi's limiter for dependency injection.
    _ = request

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning("Authentication failed for user: %s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    logger.info("Authentication successful for user: %s", user.username)
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/users/me", response_model=User)
@limiter.limit("10/minute")
async def read_users_me(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    # The `request` parameter is required by slowapi's limiter for dependency injection.
    # The `request` parameter is required by slowapi's limiter for dependency injection.
    _ = request

    return current_user


@app.get("/")
async def root():
    """
    Provide basic API metadata and a listing of available endpoints.

    Returns:
        Dict[str, Union[str, Dict[str, str]]]: A mapping containing:
            - "message": short API description string.
            - "version": API version string.
            - "endpoints": dict mapping endpoint keys to their URL paths
              (e.g., "assets": "/api/assets").
    """
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
    """Health check endpoint."""
    return {
        "status": "healthy",
        "graph_initialized": _graph_lifecycle.graph is not None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
