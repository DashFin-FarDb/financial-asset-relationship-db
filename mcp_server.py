import threading

from mcp.server.fastmcp import FastMCP

from src.logic.asset_graph import AssetRelationshipGraph

# Initialize the MCP server
mcp = FastMCP("DashFin-Relationship-Manager")

# Global instance of the graph logic

_graph_lock = threading.Lock()
graph = AssetRelationshipGraph()


@mcp.tool()
def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
    """
    Add an Equity asset to the global relationship graph after validating its fields.

    Returns:
        A success message containing the equity's name and symbol on successful validation, or
        "Validation Error: <message>" containing the validation error text if creation fails.
    """
    try:
        # Uses existing Equity dataclass for post-init validation
        new_equity = Equity(
            id=asset_id, symbol=symbol, name=name, asset_class=AssetClass.EQUITY, sector=sector, price=price
        )
        # Add the new node to the graph if it doesn't exist.
        if new_equity.id not in graph.relationships:
            graph.relationships[new_equity.id] = []
        return f"Successfully added: {new_equity.name} ({new_equity.symbol})"
    except ValueError as e:
        return f"Validation Error: {str(e)}"


@mcp.tool()
def get_3d_layout() -> str:
    """
    Return a human-readable snapshot of the graph's 3D layout for spatial reasoning.

    Calls the graph's visualization export and formats asset identifiers and their 3D coordinates into a short string.
import json

def get_3d_layout() -> str:
    """Provides current 3D visualization data for AI spatial reasoning."""
    positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
    return json.dumps({
        "asset_ids": asset_ids,
        "positions": positions.tolist(),
        "colors": colors,
        "hover": hover
    })
    positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
    return f"Assets: {asset_ids}\nPositions: {positions.tolist()}"


if __name__ == "__main__":
    mcp.run()
