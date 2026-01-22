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
    Create and configure the FastMCP application for the DashFin relationship manager.

    Performs a lazy import of the optional `mcp` dependency so importing this module
    (or showing CLI help) does not require `mcp` to be installed. Registers the
    `add_equity_node` tool and the `graph://data/3d-layout` resource on the app.

    Returns:
        Configured FastMCP application instance.
    """
    from mcp.server.fastmcp import FastMCP  # local import (lazy)

    mcp = FastMCP("DashFin-Relationship-Manager")

    @mcp.tool()
    def add_equity_node(
        asset_id: str, symbol: str, name: str, sector: str, price: float
    ) -> str:
        """
        Validate an Equity and add it to the thread-safe graph if supported.

        Constructs an Equity instance to perform validation. If the global graph
        exposes an `add_asset` method the new equity is added to the graph;
        otherwise the function performs validation only and does not mutate the
        graph.

        Returns:
            str: Success message containing the asset name and symbol, or
                `"Validation Error: <message>"` on validation failure.
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
    Run the MCP server from the command line.

    Parameters:
        argv (list[str] | None): Optional list of command-line arguments to parse; if
            None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 for successful run or when --version is printed).

    Raises:
        SystemExit: If an optional MCP dependency is missing;
            message will indicate which package to install.
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
