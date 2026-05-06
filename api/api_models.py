"""Pydantic response models for API endpoints."""

from typing import Any, Literal

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


class GraphHealthResponse(BaseModel):
    """Non-secret graph readiness status."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    asset_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)


class DatabaseHealthResponse(BaseModel):
    """Non-secret auth database readiness status."""

    model_config = ConfigDict(extra="forbid")

    configured: bool
    type: Literal["sqlite", "postgresql", "unknown"]
    reachable: bool


class DetailedHealthResponse(BaseModel):
    """Non-secret hosted deployment readiness status."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy", "degraded"]
    graph: GraphHealthResponse
    database: DatabaseHealthResponse


class GraphRebuildResponse(BaseModel):
    """Response model for explicit graph rebuild persistence."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["persisted"] = "persisted"
    source: Literal["cache", "real_data", "sample"]
    asset_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    regulatory_event_count: int = Field(ge=0)
