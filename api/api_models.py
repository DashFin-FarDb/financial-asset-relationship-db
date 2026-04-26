"""Pydantic response models for API endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class AssetResponse(BaseModel):
    """Response model for asset data."""

    id: str
    symbol: str
    name: str
    asset_class: str
    sector: str
    price: float
    market_cap: float | None = None
    currency: str = "USD"
    additional_fields: dict[str, Any] = Field(default_factory=dict)


class RelationshipResponse(BaseModel):
    """Response model for relationship data."""

    source_id: str
    target_id: str
    relationship_type: str
    strength: float


class MetricsResponse(BaseModel):
    """Response model for network metrics."""

    total_assets: int
    total_relationships: int
    asset_classes: dict[str, int]
    avg_degree: float
    max_degree: int
    network_density: float
    relationship_density: float = 0.0


class VisualizationDataResponse(BaseModel):
    """Response model for visualization data."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
