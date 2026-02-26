"""Pydantic models for the API package."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class User(BaseModel):
    """Public-facing user representation — safe to serialise in API responses."""

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False


class UserInDB(BaseModel):
    """Database-backed user record for authentication flows."""

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    hashed_password: str


# API Response Models


class AssetResponse(BaseModel):
    """Response model for asset data."""

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
    """Response model for relationship data."""

    source_id: str
    target_id: str
    relationship_type: str
    strength: float


class MetricsResponse(BaseModel):
    """Response model for graph metrics."""

    total_assets: int
    total_relationships: int
    asset_classes: Dict[str, int]
    avg_degree: float
    max_degree: int
    network_density: float
    relationship_density: float = 0.0


class VisualizationDataResponse(BaseModel):
    """Response model for 3D visualization data."""

    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
