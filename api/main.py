"""FastAPI backend for the Financial Asset Relationship Database."""

from __future__ import annotations

import logging
import math
import os
import re
import threading
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, Callable, Dict, List, NoReturn, Optional
from urllib.parse import urlparse

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

from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)

logger = logging.getLogger(__name__)

# Type alias for the graph factory callable
GraphFactory = Callable[[], AssetRelationshipGraph]

# Module-level graph state
graph: Optional[AssetRelationshipGraph] = None
graph_factory: Optional[GraphFactory] = None
graph_lock = threading.Lock()

# Asset class colour mapping for 3-D visualisation
_ASSET_CLASS_COLORS: Dict[str, str] = {
    "Equity": "#4e79a7",
    "Fixed Income": "#f28e2b",
    "Commodity": "#e15759",
    "Currency": "#76b7b2",
    "Cryptocurrency": "#59a14f",
    "RealEstate": "#edc948",
    "Alternative": "#b07aa1",
}
_DEFAULT_COLOR = "#9c755f"


def get_graph() -> AssetRelationshipGraph:
    """
    Provide the global AssetRelationshipGraph, initialising it on
    first access if necessary.

    Returns:
        AssetRelationshipGraph: The global graph instance.
    """
    if not hasattr(get_graph, "graph"):
        with graph_lock:
            if not hasattr(get_graph, "graph"):
                get_graph.graph = _initialize_graph()
                logger.info("Graph initialized successfully")
    return get_graph.graph


def set_graph(graph_instance: AssetRelationshipGraph) -> tuple[AssetRelationshipGraph, None]:
    """
    Set the module-level AssetRelationshipGraph instance and disable any
    configured graph factory.

    Parameters:
        graph_instance: The AssetRelationshipGraph to use as the global graph.
    """
    with graph_lock:
        return graph_instance, None


def set_graph_factory(
    factory: Optional[GraphFactory],
    graph_lock: threading.Lock,
    current_graph_factory: Optional[GraphFactory],
    current_graph: Optional[AssetRelationshipGraph],
) -> tuple[Optional[GraphFactory], Optional[AssetRelationshipGraph]]:
    """
    Configure the factory used to lazily construct the AssetRelationshipGraph.

    Setting a factory replaces any existing factory and clears the current
    graph so that the next access will create a new graph via the
    provided factory. Passing `None` disables the factory and causes the
    graph to be reinitialized using the default strategy on next access.

    Parameters:
        factory (Optional[GraphFactory]): A zero-argument factory that returns
            an AssetRelationshipGraph, or `None` to clear the factory.
        graph_lock (threading.Lock): Lock for synchronizing graph operations.
        current_graph_factory (Optional[GraphFactory]): The current graph factory.
        current_graph (Optional[AssetRelationshipGraph]): The current graph.
    Returns:
        Tuple containing the updated graph_factory and graph.
    """
    with graph_lock:
        current_graph_factory = factory
        current_graph = None
    return current_graph_factory, current_graph


def reset_graph() -> None:
    """Clear the global graph and factory so the graph is reinitialised on next
    access."""
    set_graph_factory(None)


def _initialize_graph() -> AssetRelationshipGraph:
    """
    Builds and returns the AssetRelationshipGraph using the configured data source.

    Prefers a configured graph factory when present. Otherwise, if the
    environment variable GRAPH_CACHE_PATH is set, it constructs a RealDataFetcher
    (network enabled when USE_REAL_DATA_FETCHER is truthy) and builds the graph
    from that cache. If GRAPH_CACHE_PATH is not set but USE_REAL_DATA_FETCHER is
    truthy, it constructs a RealDataFetcher using REAL_DATA_CACHE_PATH with
    network enabled. If neither path applies, a sample in-memory database is
    created.

    Returns:
        AssetRelationshipGraph: The constructed asset-relationship graph.
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
    Determine whether the application should use the real data fetcher based on
    environment configuration.

    Checks the `USE_REAL_DATA_FETCHER` environment variable for a truthy value.

    Returns:
        `True` if `USE_REAL_DATA_FETCHER` (case-insensitive, trimmed) is one of:
        "1", "true", "yes", "on"; `False` otherwise.
    """
    flag = os.getenv("USE_REAL_DATA_FETCHER", "false")
    return flag.strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """
    Initialize the global asset relationship graph during application startup
    and log lifecycle events.

    Initializes the singleton graph before the application begins handling
    requests; if initialization fails the original exception is re-raised to
    abort startup. Yields control for the application's running lifespan and
    logs a shutdown message when the lifespan ends.
    """
    try:
        get_graph()
        logger.info("Application startup complete - graph initialized")
    except Exception:
        logger.exception("Failed to initialize graph during startup")
        raise

    yield

    logger.info("Application shutdown")


