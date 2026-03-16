"""Pydantic models for the API authentication layer."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class UserInDB(BaseModel):
    """User record as stored in the database, including hashed password."""

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    hashed_password: str


class AssetResponse(BaseModel):
    """API response model for an asset record and its optional extra fields."""

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
    """API response model for a directed relationship between two assets."""

    source_id: str
    target_id: str
    relationship_type: str
    strength: float


class MetricsResponse(BaseModel):
    """API response model containing aggregate graph metrics."""

    total_assets: int
    total_relationships: int
    asset_classes: Dict[str, int]
    avg_degree: float
    max_degree: int
    network_density: float
    relationship_density: float = 0.0


class VisualizationDataResponse(BaseModel):
    """API response model for frontend visualization nodes and edges."""

    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
