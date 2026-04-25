"""FastAPI backend for the Financial Asset Relationship Database.

This module serves as the public entrypoint and maintains backward compatibility
for existing imports. The actual FastAPI app construction logic lives in app_factory.py.
"""

from __future__ import annotations

from collections.abc import Callable

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
from .routers.assets import router as assets_router  # noqa: F401
from .routers.auth import router as auth_router  # noqa: F401
from .routers.metrics import router as metrics_router  # noqa: F401
from .routers.relationships import router as relationships_router  # noqa: F401
from .routers.system import router as system_router  # noqa: F401
from .routers.visualization import router as visualization_router  # noqa: F401

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


def set_graph(graph_instance: AssetRelationshipGraph) -> None:
    """Set the shared asset relationship graph instance."""
    global graph  # noqa: PLW0603
    _set_graph(graph_instance)
    # Keep the module-level reference in sync so router_helpers.get_graph()
    # (which prefers api.main.graph for backward compatibility) sees the
    # updated instance immediately.
    graph = graph_instance


GraphFactory = Callable[[], AssetRelationshipGraph]


def set_graph_factory(factory: GraphFactory | None) -> None:
    """Set the factory used to build the shared asset relationship graph."""
    _set_graph_factory(factory)


def reset_graph() -> None:
    """Reset the shared asset relationship graph state."""
    global graph  # noqa: PLW0603
    _reset_graph()
    # Clear the module-level reference so router_helpers.get_graph() falls
    # through to the lifecycle get_graph() on the next request, which will
    # trigger lazy re-initialization from the configured factory or settings.
    graph = None  # type: ignore[assignment]  # Intentionally set to None (AssetRelationshipGraph | None) to signal lazy re-init on next access
