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
    Determines whether a string appears to be a valid color format.

    Parameters:
        color (str): The color string to check.

    Returns:
        bool: `True` if the string matches a common hex or rgb/rgba pattern or is accepted as a named color fallback, `False` otherwise.

    Notes:
        Named color validation is permissive: strings that are not hex or rgb/rgba are allowed as named colors and will be validated later by Plotly at render time.
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
    Build a lookup mapping from each asset ID to its zero-based index in the provided sequence.

    Returns:
        index (Dict[str, int]): Dictionary where keys are asset IDs and values are their positions (0-based) in the input list.
    """
    return {asset_id: idx for idx, asset_id in enumerate(asset_ids)}


def _build_relationship_index(
    graph: AssetRelationshipGraph, asset_ids: Iterable[str]
) -> Dict[Tuple[str, str, str], float]:
    """
    Build a fast lookup index of relationships for the provided asset IDs.

    Parameters:
        graph (AssetRelationshipGraph): Graph object exposing a mapping of relationships.
        asset_ids (Iterable[str]): Iterable of asset IDs to include in the resulting index.

    Returns:
        Dict[Tuple[str, str, str], float]: Mapping from (source_id, target_id, rel_type) to numeric strength.

    Raises:
        TypeError: If `graph` is not an AssetRelationshipGraph, `graph.relationships` is not a dict,
                   `asset_ids` is not iterable, or relationship entries have incorrect types.
        ValueError: If `graph` is missing required data or relationship entries have invalid structure or non-numeric strengths.
    """
    # Validate graph input
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(
            f"Invalid input: graph must be an AssetRelationshipGraph instance, " f"got {type(graph).__name__}"
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
        raise TypeError(f"Invalid input: asset_ids must be an iterable, " f"got {type(asset_ids).__name__}") from exc
    # Validate asset_ids contains only strings
    if not all(isinstance(aid, str) for aid in asset_ids_set):
        raise ValueError("Invalid input: asset_ids must contain only string values")
    # Thread-safe access to graph.relationships using synchronization lock
    with _graph_access_lock:
        try:
            # Create a snapshot of only the relevant source_ids to minimize lock hold time
            relevant_relationships = {
                source_id: list(rels) for source_id, rels in graph.relationships.items() if source_id in asset_ids_set
            }
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError(f"Failed to create snapshot of graph.relationships: {exc}") from exc
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
    Create a Plotly 3D node trace representing assets with markers, labels, and hover texts.

    Parameters:
        positions (np.ndarray): Array of shape (n, 3) with finite numeric coordinates for n nodes.
        asset_ids (List[str]): Sequence of n non-empty asset identifier strings.
        colors (List[str]): Sequence of n color strings (hex, rgb/rgba, or named) for node markers.
        hover_texts (List[str]): Sequence of n non-empty strings used for hover text.

    Returns:
        go.Scatter3d: A configured Scatter3d trace containing node positions, marker styling, text labels, and hover information.

    Raises:
        ValueError: If inputs are the wrong types, positions is not shape (n, 3), any list lengths differ or are zero, or any elements fail content validation (e.g., non-finite coordinates or empty strings).
    """
    # Input validation: Perform basic type checks before delegating to comprehensive validator
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
        raise ValueError(f"positions length ({positions.shape[0]}) " f"must match asset_ids length ({len(asset_ids)})")

    # Comprehensive validation: detailed checks on content, numeric types, and finite values
    # Delegates to shared validator to ensure consistency across all visualization functions
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
    Create a title string that includes the base title plus counts of assets and relationships.

    Parameters:
        num_assets (int): Number of assets included in the visualization.
        num_relationships (int): Number of relationships displayed.
        base_title (str): Base title text to prefix the counts.

    Returns:
        str: Formatted title like "Financial Asset Network - 10 Assets, 5 Relationships".
    """
    return f"{base_title} - {num_assets} Assets, {num_relationships} Relationships"


def _calculate_visible_relationships(relationship_traces: List[go.Scatter3d]) -> int:
    """
    Count visible relationship edges represented by a list of relationship traces.

    Parameters:
        relationship_traces (List[go.Scatter3d]): Scatter3d traces where each visible edge contributes three consecutive `x` coordinates.

    Returns:
        int: Number of visible relationship edges (computed as total `x` coordinates across traces divided by 3).
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
    Create a layout title and options tailored to the provided visualization data.

    Parameters:
        num_assets (int): Total number of assets represented in the figure.
        relationship_traces (List[go.Scatter3d]): Relationship traces used to determine the count of visible relationships for the dynamic title.
        base_title (str): Base title text to prefix the generated title (default: "Financial Asset Network").
        layout_options (Optional[Dict[str, object]]): Additional layout options to merge into the returned configuration; when None an empty dict is returned.

    Returns:
        Tuple[str, Dict[str, object]]: A tuple where the first element is the generated dynamic title and the second element is the layout options dictionary.
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
    Add arrow traces representing unidirectional relationships to the provided 3D figure.

    This function creates arrow traces for edges that are not bidirectional and appends them to `fig` in-place; if no unidirectional edges exist, `fig` is not modified.

    Parameters:
        fig (go.Figure): Plotly 3D figure to which arrow traces will be added.
        graph (AssetRelationshipGraph): Graph containing relationship data used to determine arrows.
        positions (np.ndarray): Array of node positions with shape (n, 3), aligned with `asset_ids`.
        asset_ids (List[str]): Ordered list of asset IDs corresponding to rows in `positions`.
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
    Configure a 3D Plotly figure's layout and scene settings.

    Parameters:
        fig (go.Figure): Plotly figure to update.
        title (str): Centered title text to apply to the figure.
        options (Optional[Dict[str, object]]): Optional overrides for layout values:
            - width (int): Figure width in pixels (default 1200).
            - height (int): Figure height in pixels (default 800).
            - gridcolor (str): Color for axis grid lines (default 'rgba(200, 200, 200, 0.3)').
            - bgcolor (str): Scene background color (default 'rgba(248, 248, 248, 0.95)').
            - legend_bgcolor (str): Legend background color (default 'rgba(255, 255, 255, 0.8)').
            - legend_bordercolor (str): Legend border color (default 'rgba(0, 0, 0, 0.3)').
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
    Validate that `positions` is a (n, 3) numeric NumPy array containing only finite values.

    Parameters:
        positions (np.ndarray): Array of 3D coordinates with shape (n, 3), where each row is (x, y, z).

    Raises:
        ValueError: If `positions` is not a numpy.ndarray.
        ValueError: If `positions` does not have two dimensions with size 3 in the second axis (i.e., not shape (n, 3)).
        ValueError: If `positions` does not have a numeric dtype.
        ValueError: If any element in `positions` is not finite (contains NaN or Inf); message includes counts of NaN and Inf.
    """
    if not isinstance(positions, np.ndarray):
        raise ValueError(f"Invalid graph data: positions must be a numpy array, " f"got {type(positions).__name__}")
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(
            "Invalid graph data: Expected positions to be a "
            "(n, 3) numpy array, got array with shape "
            f"{positions.shape}"
        )
    if not np.issubdtype(positions.dtype, np.number):
        raise ValueError(f"Invalid graph data: positions must contain numeric values, " f"got dtype {positions.dtype}")
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

    Parameters:
        asset_ids (List[str]): Sequence of asset identifier strings to validate.

    Raises:
        ValueError: If `asset_ids` is not a list or tuple, or if any element is not a non-empty string.
    """
    if not isinstance(asset_ids, (list, tuple)):
        raise ValueError(f"Invalid graph data: asset_ids must be a list or tuple, " f"got {type(asset_ids).__name__}")
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("Invalid graph data: asset_ids must contain non-empty strings")


