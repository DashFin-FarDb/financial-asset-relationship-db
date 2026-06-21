"""Pydantic response models for API endpoints."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.graph_lifecycle import GraphStartupSource
from src.data.db_models import RebuildJobStatus

GraphRebuildSource = Literal[
    "cache",
    "real_data",
    "sample",
]


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
    """Response model for paginated asset data.

    Pagination contract:
    - ``page`` is 1-indexed (first page = 1).
    - ``per_page`` defaults to 50; maximum accepted value is 1,000
      (enforced by ``Query(ge=1, le=1000)`` on the route).
    - ``total`` is the exact count of assets matching the current query
      filters (not an estimate).
    - An out-of-range ``page`` returns an empty ``items`` list, not an error.
    - Results are deterministically ordered by ``asset.id ASC`` to ensure
      stable pagination across requests.
    """

    items: list[AssetResponse]
    total: int
    page: int
    per_page: int
    hasMore: bool


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
    network_density: float


class GraphHealthResponse(BaseModel):
    """Non-secret graph readiness status."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    lifecycle_state: str = "UNINITIALIZED"
    asset_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    startup_source: GraphStartupSource = GraphStartupSource.UNKNOWN
    persistence_enabled: bool = False
    persistence_loaded: bool = False
    persistence_saved: bool = False


class DatabaseHealthResponse(BaseModel):
    """Non-secret auth database readiness status."""

    model_config = ConfigDict(extra="forbid")

    configured: bool
    type: Literal["sqlite", "postgresql", "unknown"]
    reachable: bool


class SLOEvaluationResultModel(BaseModel):
    """Response model for a single SLO evaluation."""

    model_config = ConfigDict(extra="forbid")

    slo_name: str
    is_compliant: bool
    current_value: float
    threshold: float
    margin: float


class SLOSummary(BaseModel):
    """Response model summarizing all SLO evaluations."""

    model_config = ConfigDict(extra="forbid")

    overall_compliant: bool
    evaluations: list[SLOEvaluationResultModel]


class DetailedHealthResponse(BaseModel):
    """Non-secret hosted deployment readiness status."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy", "degraded"]
    graph_persistence_configured: bool = Field(
        default=False,
        title="Graph persistence configured",
        description="Indicates whether durable graph persistence is configured (durable, non-memory store). Defaults to False for backwards compatibility.",
        examples=[False, True],
    )
    graph: GraphHealthResponse
    database: DatabaseHealthResponse


class GraphRebuildResponse(BaseModel):
    """Response model for explicit graph rebuild persistence."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["persisted"] = "persisted"
    source: GraphRebuildSource
    asset_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    regulatory_event_count: int = Field(ge=0)


class RebuildJobResponse(BaseModel):
    """Response model for rebuild job status.

    Exposes bounded sanitized rebuild job state only.
    No raw exceptions, stack traces, DB URLs, credentials, or ORM internals.
    """

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: RebuildJobStatus
    source: str | None
    requested_by: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    node_count: int | None
    edge_count: int | None
    failure_category: str | None
    failure_message: str | None


class RebuildJobListResponse(BaseModel):
    """Response model for rebuild job listing.

    Bounded rebuild job list structure.
    """

    model_config = ConfigDict(extra="forbid")

    jobs: list[RebuildJobResponse]
    count: int = Field(ge=0)
