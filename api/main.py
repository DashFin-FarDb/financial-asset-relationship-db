"""FastAPI backend for the Financial Asset Relationship Database.

This module serves as the public entrypoint and maintains backward compatibility
for existing imports. The actual FastAPI app construction logic lives in app_factory.py.
"""

from __future__ import annotations

from typing import Callable, Optional

from src.config.settings import get_settings
from src.logic.asset_graph import AssetRelationshipGraph

# Backward compatibility re-exports for response models
# noqa: F401 tells flake8 to ignore "imported but unused" warnings
from .api_models import AssetResponse, MetricsResponse, RelationshipResponse, VisualizationDataResponse  # noqa: F401

# Import the FastAPI app and lifespan from app_factory
from .app_factory import app, lifespan  # noqa: F401
from .auth import (  # noqa: F401
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

# Import and re-export limiter for backward compatibility
from .rate_limit import limiter  # noqa: F401

# Backward compatibility re-exports for helper functions
from .router_helpers import raise_asset_not_found, serialize_asset  # noqa: F401

# Backward compatibility export for older tests and callers.
ENV = get_settings().env

# Backward compatibility graph reference for older tests that patch api.main.graph.
graph = _get_graph()


def _initialize_graph() -> AssetRelationshipGraph:
    """Return a freshly initialized asset relationship graph."""
    return _lifecycle_initialize_graph()


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
