"""Core 3D graph visualization orchestration and rendering helpers."""

import logging
import re
import threading
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

import numpy as np
import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph

logger = logging.getLogger(__name__)

# Thread lock for protecting concurrent access to graph.relationships
_graph_access_lock = threading.RLock()

# Color and style mapping for relationship types (shared constant)
REL_TYPE_COLORS = defaultdict(
    lambda: "#888888",
    {
        "same_sector": "#FF6B6B",  # Red for sector relationships
        "market_cap_similar": "#4ECDC4",  # Teal for market cap
        "correlation": "#45B7D1",  # Blue for correlations
        "corporate_bond_to_equity": "#96CEB4",  # Green for corporate bonds
        "commodity_currency": "#FFEAA7",  # Yellow for commodity-currency
        "income_comparison": "#DDA0DD",  # Plum for income comparisons
        "regulatory_impact": "#FFA07A",  # Light salmon for regulatory
    },
)


def _is_valid_color_format(color: str) -> bool:
    """Validate if a string is a valid color format.

    Supports common color formats:
    - Hex colors (#RGB, #RRGGBB, #RRGGBBAA)
    - RGB/RGBA (e.g., 'rgb(255,0,0)', 'rgba(255,0,0,0.5)')
    - Named colors (delegated to Plotly)

    Args:
        color: Color string to validate

    Returns:
        True if color format is valid, False otherwise
    """
    if not isinstance(color, str) or not color:
        return False

    # Hex colors
    if re.match(r"^#(?:[0-9A-Fa-f]{3}){1,2}(?:[0-9A-Fa-f]{2})?$", color):
        return True

    # rgb/rgba functions
    rgb_or_rgba_pattern = r"^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*" r"(,\s*[\d.]+\s*)?\)$"
    if re.match(rgb_or_rgba_pattern, color):
        return True

    # Fallback: allow named colors; Plotly will validate at render time
    return True


def _build_asset_id_index(asset_ids: List[str]) -> Dict[str, int]:
    """Build O(1) lookup index for asset IDs to their positions."""
    return {asset_id: idx for idx, asset_id in enumerate(asset_ids)}


def _build_relationship_index(
    graph: AssetRelationshipGraph, asset_ids: Iterable[str]
) -> Dict[Tuple[str, str, str], float]:
    """
    Build an index of relationships limited to the provided asset IDs.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing a `relationships` mapping.
        asset_ids (Iterable[str]): Asset IDs to include; only relationships where both source and target are in this set are indexed.

    Returns:
        Dict[Tuple[str, str, str], float]: Mapping from (source_id, target_id, rel_type) to relationship strength as a float.
    """
    _validate_graph_for_relationship_index(graph)
    asset_ids_set = _normalize_asset_ids_for_index(asset_ids)
    relevant_relationships = _snapshot_relevant_relationships(
        graph,
        asset_ids_set,
    )

    relationship_index: Dict[Tuple[str, str, str], float] = {}
    for source_id, rels in relevant_relationships.items():
        _validate_source_relationships(source_id, rels)
        for idx, rel in enumerate(rels):
            target_id, rel_type, strength_float = _parse_relationship_entry(
                source_id=source_id,
                idx=idx,
                rel=rel,
            )
            if target_id in asset_ids_set:
                relationship_index[(source_id, target_id, rel_type)] = strength_float

    return relationship_index


