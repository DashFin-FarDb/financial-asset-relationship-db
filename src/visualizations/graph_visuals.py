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
    """
    Determine whether a color string is in a plausibly valid format.

    Supports common color formats:
    - Hex colors (#RGB, #RRGGBB, #RRGGBBAA)
    - RGB/RGBA functional notation (e.g., "rgb(255,0,0)", "rgba(255,0,0,0.5)")
    - Named colors (accepted as a fallback; final validation may occur at render time)

    Parameters:
        color (str): The color string to validate.

    Returns:
        bool: `True` if the string appears to be a valid color format, `False` otherwise.
    """
    if not isinstance(color, str) or not color:
        return False
    # Hex colors: #RGB, #RRGGBB, #RRGGBBAA
    if re.match(r"^#(?:[0-9A-Fa-f]{3}){1,2}(?:[0-9A-Fa-f]{2})?$", color):
        return True
    # rgb/rgba functions, e.g. rgb(255, 0, 0) or rgba(255,0,0,0.5)
    if re.match(r"^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(,\s*[\d.]+\s*)?\)$", color):
        return True
    # Fallback: allow named colors; Plotly will validate at render time
    return True


def _build_asset_id_index(asset_ids: List[str]) -> Dict[str, int]:
    """
    Create an index mapping each asset ID to its position in the input sequence.

    Returns:
        dict: Mapping from asset ID (str) to its 0-based integer index position.
    """
    return {asset_id: idx for idx, asset_id in enumerate(asset_ids)}


def _build_relationship_index(
    graph: AssetRelationshipGraph, asset_ids: Iterable[str]
) -> Dict[Tuple[str, str, str], float]:
    """
    Builds a mapping of relationships limited to the provided asset_ids.

    Creates and returns a dictionary that maps (source_id, target_id, rel_type) tuples
    to their numeric strength for relationships whose source and target are both in
    asset_ids. The function validates inputs and relationship tuple structure before
    including entries.

    Parameters:
        graph (AssetRelationshipGraph): Graph object exposing a `relationships` dictionary.
        asset_ids (Iterable[str]): Iterable of asset IDs to include in the index.

    Returns:
        Dict[Tuple[str, str, str], float]: Mapping from (source_id, target_id, rel_type)
            to the relationship strength as a float.

    Raises:
        TypeError: If `graph` is not an AssetRelationshipGraph, `graph.relationships`
            is not a dict, `asset_ids` is not iterable, or relationship entries have
            invalid types.
        ValueError: If required attributes are missing, `asset_ids` contains non-strings,
            or relationship tuples do not have the expected structure or numeric strength.
    """
    # Validate graph input
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(
            f"Invalid input: graph must be an AssetRelationshipGraph instance, "
            f"got {type(graph).__name__}"
        )
    # Validate graph.relationships exists and is a dictionary
    if not hasattr(graph, "relationships"):
        raise ValueError("Invalid graph: missing 'relationships' attribute")
    if not isinstance(graph.relationships, dict):
        raise TypeError(
            f"Invalid graph data: graph.relationships must be a dictionary, "
            f"got {type(graph.relationships).__name__}"
        )
    # Validate asset_ids is iterable and build a set for O(1) membership tests
    try:
        asset_ids_set: Set[str] = set(asset_ids)
    except TypeError as exc:
        raise TypeError(
            f"Invalid input: asset_ids must be an iterable, "
            f"got {type(asset_ids).__name__}"
        ) from exc
    # Validate asset_ids contains only strings
    if not all(isinstance(aid, str) for aid in asset_ids_set):
        raise ValueError("Invalid input: asset_ids must contain only string values")
    # Thread-safe access to graph.relationships using synchronization lock
    with _graph_access_lock:
        try:
            # Create a snapshot of only the relevant source_ids to minimize lock hold time
            relevant_relationships = {
                source_id: list(rels)
                for source_id, rels in graph.relationships.items()
                if source_id in asset_ids_set
            }
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError(
                f"Failed to create snapshot of graph.relationships: {exc}"
            ) from exc
    # Build index outside the lock
    relationship_index: Dict[Tuple[str, str, str], float] = {}
    for source_id, rels in relevant_relationships.items():
        # Validate that rels is an appropriate sequence
        if not isinstance(rels, (list, tuple)):
            raise TypeError(
                f"Invalid graph data: relationships for source_id '{source_id}' "
                f"must be a list or tuple, got {type(rels).__name__}"
            )
        for idx, rel in enumerate(rels):
            # Each relationship must be a (target_id, rel_type, strength) tuple
            if not isinstance(rel, (list, tuple)):
                raise TypeError(
                    f"Invalid graph data: relationship at index {idx} for source_id '{source_id}' "
                    f"must be a list or tuple, got {type(rel).__name__}"
                )
            if len(rel) != 3:
                raise ValueError(
                    f"Invalid graph data: relationship at index {idx} for source_id '{source_id}' "
                    f"must have exactly 3 elements (target_id, rel_type, strength), "
                    f"got {len(rel)} elements"
                )
            target_id, rel_type, strength = rel
            # Validate target_id and rel_type types
            if not isinstance(target_id, str):
                raise TypeError(
                    f"Invalid graph data: target_id at index {idx} for source_id '{source_id}' "
                    f"must be a string, got {type(target_id).__name__}"
                )
            if not isinstance(rel_type, str):
                raise TypeError(
                    f"Invalid graph data: rel_type at index {idx} for source_id '{source_id}' "
                    f"must be a string, got {type(rel_type).__name__}"
                )
            # Validate and normalize strength to float
            try:
                strength_float = float(strength)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid graph data: strength at index {idx} for source_id '{source_id}' "
                    f"must be numeric (got {type(strength).__name__} with value '{strength}')"
                ) from exc
            # Only index relationships whose target is also in the requested asset set
            if target_id in asset_ids_set:
                relationship_index[(source_id, target_id, rel_type)] = strength_float

    return relationship_index