# Initialise rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialise FastAPI app with lifespan handler
app = FastAPI(
    title="Financial Asset Relationship API",
    description="REST API for Financial Asset Relationship Database",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Determine environment (default to 'development' if not set)
ENV = os.getenv("ENV", "development").lower()


def validate_origin(origin_url: str) -> bool:
    """
    Determine whether an HTTP origin is permitted by the
    application's CORS rules.

    Re-reads the `ENV` environment variable on each call to allow runtime
    overrides.

    The check allows:
    - explicit origins listed in `ALLOWED_ORIGINS`,
    - HTTP localhost/127.0.0.1 when running in `development`,
    - HTTPS localhost/127.0.0.1 in any environment,
    - Vercel preview hostnames (e.g., `*.vercel.app`),
    - valid HTTPS origins with well-formed domain names (including IDN support).

    Parameters:
        origin_url (str): Origin URL to validate (e.g. "https://example.com",
            "http://localhost:3000", or "https://münchen.de").

    Returns:
        bool: `True` if the origin is allowed, `False` otherwise.
    """
    # Re-read environment dynamically to support runtime overrides
    # (e.g., during tests).
    current_env = os.getenv("ENV", "development").lower()

    env_allowed_origins = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
        if o.strip()
    ]
    if origin_url and origin_url in env_allowed_origins:
        return True

    # Allow HTTP localhost only in development
    if current_env == "development" and re.match(
        r"^http://(localhost|127\\.0\\.0\\.1)(:\\d+)?$",
        origin_url,
    ):
        return True

    # Allow HTTPS localhost in any environment
    if re.match(r"^https://(localhost|127\\.0\\.0\\.1)(:\\d+)?$", origin_url):
        return True

    # Allow Vercel preview deployment URLs (e.g.
    # https://project-git-branch-user.vercel.app)
    if re.match(r"^https://[a-zA-Z0-9\\-\\.]+\\.vercel\\.app$", origin_url):
        return True

    # Allow valid HTTPS URLs with proper domains (including IDN support)
    if origin_url.startswith("https://"):
        try:
            parsed = urlparse(origin_url)
            parsed = urlparse(origin_url)
            if parsed.path or parsed.params or parsed.query or parsed.fragment or parsed.username or parsed.password:
                return False
            hostname = parsed.hostname
            if hostname:
                # Convert IDN (internationalized domain names) to ASCII using IDNA encoding
                ascii_hostname = hostname.encode("idna").decode("ascii")
                # Reconstruct URL with ASCII hostname for regex validation
                # Port is included if present (urlparse already validates port number)
                port_suffix = f":{parsed.port}" if parsed.port else ""
                ascii_url = f"https://{ascii_hostname}{port_suffix}"
                # Validate the ASCII version against the domain regex
                # Note: TLD pattern allows alphanumeric and hyphens to support IDNA-encoded TLDs
                if re.match(
                    r"^https://[a-zA-Z0-9]([a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])?"
                    r"(\\.[a-zA-Z0-9]([a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])?)*"
                    r"\\.[a-zA-Z0-9\\-]{2,}(:\\d+)?$",
                    ascii_url,
                ):
                    return True
        except (ValueError, AttributeError) as e:
            # Invalid hostname or IDNA encoding failed
            logger.debug("Failed to validate origin '%s': %s", origin_url, e)

    # Support IDN (Internationalized Domain Names) — encode host to ASCII and re-validate
    parsed = urlparse(origin_url)
    if parsed.scheme == "https" and parsed.netloc:
        try:
            ascii_host = parsed.hostname.encode("idna").decode("ascii")
            ascii_origin = f"https://{ascii_host}"
            if parsed.port:
                ascii_origin += f":{parsed.port}"
            if re.match(
                r"^https://[a-zA-Z0-9]"
                r"([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
                r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
                r"\.[a-zA-Z]{2,}$",
                ascii_origin,
            ):
                return True
        except (UnicodeError, AttributeError) as e:
            # If the hostname cannot be IDNA-encoded, treat the origin as invalid.
            logger.debug("Failed to IDNA-encode hostname for origin %s: %s", origin_url, e)
            return False

    return False


