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
    """
    Create a lookup that maps each asset ID to its index in the provided list.

    Parameters:
        asset_ids (List[str]): Ordered sequence of asset IDs; the index reflects each ID's position in this list.

    Returns:
        Dict[str, int]: Dictionary mapping asset ID -> position index.
    """
    return {asset_id: idx for idx, asset_id in enumerate(asset_ids)}


def _validate_graph_relationships_structure(
    graph: AssetRelationshipGraph,
) -> None:
    """
    Ensure the provided graph is an AssetRelationshipGraph and that it exposes a `relationships` dictionary.

    Parameters:
        graph (AssetRelationshipGraph): The graph object to validate.

    Raises:
        TypeError: If `graph` is not an AssetRelationshipGraph instance or if `graph.relationships` is not a dict.
        ValueError: If `graph` does not have a `relationships` attribute.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(f"graph must be an AssetRelationshipGraph instance, got {type(graph).__name__}")
    if not hasattr(graph, "relationships"):
        raise ValueError("graph is missing 'relationships' attribute")
    if not isinstance(graph.relationships, dict):
        raise TypeError(f"graph.relationships must be a dictionary, got {type(graph.relationships).__name__}")


def _normalize_asset_ids(asset_ids: Iterable[str]) -> Set[str]:
    """
    Return a set of unique asset IDs after validating that the input is an iterable of strings.

    Parameters:
        asset_ids: Iterable of asset ID values to normalize.

    Returns:
        A set containing the unique asset ID strings from the input.

    Raises:
        TypeError: If `asset_ids` is not iterable.
        ValueError: If any element in `asset_ids` is not a string.
    """
    try:
        asset_ids_set: Set[str] = set(asset_ids)
    except TypeError as exc:
        raise TypeError(f"asset_ids must be an iterable, got {type(asset_ids).__name__}") from exc
    if not all(isinstance(aid, str) for aid in asset_ids_set):
        raise ValueError("asset_ids must contain only string values")
    return asset_ids_set


def _get_relevant_relationships(
    graph: AssetRelationshipGraph,
    asset_ids_set: Set[str],
) -> Dict[str, List[Tuple[object, object, object]]]:
    """
    Map source asset IDs in asset_ids_set to copies of their relationship lists from the graph.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing a `relationships` mapping keyed by source asset ID.
        asset_ids_set (Set[str]): Set of source asset IDs to include.

    Returns:
        Dict[str, List[Tuple[object, object, object]]]: A mapping from each source_id present in asset_ids_set to a shallow-copied list of its relationship tuples `(target_id, rel_type, strength)`.
    """
    with _graph_access_lock:
        return {src: list(rels) for src, rels in graph.relationships.items() if src in asset_ids_set}


def _parse_relationship_record(
    source_id: str,
    idx: int,
    rel: object,
) -> Tuple[str, str, float]:
    """
    Validate and normalize a single raw relationship entry.

    Parameters:
        source_id (str): The originating asset identifier for error context.
        idx (int): Index of the relationship in the source's relationship list for error context.
        rel (object): Raw relationship record expected to be a 3-tuple (target_id, rel_type, strength).

    Returns:
        tuple: (target_id, rel_type, strength_float) where `target_id` and `rel_type` are strings and `strength_float` is the relationship strength converted to a float.
    """
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
    """
    Unpack and validate a raw relationship entry for a given source.

    Parameters:
        source_id (str): Source asset identifier used in error messages.
        idx (int): Index of the relationship within the source's relationship list, used in error messages.
        rel (object): Raw relationship entry expected to be a 3-element list or tuple
            in the form (target_id, rel_type, strength).

    Returns:
        tuple: A 3-tuple (target_id, rel_type, strength) extracted from `rel`.

    Raises:
        ValueError: If `rel` is not a list or tuple of length 3.
    """
    if isinstance(rel, (list, tuple)) and len(rel) == 3:
        return rel[0], rel[1], rel[2]
    raise ValueError(
        f"relationship at index {idx} for '{source_id}' must be a 3-element tuple (target_id, rel_type, strength)"
    )


def _require_str(
    *,
    value: object,
    field: str,
    source_id: str,
    idx: int,
) -> str:
    """
    Ensure the provided value is a string and return it.

    Parameters:
        value (object): The value to validate.
        field (str): Field name included in the error message when validation fails.
        source_id (str): Relationship source identifier included in the error message.
        idx (int): Relationship entry index included in the error message.

    Returns:
        str: The validated string value.

    Raises:
        TypeError: If `value` is not a `str`. The exception message includes `field`, `idx`, and `source_id`.
    """
    if isinstance(value, str):
        return value
    raise TypeError(f"{field} at index {idx} for '{source_id}' must be a string")


def _coerce_strength(
    *,
    value: object,
    source_id: str,
    idx: int,
) -> float:
    """
    Converts a relationship strength to a float.

    If conversion fails, raises ValueError that includes the relationship index and source_id.

    Parameters:
        value: The numeric-like value to convert.
        source_id: Source asset identifier included in the error message.
        idx: Index of the relationship entry included in the error message.

    Returns:
        The strength as a float.

    Raises:
        ValueError: If `value` cannot be converted to a float; message includes `idx` and `source_id`.
    """
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"strength at index {idx} for '{source_id}' must be numeric") from exc


def _build_relationship_index(
    graph: AssetRelationshipGraph, asset_ids: Iterable[str]
) -> Dict[Tuple[str, str, str], float]:
    """
    Build a lookup mapping of (source_id, target_id, rel_type) to relationship strength for the specified assets.

    Only relationships whose source and target are both present in the provided asset_ids are included.

    Parameters:
        graph (AssetRelationshipGraph): Graph object containing a 'relationships' mapping.
        asset_ids (Iterable[str]): Iterable of asset IDs to include in the index.

    Returns:
        Dict[Tuple[str, str, str], float]: Mapping from (source_id, target_id, rel_type) to the relationship strength as a float.

    Raises:
        TypeError: If `graph` or `asset_ids` are of invalid types.
        ValueError: If relationship entries are malformed or cannot be parsed.
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
    """
    Validate and add relationships for a single source asset into the provided relationship index.

    Mutates `relationship_index` in place by inserting entries with keys `(source_id, target_id, rel_type)`
    and values equal to the relationship strength (float). Only relationships whose `target_id` is present
    in `asset_ids_set` are stored.

    Parameters:
        source_id (str): The source asset identifier whose relationships are being processed.
        rels (object): A list or tuple of relationship records; each record must be a 3-element sequence
            (target_id, rel_type, strength). Elements are validated and coerced by the parser.
        asset_ids_set (Set[str]): Set of known asset IDs used to filter which targets are stored.
        relationship_index (Dict[Tuple[str, str, str], float]): Mapping to update; keys are
            `(source_id, target_id, rel_type)` and values are the relationship strength.

    Raises:
        TypeError: If `rels` is not a list or tuple.
    """
    if not isinstance(rels, (list, tuple)):
        raise TypeError(f"relationships for '{source_id}' must be a list or tuple, got {type(rels).__name__}")
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
    """
    Insert a parsed relationship into the relationship index if the relationship's target asset is in the provided asset set.

    Parameters:
        source_id (str): The source asset identifier for the relationship.
        relationship (Tuple[str, str, float]): Parsed relationship tuple (target_id, relationship_type, strength).
        asset_ids_set (Set[str]): Allowed asset identifiers; the relationship is stored only if target_id is a member.
        relationship_index (Dict[Tuple[str, str, str], float]): Mapping to populate where keys are (source_id, target_id, relationship_type) and values are strength.
    """
    target_id, rel_type, strength_float = relationship
    if target_id not in asset_ids_set:
        return
    relationship_index[(source_id, target_id, rel_type)] = strength_float


