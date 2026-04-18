"""FastAPI backend for the Financial Asset Relationship Database."""

from __future__ import annotations

import logging
import math
import os
import re
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, Dict, List, NoReturn, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

# pylint: disable=import-error
from slowapi import (  # type: ignore[import-not-found]
    Limiter,
    _rate_limit_exceeded_handler,
)
from slowapi.errors import RateLimitExceeded  # type: ignore[import-not-found]
from slowapi.util import get_remote_address  # type: ignore[import-not-found]

from src.config.settings import get_settings
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
from .graph_lifecycle import get_graph, reset_graph, set_graph, set_graph_factory

# pylint: enable=import-error


logger = logging.getLogger(__name__)

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


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """
    Ensure the shared asset relationship graph is initialized before application startup.

    If graph initialization fails, re-raises the original exception to abort application startup.

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

# Get settings instance for environment and CORS configuration
_settings = get_settings()
ENV = _settings.env


def _read_allowed_origins() -> List[str]:
    """
    Parse the ALLOWED_ORIGINS from settings into a list of origin strings.

    Returns:
        List[str]: A list of trimmed origin strings (e.g., "https://example.com").
    """
    return get_settings().allowed_origins


def _is_http_local_in_dev(origin_url: str, current_env: str) -> bool:
    """
    Allow HTTP localhost origins only when running in the development environment.

    Parameters:
        origin_url (str): Origin to validate (e.g., "http://localhost:3000" or "http://127.0.0.1").
        current_env (str): Current environment string; allowance occurs only when this equals "development".

    Returns:
        `true` if `origin_url` is an HTTP URL for "localhost" or "127.0.0.1" with an optional `:port` and `current_env` equals "development", `false` otherwise.
    """
    return current_env == "development" and bool(re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", origin_url))


def _is_https_local(origin_url: str) -> bool:
    """
    Determine whether an origin URL represents HTTPS localhost (either localhost or 127.0.0.1), allowing an optional port.

    Parameters:
        origin_url (str): Origin string including scheme and host, optionally with port (e.g. "https://localhost:3000").

    Returns:
        True if the origin is "https://localhost" or "https://127.0.0.1" optionally followed by ":<port>", False otherwise.
    """
    return bool(re.match(r"^https://(localhost|127\.0\.0\.1)(:\d+)?$", origin_url))


def _is_vercel_preview(origin_url: str) -> bool:
    """
    Determine whether an origin URL is a Vercel preview deployment hostname.

    Parameters:
        origin_url (str): The full origin URL to test (including scheme, e.g. "https://foo.vercel.app").

    Returns:
        bool: `True` if `origin_url` matches the pattern `https://<name>.vercel.app`, `False` otherwise.
    """
    return bool(re.match(r"^https://[a-zA-Z0-9\-\.]+\.vercel\.app$", origin_url))


def _has_forbidden_origin_parts(parsed_origin: object) -> bool:
    """
    Check if a parsed origin contains disallowed URL components.

    Parameters:
        parsed_origin (object): A URL parse result (e.g., urllib.parse.ParseResult) whose attributes will be inspected.

    Returns:
        bool: `True` if any of `path`, `params`, `query`, `fragment`, `username`, or `password` are non-empty; `False` otherwise.
    """
    return any(
        [
            getattr(parsed_origin, "path", ""),
            getattr(parsed_origin, "params", ""),
            getattr(parsed_origin, "query", ""),
            getattr(parsed_origin, "fragment", ""),
            getattr(parsed_origin, "username", None),
            getattr(parsed_origin, "password", None),
        ]
    )


def _is_valid_https_domain(origin_url: str) -> bool:
    """
    Validate that an origin URL is a secure HTTPS origin with a single hostname (internationalized domain names allowed) and an optional port.

    Rejects origins that contain path, params, query, fragment, username, or password.

    Parameters:
        origin_url (str): The origin URL to validate.

    Returns:
        True if the input starts with "https://", contains a hostname (IDN allowed), has no forbidden URL parts, and matches an allowed hostname with an optional port, False otherwise.
    """
    if not origin_url.startswith("https://"):
        return False
    try:
        parsed = urlparse(origin_url)
        if _has_forbidden_origin_parts(parsed):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        ascii_hostname = hostname.encode("idna").decode("ascii")
        port_suffix = f":{parsed.port}" if parsed.port else ""
        ascii_url = f"https://{ascii_hostname}{port_suffix}"
        return bool(
            re.match(
                r"^https://[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
                r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
                r"\.[a-zA-Z0-9\-]{2,}(:\d+)?$",
                ascii_url,
            )
        )
    except (ValueError, UnicodeError, AttributeError) as exc:
        logger.debug("Failed to validate origin '%s': %s", origin_url, exc)
        return False


def validate_origin(origin_url: str) -> bool:
    """
    Check whether an origin URL is permitted by the application's CORS policy.

    Re-reads runtime settings and permits origins that are either listed in the configured
    allowed origins, local development HTTP hosts (localhost or 127.0.0.1 when the
    environment is development), local HTTPS hosts, Vercel preview hostnames
    (https://<name>.vercel.app), or otherwise valid HTTPS hostnames (including
    internationalized domain names via IDNA).

    Parameters:
        origin_url (str): Origin URL to validate (e.g. "https://example.com",
            "http://localhost:3000", or "https://münchen.de").

    Returns:
        bool: `True` if the origin is allowed, `False` otherwise.
    """
    # Re-read settings dynamically to support runtime overrides
    # (e.g., during tests).
    settings = get_settings()
    current_env = settings.env

    env_allowed_origins = settings.allowed_origins
    if origin_url and origin_url in env_allowed_origins:
        return True

    if _is_http_local_in_dev(origin_url, current_env):
        return True

    if _is_https_local(origin_url):
        return True

    if _is_vercel_preview(origin_url):
        return True

    return _is_valid_https_domain(origin_url)


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

# Append any additional validated origins from the ALLOWED_ORIGINS setting
if _settings.allowed_origins_raw:
    for _origin in _settings.allowed_origins:
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


def raise_asset_not_found(
    asset_id: str,
    resource_type: str = "Asset",
) -> NoReturn:
    """
    Raise an HTTP 404 (Not Found) error for a missing resource.

    Parameters:
        asset_id (str): Identifier of the missing resource.
        resource_type (str): Human-readable resource label (default: "Asset").

    Raises:
        HTTPException: with status code 404 and detail message "<resource_type> <asset_id> not found".
    """
    raise HTTPException(
        status_code=404,
        detail=f"{resource_type} {asset_id} not found",
    )


def serialize_asset(
    asset: Any,
    include_issuer: bool = False,
) -> Dict[str, Any]:
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
        "credit_rating",
        "contract_size",
        "delivery_date",
        "volatility",
        "exchange_rate",
        "country",
        "central_bank_rate",
    ]

    if include_issuer:
        optional_fields.append("issuer_id")

    for field in optional_fields:
        value = getattr(asset, field, None)
        if value is not None:
            asset_dict["additional_fields"][field] = value

    return asset_dict


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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
async def root() -> Dict[str, Any]:
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
async def health_check() -> Dict[str, Any]:
    """Return service health status."""
    return {"status": "healthy", "graph_initialized": True}


@app.get("/api/assets", response_model=List[AssetResponse])
async def get_assets(
    asset_class: Optional[str] = None,
    sector: Optional[str] = None,
) -> List[AssetResponse]:
    """
    Retrieve assets filtered by exact asset class and/or sector.

    Filters apply exact string matching against asset.asset_class.value and asset.sector.

    Parameters:
        asset_class (Optional[str]): Exact asset class name to filter by (for example, "Equity").
        sector (Optional[str]): Exact sector name to filter by.

    Returns:
        List[AssetResponse]: API-formatted assets that match the provided filters.

    Raises:
        HTTPException: If an unexpected error occurs while fetching assets (status code 500).
    """
    try:
        g = get_graph()
        assets = []
        for asset in g.assets.values():
            if asset_class and asset.asset_class.value != asset_class:
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
    Retrieve detailed information for the asset with the given identifier.

    Parameters:
        asset_id (str): Identifier of the asset to retrieve.

    Returns:
        AssetResponse: Serialized asset details, including issuer identifier when available.

    Raises:
        HTTPException: 404 if the asset with `asset_id` is not found.
        HTTPException: 500 if an unexpected error occurs while retrieving the asset.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)
        return AssetResponse(
            **serialize_asset(
                g.assets[asset_id],
                include_issuer=True,
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting asset detail:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get(
    "/api/assets/{asset_id}/relationships",
    response_model=List[RelationshipResponse],
)
async def get_asset_relationships(asset_id: str) -> List[RelationshipResponse]:
    """
    Get outgoing relationships for the given asset.

    Parameters:
        asset_id (str): Asset identifier to retrieve outgoing relationships for.

    Returns:
        List[RelationshipResponse]: Outgoing relationships; each entry contains `source_id`, `target_id`, `relationship_type`, and `strength`.

    Raises:
        HTTPException: 404 if the asset is not found.
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
            for target_id, rel_type, strength in g.relationships.get(
                asset_id,
                [],
            )
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting asset relationships:")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return relationships