def _create_node_trace(
    positions: np.ndarray,
    asset_ids: List[str],
    colors: List[str],
    hover_texts: List[str],
) -> go.Scatter3d:
    """
    Constructs a Plotly 3D scatter trace representing asset nodes for the visualization.

    Validates the provided positions, asset IDs, colors, and hover texts and returns a configured go.Scatter3d suitable for rendering node markers and labels.

    Returns:
        go.Scatter3d: A Scatter3d trace configured with marker styles, text labels, and hover text for each asset.

    Raises:
        ValueError: If any input is invalid, mismatched in length, empty, or contains non-finite numeric values.
    """
    # Input validation: Perform basic type checks before delegating to comprehensive validator
    # This provides early failure with clear error messages for common mistakes
    if not isinstance(positions, np.ndarray):
        raise ValueError(
            f"positions must be a numpy array, got {type(positions).__name__}"
        )
    if not isinstance(asset_ids, (list, tuple)):
        raise ValueError(
            f"asset_ids must be a list or tuple, got {type(asset_ids).__name__}"
        )
    if not isinstance(colors, (list, tuple)):
        raise ValueError(f"colors must be a list or tuple, got {type(colors).__name__}")
    if not isinstance(hover_texts, (list, tuple)):
        raise ValueError(
            f"hover_texts must be a list or tuple, got {type(hover_texts).__name__}"
        )

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
        raise ValueError(
            f"positions length ({positions.shape[0]}) "
            f"must match asset_ids length ({len(asset_ids)})"
        )

    # Comprehensive validation: detailed checks on content, numeric types, and finite values
    # Delegates to shared validator to ensure consistency across all visualization functions
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)

    # Edge case validation: Ensure inputs are not empty
    if len(asset_ids) == 0:
        raise ValueError(
            "Cannot create node trace with empty inputs (asset_ids length is 0)"
        )
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
    Create a title string that includes the base title and counts of assets and relationships.

    Parameters:
        num_assets (int): Number of assets to display.
        num_relationships (int): Number of relationships to display.
        base_title (str): Base title text to prefix (default: "Financial Asset Network").

    Returns:
        str: Formatted title like "Base Title - {num_assets} Assets, {num_relationships} Relationships".
    """
    return f"{base_title} - {num_assets} Assets, {num_relationships} Relationships"


def _calculate_visible_relationships(relationship_traces: List[go.Scatter3d]) -> int:
    """
    Return the count of visible relationship edges represented in the provided 3D traces.

    Parameters:
        relationship_traces (List[go.Scatter3d]): Scatter3d traces that encode relationship edges.

    Returns:
        int: Number of visible relationship edges across all traces; returns 0 if the traces cannot be interpreted.
    """
    try:
        return (
            sum(len(getattr(trace, "x", []) or []) for trace in relationship_traces)
            // 3
        )
    except Exception:  # pylint: disable=broad-except
        return 0


def _prepare_layout_config(
    num_assets: int,
    relationship_traces: List[go.Scatter3d],
    base_title: str = "Financial Asset Network",
    layout_options: Optional[Dict[str, object]] = None,
) -> Tuple[str, Dict[str, object]]:
    """
    Builds a dynamic title and layout options dictionary for the 3D visualization.

    Parameters:
        num_assets (int): Number of asset nodes included in the visualization.
        relationship_traces (List[go.Scatter3d]): Relationship/edge traces used to determine the visible relationship count.
        base_title (str): Base title text to prefix the dynamic counts (default: "Financial Asset Network").
        layout_options (Optional[Dict[str, object]]): Optional layout overrides; returned as-is when provided.

    Returns:
        Tuple[str, Dict[str, object]]:
            dynamic_title: A formatted title incorporating asset and visible relationship counts.
            options: A dictionary of layout options (empty dict if none were supplied).
    """
    num_relationships = _calculate_visible_relationships(relationship_traces)
    dynamic_title = _generate_dynamic_title(num_assets, num_relationships, base_title)
    options = layout_options or {}
    return dynamic_title, options


def _add_directional_arrows_to_figure(
    fig: go.Figure,
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> None:
    """
    Add directional arrow traces for unidirectional relationships to the provided figure.

    If any directional arrow traces are generated, they are appended to `fig`; otherwise `fig` is left unchanged.

    Parameters:
        fig (go.Figure): The Plotly figure to modify.
        graph (AssetRelationshipGraph): Graph containing relationship data.
        positions (np.ndarray): Array of vertex positions with shape (n, 3).
        asset_ids (List[str]): Ordered list of asset identifiers corresponding to `positions`.
    """
    arrow_traces = _create_directional_arrows(graph, positions, asset_ids)
    if arrow_traces:
        fig.add_traces(arrow_traces)


def _configure_3d_layout(
    fig: go.Figure,
    title: str,
    options: Optional[Dict[str, object]] = None,
) -> None:
    """
    Apply a standardized 3D layout and visual defaults to a Plotly Figure.

    Parameters:
        fig (go.Figure): The Plotly figure to update; layout is applied in-place.
        title (str): Title text to display at the top-center of the figure.
        options (Optional[Dict[str, object]]): Optional overrides for layout defaults. Supported keys:
            - width (int): Figure width in pixels (default: 1200).
            - height (int): Figure height in pixels (default: 800).
            - gridcolor (str): Color for axis grid lines (default: "rgba(200, 200, 200, 0.3)").
            - bgcolor (str): Scene background color (default: "rgba(248, 248, 248, 0.95)").
            - legend_bgcolor (str): Legend background color (default: "rgba(255, 255, 255, 0.8)").
            - legend_bordercolor (str): Legend border color (default: "rgba(0, 0, 0, 0.3)").
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
    Validate that `positions` is a numeric (n, 3) NumPy array containing finite values.

    Parameters:
        positions (np.ndarray): Array of 3D coordinates with shape (n, 3); each row represents an (x, y, z) position.

    Raises:
        ValueError: If `positions` is not a NumPy array, does not have shape (n, 3), has a non-numeric dtype,
                    or contains non-finite values (NaN or Inf). When non-finite values are present, the error
                    message includes the counts of NaN and Inf entries.
    """
    if not isinstance(positions, np.ndarray):
        raise ValueError(
            f"Invalid graph data: positions must be a numpy array, "
            f"got {type(positions).__name__}"
        )
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(
            "Invalid graph data: Expected positions to be a "
            "(n, 3) numpy array, got array with shape "
            f"{positions.shape}"
        )
    if not np.issubdtype(positions.dtype, np.number):
        raise ValueError(
            f"Invalid graph data: positions must contain numeric values, "
            f"got dtype {positions.dtype}"
        )
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
    Validate that `asset_ids` is a list or tuple of non-empty strings.

    Raises:
        ValueError: If `asset_ids` is not a list or tuple, or if any element is not a non-empty string.
    """
    if not isinstance(asset_ids, (list, tuple)):
        raise ValueError(
            f"Invalid graph data: asset_ids must be a list or tuple, "
            f"got {type(asset_ids).__name__}"
        )
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("Invalid graph data: asset_ids must contain non-empty strings")