def _validate_graph_for_relationship_index(
    graph: AssetRelationshipGraph,
) -> None:
    """
    Validate that `graph` is an AssetRelationshipGraph and that it exposes a dictionary-like `relationships` attribute.

    Raises:
        TypeError: If `graph` is not an instance of `AssetRelationshipGraph`.
        ValueError: If `graph` does not have a `relationships` attribute.
        TypeError: If `graph.relationships` exists but is not a `dict`.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(f"Invalid input: graph must be an AssetRelationshipGraph instance, got {type(graph).__name__}")
    if not hasattr(graph, "relationships"):
        raise ValueError("Invalid graph: missing 'relationships' attribute")
    if not isinstance(graph.relationships, dict):
        raise TypeError(
            f"Invalid graph data: graph.relationships must be a dictionary, got {type(graph.relationships).__name__}"
        )


def _normalize_asset_ids_for_index(
    asset_ids: Iterable[str],
) -> set[str]:
    """
    Normalize an iterable of asset IDs into a set of unique asset ID strings.

    Validates that the provided input is iterable and that every element is a string.

    Parameters:
        asset_ids (Iterable[str]): Iterable of asset identifier values.

    Returns:
        set[str]: A set containing the unique asset ID strings.

    Raises:
        TypeError: If `asset_ids` is not an iterable.
        ValueError: If any element in `asset_ids` is not a string.
    """
    try:
        asset_ids_set = set(asset_ids)
    except TypeError as exc:
        raise TypeError(f"Invalid input: asset_ids must be an iterable, got {type(asset_ids).__name__}") from exc
    if not all(isinstance(aid, str) for aid in asset_ids_set):
        raise ValueError("Invalid input: asset_ids must contain only string values")
    return asset_ids_set


def _snapshot_relevant_relationships(
    graph: AssetRelationshipGraph,
    asset_ids_set: set[str],
) -> Dict[str, list]:
    """
    Return a snapshot of graph.relationships limited to the provided asset IDs.

    This function captures the relationships mapping while holding the module-level access lock to ensure a consistent view.

    Parameters:
        graph (AssetRelationshipGraph): Graph object exposing a `relationships` mapping.
        asset_ids_set (set[str]): Set of source asset IDs to include in the snapshot.

    Returns:
        Dict[str, list]: A dictionary mapping each source_id in `asset_ids_set` to a shallow-copied list of its relationship entries.

    Raises:
        ValueError: If the snapshot cannot be created due to an unexpected error.
    """
    with _graph_access_lock:
        try:
            return {
                source_id: list(rels) for source_id, rels in graph.relationships.items() if source_id in asset_ids_set
            }
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError(f"Failed to create snapshot of graph.relationships: {exc}") from exc


def _validate_source_relationships(
    source_id: str,
    rels: list,
) -> None:
    """
    Ensure the relationship container for a source is a list or tuple.

    Parameters:
        source_id (str): Source asset identifier used in error messages.
        rels (list | tuple): Relationship collection to validate.

    Raises:
        TypeError: If `rels` is not a list or tuple; message includes `source_id` and the actual type.
    """
    if isinstance(rels, (list, tuple)):
        return
    raise TypeError(
        "Invalid graph data: relationships for source_id "
        f"'{source_id}' must be a list or tuple, "
        f"got {type(rels).__name__}"
    )


def _parse_relationship_entry(
    *,
    source_id: str,
    idx: int,
    rel: object,
) -> Tuple[str, str, float]:
    """
    Parse and validate a single relationship entry for a given source asset.

    Parameters:
        source_id (str): The originating asset identifier used in error messages.
        idx (int): The index of the relationship entry within the source's relationships list (used in error messages).
        rel (object): The relationship entry; must be a list or tuple of three elements: (target_id, rel_type, strength).

    Returns:
        tuple: A 3-tuple (target_id, rel_type, strength) where `target_id` and `rel_type` are strings and `strength` is a float.

    Raises:
        TypeError: If `rel` is not a list/tuple or if `target_id`/`rel_type` are not strings.
        ValueError: If `rel` does not contain exactly three elements or if `strength` cannot be converted to float.
    """
    if not isinstance(rel, (list, tuple)):
        raise TypeError(
            "Invalid graph data: relationship at index "
            f"{idx} for source_id '{source_id}' must be a list or tuple, "
            f"got {type(rel).__name__}"
        )
    if len(rel) != 3:
        raise ValueError(
            "Invalid graph data: relationship at index "
            f"{idx} for source_id '{source_id}' must have exactly 3 "
            "elements (target_id, rel_type, strength), "
            f"got {len(rel)} elements"
        )
    target_id, rel_type, strength = rel
    _ensure_string_relationship_field(
        field_name="target_id",
        value=target_id,
        source_id=source_id,
        idx=idx,
    )
    _ensure_string_relationship_field(
        field_name="rel_type",
        value=rel_type,
        source_id=source_id,
        idx=idx,
    )
    return (
        str(target_id),
        str(rel_type),
        _to_float_strength(
            strength=strength,
            source_id=source_id,
            idx=idx,
        ),
    )


def _ensure_string_relationship_field(
    *,
    field_name: str,
    value: object,
    source_id: str,
    idx: int,
) -> None:
    """
    Validate that a relationship field value is a string.

    Parameters:
        field_name (str): Name of the relationship field being validated (e.g., "target_id" or "rel_type").
        value (object): Value to validate.
        source_id (str): Source asset identifier used to provide context in error messages.
        idx (int): Index of the relationship entry within the source's relationship list used in error messages.

    Raises:
        TypeError: If `value` is not a `str`. The error message includes `field_name`, `idx`, and `source_id`.
    """
    if isinstance(value, str):
        return
    raise TypeError(
        "Invalid graph data: "
        f"{field_name} at index {idx} for source_id "
        f"'{source_id}' must be a string, got {type(value).__name__}"
    )


def _to_float_strength(
    *,
    strength: object,
    source_id: str,
    idx: int,
) -> float:
    """
    Convert a relationship strength value to a float.

    Parameters:
        strength (object): The value to convert; must represent a numeric value.
        source_id (str): Source asset identifier used in error messages.
        idx (int): Position index of the relationship entry used in error messages.

    Returns:
        float: The converted numeric strength.

    Raises:
        ValueError: If `strength` cannot be converted to float; the error message includes `source_id` and `idx`.
    """
    try:
        return float(strength)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Invalid graph data: strength at index "
            f"{idx} for source_id '{source_id}' must be numeric "
            f"(got {type(strength).__name__} with value '{strength}')"
        ) from exc


def _create_node_trace(
    positions: np.ndarray,
    asset_ids: List[str],
    colors: List[str],
    hover_texts: List[str],
) -> go.Scatter3d:
    """
    Create a Plotly 3D scatter trace representing asset nodes.

    Parameters:
        positions (np.ndarray): Array of shape (n, 3) with finite numeric x,y,z coordinates.
        asset_ids (List[str]): Sequence of n non-empty asset identifier strings.
        colors (List[str]): Sequence of n color strings (hex, rgb/rgba, or named colors) used for markers.
        hover_texts (List[str]): Sequence of n hover text strings shown for each node.

    Returns:
        go.Scatter3d: A configured Scatter3d trace with markers and labels for the provided assets.

    Raises:
        ValueError: If inputs are invalid, have mismatched lengths, contain non-finite coordinates, or otherwise fail validation.
    """
    # Input validation: basic type checks before comprehensive validator.
    # This provides early failure with clear error messages for common mistakes
    if not isinstance(positions, np.ndarray):
        raise ValueError(f"positions must be a numpy array, got {type(positions).__name__}")
    if not isinstance(asset_ids, (list, tuple)):
        raise ValueError(f"asset_ids must be a list or tuple, got {type(asset_ids).__name__}")
    if not isinstance(colors, (list, tuple)):
        raise ValueError(f"colors must be a list or tuple, got {type(colors).__name__}")
    if not isinstance(hover_texts, (list, tuple)):
        raise ValueError(f"hover_texts must be a list or tuple, got {type(hover_texts).__name__}")

    # Validate dimensions and alignment before detailed validation
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(f"positions must have shape (n, 3), got {positions.shape}")
    if len(asset_ids) != len(colors) or len(asset_ids) != len(hover_texts):
        raise ValueError(
            f"Length mismatch: asset_ids({len(asset_ids)}), "
            f"colors({len(colors)}), "
            f"hover_texts({len(hover_texts)}) must all be equal"
        )
    if positions.shape[0] != len(asset_ids):
        raise ValueError(f"positions length ({positions.shape[0]}) must match asset_ids length ({len(asset_ids)})")

    # Comprehensive validation:
    # checks content, numeric types, and finite values.
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)

    # Edge case validation: Ensure inputs are not empty
    if len(asset_ids) == 0:
        raise ValueError("Cannot create node trace with empty inputs (asset_ids length is 0)")
    return go.Scatter3d(
        x=positions[:, 0],
        y=positions[:, 1],
        z=positions[:, 2],
        mode="markers+text",
        marker=dict(
            size=15,
            color=colors,
            opacity=0.9,
            line=dict(
                color="rgba(0,0,0,0.8)",
                width=2,
            ),
            symbol="circle",
        ),
        text=asset_ids,
        hovertext=hover_texts,
        hoverinfo="text",
        textposition="top center",
        textfont=dict(size=12, color="black"),
        name="Assets",
        visible=True,
    )


def _generate_dynamic_title(
    num_assets: int,
    num_relationships: int,
    base_title: str = "Financial Asset Network",
) -> str:
    """
    Generate a visualization title that includes the provided base title and the counts of assets and relationships.

    Parameters:
        num_assets (int): Count of assets included in the visualization.
        num_relationships (int): Count of relationships included in the visualization.
        base_title (str): Base title text to prefix the counts (default: "Financial Asset Network").

    Returns:
        title (str): Combined title string in the form "<base_title> - <num_assets> Assets, <num_relationships> Relationships".
    """
    return f"{base_title} - {num_assets} Assets, {num_relationships} Relationships"


def _calculate_visible_relationships(
    relationship_traces: List[go.Scatter3d],
) -> int:
    """
    Compute the number of visible relationship edges represented by the provided relationship traces.

    Counts edges by summing the number of x-coordinate entries across traces (each edge contributes three entries: start, end, separator). If counting fails, returns 0.

    Parameters:
        relationship_traces (List[go.Scatter3d]): Traces that represent relationship edges.

    Returns:
        int: Number of visible relationship edges.
    """
    try:
        return sum(len(getattr(trace, "x", []) or []) for trace in relationship_traces) // 3
    except Exception:  # pylint: disable=broad-except
        return 0


def _prepare_layout_config(
    num_assets: int,
    relationship_traces: List[go.Scatter3d],
    base_title: str = "Financial Asset Network",
    layout_options: Optional[Dict[str, object]] = None,
) -> Tuple[str, Dict[str, object]]:
    """
    Prepare layout settings and a dynamic title for a 3D graph visualization.

    Parameters:
        num_assets (int): Number of assets shown in the visualization.
        relationship_traces (List[go.Scatter3d]): Relationship traces used to determine visible relationship count.
        base_title (str): Base title text to include in the dynamic title.
        layout_options (Optional[Dict[str, object]]): Optional layout overrides; returned as-is when provided.

    Returns:
        Tuple[str, Dict[str, object]]:
            dynamic_title: A title string that incorporates asset and visible-relationship counts.
            layout_options: The layout options dictionary to apply (empty dict if none provided).
    """
    num_relationships = _calculate_visible_relationships(relationship_traces)
    dynamic_title = _generate_dynamic_title(
        num_assets,
        num_relationships,
        base_title,
    )
    options = layout_options or {}
    return dynamic_title, options


def _add_directional_arrows_to_figure(
    fig: go.Figure,
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> None:
    """Add directional arrows to the figure for unidirectional
    relationships using batch operations.
    """
    arrow_traces = _create_directional_arrows(graph, positions, asset_ids)
    if arrow_traces:
        fig.add_traces(arrow_traces)


def _configure_3d_layout(
    fig: go.Figure,
    title: str,
    options: Optional[Dict[str, object]] = None,
) -> None:
    """Configure the 3D layout for the figure.

    Args:
        fig: Target Plotly figure
        title: Title text
        options: Optional mapping to override defaults. Supported keys:
            - width(int)
            - height(int)
            - gridcolor(str)
            - bgcolor(str)
            - legend_bgcolor(str)
            - legend_bordercolor(str)
    """
    opts = options or {}
    width = int(opts.get("width", 1200))
    height = int(opts.get("height", 800))
    gridcolor = str(opts.get("gridcolor", "rgba(200, 200, 200, 0.3)"))
    bgcolor = str(opts.get("bgcolor", "rgba(248, 248, 248, 0.95)"))
    legend_bgcolor = str(opts.get("legend_bgcolor", "rgba(255, 255, 255, 0.8)"))
    legend_bordercolor = str(opts.get("legend_bordercolor", "rgba(0, 0, 0, 0.3)"))

    fig.update_layout(
        title={
            "text": title,
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 16},
        },
        scene=dict(
            xaxis=dict(title="Dimension 1", showgrid=True, gridcolor=gridcolor),
            yaxis=dict(title="Dimension 2", showgrid=True, gridcolor=gridcolor),
            zaxis=dict(title="Dimension 3", showgrid=True, gridcolor=gridcolor),
            bgcolor=bgcolor,
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5)),
        ),
        width=width,
        height=height,
        showlegend=True,
        hovermode="closest",
        legend=dict(
            x=0.02,
            y=0.98,
            bgcolor=legend_bgcolor,
            bordercolor=legend_bordercolor,
            borderwidth=1,
        ),
    )


def _validate_positions_array(positions: np.ndarray) -> None:
    """
    Ensure `positions` is a 2D numpy array of shape (n, 3) with numeric, finite values.

    Parameters:
        positions (np.ndarray): Array of 3D coordinates for assets; expected shape is (n, 3).

    Raises:
        ValueError: If `positions` is not a numpy array, does not have shape (n, 3),
                    contains non-numeric dtype, or contains NaN/Inf values (message includes counts).
    """
    if not isinstance(positions, np.ndarray):
        raise ValueError(f"Invalid graph data: positions must be a numpy array, got {type(positions).__name__}")
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(
            f"Invalid graph data: Expected positions to be a (n, 3) numpy array, got array with shape {positions.shape}"
        )
    if not np.issubdtype(positions.dtype, np.number):
        raise ValueError(f"Invalid graph data: positions must contain numeric values, got dtype {positions.dtype}")
    if not np.isfinite(positions).all():
        nan_count = int(np.isnan(positions).sum())
        inf_count = int(np.isinf(positions).sum())
        raise ValueError(
            "Invalid graph data: positions must contain finite values "
            "(no NaN or Inf). "
            f"Found {nan_count} NaN and {inf_count} Inf"
        )


def _validate_asset_ids_list(asset_ids: List[str]) -> None:
    """
    Validate that asset_ids is a list or tuple of non-empty strings.

    Parameters:
        asset_ids (List[str] | Tuple[str, ...]): Sequence of asset identifier strings to validate.

    Raises:
        ValueError: If `asset_ids` is not a list or tuple, or if any element is not a non-empty string.
    """
    if not isinstance(asset_ids, (list, tuple)):
        raise ValueError(f"Invalid graph data: asset_ids must be a list or tuple, got {type(asset_ids).__name__}")
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("Invalid graph data: asset_ids must contain non-empty strings")


def _validate_colors_list(colors: List[str], expected_length: int) -> None:
    """
    Validate that `colors` is a list or tuple of non-empty color strings of the required length and that each entry matches an acceptable color format.

    Parameters:
        colors (List[str]): Sequence of color strings to validate.
        expected_length (int): Required number of color entries.

    Raises:
        ValueError: If `colors` is not a list/tuple of length `expected_length`, if any element is not a non-empty string, or if any color string fails format validation.
    """
    if not isinstance(colors, (list, tuple)) or len(colors) != expected_length:
        colors_type = type(colors).__name__
        colors_len = len(colors) if isinstance(colors, (list, tuple)) else "N/A"
        raise ValueError(
            f"Invalid graph data: colors must be a list/tuple of "
            f"length {expected_length}, got {colors_type} "
            f"with length {colors_len}"
        )
    if not all(isinstance(c, str) and c for c in colors):
        raise ValueError("Invalid graph data: colors must contain non-empty strings")

    for i, color in enumerate(colors):
        if not _is_valid_color_format(color):
            raise ValueError(f"Invalid graph data: colors[{i}] has invalid color format: '{color}'")


def _validate_hover_texts_list(
    hover_texts: List[str],
    expected_length: int,
) -> None:
    """
    Validate that `hover_texts` is a list or tuple of non-empty strings with the expected length.

    Parameters:
        hover_texts (List[str]): Sequence of hover text strings for each asset.
        expected_length (int): Required number of hover text entries.

    Raises:
        ValueError: If `hover_texts` is not a list/tuple of length `expected_length`, or if any element is not a non-empty string.
    """
    if not isinstance(hover_texts, (list, tuple)) or len(hover_texts) != expected_length:
        raise ValueError(f"Invalid graph data: hover_texts must be a list/tuple of length {expected_length}")
    if not all(isinstance(h, str) and h for h in hover_texts):
        raise ValueError("Invalid graph data: hover_texts must contain non-empty strings")


def _validate_asset_ids_uniqueness(asset_ids: List[str]) -> None:
    """Validate that asset IDs are unique."""
    unique_count = len(set(asset_ids))
    if unique_count != len(asset_ids):
        seen_ids: Set[str] = set()
        dup_ids: List[str] = []
        for aid in asset_ids:
            if aid in seen_ids and aid not in dup_ids:
                dup_ids.append(aid)
            else:
                seen_ids.add(aid)
        dup_str = ", ".join(dup_ids)
        raise ValueError(f"Invalid graph data: duplicate asset_ids detected: {dup_str}")


def _validate_visualization_data(
    positions: np.ndarray,
    asset_ids: List[str],
    colors: List[str],
    hover_texts: List[str],
) -> None:
    """
    Validate 3D visualization inputs and ensure positions, asset IDs, colors, and hover texts are consistent.

    Parameters:
        positions (np.ndarray): An (n, 3) numeric array of 3D coordinates for n assets.
        asset_ids (List[str]): List of n non-empty asset identifier strings; must be unique.
        colors (List[str]): List of n color strings (hex, rgb/rgba, or named colors) for node styling.
        hover_texts (List[str]): List of n non-empty strings used as hover text for each asset.

    Raises:
        TypeError: If any input has an invalid type or an element has an unexpected type/format.
        ValueError: If array shapes or list lengths do not match, color/hover formats are invalid, or asset_ids are not unique.
    """
    _validate_positions_array(positions)
    _validate_asset_ids_list(asset_ids)

    n = len(asset_ids)
    if positions.shape[0] != n:
        raise ValueError(
            f"Invalid graph data: positions length ({positions.shape[0]}) must match asset_ids length ({n})"
        )

    _validate_colors_list(colors, n)
    _validate_hover_texts_list(hover_texts, n)
    _validate_asset_ids_uniqueness(asset_ids)


def visualize_3d_graph(graph: AssetRelationshipGraph) -> go.Figure:
    """
    Create a 3D Plotly figure visualizing assets and their relationships.

    Validates the provided graph, obtains enhanced visualization data from
    the graph, and assembles node markers, relationship traces, and optional
    directional arrow traces into a Plotly Figure with a dynamic title.

    Parameters:
        graph (AssetRelationshipGraph): Graph object that implements
            `get_3d_visualization_data_enhanced()` and exposes a relationships
            container used to build relationship traces and arrows.

    Returns:
        go.Figure: A Plotly 3D figure containing asset node markers, relationship
        traces (grouped by type and direction), optional directional arrows,
        and configured layout (axes, camera, legend, and a dynamic title).

    Raises:
        ValueError: If `graph` is not a valid AssetRelationshipGraph or if the
        visualization data returned by the graph is invalid.
    """
    if not isinstance(graph, AssetRelationshipGraph) or not hasattr(graph, "get_3d_visualization_data_enhanced"):
        raise ValueError("Invalid graph data provided")

    positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

    # Validate visualization data to prevent runtime errors
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)

    fig = go.Figure()

    # Create separate traces for different relationship types and directions
    try:
        relationship_traces = _create_relationship_traces(graph, positions, asset_ids)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to create relationship traces: %s", exc)
        relationship_traces = []

    # Batch add traces
    if relationship_traces:
        try:
            fig.add_traces(relationship_traces)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to add relationship traces to figure: %s", exc)

    # Add directional arrows for unidirectional relationships
    try:
        arrow_traces = _create_directional_arrows(graph, positions, asset_ids)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to create directional arrow traces: %s", exc)
        arrow_traces = []

    if arrow_traces:
        try:
            fig.add_traces(arrow_traces)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to add arrow traces to figure: %s", exc)

    # Add nodes with enhanced styling
    node_trace = _create_node_trace(positions, asset_ids, colors, hover_texts)
    fig.add_trace(node_trace)

    # Calculate total relationships for dynamic title
    total_relationships = sum(len(getattr(trace, "x", []) or []) for trace in relationship_traces) // 3
    dynamic_title = _generate_dynamic_title(len(asset_ids), total_relationships)

    fig.update_layout(
        title={
            "text": dynamic_title,
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 16},
        },
        scene=dict(
            xaxis=dict(
                title="Dimension 1",
                showgrid=True,
                gridcolor="rgba(200, 200, 200, 0.3)",
            ),
            yaxis=dict(
                title="Dimension 2",
                showgrid=True,
                gridcolor="rgba(200, 200, 200, 0.3)",
            ),
            zaxis=dict(
                title="Dimension 3",
                showgrid=True,
                gridcolor="rgba(200, 200, 200, 0.3)",
            ),
            bgcolor="rgba(248, 248, 248, 0.95)",
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5)),
        ),
        width=1200,
        height=800,
        showlegend=True,
        hovermode="closest",
        legend=dict(
            x=0.02,
            y=0.98,
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="rgba(0, 0, 0, 0.3)",
            borderwidth=1,
        ),
    )

    return fig


def _collect_and_group_relationships(
    graph: AssetRelationshipGraph,
    asset_ids: Iterable[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> Dict[Tuple[str, bool], List[dict]]:
    """
    Group graph relationships by type and bidirectionality for the given asset subset.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing relationships keyed by source asset id.
        asset_ids (Iterable[str]): Asset ids to include when collecting relationships.
        relationship_filters (Optional[Dict[str, bool]]): Optional map of relationship type to a boolean
            indicating whether that relationship type should be included; types present with `False`
            are excluded.

    Returns:
        Dict[Tuple[str, bool], List[dict]]: A mapping where each key is a tuple `(rel_type, is_bidirectional)`
        and the value is a list of relationship records. Each record is a dict with:
            - "source_id" (str): id of the relationship source
            - "target_id" (str): id of the relationship target
            - "strength" (float): numeric strength of the relationship

    Notes:
        - Bidirectional relationships are detected by presence of the reverse pair in the graph and
          grouped under `is_bidirectional = True`. Duplicate entries for the same bidirectional pair
          are avoided so each pair appears once in the grouped output.
    """
    relationship_index = _build_relationship_index(graph, asset_ids)

    processed_pairs: Set[Tuple[str, str, str]] = set()
    relationship_groups: Dict[Tuple[str, bool], List[dict]] = defaultdict(list)

    for (
        source_id,
        target_id,
        rel_type,
    ), strength in relationship_index.items():
        if relationship_filters and rel_type in relationship_filters and not relationship_filters[rel_type]:
            continue

        # Canonical pair key for bidirectional detection
        if source_id <= target_id:
            pair_key: Tuple[str, str, str] = (source_id, target_id, rel_type)
        else:
            pair_key = (target_id, source_id, rel_type)

        # Reverse lookup for bidirectionality
        is_bidirectional = (
            target_id,
            source_id,
            rel_type,
        ) in relationship_index

        # Avoid duplicate entries for bidirectional edges
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
) -> Tuple[
    List[Optional[float]],
    List[Optional[float]],
    List[Optional[float]],
]:
    """
    Build three parallel coordinate lists for Plotly edge segments using O(1) asset index lookups.

    Parameters:
        relationships (List[dict]): Sequence of relationship dicts each containing 'source_id' and 'target_id' keys.
        positions (np.ndarray): Nx3 array of asset 3D coordinates indexed by asset_id_index values.
        asset_id_index (Dict[str, int]): Mapping from asset_id to row index in `positions`.

    Returns:
        Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        Three lists (x, y, z) of length `len(relationships) * 3`. Each relationship occupies three consecutive entries:
        the source coordinate, the target coordinate, and a `None` separator (used to break segments when plotting).
    """
    num_edges = len(relationships)
    edges_x: List[Optional[float]] = [None] * (num_edges * 3)
    edges_y: List[Optional[float]] = [None] * (num_edges * 3)
    edges_z: List[Optional[float]] = [None] * (num_edges * 3)

    for i, rel in enumerate(relationships):
        source_idx = asset_id_index[rel["source_id"]]
        target_idx = asset_id_index[rel["target_id"]]

        base_idx = i * 3

        edges_x[base_idx] = positions[source_idx, 0]
        edges_x[base_idx + 1] = positions[target_idx, 0]

        edges_y[base_idx] = positions[source_idx, 1]
        edges_y[base_idx + 1] = positions[target_idx, 1]

        edges_z[base_idx] = positions[source_idx, 2]
        edges_z[base_idx + 1] = positions[target_idx, 2]

    return edges_x, edges_y, edges_z


def _build_hover_texts(
    relationships: List[dict],
    rel_type: str,
    is_bidirectional: bool,
) -> List[Optional[str]]:
    """
    Create hover text entries formatted for Plotly 3D line segments for a list of relationships.

    Parameters:
        relationships (List[dict]): List of relationship dicts with keys 'source_id', 'target_id', and 'strength'.
        rel_type (str): Human-readable relationship type used in each hover text.
        is_bidirectional (bool): When True uses a bidirectional symbol (↔); otherwise uses a unidirectional symbol (→).

    Returns:
        List[Optional[str]]: A list with length `3 * len(relationships)` where each relationship contributes three slots:
            - The first two slots contain the same formatted hover text: "<source> <arrow> <target><br>Type: <rel_type><br>Strength: <strength>"
            - The third slot is `None` (reserved for line segmentation in Plotly).
    """
    direction_text = "↔" if is_bidirectional else "→"

    num_rels = len(relationships)
    hover_texts: List[Optional[str]] = [None] * (num_rels * 3)

    for i, rel in enumerate(relationships):
        hover_text = (
            f"{rel['source_id']} {direction_text} {rel['target_id']}<br>"
            f"Type: {rel_type}<br>Strength: {rel['strength']:.2f}"
        )
        base_idx = i * 3
        hover_texts[base_idx] = hover_text
        hover_texts[base_idx + 1] = hover_text

    return hover_texts


def _get_line_style(rel_type: str, is_bidirectional: bool) -> dict:
    """
    Determine the line style for a relationship type, validating the configured color and falling back to gray when invalid.

    Parameters:
        rel_type (str): Relationship type key used to look up the configured color.
        is_bidirectional (bool): Whether the relationship is bidirectional.

    Returns:
        dict: Mapping with keys:
            color (str): Validated color string; defaults to "#888888" if the configured color format is invalid.
            width (int): 4 for bidirectional relationships, 2 otherwise.
            dash (str): "solid" for bidirectional relationships, "dash" otherwise.
    """
    color = REL_TYPE_COLORS[rel_type]
    if not _is_valid_color_format(color):
        logger.warning(
            "Invalid color format for relationship type '%s': '%s'. Using default gray.",
            rel_type,
            color,
        )
        color = "#888888"

    return dict(
        color=color,
        width=4 if is_bidirectional else 2,
        dash="solid" if is_bidirectional else "dash",
    )


def _format_trace_name(rel_type: str, is_bidirectional: bool) -> str:
    """Format trace name for legend."""
    base_name = rel_type.replace("_", " ").title()
    direction_symbol = " (↔)" if is_bidirectional else " (→)"
    return base_name + direction_symbol


def _create_trace_for_group(
    rel_type: str,
    is_bidirectional: bool,
    relationships: List[dict],
    positions: np.ndarray,
    asset_id_index: Dict[str, int],
) -> go.Scatter3d:
    """
    Builds a Plotly Scatter3d trace representing all edges for a single relationship type and directionality.

    Parameters:
        rel_type (str): Relationship type label used for naming and styling the trace.
        is_bidirectional (bool): If True, the trace represents bidirectional edges and will use bidirectional styling.
        relationships (List[dict]): List of relationship records; each dict contains at least `source_id`, `target_id`, and `strength`.
        positions (np.ndarray): Array of asset positions with shape (n_assets, 3).
        asset_id_index (Dict[str, int]): Mapping from asset_id to its row index in `positions`.

    Returns:
        go.Scatter3d: A configured Scatter3d trace whose coordinates, line style, name, and hover texts represent the group's edges.
    """
    edges_x, edges_y, edges_z = _build_edge_coordinates_optimized(
        relationships,
        positions,
        asset_id_index,
    )
    hover_texts = _build_hover_texts(relationships, rel_type, is_bidirectional)

    return go.Scatter3d(
        x=edges_x,
        y=edges_y,
        z=edges_z,
        mode="lines",
        line=_get_line_style(rel_type, is_bidirectional),
        hovertext=hover_texts,
        hoverinfo="text",
        name=_format_trace_name(rel_type, is_bidirectional),
        visible=True,
        legendgroup=rel_type,
    )


def _create_relationship_traces(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> List[go.Scatter3d]:
    """
    Create Plotly Scatter3d traces grouped by relationship type and direction for the given graph and assets.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing a dict-like `relationships` mapping sources to relationship entries.
        positions (np.ndarray): Array of shape (n, 3) giving 3D coordinates for each asset, ordered to match `asset_ids`.
        asset_ids (List[str]): List of asset identifiers corresponding to rows in `positions`.
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping of relationship type to a boolean indicating whether that type should be included; if None, all relationship types are considered.

    Returns:
        List[go.Scatter3d]: A list of Scatter3d traces, one per (relationship type, directionality) group, ready for batch addition to a Plotly figure.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise ValueError("Invalid input data: graph must be an AssetRelationshipGraph instance")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError("Invalid input data: graph must have a relationships dictionary")
    if not isinstance(positions, np.ndarray):
        raise ValueError("Invalid input data: positions must be a numpy array")
    if len(positions) != len(asset_ids):
        raise ValueError("Invalid input data: positions array length must match asset_ids length")

    asset_id_index = _build_asset_id_index(asset_ids)

    relationship_groups = _collect_and_group_relationships(
        graph,
        asset_ids,
        relationship_filters,
    )

    traces: List[go.Scatter3d] = []
    for (rel_type, is_bidirectional), relationships in relationship_groups.items():
        if relationships:
            trace = _create_trace_for_group(
                rel_type,
                is_bidirectional,
                relationships,
                positions,
                asset_id_index,
            )
            traces.append(trace)

    return traces


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> List[go.Scatter3d]:
    """
    Create marker traces representing direction for unidirectional relationships.

    Uses the provided graph and the positions mapped by asset_ids to produce marker traces
    placed at 70% along each directed edge where the reverse relationship does not exist.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing relationships to inspect.
        positions (np.ndarray): Array of shape (n, 3) with 3D coordinates for each asset.
        asset_ids (List[str]): Ordered list of asset IDs corresponding to rows in `positions`.

    Returns:
        List[go.Scatter3d]: A list containing a single Scatter3d trace of directional markers,
        or an empty list if no unidirectional relationships are found.
    """
    positions_arr, asset_ids_norm = _prepare_directional_arrow_inputs(
        graph,
        positions,
        asset_ids,
    )

    relationship_index = _build_relationship_index(graph, asset_ids_norm)
    asset_id_index = _build_asset_id_index(asset_ids_norm)

    source_indices: List[int] = []
    target_indices: List[int] = []
    hover_texts: List[str] = []

    # Gather unidirectional relationships
    for (source_id, target_id, rel_type), _ in relationship_index.items():
        reverse_key = (target_id, source_id, rel_type)
        if reverse_key not in relationship_index:
            source_indices.append(asset_id_index[source_id])
            target_indices.append(asset_id_index[target_id])
            hover_texts.append(f"Direction: {source_id} → {target_id}<br>Type: {rel_type}")

    if not source_indices:
        return []

    # Vectorized arrow position calculation at 70% along each edge
    src_idx_arr = np.asarray(source_indices, dtype=int)
    tgt_idx_arr = np.asarray(target_indices, dtype=int)
    source_positions = positions_arr[src_idx_arr]
    target_positions = positions_arr[tgt_idx_arr]
    arrow_positions = source_positions + 0.7 * (target_positions - source_positions)

    arrow_trace = go.Scatter3d(
        x=arrow_positions[:, 0].tolist(),
        y=arrow_positions[:, 1].tolist(),
        z=arrow_positions[:, 2].tolist(),
        mode="markers",
        marker=dict(
            symbol="diamond",
            size=8,
            color="rgba(255, 0, 0, 0.8)",
            line=dict(color="red", width=1),
        ),
        hovertext=hover_texts,
        hoverinfo="text",
        name="Direction Arrows",
        visible=True,
        showlegend=False,
    )

    return [arrow_trace]


