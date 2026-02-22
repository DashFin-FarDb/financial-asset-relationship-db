import threading
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

import numpy as np

from src.logic.asset_graph import AssetRelationshipGraph

# Protects concurrent reads of graph.relationships within this module.
# Recommended usage: treat graph objects as immutable after creation.
_graph_access_lock = threading.RLock()


def _build_asset_id_index(asset_ids: List[str]) -> Dict[str, int]:
    """Return O(1) lookup index mapping asset IDs to their list positions."""
    return {asset_id: idx for idx, asset_id in enumerate(asset_ids)}


def _build_relationship_index(
    graph: AssetRelationshipGraph, asset_ids: Iterable[str]
) -> Dict[Tuple[str, str, str], float]:
    """
    Construct an index mapping (source_id, target_id, rel_type) to numeric strength for relationships among the provided asset IDs.

    Only relationships whose source and target are both present in asset_ids are included.

    Returns:
        relationship_index (Dict[Tuple[str, str, str], float]): Mapping from (source_id, target_id, rel_type) to the relationship strength as a float.

    Raises:
        TypeError: If graph is not an AssetRelationshipGraph, graph.relationships is not a dict, relationships lists are not list/tuple, or asset_ids is not iterable or contains non-string items.
        ValueError: If graph is missing a 'relationships' attribute, relationship entries are not 3-element tuples, or strength values cannot be converted to float.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(f"graph must be an AssetRelationshipGraph instance, " f"got {type(graph).__name__}")
    if not hasattr(graph, "relationships"):
        raise ValueError("graph is missing 'relationships' attribute")
    if not isinstance(graph.relationships, dict):
        raise TypeError(f"graph.relationships must be a dictionary, " f"got {type(graph.relationships).__name__}")

    try:
        asset_ids_set: Set[str] = set(asset_ids)
    except TypeError as exc:
        raise TypeError(f"asset_ids must be an iterable, got {type(asset_ids).__name__}") from exc

    if not all(isinstance(aid, str) for aid in asset_ids_set):
        raise ValueError("asset_ids must contain only string values")

    with _graph_access_lock:
        relevant_relationships = {src: list(rels) for src, rels in graph.relationships.items() if src in asset_ids_set}

    relationship_index: Dict[Tuple[str, str, str], float] = {}
    for source_id, rels in relevant_relationships.items():
        if not isinstance(rels, (list, tuple)):
            raise TypeError(f"relationships for '{source_id}' must be a list or tuple, " f"got {type(rels).__name__}")
        for idx, rel in enumerate(rels):
            if not isinstance(rel, (list, tuple)) or len(rel) != 3:
                raise ValueError(
                    f"relationship at index {idx} for '{source_id}' "
                    f"must be a 3-element tuple (target_id, rel_type, strength)"
                )
            target_id, rel_type, strength = rel
            if not isinstance(target_id, str):
                raise TypeError(f"target_id at index {idx} for '{source_id}' must be a string")
            if not isinstance(rel_type, str):
                raise TypeError(f"rel_type at index {idx} for '{source_id}' must be a string")
            try:
                strength_float = float(strength)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"strength at index {idx} for '{source_id}' must be numeric") from exc
            if target_id in asset_ids_set:
                relationship_index[(source_id, target_id, rel_type)] = strength_float

    return relationship_index


def _collect_and_group_relationships(
    graph: AssetRelationshipGraph,
    asset_ids: Iterable[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> Dict[Tuple[str, bool], List[dict]]:
    """
    Collect relationships from the graph and group them by relationship type and whether the relationship is bidirectional.

    This function builds an index of relationships restricted to the provided asset_ids, applies optional relationship type filters (skip types explicitly disabled), collapses bidirectional pairs so they are reported once, and groups each relationship as a dict with keys "source_id", "target_id", and "strength" (numeric).

    Parameters:
        graph (AssetRelationshipGraph): Graph containing a `relationships` mapping to collect from.
        asset_ids (Iterable[str]): Iterable of asset IDs to include as endpoints.
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping of relationship type to a boolean;
            if a type is present and set to False it will be excluded.

    Returns:
        Dict[Tuple[str, bool], List[dict]]: Mapping from (rel_type, is_bidirectional) to a list of relationship
        dicts. Each relationship dict contains:
            - "source_id" (str)
            - "target_id" (str)
            - "strength" (float)
    """
    relationship_index = _build_relationship_index(graph, asset_ids)

    processed_pairs: Set[Tuple[str, str, str]] = set()
    relationship_groups: Dict[Tuple[str, bool], List[dict]] = defaultdict(list)

    for (source_id, target_id, rel_type), strength in relationship_index.items():
        if relationship_filters and rel_type in relationship_filters and not relationship_filters[rel_type]:
            continue

        pair_key: Tuple[str, str, str] = (
            (source_id, target_id, rel_type) if source_id <= target_id else (target_id, source_id, rel_type)
        )
        is_bidirectional = (target_id, source_id, rel_type) in relationship_index

        if is_bidirectional and pair_key in processed_pairs:
            continue
        if is_bidirectional:
            processed_pairs.add(pair_key)

        relationship_groups[(rel_type, is_bidirectional)].append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "strength": float(strength),
            }
        )

    return relationship_groups


def _build_edge_coordinates_optimized(
    relationships: List[dict],
    positions: np.ndarray,
    asset_id_index: Dict[str, int],
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """
    Construct preallocated x, y, and z coordinate lists for edge traces corresponding to the given relationships.

    Each returned list has length len(relationships) * 3. For relationship i the source vertex coordinate is written at index i*3, the target vertex coordinate at index i*3 + 1, and index i*3 + 2 is left as a separator (None) to separate edge segments in plotting libraries.

    Parameters:
        relationships: List of relationship dicts containing at least "source_id" and "target_id" keys.
        positions: NumPy array of vertex positions with shape (num_vertices, 3) where columns are x, y, z.
        asset_id_index: Mapping from asset_id string to its row index in `positions`.

    Returns:
        Tuple of three lists (edges_x, edges_y, edges_z). Each list contains floats or None aligned as described above.
    """
    n = len(relationships)
    edges_x: List[Optional[float]] = [None] * (n * 3)
    edges_y: List[Optional[float]] = [None] * (n * 3)
    edges_z: List[Optional[float]] = [None] * (n * 3)

    for i, rel in enumerate(relationships):
        src = asset_id_index[rel["source_id"]]
        tgt = asset_id_index[rel["target_id"]]
        base = i * 3
        edges_x[base], edges_x[base + 1] = positions[src, 0], positions[tgt, 0]
        edges_y[base], edges_y[base + 1] = positions[src, 1], positions[tgt, 1]
        edges_z[base], edges_z[base + 1] = positions[src, 2], positions[tgt, 2]

    return edges_x, edges_y, edges_z


def _build_hover_texts(relationships: List[dict], rel_type: str, is_bidirectional: bool) -> List[Optional[str]]:
    """
    Construct a pre-allocated list of hover text strings for a group of relationships.

    Each relationship produces a formatted hover string of the form
    "source_id (↔ or →) target_id<br>Type: {rel_type}<br>Strength: {strength:.2f}".
    For each relationship i the list has length n * 3 and the formatted string is written
    to positions `i*3` and `i*3 + 1`; the third slot per relationship remains None.

    Parameters:
        relationships (List[dict]): Sequence of relationship dicts with keys
            'source_id' (str), 'target_id' (str), and 'strength' (numeric).
        rel_type (str): Relationship type used in the hover text "Type" field.
        is_bidirectional (bool): If true uses "↔" as the direction symbol, otherwise "→".

    Returns:
        List[Optional[str]]: A list of length `len(relationships) * 3` containing hover text
        strings at the first two positions of each three-slot block and `None` in the third.
    """
    direction = "↔" if is_bidirectional else "→"
    n = len(relationships)
    hover_texts: List[Optional[str]] = [None] * (n * 3)

    for i, rel in enumerate(relationships):
        text = (
            f"{rel['source_id']} {direction} {rel['target_id']}<br>"
            f"Type: {rel_type}<br>Strength: {rel['strength']:.2f}"
        )
        base = i * 3
        hover_texts[base] = text
        hover_texts[base + 1] = text

    return hover_texts