def _validate_colors_list(colors: List[str], expected_length: int) -> None:
    """
    Validate that `colors` is a list or tuple of color strings with the expected length and valid formats.

    Parameters:
        colors (List[str]): Sequence of color strings to validate.
        expected_length (int): Required number of color entries.

    Raises:
        ValueError: If `colors` is not a list/tuple of length `expected_length`, if any element is not a non-empty string, or if any color string fails `_is_valid_color_format`.
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
            raise ValueError(f"Invalid graph data: colors[{i}] has invalid color format: '{color}'")


def _validate_hover_texts_list(
    hover_texts: List[str],
    expected_length: int,
) -> None:
    """
    Validate the structure and contents of the hover_texts list used for node/edge tooltips.

    Parameters:
        hover_texts (List[str]): Sequence of hover text entries; each entry must be a non-empty string.
        expected_length (int): Required length of the sequence; hover_texts must have this exact length.

    Raises:
        ValueError: If hover_texts is not a list or tuple of length `expected_length`, or if any entry is not a non-empty string.
    """
    if not isinstance(hover_texts, (list, tuple)) or len(hover_texts) != expected_length:
        raise ValueError(f"Invalid graph data: hover_texts must be a list/tuple of length " f"{expected_length}")
    if not all(isinstance(h, str) and h for h in hover_texts):
        raise ValueError("Invalid graph data: hover_texts must contain non-empty strings")


def _validate_asset_ids_uniqueness(asset_ids: List[str]) -> None:
    """
    Ensure all asset IDs are unique.

    Parameters:
        asset_ids (List[str]): Sequence of asset identifier strings to validate.

    Raises:
        ValueError: If any duplicate asset IDs are found. The exception message lists the duplicate IDs.
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
    Validate arrays and lists used for 3D visualization to ensure consistent shapes, types, and content.

    Parameters:
        positions (np.ndarray): Array of shape (n, 3) containing finite numeric coordinates for n assets.
        asset_ids (List[str]): List of n non-empty asset identifier strings; must be unique.
        colors (List[str]): List of n color strings (e.g., hex, rgb/rgba, or named colors) validated for acceptable format.
        hover_texts (List[str]): List of n non-empty hover text strings for nodes.

    Raises:
        ValueError: If lengths or shapes do not match, if values are missing/invalid, or if asset_ids are not unique.
    """
    _validate_positions_array(positions)
    _validate_asset_ids_list(asset_ids)

    n = len(asset_ids)
    if positions.shape[0] != n:
        raise ValueError(
            f"Invalid graph data: positions length ({positions.shape[0]}) " f"must match asset_ids length ({n})"
        )

    _validate_colors_list(colors, n)
    _validate_hover_texts_list(hover_texts, n)
    _validate_asset_ids_uniqueness(asset_ids)


def visualize_3d_graph(graph: AssetRelationshipGraph) -> go.Figure:
    """
    Build a 3D Plotly figure visualizing an AssetRelationshipGraph with node markers, relationship line traces, and optional directional arrow indicators.

    Parameters:
        graph (AssetRelationshipGraph): Graph object exposing `get_3d_visualization_data_enhanced()` used to obtain node positions, asset identifiers, colors, and hover texts.

    Returns:
        go.Figure: A configured Plotly 3D figure containing node and relationship traces along with layout and legend settings.

    Raises:
        ValueError: If `graph` is not a valid AssetRelationshipGraph or the visualization data is missing or fails validation.
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
            xaxis=dict(title="Dimension 1", showgrid=True, gridcolor="rgba(200, 200, 200, 0.3)"),
            yaxis=dict(title="Dimension 2", showgrid=True, gridcolor="rgba(200, 200, 200, 0.3)"),
            zaxis=dict(title="Dimension 3", showgrid=True, gridcolor="rgba(200, 200, 200, 0.3)"),
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
    Group the graph's relationships by relationship type and whether they are bidirectional.

    This scans the graph for relationships that involve any of the provided asset_ids, optionally filters out disabled relationship types, and produces groups keyed by (rel_type, is_bidirectional). Each group contains a list of relationship dictionaries with `source_id`, `target_id`, and numeric `strength`. Bidirectional relationships are detected by the presence of the reverse edge and are included only once in the bidirectional group.

    Parameters:
        graph (AssetRelationshipGraph): Graph to scan for relationships.
        asset_ids (Iterable[str]): Asset IDs to include when building the relationship snapshot.
        relationship_filters (Optional[Dict[str, bool]]): If provided, keys are relationship types and values enable (`True`) or disable (`False`) inclusion; disabled types are skipped.

    Returns:
        Dict[Tuple[str, bool], List[dict]]: Mapping from `(rel_type, is_bidirectional)` to a list of relationships where each relationship is `{"source_id": str, "target_id": str, "strength": float}`.
    """
    relationship_index = _build_relationship_index(graph, asset_ids)

    processed_pairs: Set[Tuple[str, str, str]] = set()
    relationship_groups: Dict[Tuple[str, bool], List[dict]] = defaultdict(list)

    for (source_id, target_id, rel_type), strength in relationship_index.items():
        if relationship_filters and rel_type in relationship_filters and not relationship_filters[rel_type]:
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
    Build x, y, and z coordinate lists for edge traces using O(1) lookups.

    Parameters:
        relationships (List[dict]): Sequence of relationship dicts; each dict must contain
            the keys "source_id" and "target_id" identifying endpoints.
        positions (np.ndarray): Array of shape (n, 3) with 3D coordinates for each asset.
        asset_id_index (Dict[str, int]): Mapping from asset_id to its row index in `positions`.

    Returns:
        Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
            Three lists (edges_x, edges_y, edges_z), each of length 3 * number_of_relationships.
            For each relationship, its two endpoint coordinates occupy consecutive positions
            and the third entry is a `None` separator (i.e., [x_src, x_tgt, None, x_src2, x_tgt2, None, ...]).
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


def _build_hover_texts(relationships: List[dict], rel_type: str, is_bidirectional: bool) -> List[Optional[str]]:
    """
    Create hover text entries for a group of relationships, preallocating None placeholders so the result aligns with Plotly edge coordinate triples.

    Parameters:
        relationships (List[dict]): Sequence of relationship dicts. Each dict must contain 'source_id' (str), 'target_id' (str), and 'strength' (numeric).
        rel_type (str): Relationship type label included in each hover entry.
        is_bidirectional (bool): If True, uses the bidirectional symbol (↔) in the hover text; otherwise uses the unidirectional symbol (→).

    Returns:
        List[Optional[str]]: A list sized to 3 * len(relationships) where, for each relationship, index 3*i and 3*i+1 contain identical HTML-formatted hover text
        ("{source} ↔/→ {target}<br>Type: {rel_type}<br>Strength: {strength:.2f}") and index 3*i+2 is left as None (placeholder) for alignment with edge coordinate arrays.
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
    Determine the line styling for a relationship group, returning a dictionary of color, width, and dash.

    Validates the configured color for the given relationship type and uses a gray fallback ("#888888") if the color is invalid.

    Returns:
        dict: A mapping with keys:
            - `color` (str): The validated color string to use.
            - `width` (int): Line width (4 for bidirectional, 2 otherwise).
            - `dash` (str): Dash style ("solid" for bidirectional, "dash" otherwise).
    """
    color = REL_TYPE_COLORS[rel_type]
    if not _is_valid_color_format(color):
        logger.warning(
            "Invalid color format for relationship type '%s': '%s'. " "Using default gray.",
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
    Create a human-readable trace name for a relationship group.

    Parameters:
        rel_type (str): Relationship type identifier (e.g., "same_sector").
        is_bidirectional (bool): Whether the relationship is bidirectional.

    Returns:
        str: Title-cased relationship name with " (↔)" if bidirectional, otherwise " (→)".
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
    Create a 3D line trace representing a group of relationships.

    Returns:
        go.Scatter3d: A configured 3D line trace containing the group's edge coordinates, hover texts, visual style (color, width, dash), and legend grouping.
    """
    edges_x, edges_y, edges_z = _build_edge_coordinates_optimized(relationships, positions, asset_id_index)
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
    Create Plotly 3D line traces grouped by relationship type and directionality for batch addition to a figure.

    This function groups graph.relationships by (relationship type, is_bidirectional), builds optimized edge coordinates and hover information for each non-empty group, and returns a list of go.Scatter3d traces ready to add to a Plotly figure.

    Parameters:
        graph (AssetRelationshipGraph): Source graph containing a `relationships` mapping.
        positions (numpy.ndarray): Array of 3D node positions with one row per asset.
        asset_ids (List[str]): Ordered list of asset IDs corresponding to `positions`.
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping of relationship type keys to booleans to include/exclude specific relationship types; when None all relationship types are considered.

    Returns:
        List[go.Scatter3d]: A list of configured 3D scatter traces (one per relationship group) suitable for fig.add_traces().

    Raises:
        ValueError: If `graph` is not an AssetRelationshipGraph, if `graph.relationships` is missing or not a dict, if `positions` is not a numpy array, or if `positions` length does not match `asset_ids`.
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

    relationship_groups = _collect_and_group_relationships(graph, asset_ids, relationship_filters)

    traces: List[go.Scatter3d] = []
    for (rel_type, is_bidirectional), relationships in relationship_groups.items():
        if relationships:
            trace = _create_trace_for_group(rel_type, is_bidirectional, relationships, positions, asset_id_index)
            traces.append(trace)

    return traces


