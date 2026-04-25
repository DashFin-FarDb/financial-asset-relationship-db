"""Pydantic models for the API authentication layer."""

from typing import Any

from pydantic import BaseModel, Field


class User(BaseModel):
    """User model for authentication."""

    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    """User model with hashed password for database storage."""

    hashed_password: str


class AssetResponse(BaseModel):
    """API response model for an asset record and its optional extra fields."""

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
    """API response model for a directed relationship between two assets."""

    source_id: str
    target_id: str
    relationship_type: str
    strength: float


class MetricsResponse(BaseModel):
    """API response model containing aggregate graph metrics."""

    total_assets: int
    total_relationships: int
    asset_classes: dict[str, int]
    avg_degree: float
    max_degree: int
    network_density: float
    relationship_density: float = 0.0


class VisualizationDataResponse(BaseModel):
    """API response model for frontend visualization nodes and edges."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
