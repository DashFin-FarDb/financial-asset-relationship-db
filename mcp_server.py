"""MCP server entrypoint for asset graph operations."""

import argparse
import copy
import json
import threading

from mcp.server.fastmcp import FastMCP
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity

# Shared lock for graph access
_graph_lock = threading.Lock()


class _ThreadSafeGraph:  # pylint: disable=too-few-public-methods
    """Proxy that serializes all access to the underlying graph via a lock."""

    def __init__(self, graph_obj: AssetRelationshipGraph, lock: threading.Lock):
        self._graph = graph_obj
        self._lock = lock

    def __getattr__(self, name: str):
        """
        Dynamically resolves attribute access under a lock to avoid race conditions.
        If the attribute is callable, returns a wrapper that locks around calls;
        otherwise, returns a defensive deep copy of the attribute.
        """
        # Resolve the attribute under lock to avoid races.
        with self._lock:
            attr = getattr(self._graph, name)

            if callable(attr):

                def _wrapped(*args, **kwargs):
                    """
                    Thread-safe wrapper for callable attributes that acquires the lock
                    before invocation.
                    """
                    with self._lock:
                        return attr(*args, **kwargs)

                return _wrapped

            # For non-callable attributes, return a defensive copy so callers cannot
            # mutate shared state without holding the lock.
            # Deepcopy must occur INSIDE the lock context.
            return copy.deepcopy(attr)


# Global, thread-safe graph instance shared across MCP calls.
graph = _ThreadSafeGraph(AssetRelationshipGraph(), _graph_lock)


def _get_3d_layout_resource() -> str:
    """Provide current 3D visualization data for AI spatial reasoning as JSON."""
    positions, asset_ids, colors, hover = (
        graph.get_3d_visualization_data_enhanced()
    )
    return json.dumps(
        {
            "asset_ids": asset_ids,
            "positions": positions.tolist(),
            "colors": colors,
            "hover": hover,
        }
    )


def _register_mcp_handlers(mcp: FastMCP) -> None:
    """Register MCP tools and resources on the provided app instance."""

    def add_equity_node(
        asset_id: str,
        symbol: str,
        name: str,
        sector: str,
        price: float,
    ) -> str:
        """Validate and optionally add an equity node to the shared graph."""
        try:
            new_equity = Equity(
                id=asset_id,
                symbol=symbol,
                name=name,
                asset_class=AssetClass.EQUITY,
                sector=sector,
                price=price,
            )
            add_asset = getattr(graph, "add_asset", None)
            if callable(add_asset):
                add_asset(new_equity)
                return (
                    f"Successfully added: {new_equity.name} "
                    f"({new_equity.symbol})"
                )
            return (
                "Successfully validated (Graph mutation not supported): "
                f"{new_equity.name} ({new_equity.symbol})"
            )
        except ValueError as e:
            return f"Validation Error: {str(e)}"

    mcp.tool()(add_equity_node)
    mcp.resource("graph://data/3d-layout")(_get_3d_layout_resource)


def _build_mcp_app():
    """
    Create and configure the FastMCP application used by the relationship manager.

    Registers an `add_equity_node` tool that validates (and, if supported by
    the module-level graph, adds) an Equity asset, and a
    `graph://data/3d-layout` resource that returns the current 3D
    visualization data as a JSON string.

    Returns:
        mcp (FastMCP): Configured FastMCP application instance.
    """
    mcp = FastMCP("DashFin-Relationship-Manager")
    _register_mcp_handlers(mcp)
    return mcp


def main(argv: list[str] | None = None) -> int:
    """
    Run the MCP server command-line entry point.

    Parameters:
        argv (list[str] | None): Command-line arguments to parse. If None, uses
            sys.argv[1:].

    Returns:
        int: Exit code (0 on success or after printing version information).

    Raises:
        SystemExit: If a required optional dependency is missing (suggests
            installing the MCP package).
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
            "Install the MCP package to run the server."
        ) from e

    mcp.run()
    return 0
