"""Prometheus metrics for the Financial Asset Relationship API."""

from prometheus_client import Counter, Gauge, Histogram

# Rebuild metrics
REBUILD_REQUESTS = Counter(
    "graph_rebuild_requests_total",
    "Total number of graph rebuild requests received.",
)

REBUILD_SUCCESS = Counter(
    "graph_rebuild_success_total",
    "Total number of successful graph rebuilds.",
    ["source"],
)

REBUILD_FAILURE = Counter(
    "graph_rebuild_failure_total",
    "Total number of failed graph rebuilds.",
    ["category"],
)

REBUILD_DURATION = Histogram(
    "graph_rebuild_duration_seconds",
    "Time spent rebuilding the graph.",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)

# Graph state metrics
GRAPH_ASSETS = Gauge(
    "graph_assets_count",
    "Current number of assets in the graph.",
)

GRAPH_RELATIONSHIPS = Gauge(
    "graph_relationships_count",
    "Current number of relationships in the graph.",
)


def update_graph_metrics(asset_count: int, relationship_count: int) -> None:
    """Update gauge metrics for the current graph state."""
    GRAPH_ASSETS.set(asset_count)
    GRAPH_RELATIONSHIPS.set(relationship_count)