def _collect_and_group_relationships(
    graph: AssetRelationshipGraph,
    asset_ids: Iterable[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> Dict[Tuple[str, bool], List[dict]]:
    """
    Group relationships from the graph by relationship type and whether each pair is bidirectional.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing a `relationships` mapping.
        asset_ids (Iterable[str]): Iterable of asset IDs to include when collecting relationships.
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping of relationship type to enabled state;
            a type present with value False will be excluded.

    Returns:
        Dict[Tuple[str, bool], List[dict]]: Mapping where each key is `(rel_type, is_bidirectional)` and each
        value is a list of relationship dictionaries. Each relationship dictionary contains:
            - "source_id" (str): source asset ID
            - "target_id" (str): target asset ID
            - "strength" (float): numeric strength of the relationship
    """
    relationship_index = _build_relationship_index(graph, asset_ids)

    processed_pairs: Set[Tuple[str, str, str]] = set()
    relationship_groups: Dict[Tuple[str, bool], List[dict]] = defaultdict(list)

    for relationship_key, strength in relationship_index.items():
        source_id, target_id, rel_type = relationship_key
        if _is_filtered_relationship(rel_type, relationship_filters):
            continue

        pair_key: Tuple[str, str, str] = (
            (source_id, target_id, rel_type) if source_id <= target_id else (target_id, source_id, rel_type)
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
    """
    Determine whether a relationship type is disabled by the provided filters.

    Parameters:
        relationship_filters (Optional[Dict[str, bool]]): Mapping from relationship type to enabled flag; a value of `False` disables that type. If `None`, no types are filtered.

    Returns:
        `true` if `rel_type` is present in `relationship_filters` and set to `False`, `false` otherwise.
    """
    if relationship_filters is None:
        return False
    return rel_type in relationship_filters and not relationship_filters[rel_type]


def _is_processed_bidirectional_pair(
    *,
    pair_key: Tuple[str, str, str],
    is_bidirectional: bool,
    processed_pairs: Set[Tuple[str, str, str]],
) -> bool:
    """
    Check whether a bidirectional relationship pair has already been recorded as processed.

    Parameters:
        pair_key (Tuple[str, str, str]): Canonical relationship key used in processed_pairs.
        is_bidirectional (bool): Whether the current relationship is bidirectional.
        processed_pairs (Set[Tuple[str, str, str]]): Set of canonical relationship keys that have been processed.

    Returns:
        `True` if `is_bidirectional` is `True` and `pair_key` exists in `processed_pairs`, `False` otherwise.
    """
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
    """
    Prepare x, y, and z coordinate lists for plotting edges where each edge occupies three consecutive slots.

    Parameters:
        relationships (List[dict]): Sequence of relationship dicts; each must contain 'source_id' and 'target_id' keys.
        positions (np.ndarray): Array of node positions with shape (num_nodes, 3); columns are x, y, z.
        asset_id_index (Dict[str, int]): Mapping from asset ID to its row index in `positions`.

    Returns:
        edges_x (List[Optional[float]]): Flat list of x coordinates of length `len(relationships) * 3`. For each relationship i, positions are assigned at indices [3*i, 3*i+1]; index 3*i+2 is left as None (separator).
        edges_y (List[Optional[float]]): Flat list of y coordinates with the same layout as `edges_x`.
        edges_z (List[Optional[float]]): Flat list of z coordinates with the same layout as `edges_x`.
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


def _build_hover_texts(
    relationships: List[dict],
    rel_type: str,
    is_bidirectional: bool,
) -> List[Optional[str]]:
    """
    Construct hover text entries for a group of relationships.

    Each relationship in `relationships` must be a dict containing the keys
    `'source_id'`, `'target_id'`, and `'strength'`. The produced hover text
    for each relationship uses the provided `rel_type` and a direction symbol
    ("↔" when `is_bidirectional` is True, otherwise "→"), and formats the
    strength to two decimal places.

    Parameters:
        relationships (List[dict]): List of relationship dictionaries with keys
            `'source_id'` (str), `'target_id'` (str), and `'strength'` (numeric).
        rel_type (str): The relationship type label to include in each hover text.
        is_bidirectional (bool): If True use the bidirectional symbol in the text.

    Returns:
        List[Optional[str]]: A list of length `len(relationships) * 3` where, for
        each relationship at index `i`, the entries at positions `3*i` and
        `3*i + 1` contain the hover text string and position `3*i + 2` is `None`.
    """
    direction = "↔" if is_bidirectional else "→"
    n = len(relationships)
    hover_texts: List[Optional[str]] = [None] * (n * 3)

    for i, rel in enumerate(relationships):
        text = (
            f"{rel['source_id']} {direction} {rel['target_id']}<br>Type: {rel_type}<br>Strength: {rel['strength']:.2f}"
        )
        base = i * 3
        hover_texts[base] = text
        hover_texts[base + 1] = text

    return hover_texts
