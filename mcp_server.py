import argparse
import copy
import json
import sys
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
            # FIX: Deepcopy must occur INSIDE the lock context.
            return copy.deepcopy(attr)


# Global, thread-safe graph instance shared across MCP calls.
graph = _ThreadSafeGraph(AssetRelationshipGraph(), _graph_lock)


def _build_mcp_app():
    """
    Build and return the FastMCP app.

    Kept in a function so importing this module (or running `--help`) does not
    require the optional `mcp` dependency to be importable.
    """
    from mcp.server.fastmcp import FastMCP  # local import (lazy)

    mcp = FastMCP("DashFin-Relationship-Manager")

    @mcp.tool()
    def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
        """
        Validate an Equity asset and add it to the graph.

        If the graph exposes an `add_asset` method, the asset is added.
        Otherwise, this tool performs validation only (no persistent changes).

        Returns:
            Success message or 'Validation Error: <message>'.
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
            # FIX: Explicitly indicate that no mutation occurred.
            return f"Successfully validated (Graph mutation not supported): {new_equity.name} ({new_equity.symbol})"
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
    parser = argparse.ArgumentParser(prog="mcp_server.py", description="DashFin MCP server")
    parser.add_argument("--version", action="store_true", help="Print version info and exit")
    args = parser.parse_args(argv)

    if args.version:
        print("DashFin-Relationship-Manager MCP server")
        return 0

    try:
        mcp = _build_mcp_app()
    except ModuleNotFoundError as e:
        # Provide a clear message for missing optional dependency when invoked via the CLI.
        missing = getattr(e, "name", None) or str(e)
        raise SystemExit(f"Missing dependency '{missing}'. Install the MCP package to run the server.") from e

    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
