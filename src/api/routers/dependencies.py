from src.logic.asset_graph import AssetRelationshipGraph
import threading

_graph: AssetRelationshipGraph | None = None
_graph_lock = threading.Lock()

def get_graph() -> AssetRelationshipGraph:
    global _graph
    if _graph is None:
        with _graph_lock:
            if _graph is None:
                _graph = _initialize_graph()  # move _initialize_graph here too
    return _graph
