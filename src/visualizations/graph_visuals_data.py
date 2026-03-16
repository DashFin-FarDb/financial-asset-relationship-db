"""Data-preparation helpers for graph visualization pipelines."""

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


def _validate_graph_relationships_structure(
    graph: AssetRelationshipGraph,
) -> None:
    """Validate graph type and relationships container."""
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(
            f"graph must be an AssetRelationshipGraph instance, "
            f"got {type(graph).__name__}"
        )
    if not hasattr(graph, "relationships"):
        raise ValueError("graph is missing 'relationships' attribute")
    if not isinstance(graph.relationships, dict):
        raise TypeError(
            "graph.relationships must be a dictionary, "
            f"got {type(graph.relationships).__name__}"
        )


def _normalize_asset_ids(asset_ids: Iterable[str]) -> Set[str]:
    """Normalize and validate iterable asset IDs."""
    try:
        asset_ids_set: Set[str] = set(asset_ids)
    except TypeError as exc:
        raise TypeError(
            "asset_ids must be an iterable, "
            f"got {type(asset_ids).__name__}"
        ) from exc
    if not all(isinstance(aid, str) for aid in asset_ids_set):
        raise ValueError("asset_ids must contain only string values")
    return asset_ids_set


def _get_relevant_relationships(
    graph: AssetRelationshipGraph,
    asset_ids_set: Set[str],
) -> Dict[str, List[Tuple[object, object, object]]]:
    """Copy source relationships for provided asset IDs."""
    with _graph_access_lock:
        return {
            src: list(rels)
            for src, rels in graph.relationships.items()
            if src in asset_ids_set
        }


def _parse_relationship_record(
    source_id: str,
    idx: int,
    rel: object,
) -> Tuple[str, str, float]:
    """Parse and validate one relationship tuple."""
    target_id, rel_type, strength = _unpack_relationship_tuple(
        source_id=source_id,
        idx=idx,
        rel=rel,
    )
    target = _require_str(
        value=target_id,
        field="target_id",
        source_id=source_id,
        idx=idx,
    )
    relationship_type = _require_str(
        value=rel_type,
        field="rel_type",
        source_id=source_id,
        idx=idx,
    )
    strength_float = _coerce_strength(
        value=strength,
        source_id=source_id,
        idx=idx,
    )
    return target, relationship_type, strength_float


def _unpack_relationship_tuple(
    source_id: str,
    idx: int,
    rel: object,
) -> Tuple[object, object, object]:
    """Validate and unpack a raw relationship tuple."""
    if isinstance(rel, (list, tuple)) and len(rel) == 3:
        return rel[0], rel[1], rel[2]
    raise ValueError(
        f"relationship at index {idx} for '{source_id}' "
        "must be a 3-element tuple (target_id, rel_type, strength)"
    )


def _require_str(
    *,
    value: object,
    field: str,
    source_id: str,
    idx: int,
) -> str:
    """Return value when it is a string, otherwise raise."""
    if isinstance(value, str):
        return value
    raise TypeError(
        f"{field} at index {idx} for '{source_id}' must be a string"
    )


def _coerce_strength(
    *,
    value: object,
    source_id: str,
    idx: int,
) -> float:
    """Convert numeric-like strength value to float."""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"strength at index {idx} for '{source_id}' must be numeric"
        ) from exc


def _build_relationship_index(
    graph: AssetRelationshipGraph, asset_ids: Iterable[str]
) -> Dict[Tuple[str, str, str], float]:
    """Build a (source, target, rel_type) strength index for given assets.

    Only relationships where both endpoints are in *asset_ids* are included.

    Raises:
        TypeError: If graph or asset_ids types are invalid.
        ValueError: If relationship data is malformed.
    """
    _validate_graph_relationships_structure(graph)
    asset_ids_set = _normalize_asset_ids(asset_ids)
    relevant_relationships = _get_relevant_relationships(graph, asset_ids_set)

    relationship_index: Dict[Tuple[str, str, str], float] = {}
    for source_id, rels in relevant_relationships.items():
        _accumulate_source_relationships(
            source_id=source_id,
            rels=rels,
            asset_ids_set=asset_ids_set,
            relationship_index=relationship_index,
        )

    return relationship_index


def _accumulate_source_relationships(
    *,
    source_id: str,
    rels: object,
    asset_ids_set: Set[str],
    relationship_index: Dict[Tuple[str, str, str], float],
) -> None:
    """Validate and add one source node's relationships into the index."""
    if not isinstance(rels, (list, tuple)):
        raise TypeError(
            f"relationships for '{source_id}' must be a list or tuple, "
            f"got {type(rels).__name__}"
        )
    for idx, rel in enumerate(rels):
        target_id, rel_type, strength_float = _parse_relationship_record(
            source_id=source_id,
            idx=idx,
            rel=rel,
        )
        _store_relationship_if_target_known(
            source_id=source_id,
            relationship=(target_id, rel_type, strength_float),
            asset_ids_set=asset_ids_set,
            relationship_index=relationship_index,
        )


def _store_relationship_if_target_known(
    *,
    source_id: str,
    relationship: Tuple[str, str, float],
    asset_ids_set: Set[str],
    relationship_index: Dict[Tuple[str, str, str], float],
) -> None:
    """Store relationship only when target is part of requested assets."""
    target_id, rel_type, strength_float = relationship
    if target_id not in asset_ids_set:
        return
    relationship_index[(source_id, target_id, rel_type)] = strength_float


def _collect_and_group_relationships(
    graph: AssetRelationshipGraph,
    asset_ids: Iterable[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> Dict[Tuple[str, bool], List[dict]]:
    """Collect relationships and group by `(rel_type, is_bidirectional)`."""
    relationship_index = _build_relationship_index(graph, asset_ids)

    processed_pairs: Set[Tuple[str, str, str]] = set()
    relationship_groups: Dict[Tuple[str, bool], List[dict]] = defaultdict(list)

    for relationship_key, strength in relationship_index.items():
        source_id, target_id, rel_type = relationship_key
        if _is_filtered_relationship(rel_type, relationship_filters):
            continue

        pair_key: Tuple[str, str, str] = (
            (source_id, target_id, rel_type)
            if source_id <= target_id
            else (target_id, source_id, rel_type)
        )
        is_bidirectional = (
            target_id,
            source_id,
            rel_type,
        ) in relationship_index

        if _is_processed_bidirectional_pair(
            pair_key=pair_key,
            is_bidirectional=is_bidirectional,
            processed_pairs=processed_pairs,
        ):
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


def _is_filtered_relationship(
    rel_type: str,
    relationship_filters: Optional[Dict[str, bool]],
) -> bool:
    """Return True when a relationship type is explicitly disabled."""
    if relationship_filters is None:
        return False
    return (
        rel_type in relationship_filters
        and not relationship_filters[rel_type]
    )


def _is_processed_bidirectional_pair(
    *,
    pair_key: Tuple[str, str, str],
    is_bidirectional: bool,
    processed_pairs: Set[Tuple[str, str, str]],
) -> bool:
    """Return True when a bidirectional pair was already handled."""
    return is_bidirectional and pair_key in processed_pairs


def _build_edge_coordinates_optimized(
    relationships: List[dict],
    positions: np.ndarray,
    asset_id_index: Dict[str, int],
) -> Tuple[
    List[Optional[float]],
    List[Optional[float]],
    List[Optional[float]],
]:
    """Build x/y/z coordinate lists for edge traces."""
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
    relationships: List[dict],
    rel_type: str,
    is_bidirectional: bool,
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
