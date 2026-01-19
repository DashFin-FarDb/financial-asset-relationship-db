import argparse
import copy
import json
import threading

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity

# Shared lock for graph access
_graph_lock = threading.Lock()


class _ThreadSafeGraph:
    """Proxy that serializes all access to the underlying graph via a lock."""

    def __init__(self, graph_obj: AssetRelationshipGraph, lock: threading.Lock):
        self._graph = graph_obj
        self._lock = lock

    def __getattr__(self, name: str):
        # Resolve the attribute under lock to avoid races.
        with self._lock:
            attr = getattr(self._graph, name)

            if callable(attr):

                def _wrapped(*args, **kwargs):
                    with self._lock:
                        return attr(*args, **kwargs)

                return _wrapped

            # For non-callable attributes, return a defensive copy so callers cannot
            # mutate shared state without holding the lock.
            # Deepcopy must occur INSIDE the lock context.
            return copy.deepcopy(attr)


# Global, thread-safe graph instance shared across MCP calls.
graph = _ThreadSafeGraph(AssetRelationshipGraph(), _graph_lock)


def _build_mcp_app():
    """
    Construct the FastMCP application used by the Relationship Manager.

    Keeps the optional `mcp` dependency import local so importing this module (or
    running command-line help) does not require `mcp` to be installed.

    Returns:
        FastMCP: Configured FastMCP instance with registered tools and resources.
    """
    """
    Validate an Equity asset and add it to the global graph when supported.
    
    Performs dataclass validation for the provided fields. If the global graph
    exposes an `add_asset` method, the validated Equity is added to the graph;
    otherwise only validation is performed and no mutation occurs.
    
    Returns:
        str: A message describing the outcome: successful add, successful validation
        without mutation, or a validation error prefixed with "Validation Error:".
    """
    """
    Return current 3D visualization data for the graph as a JSON string.
    
    Returns:
        str: JSON string with keys `asset_ids`, `positions` (list of position lists),
        `colors`, and `hover`.
    """
    from mcp.server.fastmcp import FastMCP  # local import (lazy)

    mcp = FastMCP("DashFin-Relationship-Manager")

    @mcp.tool()
    def add_equity_node(
        asset_id: str, symbol: str, name: str, sector: str, price: float
    ) -> str:
        """
        Validate an Equity asset and add it to the global graph when supported.

        Constructs an Equity instance from the provided fields to perform validation. If the global graph exposes an add operation the asset is added; otherwise the function performs validation only and does not mutate the graph.

        Returns:
            str: A message indicating successful addition or successful validation without mutation. If validation fails, returns "Validation Error: <message>".
        """
        try:
            # Uses existing Equity dataclass for post-init validation.
            new_equity = Equity(
                id=asset_id,
                symbol=symbol,
                name=name,
                asset_class=AssetClass.EQUITY,
                sector=sector,
                price=price,
            )

            # Prefer using the graph's public add_asset API (per AssetRelationshipGraph).
            add_asset = getattr(graph, "add_asset", None)
            if callable(add_asset):
                add_asset(new_equity)
                return f"Successfully added: {new_equity.name} ({new_equity.symbol})"

            # Fallback: validation-only behavior if the graph does not expose an add API.
            # Explicitly indicate that no mutation occurred.
            return (
                f"Successfully validated (Graph mutation not supported): "
                f"{new_equity.name} ({new_equity.symbol})"
            )
        except ValueError as e:
            return f"Validation Error: {str(e)}"

    @mcp.resource("graph://data/3d-layout")
    def get_3d_layout() -> str:
        """Provide current 3D visualization data for AI spatial reasoning as JSON."""
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        return json.dumps(
            {
                "asset_ids": asset_ids,
                "positions": positions.tolist(),
                "colors": colors,
                "hover": hover,
            }
        )

    return mcp


def main(argv: list[str] | None = None) -> int:
    """
    Parse command-line arguments, build and run the MCP application, and return an exit code.

    Parameters:
        argv (list[str] | None): Optional list of command-line arguments to parse; if None, the process's arguments are used.

    Returns:
        int: Exit code (0 on success or after printing version information).

    Raises:
        SystemExit: If a required MCP dependency is missing; the exception message indicates the missing package and suggests installing the MCP package.
    """
    parser = argparse.ArgumentParser(
        prog="mcp_server.py",
        description="DashFin MCP server",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version info and exit",
    )
    args = parser.parse_args(argv)

    if args.version:
        print("DashFin-Relationship-Manager MCP server")
        return 0

    try:
        mcp = _build_mcp_app()
    except ModuleNotFoundError as e:
        # Provide a clear message for missing optional dependency
        # when invoked via the CLI.
        missing = getattr(e, "name", None) or str(e)
        raise SystemExit(
            f"Missing dependency '{missing}'. "
            + "Install the MCP package to run the server."
        ) from e

    mcp.run()
    return 0