def _validate_colors_list(colors: List[str], expected_length: int) -> None:
    """
    Validate that `colors` is a list or tuple of non-empty color strings of the expected length and that each entry matches accepted color formats.

    Parameters:
        colors (List[str] | Tuple[str, ...]): Sequence of color specifications (hex, rgb/rgba, or color name).
        expected_length (int): Required number of color entries.

    Raises:
        ValueError: If `colors` is not a list/tuple of length `expected_length`, if any entry is not a non-empty string, or if any color does not pass the accepted color format check.
    """
    if not isinstance(colors, (list, tuple)) or len(colors) != expected_length:
        colors_type = type(colors).__name__
        colors_len = len(colors) if isinstance(colors, (list, tuple)) else "N/A"
        raise ValueError(
            f"Invalid graph data: colors must be a list/tuple of "
            f"length {expected_length}, got {colors_type} with length {colors_len}"
        )
    if not all(isinstance(c, str) and c for c in colors):
        raise ValueError("Invalid graph data: colors must contain non-empty strings")

    for i, color in enumerate(colors):
        if not _is_valid_color_format(color):
            raise ValueError(
                f"Invalid graph data: colors[{i}] has invalid color format: '{color}'"
            )


def _validate_hover_texts_list(
    hover_texts: List[str],
    expected_length: int,
) -> None:
    """
    Validate that `hover_texts` is a sequence of non-empty strings of the expected length.

    Parameters:
        hover_texts (List[str]): Sequence of hover text strings to validate.
        expected_length (int): Required length of the `hover_texts` sequence.

    Raises:
        ValueError: If `hover_texts` is not a list or tuple of length `expected_length`,
                    or if any element is not a non-empty string.
    """
    if (
        not isinstance(hover_texts, (list, tuple))
        or len(hover_texts) != expected_length
    ):
        raise ValueError(
            f"Invalid graph data: hover_texts must be a list/tuple of length "
            f"{expected_length}"
        )
    if not all(isinstance(h, str) and h for h in hover_texts):
        raise ValueError(
            "Invalid graph data: hover_texts must contain non-empty strings"
        )


