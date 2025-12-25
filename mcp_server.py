import numpy as np
from mcp.server.fastmcp import FastMCP

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset, AssetClass, Equity

# Initialize the MCP server
mcp = FastMCP("DashFin-Relationship-Manager")

# Global instance of the graph logic
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
        return f"Successfully validated: {new_equity.name} ({new_equity.symbol})"
    except ValueError as e:
        return f"Validation Error: {str(e)}"


@mcp.resource("graph://data/3d-layout")
def get_3d_layout() -> str:
    """
    Return a human-readable snapshot of the graph's 3D layout for spatial reasoning.

    Calls the graph's visualization export and formats asset identifiers and their 3D coordinates into a short string.

    Returns:
        A string containing "Assets: [asset_id, ...]" and "Positions: [[x, y, z], ...]" where positions is a list of 3-element coordinate lists corresponding to the asset IDs.
    """
    # Leverages existing logic for deterministic layouts (seed 42)
    positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
    return f"Assets: {asset_ids}\nPositions: {positions.tolist()}"


if __name__ == "__main__":
    mcp.run()
