import threading

from mcp.server.fastmcp import FastMCP

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset, AssetClass, Equity

# Initialize the MCP server
mcp = FastMCP("DashFin-Relationship-Manager")

# Global instance of the graph logic

_graph_lock = threading.Lock()


class _ThreadSafeGraph:
    """Proxy that serializes all method calls on the underlying graph via the provided lock."""

    def __init__(self, graph_obj: AssetRelationshipGraph, lock: threading.Lock):
        self._graph = graph_obj
        self._lock = lock

    def __getattr__(self, name):
        attr = getattr(self._graph, name)
        if callable(attr):
            def _wrapped(*args, **kwargs):
                with self._lock:
                    return attr(*args, **kwargs)

            return _wrapped
        return attr


graph = _ThreadSafeGraph(AssetRelationshipGraph(), _graph_lock)


@mcp.tool()
def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
    """
    Add an Equity asset to the global relationship graph after validating its fields.

    Returns:
        A success message containing the equity's name and symbol on successful validation, or
        "Validation Error: <message>" containing the validation error text if creation fails.
    """
    # Local import to prevent NameError if module imports are refactored.
    from src.models.financial_models import AssetClass, Equity

    try:
        # Uses existing Equity dataclass for post-init validation
        new_equity = Equity(
            id=asset_id,
            symbol=symbol,
            name=name,
            asset_class=AssetClass.EQUITY,
            sector=sector,
            price=price,
        )

        graph.add_equity(new_equity)
        return f"Successfully added: {new_equity.name} ({new_equity.symbol})"
    except ValueError as e:
        return f"Validation Error: {str(e)}"


def get_3d_layout() -> str:
    """Provides current 3D visualization data for AI spatial reasoning."""
    positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
    return json.dumps({
        "asset_ids": asset_ids,
        "positions": positions.tolist(),
@ mcp.resource("graph://data/3d-layout")
def get_3d_layout() -> str:
    """Provides current 3D visualization data for AI spatial reasoning."""
    # Leverages existing logic for deterministic layouts (seed 42)
    positions, asset_ids, colors, hover= graph.get_3d_visualization_data_enhanced()
    return f"Assets: {asset_ids}\nPositions: {positions.tolist()}"


if __name__ == "__main__":
    mcp.run()
