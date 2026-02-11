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


def _build_mcp_app():
    """
    Builds and configures the FastMCP application used by the relationship manager.

    Performs a local import of the optional MCP dependency so the module can be
    imported (or `--help` shown) without requiring the MCP package to be installed.
    Registers an `add_equity_node` tool for validating/adding Equity assets and a
    `graph://data/3d-layout` resource that returns the current 3D visualization data
    as JSON.

    Returns:
        mcp (FastMCP): Configured FastMCP application instance.
    """
    from mcp.server.fastmcp import FastMCP  # local import (lazy)

    mcp = FastMCP("DashFin-Relationship-Manager")

    @mcp.tool()
    def add_equity_node(
        asset_id: str,
        symbol: str,
        name: str,
        sector: str,
        price: float,
    ) -> str:
        """
        Validate an Equity asset and add it to the graph if supported.

        Constructs an Equity instance to validate the provided fields.
        If the module-level graph exposes an `add_asset` callable the asset is
        added to the graph; otherwise the function performs validation only.
        and no graph mutation occurs.

        Returns:
            A success message including the asset name and symbol on success, or
            `Validation Error: <message>` describing why validation failed.
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

            # Prefer using the graph's public add_asset API
            # (per AssetRelationshipGraph).
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
    """Entry point for the MCP server CLI."""
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
