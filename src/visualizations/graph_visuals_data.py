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
    """Build a (source, target, rel_type) → strength index for the given asset IDs.

    Only relationships where both endpoints are in *asset_ids* are included.

    Raises:
        TypeError: If graph or asset_ids types are invalid.
        ValueError: If relationship data is malformed.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(
            f"graph must be an AssetRelationshipGraph instance, "
            f"got {type(graph).__name__}"
        )
    if not hasattr(graph, "relationships"):
        raise ValueError("graph is missing 'relationships' attribute")
    if not isinstance(graph.relationships, dict):
        raise TypeError(
            f"graph.relationships must be a dictionary, "
            f"got {type(graph.relationships).__name__}"
        )

    try:
        asset_ids_set: Set[str] = set(asset_ids)
    except TypeError as exc:
        raise TypeError(
            f"asset_ids must be an iterable, got {type(asset_ids).__name__}"
        ) from exc

    if not all(isinstance(aid, str) for aid in asset_ids_set):
        raise ValueError("asset_ids must contain only string values")

    with _graph_access_lock:
        relevant_relationships = {
            src: list(rels)
            for src, rels in graph.relationships.items()
            if src in asset_ids_set
        }

    relationship_index: Dict[Tuple[str, str, str], float] = {}
    for source_id, rels in relevant_relationships.items():
        if not isinstance(rels, (list, tuple)):
            raise TypeError(
                f"relationships for '{source_id}' must be a list or tuple, "
                f"got {type(rels).__name__}"
            )
        for idx, rel in enumerate(rels):
            if not isinstance(rel, (list, tuple)) or len(rel) != 3:
                raise ValueError(
                    f"relationship at index {idx} for '{source_id}' "
                    f"must be a 3-element tuple (target_id, rel_type, strength)"
                )
            target_id, rel_type, strength = rel
            if not isinstance(target_id, str):
                raise TypeError(
                    f"target_id at index {idx} for '{source_id}' must be a string"
                )
            if not isinstance(rel_type, str):
                raise TypeError(
                    f"rel_type at index {idx} for '{source_id}' must be a string"
                )
            try:
                strength_float = float(strength)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"strength at index {idx} for '{source_id}' must be numeric"
                ) from exc
            if target_id in asset_ids_set:
                relationship_index[(source_id, target_id, rel_type)] = strength_float

    return relationship_index


def _collect_and_group_relationships(
    graph: AssetRelationshipGraph,
    asset_ids: Iterable[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> Dict[Tuple[str, bool], List[dict]]:
    """Collect relationships in one pass and group by (rel_type, is_bidirectional)."""
    relationship_index = _build_relationship_index(graph, asset_ids)

    processed_pairs: Set[Tuple[str, str, str]] = set()
    relationship_groups: Dict[Tuple[str, bool], List[dict]] = defaultdict(list)

    for (source_id, target_id, rel_type), strength in relationship_index.items():
        if (
            relationship_filters
            and rel_type in relationship_filters
            and not relationship_filters[rel_type]
        ):
            continue

        pair_key: Tuple[str, str, str] = (
            (source_id, target_id, rel_type)
            if source_id <= target_id
            else (target_id, source_id, rel_type)
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
    """Build x/y/z coordinate lists for edge traces using pre-allocated arrays."""
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


def _build_hover_texts(
    relationships: List[dict], rel_type: str, is_bidirectional: bool
) -> List[Optional[str]]:
    """Build pre-allocated hover text list for a relationship group."""
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
