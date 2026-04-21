"""FastAPI backend for the Financial Asset Relationship Database."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, Callable, Dict, List, NoReturn, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

# pylint: disable=import-error
from slowapi import (  # type: ignore[import-not-found]
    Limiter,
    _rate_limit_exceeded_handler,
)
from slowapi.errors import RateLimitExceeded  # type: ignore[import-not-found]
from slowapi.util import get_remote_address  # type: ignore[import-not-found]

from src.logic.asset_graph import AssetRelationshipGraph

from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)
from .cors_policy import configure_cors, validate_origin  # noqa: F401
from .graph_lifecycle import _initialize_graph as _lifecycle_initialize_graph
from .graph_lifecycle import get_graph as _get_graph
from .graph_lifecycle import reset_graph as _reset_graph
from .graph_lifecycle import set_graph as _set_graph
from .graph_lifecycle import set_graph_factory as _set_graph_factory
from .routers.assets import router as assets_router
from .routers.metrics import router as metrics_router
from .routers.relationships import router as relationships_router
from .routers.system import router as system_router
from .routers.visualization import router as visualization_router


def _initialize_graph() -> AssetRelationshipGraph:
    """Return a freshly initialized asset relationship graph."""
    return _lifecycle_initialize_graph()


# pylint: enable=import-error

logger = logging.getLogger(__name__)


def get_graph() -> AssetRelationshipGraph:
    """Return the shared asset relationship graph instance."""
    return _get_graph()


def set_graph(graph: AssetRelationshipGraph) -> None:
    """Set the shared asset relationship graph instance."""
    _set_graph(graph)


GraphFactory = Callable[[], AssetRelationshipGraph]


def set_graph_factory(factory: Optional[GraphFactory]) -> None:
    """Set the factory used to build the shared asset relationship graph."""
    _set_graph_factory(factory)


def reset_graph() -> None:
    """Reset the shared asset relationship graph state."""
    _reset_graph()


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

# Configure CORS via extracted policy
configure_cors(app)

app.include_router(system_router)
app.include_router(assets_router)
app.include_router(relationships_router)
app.include_router(metrics_router)
app.include_router(visualization_router)


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