@app.get("/api/relationships", response_model=List[RelationshipResponse])
async def get_all_relationships() -> List[RelationshipResponse]:
    """Retrieve all directed relationships from the asset graph."""
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
    Compute metrics summarizing the asset relationship network.

    Returns:
        MetricsResponse: Aggregated statistics including:
            - total_assets: number of assets in the graph
            - total_relationships: number of directed relationships
            - asset_classes: mapping of asset class name to asset count
            - avg_degree: average out-degree across assets
            - max_degree: maximum out-degree of any asset
            - network_density: density measure of the network
            - relationship_density: same as `network_density` (provided for compatibility)

    Raises:
        HTTPException: 500 with an error message if metric computation fails.
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


def _calculate_node_degrees(g: AssetRelationshipGraph) -> Dict[str, int]:
    """
    Compute the out-degree (number of outgoing relationships) for each asset in the graph.

    Parameters:
        g (AssetRelationshipGraph): Graph to analyze.

    Returns:
        Dict[str, int]: Mapping from asset ID to its out-degree (number of outgoing relationships).
    """
    degree: Dict[str, int] = {asset_id: 0 for asset_id in g.assets.keys()}
    for source_id, rels in g.relationships.items():
        degree[source_id] = degree.get(source_id, 0) + len(rels)
    return degree


