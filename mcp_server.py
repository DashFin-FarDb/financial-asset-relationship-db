import json
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

    import copy

    # Acquire the lock while resolving the attribute to avoid races where the
    # underlying graph is mutated concurrently during attribute access (e.g.,
    # properties/descriptors or mutable fields being swapped out).
    with self._lock:
        attr = getattr(self._graph, name)

        if callable(attr):
            def _wrapped(*args, **kwargs):
                with self._lock:
                    return getattr(self._graph, name)(*args, **kwargs)

            return _wrapped

        # For non-callable attributes, return a defensive copy so callers cannot
        # mutate shared state without holding the lock.
        return copy.deepcopy(attr)


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
        graph.add_asset(new_equity)


@mcp.tool()
def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
    """
    Add an Equity asset after validating its fields.

    Note: AssetRelationshipGraph currently does not expose an add_equity/add_asset API,
    so this tool validates and returns the created object details without mutating the graph.

    Returns:
        A success message containing the equity's name and symbol on successful validation, or
        "Validation Error: <message>" containing the validation error text if creation fails.
    """
    # Local import to prevent NameError if module imports are refactored.
    from src.models.financial_models import AssetClass, Equity

    try:
        # Uses existing Equity dataclass for post-init validation
        new_equity = Equity(
            _graph_lock=threading.Lock()


            class _ThreadSafeGraph:
            """Proxy that serializes all method calls on the underlying graph via the provided lock."""

            def __init__(self, graph_obj: AssetRelationshipGraph, lock: threading.Lock):
            self._graph=graph_obj
            self._lock=lock

            def __getattr__(self, name):
            # Acquire the lock while resolving the attribute to avoid races where the
            # underlying graph is mutated concurrently during attribute access (e.g.,
            # properties/descriptors or mutable fields being swapped out).
            with self._lock:
            attr=getattr(self._graph, name)

            if callable(attr):

            def _wrapped(*args, **kwargs):
                with self._lock:
                    return attr(*args, **kwargs)

            return _wrapped

            # For non-callable attributes, return a defensive copy so callers cannot
            # mutate shared state without holding the lock.
            import copy

            with self._lock:
            return copy.deepcopy(attr)


            graph=_ThreadSafeGraph(AssetRelationshipGraph(), _graph_lock)
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
            new_equity=Equity(
                id=asset_id,
                symbol=symbol,
                name=name,
                asset_class=AssetClass.EQUITY,
                sector=sector,
                price=price,
            )
            graph.add_asset(new_equity)
            return f"Successfully added: {new_equity.name} ({new_equity.symbol})"
import json
import threading

from mcp.server.fastmcp import FastMCP

from src.logic.asset_graph import AssetRelationshipGraph


mcp = FastMCP("DashFin-Relationship-Manager")

_graph_lock = threading.Lock()


class _ThreadSafeGraph:
    """Proxy that serializes all method calls on the underlying graph via the provided lock."""

    def __init__(self, graph_obj: AssetRelationshipGraph, lock: threading.Lock):
        self._graph = graph_obj
        self._lock = lock

    def __getattr__(self, name: str):
        # Resolve the attribute under lock to avoid races during attribute access.
        with self._lock:
            attr = getattr(self._graph, name)

        if callable(attr):

            def _wrapped(*args, **kwargs):
                with self._lock:
                    return attr(*args, **kwargs)

            return _wrapped

        # For non-callable attributes, return a defensive copy so callers cannot
        # mutate shared state without holding the lock.
        import copy

        with self._lock:
            return copy.deepcopy(attr)


graph = _ThreadSafeGraph(AssetRelationshipGraph(), _graph_lock)


@mcp.tool()
def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
    """
    Add an Equity asset after validating its fields.

    If the underlying graph exposes an `add_asset` method, the validated asset will be added.
    Otherwise, the tool returns validation success without mutating the graph.

    Returns:
        Success/validation message, or "Validation Error: <message>" on failure.
    """
    # Local import to avoid hard import coupling if the models module is refactored.
    from src.models.financial_models import AssetClass, Equity

    try:
        new_equity = Equity(
            id=asset_id,
            symbol=symbol,
            name=name,
            asset_class=AssetClass.EQUITY,
            sector=sector,
            price=price,
        )

        if hasattr(graph, "add_asset") and callable(getattr(graph, "add_asset")):
            graph.add_asset(new_equity)
            return f"Successfully added: {new_equity.name} ({new_equity.symbol})"

        return f"Successfully validated: {new_equity.name} ({new_equity.symbol})"
    except ValueError as e:
        return f"Validation Error: {str(e)}"


@mcp.resource("graph://data/3d-layout")
def get_3d_layout() -> str:
    """Provides current 3D visualization data for AI spatial reasoning."""
    positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
    return json.dumps(
        {
            "asset_ids": asset_ids,
            "positions": positions.tolist(),
            "colors": colors,
            "hover": hover,
        }
    )


if __name__ == "__main__":
    mcp.run()
            return f"Validation Error: {str(e)}"
            symbol=symbol,
            name=name,
            asset_class=AssetClass.EQUITY,
            sector=sector,
            price=price,
        )
        return f"Successfully validated: {new_equity.name} ({new_equity.symbol})"
    except ValueError as e:
        return f"Validation Error: {str(e)}"

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

        graph.add_asset(new_equity)
        return f"Successfully added: {new_equity.name} ({new_equity.symbol})"
    except ValueError as e:
        return f"Validation Error: {str(e)}"


# Initialize the MCP server
mcp = FastMCP("DashFin-Relationship-Manager")

_graph_lock = threading.Lock()


class _ThreadSafeGraph:
    """Proxy that serializes all method calls on the underlying graph via the provided lock."""

    def __init__(self, graph_obj: AssetRelationshipGraph, lock: threading.Lock):
        self._graph = graph_obj
        self._lock = lock

    def __getattr__(self, name):
        # Acquire the lock while resolving the attribute to avoid races where the
        # underlying graph is mutated concurrently during attribute access (e.g.,
        # properties/descriptors or mutable fields being swapped out).
        with self._lock:
            attr = getattr(self._graph, name)

        if callable(attr):

            def _wrapped(*args, **kwargs):
                with self._lock:
                    return attr(*args, **kwargs)

            return _wrapped

        # For non-callable attributes, return a defensive copy so callers cannot
        # mutate shared state without holding the lock.
        import copy

        with self._lock:
            return copy.deepcopy(attr)


graph = _ThreadSafeGraph(AssetRelationshipGraph(), _graph_lock)


@mcp.tool()
def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
    """
    Add an Equity asset after validating its fields.

    Returns:
        A success message containing the equity's name and symbol on successful validation, or
        "Validation Error: <message>" containing the validation error text if creation fails.
    """
    # Local import to prevent NameError if module imports are refactored.
    from src.models.financial_models import AssetClass, Equity

    try:
        new_equity = Equity(
            id=asset_id,
            symbol=symbol,
            name=name,
            asset_class=AssetClass.EQUITY,
            sector=sector,
            price=price,
        )
        return f"Successfully validated: {new_equity.name} ({new_equity.symbol})"
    except ValueError as e:
        return f"Validation Error: {str(e)}"


@mcp.resource("graph://data/3d-layout")
def get_3d_layout() -> str:
    """Provides current 3D visualization data for AI spatial reasoning."""
    positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
    return json.dumps(
        {
            "asset_ids": asset_ids,
            "positions": positions.tolist(),
            "colors": colors,
            "hover": hover,
        }
    )


if __name__ == "__main__":
    mcp.run()
