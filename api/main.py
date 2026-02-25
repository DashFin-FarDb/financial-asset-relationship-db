"""FastAPI backend for the Financial Asset Relationship Database."""

import logging
import os
import re
import threading
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.data.real_data_fetcher import RealDataFetcher
from src.logic.asset_graph import AssetRelationshipGraph

from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)

logger = logging.getLogger(__name__)

# Module-level graph state
graph: Optional[AssetRelationshipGraph] = None
graph_factory: Optional[Callable[[], AssetRelationshipGraph]] = None
graph_lock = threading.Lock()


def get_graph() -> AssetRelationshipGraph:
    """
    Provide the global AssetRelationshipGraph, initialising it on first access if necessary.

    Returns:
        AssetRelationshipGraph: The global graph instance.
    """
    global graph
    if graph is None:
        with graph_lock:
            if graph is None:
                graph = _initialize_graph()
                logger.info("Graph initialized successfully")
    return graph


def set_graph(graph_instance: AssetRelationshipGraph) -> None:
    """
    Set the module-level graph to the provided AssetRelationshipGraph and clear any configured graph factory.

    Parameters:
        graph_instance (AssetRelationshipGraph): Graph instance to use as the global graph.
    """
    global graph, graph_factory
    with graph_lock:
        graph = graph_instance
        graph_factory = None


def set_graph_factory(factory: Optional[Callable[[], AssetRelationshipGraph]]) -> None:
    """Set the callable used to construct the global AssetRelationshipGraph."""
    global graph, graph_factory
    with graph_lock:
        graph_factory = factory
        graph = None


def reset_graph() -> None:
    """
    Clear the global graph and any configured factory so the graph will be reinitialised on next access.

    This removes any existing graph instance and clears the graph factory.
    """
    set_graph_factory(None)


def _initialize_graph() -> AssetRelationshipGraph:
    """Constructs and returns the asset relationship graph."""
    if graph_factory is not None:
        return graph_factory()

    cache_path = os.getenv("GRAPH_CACHE_PATH")
    use_real_data = _should_use_real_data_fetcher()

    if cache_path:
        fetcher = RealDataFetcher(cache_path=cache_path, enable_network=use_real_data)
        return fetcher.create_real_database()

    if use_real_data:
        cache_path_env = os.getenv("REAL_DATA_CACHE_PATH")
        fetcher = RealDataFetcher(cache_path=cache_path_env, enable_network=True)
        return fetcher.create_real_database()

    from src.data.sample_data import create_sample_database

    return create_sample_database()