def _prepare_directional_arrow_inputs(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> Tuple[np.ndarray, List[str]]:
    """
    Validate and normalize inputs used to compute directional arrow markers for a graph visualization.

    Parameters:
        graph: The AssetRelationshipGraph instance; must expose a `relationships` dict-like attribute.
        positions: Array-like positions for assets; will be converted to a numpy.ndarray of shape (n, 3).
        asset_ids: Iterable of asset identifier strings; will be converted to a list of non-empty strings.

    Returns:
        Tuple containing:
            positions_arr (numpy.ndarray): Numeric, finite array with shape (n, 3).
            asset_ids_list (List[str]): List of non-empty asset id strings of length n.
    """
    _validate_graph_relationships_dict(graph)
    positions_arr = _normalize_positions_array(positions)
    asset_ids_list = _normalize_asset_ids_list(asset_ids)
    _validate_positions_and_asset_ids_lengths(positions_arr, asset_ids_list)
    positions_arr = _ensure_numeric_positions(positions_arr)
    _ensure_finite_positions(positions_arr)
    _ensure_non_empty_string_asset_ids(asset_ids_list)
    return positions_arr, asset_ids_list


def _validate_graph_relationships_dict(graph: AssetRelationshipGraph) -> None:
    """
    Validate that `graph` is an AssetRelationshipGraph and that it exposes a `relationships` attribute of type `dict`.

    Parameters:
        graph (AssetRelationshipGraph): Object to validate.

    Raises:
        TypeError: If `graph` is not an instance of AssetRelationshipGraph.
        ValueError: If `graph` does not have a `relationships` attribute or if it is not a `dict`.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError("Invalid input data: graph must have a relationships dictionary")


def _normalize_positions_array(positions: np.ndarray) -> np.ndarray:
    """
    Normalize the positions input and return it as a NumPy ndarray.

    Parameters:
        positions (array-like | numpy.ndarray): Positions to normalize; may be an existing ndarray or any array-like object. Must not be None.

    Returns:
        numpy.ndarray: The positions converted to a NumPy ndarray (returned unchanged if already an ndarray).

    Raises:
        ValueError: If `positions` is None.
    """
    if positions is None:
        raise ValueError("positions and asset_ids must not be None")
    if isinstance(positions, np.ndarray):
        return positions
    return np.asarray(positions)


def _normalize_asset_ids_list(asset_ids: List[str]) -> List[str]:
    """
    Convert an iterable of asset IDs to a plain Python list preserving iteration order.

    Returns:
        list[str]: A list containing the asset ID elements in the original iteration order.

    Raises:
        ValueError: If `asset_ids` is None or is not an iterable.

    Notes:
        This function does not validate the type or contents of individual elements.
    """
    if asset_ids is None:
        raise ValueError("positions and asset_ids must not be None")
    if isinstance(asset_ids, (list, tuple)):
        return list(asset_ids)
    try:
        return list(asset_ids)
    except Exception as exc:  # pylint: disable=broad-except
        raise ValueError("asset_ids must be an iterable of strings") from exc


def _validate_positions_and_asset_ids_lengths(
    positions: np.ndarray,
    asset_ids: List[str],
) -> None:
    """
    Ensure the positions array and asset_ids sequence refer to the same number of assets and that positions have shape (n, 3).

    Parameters:
        positions (np.ndarray): 2-D numeric array representing coordinates; expected shape is (n, 3).
        asset_ids (List[str]): Sequence of asset identifiers; length must equal n.

    Raises:
        ValueError: If `positions` and `asset_ids` do not have the same length, if `positions` is not a 2-D array with 3 columns, or if either input does not support `len()`.
    """
    try:
        if len(positions) != len(asset_ids):
            raise ValueError("positions and asset_ids must have the same length")
    except TypeError as exc:
        raise ValueError("Invalid input data: positions and asset_ids must support len()") from exc
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("Invalid positions shape: expected (n, 3)")


def _ensure_numeric_positions(positions: np.ndarray) -> np.ndarray:
    """
    Validate that a NumPy positions array contains numeric values and convert it to a floating-point dtype if needed.

    Parameters:
        positions (np.ndarray): Array of positions to validate and convert.

    Returns:
        np.ndarray: The same array with a floating-point dtype.

    Raises:
        ValueError: If the array cannot be converted to numeric (float) values.
    """
    if np.issubdtype(positions.dtype, np.number):
        return positions
    try:
        return positions.astype(float)
    except Exception as exc:  # pylint: disable=broad-except
        raise ValueError("Invalid positions: values must be numeric") from exc


def _ensure_finite_positions(positions: np.ndarray) -> None:
    """
    Ensure all entries in the positions array are finite numbers.

    Parameters:
        positions (np.ndarray): Array of numeric position values to validate.

    Raises:
        ValueError: If any element in `positions` is NaN or infinite.
    """
    if not np.isfinite(positions).all():
        raise ValueError("Invalid positions: values must be finite numbers")


def _ensure_non_empty_string_asset_ids(asset_ids: List[str]) -> None:
    """
    Validate that every item in `asset_ids` is a non-empty string.

    Raises:
        ValueError: If any element of `asset_ids` is not a string or is an empty string.
    """
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("asset_ids must contain non-empty strings")


def _validate_filter_parameters(filter_params: Dict[str, bool]) -> None:
    """
    Validate that `filter_params` is a mapping of filter names to boolean flags.

    Parameters:
        filter_params (dict): Mapping from filter name to `bool`. Expected keys include:
            show_same_sector, show_market_cap, show_correlation, show_corporate_bond,
            show_commodity_currency, show_income_comparison, show_regulatory,
            show_all_relationships, toggle_arrows

    Raises:
        TypeError: If `filter_params` is not a `dict` or any mapping value is not a `bool`.
    """
    if not isinstance(filter_params, dict):
        raise TypeError(
            f"Invalid filter configuration: filter_params must be a dictionary, got {type(filter_params).__name__}"
        )

    invalid_params = [name for name, value in filter_params.items() if not isinstance(value, bool)]

    if invalid_params:
        raise TypeError(
            f"Invalid filter configuration: The following parameters must be "
            f"boolean values: {', '.join(invalid_params)}"
        )


def _validate_relationship_filters(
    relationship_filters: Optional[Dict[str, bool]],
) -> None:
    """
    Validate the structure and contents of a relationship filter mapping.

    Parameters:
        relationship_filters (Optional[Dict[str, bool]]): Mapping from relationship type names to boolean
            visibility flags; may be None.

    Raises:
        TypeError: If `relationship_filters` is not None and not a dict.
        ValueError: If any keys are not strings or any values are not booleans.
    """
    if relationship_filters is None:
        return

    if not isinstance(relationship_filters, dict):
        raise TypeError(
            f"Invalid filter configuration: "
            f"relationship_filters must be a dictionary or None, "
            f"got {type(relationship_filters).__name__}"
        )

    # Validate all values are boolean
    invalid_values = [key for key, value in relationship_filters.items() if not isinstance(value, bool)]
    if invalid_values:
        raise ValueError(
            f"Invalid filter configuration: "
            f"relationship_filters must contain only boolean "
            f"values. Invalid keys: {', '.join(invalid_values)}"
        )

    # Validate keys are strings
    invalid_keys = [key for key in relationship_filters.keys() if not isinstance(key, str)]
    if invalid_keys:
        raise ValueError(
            f"Invalid filter configuration: relationship_filters keys must be strings. Invalid keys: {invalid_keys}"
        )


def _validate_graph_for_filtered_visualization(
    graph: AssetRelationshipGraph,
) -> None:
    """
    Ensure the provided graph supports filtered 3D visualization.

    Raises:
        ValueError: If `graph` is not an `AssetRelationshipGraph` instance or does not implement
        `get_3d_visualization_data_enhanced`.
    """
    if isinstance(graph, AssetRelationshipGraph) and hasattr(graph, "get_3d_visualization_data_enhanced"):
        return
    raise ValueError(
        "Invalid graph data provided: graph must be an "
        "AssetRelationshipGraph instance with "
        "get_3d_visualization_data_enhanced method"
    )


def _build_relationship_filters_for_visualization(
    *,
    show_same_sector: bool,
    show_market_cap: bool,
    show_correlation: bool,
    show_corporate_bond: bool,
    show_commodity_currency: bool,
    show_income_comparison: bool,
    show_regulatory: bool,
    show_all_relationships: bool,
) -> Optional[Dict[str, bool]]:
    """
    Builds a relationship filter map for visualization based on individual show flags.

    If `show_all_relationships` is True, returns None to indicate no filtering; otherwise returns a dict mapping the following relationship keys to booleans: "same_sector", "market_cap_similar", "correlation", "corporate_bond_to_equity", "commodity_currency", "income_comparison", and "regulatory_impact". Logs a warning if all returned filters are False.

    Returns:
        Optional[Dict[str, bool]]: `None` when no filtering should be applied; otherwise a mapping of relationship filter names to booleans.
    """
    if show_all_relationships:
        return None
    relationship_filters = {
        "same_sector": show_same_sector,
        "market_cap_similar": show_market_cap,
        "correlation": show_correlation,
        "corporate_bond_to_equity": show_corporate_bond,
        "commodity_currency": show_commodity_currency,
        "income_comparison": show_income_comparison,
        "regulatory_impact": show_regulatory,
    }
    _validate_relationship_filters(relationship_filters)
    if not any(relationship_filters.values()):
        logger.warning("All relationship filters are disabled. Visualization will show no relationships.")
    return relationship_filters


def _get_and_validate_visualization_data(
    graph: AssetRelationshipGraph,
) -> Tuple[np.ndarray, List[str], List[str], List[str]]:
    """
    Retrieve and validate 3D visualization positions and associated metadata from the graph.

    Parameters:
        graph (AssetRelationshipGraph): Graph providing `get_3d_visualization_data_enhanced()`.

    Returns:
        tuple: A 4-tuple containing:
            - positions (np.ndarray): Numeric array with shape (n, 3) of asset coordinates.
            - asset_ids (List[str]): List of asset identifier strings, length n.
            - colors (List[str]): List of color strings for each asset, length n.
            - hover_texts (List[str]): List of hover text strings for each asset, length n.

    Raises:
        ValueError: If retrieving visualization data from the graph fails.
        TypeError, ValueError: If the retrieved data fails validation.
    """
    try:
        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Failed to retrieve visualization data from graph: %s",
            exc,
        )
        raise ValueError("Failed to retrieve graph visualization data") from exc
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)
    return positions, asset_ids, colors, hover_texts


def _create_relationship_traces_with_fallback(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
    relationship_filters: Optional[Dict[str, bool]],
) -> List[go.Scatter3d]:
    """
    Attempt to build 3D relationship traces for the given graph visualization.

    Calls the internal trace-building routine and returns its traces. If the underlying call fails due to invalid input (TypeError or ValueError), a ValueError is raised with contextual information. If any other unexpected error occurs, an empty list is returned.

    Parameters:
        relationship_filters (Optional[Dict[str, bool]]): Mapping of relationship type to a boolean indicating whether that type should be included; may be None to indicate no filtering.

    Returns:
        List[go.Scatter3d]: A list of Plotly Scatter3d traces representing relationships; empty list if an unexpected error prevented trace creation.

    Raises:
        ValueError: If trace creation fails due to invalid input (propagated from TypeError or ValueError).
    """
    try:
        return _create_relationship_traces(
            graph,
            positions,
            asset_ids,
            relationship_filters,
        )
    except (TypeError, ValueError) as exc:
        logger.exception(
            "Failed to create filtered relationship traces due to invalid data (filters: %s): %s",
            relationship_filters,
            exc,
        )
        raise ValueError(f"Failed to create relationship traces: {exc}") from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Unexpected error creating filtered relationship traces (filters: %s): %s",
            relationship_filters,
            exc,
        )
        return []


def _add_traces_with_logging(
    fig: go.Figure,
    traces: List[go.Scatter3d],
    failure_message: str,
) -> None:
    """
    Add the provided 3D traces to a Plotly figure, logging any exception and continuing silently.

    If `traces` is empty this function returns immediately. On error it logs `failure_message` along with the caught exception and does not re-raise.

    Parameters:
        fig (go.Figure): Target Plotly figure to receive the traces.
        traces (List[go.Scatter3d]): 3D trace objects to add to the figure.
        failure_message (str): Message to include in the log if adding traces fails.
    """
    if not traces:
        return
    try:
        fig.add_traces(traces)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(failure_message, exc)


def _create_directional_arrows_with_fallback(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> List[go.Scatter3d]:
    """
    Create directional arrow traces for the graph; return an empty list if creation fails.

    Returns:
        A list of Plotly Scatter3d traces representing directional arrows, or an empty list if trace creation failed.
    """
    try:
        return _create_directional_arrows(graph, positions, asset_ids)
    except (TypeError, ValueError) as exc:
        logger.exception(
            "Failed to create directional arrows due to invalid data: %s",
            exc,
        )
        return []
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Unexpected error creating directional arrows: %s",
            exc,
        )
        return []


def _configure_layout_with_fallback(
    fig: go.Figure,
    asset_ids: List[str],
    relationship_traces: List[go.Scatter3d],
) -> None:
    """
    Update the given Plotly 3D figure's layout with a dynamic title based on the provided assets and visible relationships; if an error occurs, set a safe default title.

    This function mutates `fig` in place and will fall back to the title "Financial Asset Network" on any failure.
    """
    try:
        dynamic_title, options = _prepare_layout_config(
            len(asset_ids),
            relationship_traces,
        )
        _configure_3d_layout(fig, dynamic_title, options)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to configure figure layout: %s", exc)
        _configure_3d_layout(fig, "Financial Asset Network")


def visualize_3d_graph_with_filters(
    graph: AssetRelationshipGraph,
    show_same_sector: bool = True,
    show_market_cap: bool = True,
    show_correlation: bool = True,
    show_corporate_bond: bool = True,
    show_commodity_currency: bool = True,
    show_income_comparison: bool = True,
    show_regulatory: bool = True,
    show_all_relationships: bool = True,
    toggle_arrows: bool = True,
) -> go.Figure:
    """
    Render a 3D Plotly figure of the given asset relationship graph with optional relationship-type filters.

    Create a visualization containing node traces and relationship traces; relationship booleans control which relationship categories are included and `toggle_arrows` enables directional arrow markers for unidirectional edges.

    Parameters:
        graph: AssetRelationshipGraph to visualize.
        show_same_sector: Include "same sector" relationships.
        show_market_cap: Include "market cap" relationships.
        show_correlation: Include "correlation" relationships.
        show_corporate_bond: Include "corporate bond" relationships.
        show_commodity_currency: Include "commodity/currency" relationships.
        show_income_comparison: Include "income comparison" relationships.
        show_regulatory: Include "regulatory" relationships.
        show_all_relationships: If True, override individual filters to show all relationship types.
        toggle_arrows: If True, add directional arrow markers for unidirectional relationships.

    Returns:
        go.Figure: A Plotly 3D figure containing node and relationship traces for the graph.

    Raises:
        ValueError: If the provided graph is invalid or required visualization data cannot be produced.
        TypeError: If one or more filter parameters are not boolean.
    """
    _validate_graph_for_filtered_visualization(graph)

    # Build filter parameters dictionary and validate
    filter_params = {
        "show_same_sector": show_same_sector,
        "show_market_cap": show_market_cap,
        "show_correlation": show_correlation,
        "show_corporate_bond": show_corporate_bond,
        "show_commodity_currency": show_commodity_currency,
        "show_income_comparison": show_income_comparison,
        "show_regulatory": show_regulatory,
        "show_all_relationships": show_all_relationships,
        "toggle_arrows": toggle_arrows,
    }
    try:
        _validate_filter_parameters(filter_params)
    except TypeError as exc:
        logger.error("Invalid filter configuration: %s", exc)
        raise

    try:
        relationship_filters = _build_relationship_filters_for_visualization(
            show_same_sector=show_same_sector,
            show_market_cap=show_market_cap,
            show_correlation=show_correlation,
            show_corporate_bond=show_corporate_bond,
            show_commodity_currency=show_commodity_currency,
            show_income_comparison=show_income_comparison,
            show_regulatory=show_regulatory,
            show_all_relationships=show_all_relationships,
        )
    except (TypeError, ValueError) as exc:
        logger.exception("Failed to build filter configuration: %s", exc)
        raise ValueError(f"Invalid filter configuration: {exc}") from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Unexpected error building filter configuration: %s",
            exc,
        )
        raise ValueError("Failed to build filter configuration") from exc

    positions, asset_ids, colors, hover_texts = _get_and_validate_visualization_data(graph)

    # Create figure
    fig = go.Figure()

    relationship_traces = _create_relationship_traces_with_fallback(
        graph,
        positions,
        asset_ids,
        relationship_filters,
    )
    _add_traces_with_logging(
        fig,
        relationship_traces,
        "Failed to add filtered relationship traces to figure: %s",
    )

    if toggle_arrows:
        arrow_traces = _create_directional_arrows_with_fallback(
            graph,
            positions,
            asset_ids,
        )
        _add_traces_with_logging(
            fig,
            arrow_traces,
            "Failed to add directional arrows to figure: %s",
        )

    # Add node trace
    try:
        node_trace = _create_node_trace(positions, asset_ids, colors, hover_texts)
        fig.add_trace(node_trace)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to create or add node trace: %s", exc)
        raise ValueError("Failed to create node visualization") from exc

    _configure_layout_with_fallback(fig, asset_ids, relationship_traces)

    return fig
