# Comprehensive test coverage available in tests/unit/test_api_main.py
"""FastAPI backend for Financial Asset Relationship Database"""

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
from src.models.financial_models import AssetClass

from .auth import Token, User, authenticate_user, create_access_token, get_current_active_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Authentication settings
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Global graph instance with thread-safe initialization and configurable factory
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
    """
    Set the callable used to construct the global AssetRelationshipGraph on demand.

    If `factory` is a callable it will be used to build the graph the next time `get_graph()` is called. Passing `None` clears any configured factory. In all cases the current global graph instance is cleared so a new graph will be created on next access; this operation is performed in a thread-safe manner.

    Parameters:
        factory (Optional[Callable[[], AssetRelationshipGraph]]): A zero-argument callable that returns an `AssetRelationshipGraph`, or `None` to remove the factory and force recreation from defaults.
    """
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
    """
    Construct the asset relationship graph using the configured factory or environment-backed data sources.

    If a `graph_factory` is configured it is invoked. Otherwise, if `GRAPH_CACHE_PATH` is set a real-data graph is created (network access enabled when `USE_REAL_DATA_FETCHER` indicates real data should be used). If `GRAPH_CACHE_PATH` is not set but `USE_REAL_DATA_FETCHER` is true, `REAL_DATA_CACHE_PATH` is consulted to create a real-data graph. If neither real-data path nor real-data mode is available, a sample database graph is returned.

    Returns:
        AssetRelationshipGraph: The initialized graph instance.
    """
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
    """
    Decides whether the application should use the real data fetcher based on the `USE_REAL_DATA_FETCHER` environment variable.

    Returns:
        `True` if `USE_REAL_DATA_FETCHER` is set to a truthy value (`1`, `true`, `yes`, `on`), `False` otherwise.
    """
    flag = os.getenv("USE_REAL_DATA_FETCHER", "false")
    return flag.strip().lower() in {"1", "true", "yes", "on"}


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


@app.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Create a JWT access token for a user authenticated with a username and password.

    Parameters:
        form_data (OAuth2PasswordRequestForm): Client-submitted credentials (`username` and `password`).

    Returns:
        dict: Mapping with `access_token` (JWT string) and `token_type` set to `'bearer'`.
    """
    # The `request` parameter is required by slowapi's limiter for dependency injection.
    _ = request

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/users/me", response_model=User)
@limiter.limit("10/minute")
async def read_users_me(request: Request, current_user: User = Depends(get_current_active_user)):
    """
    Retrieve the currently authenticated user.

    Parameters:
        request (Request): Included for slowapi limiter dependency injection; unused by the function.
        current_user (User): Active user injected by the authentication dependency.

    Returns:
        The authenticated user.
    """

    # The `request` parameter is required by slowapi's limiter for dependency injection.
    _ = request

    return current_user


def validate_origin(origin: str) -> bool:
    """
    Determine whether an HTTP origin is permitted by the application's CORS rules.

    Allows explicitly configured origins, HTTPS origins with a valid domain, Vercel preview hostnames, HTTPS localhost/127.0.0.1 in any environment, and HTTP localhost/127.0.0.1 when ENV is "development".

    Parameters:
        origin (str): Origin URL to validate (for example "https://example.com" or "http://localhost:3000").

    Returns:
        True if the origin is allowed, False otherwise.
    """
    # Read environment dynamically to support runtime overrides (e.g., during tests)
    current_env = os.getenv("ENV", "development").lower()

    # Get allowed origins from environment variable or use default
    allowed_origins = [origin for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin]

    # If origin is in explicitly allowed list, return True
    if origin in allowed_origins and origin:
        return True

    # Allow HTTP localhost only in development
    if current_env == "development" and re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", origin):
        return True
    # Allow HTTPS localhost in any environment
    if re.match(r"^https://(localhost|127\.0\.0\.1)(:\d+)?$", origin):
        return True
    # Allow Vercel preview deployment URLs (e.g., https://project-git-branch-user.vercel.app)
    if re.match(r"^https://[a-zA-Z0-9\-\.]+\.vercel\.app$", origin):
        return True
    # Allow valid HTTPS URLs with proper domains
    if re.match(
        r"^https://[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$",
        origin,
    ):
        return True
    return False


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


@app.get("/")
async def root():
    """
    Provide basic API metadata and a listing of available endpoints.

    Returns:
        Dict[str, Union[str, Dict[str, str]]]: A mapping containing:
            - "message": short API description string.
            - "version": API version string.
            - "endpoints": dict mapping endpoint keys to their URL paths (e.g., "assets": "/api/assets").
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
    """Health check endpoint"""
    return {"status": "healthy", "graph_initialized": True}


@app.get("/api/assets", response_model=List[AssetResponse])
async def get_assets(asset_class: Optional[str] = None, sector: Optional[str] = None):
    """
    List assets, optionally filtered by asset class and sector.

    Parameters:
        asset_class (Optional[str]): Filter to include only assets whose `asset_class.value` equals this string.
        sector (Optional[str]): Filter to include only assets whose `sector` equals this string.

    Returns:
        List[AssetResponse]: AssetResponse objects matching the filters. Each object's `additional_fields` contains any non-null, asset-type-specific attributes as defined in the respective asset model classes.
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
    """
    Retrieve detailed information for the asset identified by `asset_id`.

    Parameters:
        asset_id (str): Identifier of the asset whose details are requested.

    Returns:
        AssetResponse: Detailed asset information as defined in the AssetResponse model, including core fields and an `additional_fields` map containing any asset-specific attributes that are present and non-null.

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


