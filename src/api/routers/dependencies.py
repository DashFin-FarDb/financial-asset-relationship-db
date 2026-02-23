import threading

from src.logic.asset_graph import AssetRelationshipGraph

_graph: AssetRelationshipGraph | None = None
_graph_lock = threading.Lock()


def get_graph() -> AssetRelationshipGraph:
    """
    Return the lazily initialised AssetRelationshipGraph singleton.

    Returns:
        AssetRelationshipGraph: The shared graph instance.

    Raises:
        RuntimeError: If initialisation fails (propagated from the graph builder).
    """
    global _graph
    if _graph is None:
        with _graph_lock:
            if _graph is None:
                _graph = _initialize_graph()  # move _initialize_graph here too
    return _graph
