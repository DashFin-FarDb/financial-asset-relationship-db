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
    Builds an index mapping (source_id, target_id, rel_type) to numeric strength for relationships where both endpoints are in the provided asset IDs.
    
    Parameters:
        graph (AssetRelationshipGraph): Graph containing a `relationships` mapping.
        asset_ids (Iterable[str]): Iterable of asset IDs to include.
    
    Returns:
        Dict[Tuple[str, str, str], float]: Mapping from (source_id, target_id, rel_type) to the relationship strength as a float.
    
    Raises:
        TypeError: If `graph` is not an AssetRelationshipGraph, `graph.relationships` is not a dict, `asset_ids` is not iterable, or relationship entries have incorrect types.
        ValueError: If `graph` is missing `relationships`, `asset_ids` contains non-string values, relationship entries are not 3-element tuples, or strength values are not numeric.
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
    Collect relationships for the given asset_ids and group them by relationship type and bidirectionality.
    
    Parameters:
        graph (AssetRelationshipGraph): Graph to read relationships from.
        asset_ids (Iterable[str]): Asset IDs to include.
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping of relationship type to a boolean; relationship types present with a value of False are excluded.
    
    Returns:
        relationship_groups (Dict[Tuple[str, bool], List[dict]]): Mapping from (rel_type, is_bidirectional) to lists of relationship dictionaries. Each dictionary contains "source_id", "target_id", and "strength" (float).
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
    Create pre-allocated x, y, and z coordinate lists for edge traces from relationships and node positions.
    
    Parameters:
        relationships (List[dict]): List of relationship dicts containing at least "source_id" and "target_id".
        positions (np.ndarray): Array of node positions with shape (N, 3) where columns are x, y, z.
        asset_id_index (Dict[str, int]): Mapping from asset ID to row index in `positions`.
    
    Returns:
        edges_x (List[Optional[float]]): List of length 3 * len(relationships) where for each relationship i
            the source x and target x are stored at indices 3*i and 3*i+1 respectively (third slot remains None).
        edges_y (List[Optional[float]]): Same layout as `edges_x`, for y coordinates.
        edges_z (List[Optional[float]]): Same layout as `edges_x`, for z coordinates.
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
    Build hover text entries for a group of relationships, pre-allocating space for plotting traces.
    
    Parameters:
        relationships (List[dict]): List of relationship dicts containing at least the keys
            'source_id', 'target_id', and 'strength'.
        rel_type (str): Relationship type label to include in each hover text.
        is_bidirectional (bool): Whether the relationship is bidirectional; affects the direction symbol.
    
    Returns:
        List[Optional[str]]: A list of length 3 * len(relationships) containing hover text strings and None
        placeholders. For each relationship, the formatted hover text appears at positions base and base+1
        (where base = index * 3); the third slot for each relationship is left as None.
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