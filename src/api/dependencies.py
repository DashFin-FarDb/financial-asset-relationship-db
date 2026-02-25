"""FastAPI dependency providers for the schema-report router."""

from __future__ import annotations

from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph


def get_graph() -> AssetRelationshipGraph:
    """Return an initialised graph using sample data."""
    return create_sample_database()
