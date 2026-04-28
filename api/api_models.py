"""Pydantic response models for API endpoints."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class AssetPageResponse(BaseModel):
    """Response model for paginated asset data."""

    items: list[AssetResponse]
    total: int
    page: int
    per_page: int


class RelationshipResponse(BaseModel):
    """Response model for relationship data."""

    source_id: str
    target_id: str
    relationship_type: str
    strength: float


class MetricsResponse(BaseModel):
    """Response model for graph-owned public network metrics."""

    total_assets: int
    total_relationships: int
    asset_classes: dict[str, int]
    avg_degree: float
    max_degree: int
    network_density: float
    relationship_density: float = 0.0


class VisualizationNode(BaseModel):
    """Response model for a visualization node."""

    model_config = ConfigDict(extra="forbid")

    id: str
    symbol: str
    name: str
    asset_class: str
    x: float
    y: float
    z: float
    color: str
    size: int


class VisualizationEdge(BaseModel):
    """Response model for a visualization edge."""

    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relationship_type: str
    strength: float


class VisualizationDataResponse(BaseModel):
    """Response model for typed visualization data."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[VisualizationNode]
    edges: list[VisualizationEdge]