def _validate_asset_ids_uniqueness(asset_ids: List[str]) -> None:
    """
    Ensure all asset IDs are unique.

    Parameters:
        asset_ids (List[str]): Sequence of asset identifier strings to validate.

    Raises:
        ValueError: If duplicate asset IDs are found; the error message lists the duplicated IDs.
    """
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
    Validate positions, asset IDs, colors, and hover texts for consistency and correctness.

    Performs comprehensive checks that:
    - positions is a (n, 3) numeric, finite numpy array,
    - asset_ids is a sequence of n non-empty, unique strings,
    - colors is a sequence of n non-empty color strings,
    - hover_texts is a sequence of n non-empty strings.

    Parameters:
        positions (np.ndarray): Array of 3D coordinates with shape (n, 3).
        asset_ids (List[str]): List of asset identifier strings of length n.
        colors (List[str]): List of color values (hex, rgb/rgba, or names) of length n.
        hover_texts (List[str]): List of hover text strings of length n.

    Raises:
        ValueError: If lengths are inconsistent, values are invalid, or duplicate asset_ids are found.
        TypeError: If any input has an unexpected type.
    """
    _validate_positions_array(positions)
    _validate_asset_ids_list(asset_ids)

    n = len(asset_ids)
    if positions.shape[0] != n:
        raise ValueError(
            f"Invalid graph data: positions length ({positions.shape[0]}) "
            f"must match asset_ids length ({n})"
        )

    _validate_colors_list(colors, n)
    _validate_hover_texts_list(hover_texts, n)
    _validate_asset_ids_uniqueness(asset_ids)


def visualize_3d_graph(graph: AssetRelationshipGraph) -> go.Figure:
    """
    Render an interactive 3D Plotly figure showing assets and their relationships.

    The figure contains node markers for each asset, separate line traces for relationship
    types and directions, and optional directional arrow markers for unidirectional edges.
    Layout is configured with axis titles, grid styling, a centered dynamic title that
    reflects the number of assets and visible relationships, and a legend.

    Parameters:
        graph (AssetRelationshipGraph): Graph object that implements
            `get_3d_visualization_data_enhanced()` and exposes a `relationships` mapping.
            The visualization data must provide (positions, asset_ids, colors, hover_texts).

    Returns:
        go.Figure: Configured Plotly 3D figure containing node, relationship, and arrow traces.

    Raises:
        ValueError: If `graph` is not a valid AssetRelationshipGraph, if the graph does not
            provide the enhanced visualization data method, or if the returned visualization
            data fails validation.
    """
    if not isinstance(graph, AssetRelationshipGraph) or not hasattr(
        graph, "get_3d_visualization_data_enhanced"
    ):
        raise ValueError("Invalid graph data provided")

    positions, asset_ids, colors, hover_texts = (
        graph.get_3d_visualization_data_enhanced()
    )

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
    total_relationships = (
        sum(len(getattr(trace, "x", []) or []) for trace in relationship_traces) // 3
    )
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
                title="Dimension 1", showgrid=True, gridcolor="rgba(200, 200, 200, 0.3)"
            ),
            yaxis=dict(
                title="Dimension 2", showgrid=True, gridcolor="rgba(200, 200, 200, 0.3)"
            ),
            zaxis=dict(
                title="Dimension 3", showgrid=True, gridcolor="rgba(200, 200, 200, 0.3)"
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
    Group relationships by type and bidirectionality, returning lists of relationship entries for rendering.

    Parameters:
        graph (AssetRelationshipGraph): Graph providing relationship data.
        asset_ids (Iterable[str]): Asset IDs to consider; only relationships where both ends are in this collection are included.
        relationship_filters (Optional[Dict[str, bool]]): Optional map of relationship type -> bool; types mapped to False are excluded.

    Returns:
        grouped (Dict[Tuple[str, bool], List[dict]]): Mapping from (rel_type, is_bidirectional) to a list of relationship dicts. Each dict contains:
            - `source_id` (str): ID of the source asset.
            - `target_id` (str): ID of the target asset.
            - `strength` (float): Relationship strength as a float.

    Behavior:
        - A relationship is considered bidirectional when the reverse (target→source) with the same type exists; such pairs are emitted once under `is_bidirectional=True`.
        - The function applies `relationship_filters` to exclude types when provided.
    """
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

        # Canonical pair key for bidirectional detection
        if source_id <= target_id:
            pair_key: Tuple[str, str, str] = (source_id, target_id, rel_type)
        else:
            pair_key = (target_id, source_id, rel_type)

        # Reverse lookup for bidirectionality
        is_bidirectional = (target_id, source_id, rel_type) in relationship_index

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
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """
    Build flat coordinate arrays for a list of relationships so each edge occupies three consecutive entries (source, target, separator) for efficient Plotly line rendering.

    Parameters:
        relationships (List[dict]): Sequence of relationship records; each must contain 'source_id' and 'target_id' keys.
        positions (np.ndarray): Array of shape (n, 3) containing XYZ coordinates for assets.
        asset_id_index (Dict[str, int]): Mapping from asset_id to its integer index into `positions`.

    Returns:
        Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
            Three lists (x, y, z). For the i-th relationship, values are placed at indices
            i*3 and i*3+1 for the source and target coordinates respectively; index i*3+2
            is left as a separator (typically None).
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
    relationships: List[dict], rel_type: str, is_bidirectional: bool
) -> List[Optional[str]]:
    """
    Builds hover text entries for a list of relationships, preallocating a flat list sized 3 entries per relationship for downstream plotting.

    Each relationship produces a hover text string of the form:
        "{source_id} {direction} {target_id}<br>Type: {rel_type}<br>Strength: {strength:.2f}"
    where `direction` is "↔" for bidirectional or "→" for unidirectional and `strength` is formatted to two decimal places.

    Parameters:
        relationships (List[dict]): Sequence of relationship dicts, each requiring the keys
            'source_id', 'target_id', and 'strength'.
        rel_type (str): The relationship type label to include in each hover text.
        is_bidirectional (bool): If True, use the bidirectional symbol ("↔"); otherwise use ("→").

    Returns:
        List[Optional[str]]: A flat list of length `len(relationships) * 3` where, for each relationship i,
            entries at indices `3*i` and `3*i + 1` contain the hover text string and index `3*i + 2`
            is left as `None`. This layout matches downstream plotting expectations for triplet-per-edge data.
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
    Return line style configuration for a relationship type.

    Parameters:
        rel_type (str): Relationship type key used to look up a configured color.
        is_bidirectional (bool): Whether the relationship is bidirectional; alters line width and dash style.

    Returns:
        dict: A mapping with keys:
            - `color` (str): Validated color string for the line (falls back to '#888888' on invalid format).
            - `width` (int): `4` when `is_bidirectional` is True, otherwise `2`.
            - `dash` (str): `'solid'` when `is_bidirectional` is True, otherwise `'dash'`.
    """
    color = REL_TYPE_COLORS[rel_type]
    if not _is_valid_color_format(color):
        logger.warning(
            "Invalid color format for relationship type '%s': '%s'. "
            "Using default gray.",
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
    """
    Create a human-readable legend label for a relationship trace.

    Returns:
        str: The relationship type formatted (underscores replaced by spaces and title-cased) with a directional marker — `(↔)` for bidirectional or `(→)` for unidirectional.
    """
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
    Create a Plotly 3D line trace representing a group of relationships of the same type and directionality.

    Parameters:
        rel_type (str): Relationship type identifier used for styling and legend grouping.
        is_bidirectional (bool): Whether the relationships in this group are bidirectional.
        relationships (List[dict]): List of relationship records; each dict must contain at least source_id, target_id, and strength.
        positions (np.ndarray): Array of node positions with shape (n, 3); used to derive edge coordinates.
        asset_id_index (Dict[str, int]): Mapping from asset_id to row index in `positions` for O(1) lookups.

    Returns:
        go.Scatter3d: A configured 3D line trace representing the group's edges with hover texts, styling, and legend grouping.
    """
    edges_x, edges_y, edges_z = _build_edge_coordinates_optimized(
        relationships, positions, asset_id_index
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
    Create Plotly 3D traces for each relationship type and directionality present in the graph.

    Builds grouped line traces (one per combination of relationship type and bidirectionality) for efficient batch addition to a figure. The function validates inputs and will raise a ValueError for invalid graph, relationships structure, or mismatched positions and asset_ids.

    Parameters:
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping of relationship type to a boolean flag indicating whether that type should be included; when None, all types are considered.

    Returns:
        List[go.Scatter3d]: A list of 3D line traces, each representing a group of relationships of the same type and directionality.

    Raises:
        ValueError: If graph is not an AssetRelationshipGraph, graph.relationships is not a dict, positions is not a numpy array, or the length of positions does not match asset_ids.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise ValueError(
            "Invalid input data: graph must be an AssetRelationshipGraph instance"
        )
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError(
            "Invalid input data: graph must have a relationships dictionary"
        )
    if not isinstance(positions, np.ndarray):
        raise ValueError("Invalid input data: positions must be a numpy array")
    if len(positions) != len(asset_ids):
        raise ValueError(
            "Invalid input data: positions array length must match asset_ids length"
        )

    asset_id_index = _build_asset_id_index(asset_ids)

    relationship_groups = _collect_and_group_relationships(
        graph, asset_ids, relationship_filters
    )

    traces: List[go.Scatter3d] = []
    for (rel_type, is_bidirectional), relationships in relationship_groups.items():
        if relationships:
            trace = _create_trace_for_group(
                rel_type, is_bidirectional, relationships, positions, asset_id_index
            )
            traces.append(trace)

    return traces


def _validate_directional_arrows_inputs(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> None:
    """
    Validate inputs required to compute directional arrow traces for a graph visualization.

    Parameters:
        graph (AssetRelationshipGraph): The graph object which must expose a `relationships` dict.
        positions (np.ndarray): Array of node positions; must support len() and have the same length as `asset_ids`.
        asset_ids (List[str]): Sequence of asset identifiers corresponding one-to-one with `positions`.

    Raises:
        TypeError: If `graph` is not an instance of AssetRelationshipGraph.
        ValueError: If `graph.relationships` is missing or not a dict, if `positions` or `asset_ids` is None,
                    or if `positions` and `asset_ids` do not have the same length.
        ValueError: If `positions` or `asset_ids` do not support len(), a ValueError is raised wrapping the original TypeError.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError(
            "Invalid input data: graph must have a relationships dictionary"
        )
    if positions is None or asset_ids is None:
        raise ValueError("positions and asset_ids must not be None")
    try:
        if len(positions) != len(asset_ids):
            raise ValueError(
                "Invalid input data: positions and asset_ids must have the same length"
            )
    except TypeError as exc:
        raise ValueError(
            "Invalid input data: positions and asset_ids must support len()"
        ) from exc


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> List[go.Scatter3d]:
    """
    Create Plotly 3D arrow markers for unidirectional relationships in the graph.

    This builds a single Scatter3d trace of diamond markers positioned along each
    unidirectional edge (at 70% of the vector from source to target) and returns
    it inside a list. If no unidirectional relationships exist, returns an empty list.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing a relationships mapping.
        positions (np.ndarray): Array of shape (n, 3) of numeric, finite coordinates
            ordered to match `asset_ids`.
        asset_ids (List[str]): Iterable of non-empty asset identifier strings
            corresponding one-to-one with `positions`.

    Returns:
        List[go.Scatter3d]: A list containing a single Scatter3d trace with arrow
        markers, or an empty list if no unidirectional relationships are present.

    Raises:
        ValueError: If `positions` is not shape (n, 3), contains non-numeric or
            non-finite values, if `asset_ids` cannot be treated as an iterable of
            non-empty strings, or on other invalid input discovered during validation.
    """
    _validate_directional_arrows_inputs(graph, positions, asset_ids)
    # original arrow creation logic follows unchanged
    ...

    if not isinstance(positions, np.ndarray):
        positions = np.asarray(positions)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("Invalid positions shape: expected (n, 3)")

    if not isinstance(asset_ids, (list, tuple)):
        try:
            asset_ids = list(asset_ids)
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError("asset_ids must be an iterable of strings") from exc

    if not np.issubdtype(positions.dtype, np.number):
        try:
            positions = positions.astype(float)
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError("Invalid positions: values must be numeric") from exc

    if not np.isfinite(positions).all():
        raise ValueError("Invalid positions: values must be finite numbers")

    # Early return optimization:
    # prevent unnecessary computation and memory allocation
    # when there are no unidirectional relationships to display
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("asset_ids must contain non-empty strings")

    relationship_index = _build_relationship_index(graph, asset_ids)
    asset_id_index = _build_asset_id_index(asset_ids)

    source_indices: List[int] = []
    target_indices: List[int] = []
    hover_texts: List[str] = []

    # Gather unidirectional relationships
    for (source_id, target_id, rel_type), _ in relationship_index.items():
        reverse_key = (target_id, source_id, rel_type)
        if reverse_key not in relationship_index:
            source_indices.append(asset_id_index[source_id])
            target_indices.append(asset_id_index[target_id])
            hover_texts.append(
                f"Direction: {source_id} → {target_id}<br>Type: {rel_type}"
            )

    if not source_indices:
        return []

    # Vectorized arrow position calculation at 70% along each edge
    src_idx_arr = np.asarray(source_indices, dtype=int)
    tgt_idx_arr = np.asarray(target_indices, dtype=int)
    source_positions = positions[src_idx_arr]
    target_positions = positions[tgt_idx_arr]
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


def _validate_filter_parameters(filter_params: Dict[str, bool]) -> None:
    """Validate that all filter parameters are boolean values.

    Args:
        filter_params: Dictionary mapping filter parameter names to
            their boolean values.
            Expected keys:
                show_same_sector,
                show_market_cap,
                show_correlation,
                show_corporate_bond,
                show_commodity_currency,
                show_income_comparison,
                show_regulatory,
                show_all_relationships,
                toggle_arrows

    Raises:
        TypeError: If any parameter is not a boolean or if filter_params is not
            a dictionary
    """
    if not isinstance(filter_params, dict):
        raise TypeError(
            f"Invalid filter configuration: filter_params must be a dictionary, "
            f"got {type(filter_params).__name__}"
        )

    invalid_params = [
        name for name, value in filter_params.items() if not isinstance(value, bool)
    ]

    if invalid_params:
        raise TypeError(
            f"Invalid filter configuration: The following parameters must be "
            f"boolean values: {', '.join(invalid_params)}"
        )


def _validate_relationship_filters(
    relationship_filters: Optional[Dict[str, bool]],
) -> None:
    """
    Verify that `relationship_filters` is either `None` or a dictionary mapping string keys to boolean values.

    Parameters:
        relationship_filters (Optional[Dict[str, bool]]): Mapping of relationship type names to visibility flags, or `None` to indicate no filtering.

    Raises:
        TypeError: If `relationship_filters` is not `None` and not a `dict`.
        ValueError: If any key in `relationship_filters` is not a `str`, or if any value is not a `bool`.
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
    invalid_values = [
        key
        for key, value in relationship_filters.items()
        if not isinstance(value, bool)
    ]
    if invalid_values:
        raise ValueError(
            f"Invalid filter configuration: "
            f"relationship_filters must contain only boolean "
            f"values. Invalid keys: {', '.join(invalid_values)}"
        )

    # Validate keys are strings
    invalid_keys = [
        key for key in relationship_filters.keys() if not isinstance(key, str)
    ]
    if invalid_keys:
        raise ValueError(
            f"Invalid filter configuration: relationship_filters keys must be strings. "
            f"Invalid keys: {invalid_keys}"
        )


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
    Create a 3D Plotly figure of an AssetRelationshipGraph with optional per-relationship-type filtering and optional directional arrows.

    Builds node, relationship, and optional arrow traces from the graph's enhanced 3D visualization data, applies filters to include or exclude relationship types, and configures the figure layout.

    Parameters:
        graph (AssetRelationshipGraph): Graph providing get_3d_visualization_data_enhanced().
        show_same_sector (bool): Include "same sector" relationships.
        show_market_cap (bool): Include "market cap similar" relationships.
        show_correlation (bool): Include "correlation" relationships.
        show_corporate_bond (bool): Include "corporate bond to equity" relationships.
        show_commodity_currency (bool): Include "commodity currency" relationships.
        show_income_comparison (bool): Include "income comparison" relationships.
        show_regulatory (bool): Include "regulatory impact" relationships.
        show_all_relationships (bool): If True, ignore individual filters and include all relationship types.
        toggle_arrows (bool): If True, add directional arrow markers for unidirectional edges.

    Returns:
        go.Figure: A Plotly 3D figure containing node markers, relationship traces (filtered by the selected options), and optional directional arrows.

    Raises:
        ValueError: If the provided graph is not a valid AssetRelationshipGraph or if visualization data or filters are invalid.
        TypeError: If filter parameter types are not boolean.
    """
    # Validate graph input
    if not isinstance(graph, AssetRelationshipGraph) or not hasattr(
        graph, "get_3d_visualization_data_enhanced"
    ):
        raise ValueError(
            "Invalid graph data provided: graph must be an AssetRelationshipGraph instance "
            "with get_3d_visualization_data_enhanced method"
        )

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

    # Build filter configuration with validation
    try:
        if not show_all_relationships:
            relationship_filters = {
                "same_sector": show_same_sector,
                "market_cap_similar": show_market_cap,
                "correlation": show_correlation,
                "corporate_bond_to_equity": show_corporate_bond,
                "commodity_currency": show_commodity_currency,
                "income_comparison": show_income_comparison,
                "regulatory_impact": show_regulatory,
            }
            # Validate the constructed filter dictionary
            _validate_relationship_filters(relationship_filters)

            # Check if all filters are disabled (would result in empty
            # visualization)
            if not any(relationship_filters.values()):
                logger.warning(
                    "All relationship filters are disabled. "
                    "Visualization will show no relationships."
                )
        else:
            relationship_filters = None
    except (TypeError, ValueError) as exc:
        logger.exception("Failed to build filter configuration: %s", exc)
        raise ValueError(f"Invalid filter configuration: {exc}") from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Unexpected error building filter configuration: %s",
            exc,
        )
        raise ValueError("Failed to build filter configuration") from exc

    # Retrieve visualization data with error handling
    try:
        positions, asset_ids, colors, hover_texts = (
            graph.get_3d_visualization_data_enhanced()
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Failed to retrieve visualization data from graph: %s",
            exc,
        )
        raise ValueError("Failed to retrieve graph visualization data") from exc

    # Validate retrieved data
    try:
        _validate_visualization_data(positions, asset_ids, colors, hover_texts)
    except ValueError as exc:
        logger.error("Invalid visualization data: %s", exc)
        raise

    # Create figure
    fig = go.Figure()

    # Build relationship traces with comprehensive error handling
    try:
        relationship_traces = _create_relationship_traces(
            graph, positions, asset_ids, relationship_filters
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
        relationship_traces = []

    # Add relationship traces with error handling
    if relationship_traces:
        try:
            fig.add_traces(relationship_traces)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "Failed to add filtered relationship traces to figure: %s", exc
            )

    # Add directional arrows if enabled
    if toggle_arrows:
        try:
            arrow_traces = _create_directional_arrows(graph, positions, asset_ids)
        except (TypeError, ValueError) as exc:
            logger.exception(
                "Failed to create directional arrows due to invalid data: %s", exc
            )
            arrow_traces = []
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error creating directional arrows: %s", exc)
            arrow_traces = []

        if arrow_traces:
            try:
                fig.add_traces(arrow_traces)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Failed to add directional arrows to figure: %s", exc)

    # Add node trace
    try:
        node_trace = _create_node_trace(positions, asset_ids, colors, hover_texts)
        fig.add_trace(node_trace)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to create or add node trace: %s", exc)
        raise ValueError("Failed to create node visualization") from exc

    # Configure layout using centralized helper function
    try:
        dynamic_title, options = _prepare_layout_config(
            len(asset_ids), relationship_traces
        )
        _configure_3d_layout(fig, dynamic_title, options)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to configure figure layout: %s", exc)
        # Use fallback title if dynamic title generation fails
        fallback_title = "Financial Asset Network"
        _configure_3d_layout(fig, fallback_title)

    return fig