def _validate_directional_arrows_inputs(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> None:
    """
    Validate inputs required to create directional arrow traces.

    Parameters:
        graph (AssetRelationshipGraph): Graph object expected to expose a `relationships` dictionary.
        positions (np.ndarray): Array of 3D positions; must support len() and have one entry per asset.
        asset_ids (List[str]): Sequence of asset identifiers matching `positions` length.

    Raises:
        TypeError: If `graph` is not an instance of AssetRelationshipGraph.
        ValueError: If `graph.relationships` is missing or not a dict; if `positions` or `asset_ids` is None; if their lengths differ or do not support len().
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError("Invalid input data: graph must have a relationships dictionary")
    if positions is None or asset_ids is None:
        raise ValueError("positions and asset_ids must not be None")
    try:
        if len(positions) != len(asset_ids):
            raise ValueError("Invalid input data: positions and asset_ids must have the same length")
    except TypeError as exc:
        raise ValueError("Invalid input data: positions and asset_ids must support len()") from exc


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> List[go.Scatter3d]:
    """
    Create marker traces representing directional arrows for unidirectional relationships in the graph.

    For each relationship that does not have a corresponding reverse relationship, computes an arrow position at 70% of the vector from source to target and returns a list containing a single Scatter3d trace of diamond markers (one marker per unidirectional relationship). If there are no unidirectional relationships, returns an empty list.

    Returns:
        List[go.Scatter3d]: A list containing one Scatter3d trace with marker positions and hover texts for unidirectional relationships, or an empty list if none are present.
    """
    _validate_directional_arrows_inputs(graph, positions, asset_ids)
    # Input validation complete; proceed with arrow creation logic below

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
            hover_texts.append(f"Direction: {source_id} → {target_id}<br>Type: {rel_type}")

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
    """
    Validate that all values in filter_params are booleans.

    Parameters:
        filter_params (dict): Mapping of filter names to boolean flags. Expected keys include
            'show_same_sector', 'show_market_cap', 'show_correlation', 'show_corporate_bond',
            'show_commodity_currency', 'show_income_comparison', 'show_regulatory',
            'show_all_relationships', and 'toggle_arrows'.

    Raises:
        TypeError: If `filter_params` is not a dict or if any mapped value is not a boolean.
    """
    if not isinstance(filter_params, dict):
        raise TypeError(
            f"Invalid filter configuration: filter_params must be a dictionary, " f"got {type(filter_params).__name__}"
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
    Validate the structure and contents of a relationship_filters mapping.

    Parameters:
        relationship_filters (Optional[Dict[str, bool]]): Mapping from relationship type names
            to boolean flags indicating whether each type should be shown. May be None to
            indicate no filtering.

    Raises:
        TypeError: If relationship_filters is not None and is not a dictionary.
        ValueError: If any key in relationship_filters is not a string or any value is not a boolean.
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
            f"Invalid filter configuration: relationship_filters keys must be strings. " f"Invalid keys: {invalid_keys}"
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
    Create a 3D Plotly Figure of the asset relationship graph with optional relationship-type filters and toggleable directional arrows.

    Parameters:
        graph (AssetRelationshipGraph): Source graph providing visualization data via get_3d_visualization_data_enhanced().
        toggle_arrows (bool): If True, include directional arrow indicators for unidirectional relationships.

    Returns:
        go.Figure: A Plotly Figure containing node and relationship traces configured according to the provided filters.

    Raises:
        ValueError: If the graph is invalid, required visualization data cannot be retrieved, or required traces cannot be constructed.
        TypeError: If any provided filter parameter is not a boolean.
    """
    # Validate graph input
    if not isinstance(graph, AssetRelationshipGraph) or not hasattr(graph, "get_3d_visualization_data_enhanced"):
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
                logger.warning("All relationship filters are disabled. " "Visualization will show no relationships.")
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
        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
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
        relationship_traces = _create_relationship_traces(graph, positions, asset_ids, relationship_filters)
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
            logger.exception("Failed to add filtered relationship traces to figure: %s", exc)

    # Add directional arrows if enabled
    if toggle_arrows:
        try:
            arrow_traces = _create_directional_arrows(graph, positions, asset_ids)
        except (TypeError, ValueError) as exc:
            logger.exception("Failed to create directional arrows due to invalid data: %s", exc)
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
        dynamic_title, options = _prepare_layout_config(len(asset_ids), relationship_traces)
        _configure_3d_layout(fig, dynamic_title, options)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to configure figure layout: %s", exc)
        # Use fallback title if dynamic title generation fails
        fallback_title = "Financial Asset Network"
        _configure_3d_layout(fig, fallback_title)

    return fig