def _compute_fibonacci_position(
    idx: int,
    total_nodes: int,
    golden_ratio: float,
) -> tuple[float, float, float]:
    """
    Compute a 3D point on the unit sphere using a Fibonacci-lattice distribution.

    Parameters:
        idx (int): Zero-based index of the node within the range [0, total_nodes).
        total_nodes (int): Total number of nodes to place on the sphere.
        golden_ratio (float): Value controlling azimuthal spacing (typically the golden ratio).

    Returns:
        tuple[float, float, float]: (x, y, z) coordinates of the node on the unit sphere.
    """
    if total_nodes <= 1:
        return 0.0, 0.0, 0.0
    theta = math.acos(1 - 2 * (idx + 0.5) / total_nodes)
    phi = 2 * math.pi * idx / golden_ratio
    x = math.sin(theta) * math.cos(phi)
    y = math.sin(theta) * math.sin(phi)
    z = math.cos(theta)
    return x, y, z


def _build_visualization_nodes(
    g: AssetRelationshipGraph,
    asset_ids: List[str],
) -> List[Dict[str, Any]]:
    """
    Construct visualization node dictionaries for the given assets in the graph.

    Parameters:
        g (AssetRelationshipGraph): Graph containing assets and relationships.
        asset_ids (List[str]): Ordered list of asset IDs to include as nodes.

    Returns:
        List[Dict[str, Any]]: A list of node objects with keys:
            - id: asset ID string
            - symbol: asset symbol
            - name: asset name
            - asset_class: asset class name
            - x, y, z: 3-D coordinates for visualization (floats)
            - color: hex color string for the asset class
            - size: visual node size (integer)
    """
    degree = _calculate_node_degrees(g)
    total_nodes = len(asset_ids)
    golden_ratio = (1 + math.sqrt(5)) / 2
    nodes: List[Dict[str, Any]] = []
    for idx, asset_id in enumerate(asset_ids):
        asset = g.assets[asset_id]
        x, y, z = _compute_fibonacci_position(idx, total_nodes, golden_ratio)
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
    return nodes


def _build_visualization_edges(g: AssetRelationshipGraph) -> List[Dict[str, Any]]:
    """
    Create a list of edge dictionaries for visualization extracted from the asset relationship graph.

    Parameters:
        g (AssetRelationshipGraph): Graph whose directed relationships will be converted into visualization edges.

    Returns:
        List[dict]: Each dictionary represents a directed relationship with keys:
            `source` (source asset id),
            `target` (target asset id),
            `relationship_type` (relationship label),
            `strength` (numeric relationship strength).
    """
    return [
        {
            "source": source_id,
            "target": target_id,
            "relationship_type": rel_type,
            "strength": strength,
        }
        for source_id, rels in g.relationships.items()
        for target_id, rel_type, strength in rels
    ]


@app.get("/api/visualization", response_model=VisualizationDataResponse)
async def get_visualization_data() -> VisualizationDataResponse:
    """
    Produce visualization nodes and edges representing the current asset relationship graph.

    Returns:
        VisualizationDataResponse: Object with `nodes` (list of node dictionaries) and `edges` (list of edge dictionaries) suitable for frontend rendering.

    Raises:
        HTTPException: With status code 500 if an unexpected error occurs while constructing the visualization data.
    """
    try:
        g = get_graph()
        asset_ids = list(g.assets.keys())
        nodes = _build_visualization_nodes(g, asset_ids)
        edges = _build_visualization_edges(g)

        return VisualizationDataResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.exception("Error getting visualization data:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/asset-classes")
async def get_asset_classes() -> Dict[str, List[str]]:
    """Return all AssetClass enum values sorted alphabetically."""
    try:
        return {"asset_classes": sorted(ac.value for ac in AssetClass)}
    except Exception as e:
        logger.exception("Error getting asset classes:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sectors")
async def get_sectors() -> Dict[str, List[str]]:
    """Return distinct sorted sector values from the graph."""
    try:
        g = get_graph()
        return {"sectors": sorted({a.sector for a in g.assets.values() if a.sector})}
    except Exception as e:
        logger.exception("Error getting sectors:")
        raise HTTPException(status_code=500, detail=str(e)) from e