@app.get("/api/assets/{asset_id}/relationships", response_model=List[RelationshipResponse])
async def get_asset_relationships(asset_id: str):
    """
    List outgoing relationships for the specified asset.

    Parameters:
        asset_id (str): Identifier of the asset whose outgoing relationships are requested.

    Returns:
        List[RelationshipResponse]: Outgoing relationship records for the asset (each with source_id, target_id, relationship_type, and strength).

    Raises:
        HTTPException: 404 if the asset is not found; 500 for unexpected errors.
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
                        source_id=asset_id, target_id=target_id, relationship_type=rel_type, strength=strength
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
    """
    List all directed relationships in the initialized asset graph.

    Returns:
        List[RelationshipResponse]: List of relationships where each item contains `source_id`, `target_id`, `relationship_type`, and `strength`.
    """
    try:
        g = get_graph()
        relationships = []

        for source_id, rels in g.relationships.items():
            for target_id, rel_type, strength in rels:
                relationships.append(
                    RelationshipResponse(
                        source_id=source_id, target_id=target_id, relationship_type=rel_type, strength=strength
                    )
                )
    except Exception as e:
        logger.exception("Error getting relationships:")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return relationships


@app.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Aggregate network metrics and counts of assets by asset class.

    Returns:
        MetricsResponse: Aggregated metrics including:
            - total_assets: total number of assets.
            - total_relationships: total number of directed relationships.
            - asset_classes: dict mapping asset class name (str) to asset count (int).
            - avg_degree: average node degree (float).
            - max_degree: maximum node degree (int).
            - network_density: network density (float).
            - relationship_density: relationship density (float).

    Raises:
        HTTPException: with status code 500 if metrics cannot be obtained.
    """
    try:
        g = get_graph()
        metrics = g.calculate_metrics()

        # Count assets by class
        asset_classes = {}
        for asset in g.assets.values():
            class_name = asset.asset_class.value
            asset_classes[class_name] = asset_classes.get(class_name, 0) + 1

        return MetricsResponse(
            total_assets=metrics.get("total_assets", 0),
            total_relationships=metrics.get("total_relationships", 0),
            asset_classes=asset_classes,
            avg_degree=metrics.get("avg_degree", 0.0),
            max_degree=metrics.get("max_degree", 0),
            network_density=metrics.get("network_density", 0.0),
            relationship_density=metrics.get("relationship_density", 0.0),
        )
    except Exception as e:
        logger.exception("Error getting metrics:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/visualization", response_model=VisualizationDataResponse)
async def get_visualization_data():
    """
    Provide nodes and edges prepared for 3D visualization of the asset graph.

    Builds a list of node dictionaries (each with id, name, symbol, asset_class, x, y, z, color, size) and a list of edge dictionaries (each with source, target, relationship_type, strength) suitable for the API response.

    Returns:
        VisualizationDataResponse: An object with `nodes` (list of node dicts) and `edges` (list of edge dicts).

    Raises:
        HTTPException: If visualization data cannot be retrieved or processed; results in a 500 status with the error detail.
    """
    try:
        g = get_graph()
        # get_3d_visualization_data returns: (positions, asset_ids, asset_colors, asset_text, (edges_x, edges_y, edges_z)), but edge coordinates are not used in this endpoint
        positions, asset_ids, asset_colors, _ = g.get_3d_visualization_data()[:4]

        nodes = []
        for i, asset_id in enumerate(asset_ids):
            asset = g.assets[asset_id]
            nodes.append(
                {
                    "id": asset_id,
                    "name": asset.name,
                    "symbol": asset.symbol,
                    "asset_class": asset.asset_class.value,
                    "x": float(positions[i, 0]),
                    "y": float(positions[i, 1]),
                    "z": float(positions[i, 2]),
                    "color": asset_colors[i],
                    "size": 5,
                }
            )

        edges = []
        # Build edges directly from graph.relationships to avoid rebuilding from intermediate data structures
        # Only include edges where both source and target are in the asset_ids list
        asset_id_set = set(asset_ids)
        for source_id in g.relationships:
            if source_id not in asset_id_set:
                continue
            for target_id, rel_type, strength in g.relationships[source_id]:
                if target_id in asset_id_set:
                    edges.append(
                        {
                            "source": source_id,
                            "target": target_id,
                            "relationship_type": rel_type,
                            "strength": float(strength),
                        }
                    )

        return VisualizationDataResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.exception("Error getting visualization data:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/asset-classes")
async def get_asset_classes():
    """
    List available asset classes.

    Returns:
        Dict[str, List[str]]: A mapping with key "asset_classes" whose value is a list of asset class string values.
    """
    return {"asset_classes": [ac.value for ac in AssetClass]}


@app.get("/api/sectors")
async def get_sectors():
    """
    List unique sector names present in the global asset graph in sorted order.

    Returns:
        Dict[str, List[str]]: Mapping with key "sectors" to a sorted list of unique sector names.

    Raises:
        HTTPException: Raised with status code 500 if an unexpected error occurs while retrieving sectors.
    """
    try:
        g = get_graph()
        sectors = set()
        for asset in g.assets.values():
            if asset.sector:
                sectors.add(asset.sector)
        return {"sectors": sorted(list(sectors))}
    except Exception as e:
        logger.exception("Error getting sectors:")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn
    from mangum import Mangum

    # For Vercel Serverless deployment
    handler = Mangum(app)

    # For local development using uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