def _should_use_real_data_fetcher() -> bool:
    """Determine if the real data fetcher should be used based on the environment
    variable."""
    flag = os.getenv("USE_REAL_DATA_FETCHER", "false")
    return flag.strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """
    Manage the application's lifespan by initialising the global graph on startup and logging shutdown.

    Initialises the global asset relationship graph before the application begins handling requests;
    if initialisation fails the exception is re-raised to abort startup. Yields control for the
    application's running lifetime and logs on shutdown.

    Parameters:
        fastapi_app (FastAPI): The FastAPI application instance.
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

# Determine environment (default to 'development' if not set)
ENV = os.getenv("ENV", "development").lower()


def validate_origin(origin_url: str) -> bool:
    # Read environment dynamically to support runtime overrides (e.g., during tests)
    """Determine whether an HTTP origin is permitted by the application's CORS rules.

    This function validates the provided origin URL against a set of rules defined
    by the application's CORS configuration. It checks for explicitly allowed
    origins, allows HTTPS origins with valid domains, permits Vercel preview
    hostnames, and allows localhost/127.0.0.1 under specific conditions based on
    the current environment.

    Args:
        origin_url (str): Origin URL to validate (for example "https://example.com" or
            "http://localhost:3000").

    Returns:
        bool: True if the origin is allowed, False otherwise.
    """
    current_env = os.getenv("ENV", "development").lower()

    # Get allowed origins from environment variable or use default
    env_allowed_origins = [o for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o]

    # If origin is in explicitly allowed list, return True
    if origin_url in env_allowed_origins and origin_url:
        return True

    # Allow HTTP localhost only in development
    if current_env == "development" and re.match(
        r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
        origin_url,
    ):
        return True
    # Allow HTTPS localhost in any environment
    if re.match(
        r"^https://(localhost|127\.0\.0\.1)(:\d+)?$",
        origin_url,
    ):
        return True
    # Allow Vercel preview deployment URLs
    # (e.g., https://project-git-branch-user.vercel.app)
    if re.match(
        r"^https://[a-zA-Z0-9\-\.]+\.vercel\.app$",
        origin_url,
    ):
        return True
    # Allow valid HTTPS URLs with proper domains
    if re.match(
        r"^https://[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
        r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
        r"\.[a-zA-Z]{2,}$",
        origin_url,
    ):
        return True
    return False


# Set allowed_origins based on environment
allowed_origins: List[str] = []
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
    additional_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    for origin in additional_origins:
        stripped_origin = origin.strip()
        if validate_origin(stripped_origin):
            allowed_origins.append(stripped_origin)
        else:
            logger.warning("Skipping invalid CORS origin: %s", stripped_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def raise_asset_not_found(asset_id: str, resource_type: str = "Asset") -> None:
    """
    Raise HTTPException for missing resources.

    Args:
        asset_id (str): ID of the asset that was not found.
        resource_type (str): Type of resource (default: "Asset").
    """
    raise HTTPException(status_code=404, detail=f"{resource_type} {asset_id} not found")


def serialize_asset(asset: Any, include_issuer: bool = False) -> Dict[str, Any]:
    """
    Serialize an Asset object to a dictionary representation.

    Args:
        asset: Asset object to serialize
        include_issuer: Whether to include issuer_id field (for detail views)

    Returns:
        Dictionary containing asset data with additional_fields
    """
    asset_dict = {
        "id": asset.id,
        "symbol": asset.symbol,
        "name": asset.name,
        "asset_class": asset.asset_class.value,
        "sector": asset.sector,
        "price": asset.price,
        "market_cap": asset.market_cap,
        "currency": asset.currency,
        "additional_fields": {},
    }

    # Define field list
    fields = [
        "pe_ratio",
        "dividend_yield",
        "earnings_per_share",
        "book_value",
        "yield_to_maturity",
        "coupon_rate",
        "maturity_date",
        "credit_rating",
        "contract_size",
        "delivery_date",
        "volatility",
        "exchange_rate",
        "country",
        "central_bank_rate",
    ]

    if include_issuer:
        fields.append("issuer_id")

    # Add asset-specific fields
    for field in fields:
        value = getattr(asset, field, None)
        if value is not None:
            asset_dict["additional_fields"][field] = value

    return asset_dict


# Pydantic models for API responses
class AssetResponse(BaseModel):
    id: str
    symbol: str
    name: str
    asset_class: str
    sector: str
    price: float
    market_cap: Optional[float] = None
    currency: str = "USD"
    additional_fields: Dict[str, Any] = {}


class RelationshipResponse(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    strength: float


class MetricsResponse(BaseModel):
    total_assets: int
    total_relationships: int
    asset_classes: Dict[str, int]
    avg_degree: float
    max_degree: int
    network_density: float
    relationship_density: float = 0.0


class VisualizationDataResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


@app.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends()
):
    # The `request` parameter is required by slowapi's limiter for dependency injection.
    """Create a JWT access token for authenticated users."""
    _ = request

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/users/me", response_model=User)
@limiter.limit("10/minute")
async def read_users_me(
    request: Request, current_user: User = Depends(get_current_active_user)
):
    # The `request` parameter is required by slowapi's limiter for dependency injection.
    """Retrieve the currently authenticated user."""
    _ = request

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
    """Health check endpoint."""
    return {"status": "healthy", "graph_initialized": True}


@app.get("/api/assets", response_model=List[AssetResponse])
async def get_assets(asset_class: Optional[str] = None, sector: Optional[str] = None):
    """Retrieve a list of assets, optionally filtered by asset class and sector.

    This function queries the graph for assets and applies optional filters  based
    on the provided `asset_class` and `sector` parameters. It iterates  through the
    assets, checking each asset against the filters, and builds  a list of
    `AssetResponse` objects using a serialization utility. If an  error occurs
    during the process, it logs the exception and raises an  HTTPException with a
    500 status code.
    """
    try:
        g = get_graph()
        assets = []

        for _, asset in g.assets.items():
            # Apply filters
            if asset_class and asset.asset_class.value != asset_class:
                continue
            if sector and asset.sector != sector:
                continue

            # Build response using serialization utility
            asset_dict = serialize_asset(asset)
            assets.append(AssetResponse(**asset_dict))
    except Exception as e:
        logger.exception("Error getting assets:")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return assets


@app.get("/api/assets/{asset_id}", response_model=AssetResponse)
async def get_asset_detail(asset_id: str):
    """Retrieve detailed information for the asset identified by `asset_id`.

    Args:
        asset_id (str): Identifier of the asset whose details are requested.

    Returns:
        AssetResponse: Detailed asset information including core fields and asset-specific attributes.

    Raises:
        HTTPException: 404 if the asset is not found.
        HTTPException: 500 for unexpected errors while retrieving the asset.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)

        asset = g.assets[asset_id]

        # Build response using serialization utility with issuer_id included
        asset_dict = serialize_asset(asset, include_issuer=True)
        return AssetResponse(**asset_dict)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting asset detail:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get(
    "/api/assets/{asset_id}/relationships", response_model=List[RelationshipResponse]
)
async def get_asset_relationships(asset_id: str):
    """List outgoing relationships for the specified asset.

    This function retrieves the outgoing relationships for a given asset identified
    by  the asset_id. It first checks if the asset exists in the graph; if not, it
    raises  an asset not found error. If the asset has relationships, it constructs
    a list of  RelationshipResponse objects containing the target asset IDs,
    relationship types,  and strengths. Any exceptions encountered during the
    process are logged, and a  500 HTTPException is raised for unexpected errors.

    Args:
        asset_id (str): Identifier of the asset whose outgoing relationships are requested.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)

        relationships = []

        # Outgoing relationships
        if asset_id in g.relationships:
            for target_id, rel_type, strength in g.relationships[asset_id]:
                relationships.append(
                    RelationshipResponse(
                        source_id=asset_id,
                        target_id=target_id,
                        relationship_type=rel_type,
                        strength=strength,
                    )
                )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting asset relationships:")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return relationships


@app.get("/api/relationships", response_model=List[RelationshipResponse])
async def get_all_relationships():
    """Retrieve all directed relationships from the asset graph."""
    try:
        g = get_graph()
        relationships = []

        for source_id, rels in g.relationships.items():
            for target_id, rel_type, strength in rels:
                relationships.append(
                    RelationshipResponse(
                        source_id=source_id,
                        target_id=target_id,
                        relationship_type=rel_type,
                        strength=strength,
                    )
                )
    except Exception as e:
        logger.exception("Error getting all relationships:")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return relationships


@app.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Return computed network metrics for the asset relationship graph.

    This function retrieves the asset relationship graph using the get_graph()
    function and calculates various metrics, including total assets and
    relationships. It builds an asset class distribution map and computes  degree
    statistics such as average and maximum degree. Finally, it returns  a
    MetricsResponse containing the computed metrics, including network density  and
    relationship density.
    """
    try:
        g = get_graph()
        metrics = g.calculate_metrics()

        # Build asset class distribution map
        asset_classes: Dict[str, int] = {}
        for asset in g.assets.values():
            key = asset.asset_class.value
            asset_classes[key] = asset_classes.get(key, 0) + 1

        # Compute degree statistics
        degrees = [len(rels) for rels in g.relationships.values()]
        avg_degree = sum(degrees) / len(degrees) if degrees else 0.0
        max_degree = max(degrees) if degrees else 0

        return MetricsResponse(
            total_assets=metrics["total_assets"],
            total_relationships=metrics["total_relationships"],
            asset_classes=asset_classes,
            avg_degree=avg_degree,
            max_degree=max_degree,
            network_density=metrics.get("relationship_density", 0.0),
            relationship_density=metrics.get("relationship_density", 0.0),
        )
    except Exception as e:
        logger.exception("Error getting metrics:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/visualization", response_model=VisualizationDataResponse)