# Build the initial allowed origins list based on environment
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
    allowed_origins.extend(
        [
            "https://localhost:3000",
            "https://localhost:7860",
        ]
    )

# Append any additional validated origins from the ALLOWED_ORIGINS environment variable
if os.getenv("ALLOWED_ORIGINS"):
    for _origin in os.getenv("ALLOWED_ORIGINS", "").split(","):
        _origin = _origin.strip()
        if validate_origin(_origin):
            allowed_origins.append(_origin)
        else:
            logger.warning("Skipping invalid CORS origin: %s", _origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def raise_asset_not_found(asset_id: str, resource_type: str = "Asset") -> NoReturn:
    """
    Raise an HTTP 404 exception for a missing resource.

    Args:
        asset_id (str): ID of the asset that was not found.
        resource_type (str): Human-readable resource type label (default: ``"Asset"``).

    Raises:
        HTTPException: Always raised with status code 404.
    """
    raise HTTPException(status_code=404, detail=f"{resource_type} {asset_id} not found")


def serialize_asset(asset: Any, include_issuer: bool = False) -> Dict[str, Any]:
    """
    Serialize an Asset object to a dictionary representation.

    Args:
        asset: Asset object to serialize.
        include_issuer (bool): Whether to include the ``issuer_id`` field
            (useful for detail views). Defaults to ``False``.

    Returns:
        Dict[str, Any]: Dictionary containing core asset fields plus any
        non-``None`` asset-specific attributes under ``additional_fields``.
    """
    asset_dict: Dict[str, Any] = {
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

    optional_fields = [
        "pe_ratio",
        "dividend_yield",
        "earnings_per_share",
        "book_value",
        "yield_to_maturity",
        "coupon_rate",
        "maturity_date",
# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class AssetResponse(BaseModel):
    """Response model representing an asset with its basic attributes, financial metrics, and any additional metadata."""
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
    """Response model for representing a relationship between two assets, including type and strength."""
    source_id: str
    target_id: str
    relationship_type: str
    strength: float


class MetricsResponse(BaseModel):
    """Response model providing aggregated metrics about assets and their network relationships."""
    total_assets: int
    total_relationships: int
    asset_classes: Dict[str, int]
    avg_degree: float
    max_degree: int
    network_density: float
    relationship_density: float = 0.0


class VisualizationDataResponse(BaseModel):
    """Response model containing data structures for visualizing nodes and edges in a network graph."""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
        Token: An object containing the JWT `access_token`
        and `token_type` ("bearer").

    Raises:
        HTTPException: With status 401 if the provided credentials are incorrect.
    """
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
    """
    Return the currently authenticated user.

    Parameters:
        request(Request): Request object used by the rate limiter for key extraction.

    Returns:
        User: The active authenticated user.
    """
    return current_user


@app.get("/")
async def root() -> Dict[str, Any]:
    """
    Provide basic API metadata and a listing of available endpoints.

    Returns:
        info(Dict[str, Any]): A dictionary with keys "message", "version",
            and "endpoints",
            where "endpoints" maps logical names to their URL paths.
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
async def health_check() -> Dict[str, Any]:
    """
    Report service health and whether the global asset graph has been
    initialized.

    Returns:
        health(Dict[str, Any]): A dictionary with:
            - `status` (str): Overall service health status(e.g., "healthy").
            - `graph_initialized` (bool): `True` if the global asset
              relationship graph is initialized, `False` otherwise.
    """
    with graph_lock:
        graph_initialized = graph is not None
    return {"status": "healthy", "graph_initialized": graph_initialized}


@app.get("/api/assets", response_model=List[AssetResponse])
async def get_assets(
    asset_class: Optional[str] = None,
    sector: Optional[str] = None,
) -> List[AssetResponse]:
    """
    Retrieve assets optionally filtered by asset class and sector.

    Parameters:
        asset_class(Optional[str]): Asset class value to filter by(e.g., "Equity").
        sector(Optional[str]): Sector name to filter by.

    Returns:
        List[AssetResponse]: Matching assets serialized for API responses.

    Raises:
        HTTPException: If an unexpected error occurs(HTTP 500).
    """
    try:
        g = get_graph()
        assets = []
        for asset in g.assets.values():
            if asset_class:
                requested = asset_class.strip().lower()
                if requested not in {
                    asset.asset_class.value.lower(),
                    asset.asset_class.name.lower(),
                }:
                    continue
            if sector and asset.sector != sector:
                continue
            assets.append(AssetResponse(**serialize_asset(asset)))
    except Exception as e:
        logger.exception("Error getting assets:")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return assets


@app.get("/api/assets/{asset_id}", response_model=AssetResponse)
async def get_asset_detail(asset_id: str) -> AssetResponse:
    """
    Retrieve detailed information for the asset identified by asset_id.

    Parameters:
        asset_id(str): Asset identifier.

    Returns:
        AssetResponse: Asset details including issuer information when available.

    Raises:
        HTTPException: 404 if the asset is not found.
        HTTPException: 500 for unexpected errors.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)
        return AssetResponse(
            **serialize_asset(
                g.assets[asset_id],
                include_issuer=True
            )
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting asset detail:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get(
    "/api/assets/{asset_id}/relationships",
    response_model=List[RelationshipResponse],
)
async def get_asset_relationships(
    asset_id: str,
) -> List[RelationshipResponse]:
    """
    Return the outgoing relationships for the specified asset.

    Returns:
        List[RelationshipResponse]: Outgoing relationships; each entry includes
            `source_id`, `target_id`, `relationship_type`, and `strength`.

    Raises:
        HTTPException: 404 if the asset with `asset_id` is not found.
        HTTPException: 500 for unexpected internal errors.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)
        relationships = [
            RelationshipResponse(
                source_id=asset_id,
                target_id=target_id,
                relationship_type=rel_type,
                strength=strength,
            )
            for target_id, rel_type, strength in g.relationships.get(asset_id, [])
        ]
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting asset relationships:")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return relationships


@app.get("/api/relationships", response_model=List[RelationshipResponse])
async def get_all_relationships() -> List[RelationshipResponse]:
    """
    Return all directed relationships present in the global asset graph.

    Returns:
        List[RelationshipResponse]: A list of relationship records.
            Each record contains `source_id`, `target_id`, `relationship_type`, and `strength`.

    Raises:
        HTTPException: Raised with status code 500 if an unexpected error occurs
            while retrieving relationships.
    """
    try:
        g = get_graph()
        return [
            RelationshipResponse(
                source_id=source_id,
                target_id=target_id,
                relationship_type=rel_type,
                strength=strength,
            )
            for source_id, rels in g.relationships.items()
            for target_id, rel_type, strength in rels
        ]
    except Exception as e:
        logger.exception("Error getting all relationships:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """
    Compute network - level metrics for the global asset relationship graph.

    Returns:
        MetricsResponse: Contains:
            - total_assets: total number of assets in the graph
            - total_relationships: total number of directed relationships
            - asset_classes: mapping from asset class name to asset count
            - avg_degree: average out - degree across nodes
            - max_degree: maximum out - degree observed
            - network_density: network density metric
            - relationship_density: relationship density metric

    Raises:
        HTTPException: with status code 500 and error detail for unexpected failures.
    """
    try:
        g = get_graph()
        metrics = g.calculate_metrics()

        asset_classes: Dict[str, int] = {}
        for asset in g.assets.values():
            key = asset.asset_class.value
            asset_classes[key] = asset_classes.get(key, 0) + 1

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
async def get_visualization_data() -> VisualizationDataResponse:
    """
    Prepare nodes and edges for 3 - D visualization of the asset graph.

    Nodes are placed on a sphere using a Fibonacci - lattice distribution.
    Nodes are colored by asset class .
    They are sized proportionally to each node's outgoing degree.
    Edges contain source, target, relationship type, and strength.

    Returns:
        VisualizationDataResponse: A response object containing `nodes` and `edges`.
        `nodes`: List of node dicts with keys `id`, `symbol`, `name`, `asset_class`, `x`, `y`, `z`, `color`, `size`.
        `edges`: List of edge dicts with keys `source`, `target`, `relationship_type`, `strength`.

    Raises:
        HTTPException: HTTP 500 if an unexpected error occurs while generating
            visualization data.
    """
    try:
        g = get_graph()
        asset_ids = list(g.assets.keys())
        n = len(asset_ids)

        # Pre-compute out-degree for each node (used for size scaling)
        degree: Dict[str, int] = {aid: 0 for aid in asset_ids}
        for source_id, rels in g.relationships.items():
            degree[source_id] = degree.get(source_id, 0) + len(rels)

        # Distribute nodes evenly on a sphere using the Fibonacci lattice
        golden = (1 + math.sqrt(5)) / 2
        nodes = []
        for idx, asset_id in enumerate(asset_ids):
            asset = g.assets[asset_id]
            if n > 1:
                theta = math.acos(1 - 2 * (idx + 0.5) / n)
                phi = 2 * math.pi * idx / golden
                x = math.sin(theta) * math.cos(phi)
                y = math.sin(theta) * math.sin(phi)
                z = math.cos(theta)
            else:
                x, y, z = 0.0, 0.0, 0.0

            asset_class_val = asset.asset_class.value
            nodes.append(
                {
                    "id": asset_id,
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_class": asset_class_val,
                    "x": round(x, 6),
                    "y": round(y, 6),
                    "z": round(z, 6),
                    "color": _ASSET_CLASS_COLORS.get(asset_class_val, _DEFAULT_COLOR),
                    "size": max(5, min(20, 5 + degree.get(asset_id, 0) * 2)),
                }
            )

        edges = [
            {
                "source": source_id,
                "target": target_id,
                "relationship_type": rel_type,
                "strength": strength,
            }
            for source_id, rels in g.relationships.items()
            for target_id, rel_type, strength in rels
        ]

        return VisualizationDataResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.exception("Error getting visualization data:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/asset-classes")
async def get_asset_classes() -> Dict[str, List[str]]:
    """
    List all asset classes in alphabetical order.

    Returns:
        Dict[str, List[str]]: A dictionary with the key "asset_classes" mapped to a
            list of asset class values (strings) sorted alphabetically.

    Raises:
        HTTPException: Raised with status code 500 if an unexpected error
            occurs while collecting asset classes.
    """
    try:
        return {"asset_classes": sorted(ac.value for ac in AssetClass)}
    except Exception as e:
        logger.exception("Error getting asset classes:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sectors")
async def get_sectors() -> Dict[str, List[str]]:
    """
    Get distinct sector names from the asset graph, sorted alphabetically.

    Returns:
        dict: A mapping with key "sectors" to a list of sector names sorted
            in ascending order.

    Raises:
        HTTPException: With status code 500 if an unexpected error occurs while
            accessing or processing the graph.
    """
    try:
        g = get_graph()
        return {"sectors": sorted({a.sector for a in g.assets.values() if a.sector})}
    except Exception as e:
        logger.exception("Error getting sectors:")
        raise HTTPException(status_code=500, detail=str(e)) from e
