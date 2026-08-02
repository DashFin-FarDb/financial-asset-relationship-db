"""Shared helper functions for API routers."""

import logging
from typing import Any, NoReturn

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Color mapping for each AssetClass.value string used by the visualization router.
_DEFAULT_COLOR = "#7f7f7f"
_ASSET_CLASS_COLORS: dict[str, str] = {
    "Equity": "#1f77b4",
    "Fixed Income": "#2ca02c",
    "Commodity": "#ff7f0e",
    "Currency": "#d62728",
    "Derivative": "#9467bd",
}


def get_graph():
    """Return the active graph instance and retain its publication binding."""
    graph = None
    try:
        import api.main as api_main  # local import to avoid import cycle at module import time

        if hasattr(api_main, "graph") and api_main.graph is not None:
            graph = api_main.graph
    except Exception:
        pass

    if graph is None:
        from .graph_lifecycle import get_graph as _get_graph

        graph = _get_graph()

    from .services.relationship_index import register_runtime_graph_publication_binding

    register_runtime_graph_publication_binding(graph)
    return graph


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
) -> dict[str, Any]:
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
    asset_dict: dict[str, Any] = {
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
        "expiry_date",
        "underlying_asset",
        "strike_price",
        "volatility",
        "country",
        "exchange",
        "ceo",
        "employees",
        "founded_year",
    ]

    for field in optional_fields:
        if hasattr(asset, field):
            value = getattr(asset, field)
            if value is not None:
                asset_dict["additional_fields"][field] = value

    if include_issuer and hasattr(asset, "issuer_id"):
        issuer_id = getattr(asset, "issuer_id")
        if issuer_id is not None:
            asset_dict["issuer_id"] = issuer_id

    return asset_dict