async def get_visualization_data():
    """Retrieve graph nodes and edges for 3D visualization.

    This function generates a structured dataset containing nodes and edges
    formatted for rendering in a frontend application. It computes 3D coordinates
    for each node using a Fibonacci lattice distribution, assigns colors based on
    asset classes, and sizes proportional to the node's degree in the graph.  The
    edges represent relationships between the nodes, capturing their  interactions
    and strengths.
    """
    import math

    # Color map for asset classes
    _ASSET_CLASS_COLORS: Dict[str, str] = {
        "Equity": "#4e79a7",
        "FixedIncome": "#f28e2b",
        "Commodity": "#e15759",
        "Currency": "#76b7b2",
        "Cryptocurrency": "#59a14f",
        "RealEstate": "#edc948",
        "Alternative": "#b07aa1",
    }
    _DEFAULT_COLOR = "#9c755f"

    try:
        g = get_graph()

        asset_ids = list(g.assets.keys())
        n = len(asset_ids)

        # Compute degree for each node (used for size scaling)
        degree: Dict[str, int] = {aid: 0 for aid in asset_ids}
        for source_id, rels in g.relationships.items():
            degree[source_id] = degree.get(source_id, 0) + len(rels)

        # Distribute nodes evenly on a sphere using the Fibonacci lattice
        nodes = []
        for idx, asset_id in enumerate(asset_ids):
            asset = g.assets[asset_id]
            if n > 1:
                golden = (1 + math.sqrt(5)) / 2
                theta = math.acos(1 - 2 * (idx + 0.5) / n)
                phi = 2 * math.pi * idx / golden
                x = math.sin(theta) * math.cos(phi)
                y = math.sin(theta) * math.sin(phi)
                z = math.cos(theta)
            else:
                x, y, z = 0.0, 0.0, 0.0

            asset_class_val = asset.asset_class.value
            color = _ASSET_CLASS_COLORS.get(asset_class_val, _DEFAULT_COLOR)
            size = max(5, min(20, 5 + degree.get(asset_id, 0) * 2))

            nodes.append(
                {
                    "id": asset_id,
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_class": asset_class_val,
                    "x": round(x, 6),
                    "y": round(y, 6),
                    "z": round(z, 6),
                    "color": color,
                    "size": size,
                }
            )

        edges = []
        for source_id, rels in g.relationships.items():
            for target_id, rel_type, strength in rels:
                edges.append(
                    {
                        "source": source_id,
                        "target": target_id,
                        "relationship_type": rel_type,
                        "strength": strength,
                    }
                )

        return VisualizationDataResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.exception("Error getting visualization data:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/asset-classes")
async def get_asset_classes():
    """Return distinct sorted asset class values from the graph."""
    try:
        g = get_graph()
        classes = sorted({asset.asset_class.value for asset in g.assets.values()})
        return {"asset_classes": classes}
    except Exception as e:
        logger.exception("Error getting asset classes:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sectors")
async def get_sectors():
    """Return distinct sorted sector values from the graph."""
    try:
        g = get_graph()
        sectors = sorted({asset.sector for asset in g.assets.values() if asset.sector})
        return {"sectors": sectors}
    except Exception as e:
        logger.exception("Error getting sectors:")
        raise HTTPException(status_code=500, detail=str(e)) from e
