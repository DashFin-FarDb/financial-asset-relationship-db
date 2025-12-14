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
    if re.match(r"^rgba?\\(\\s*\\d+\\s*,\\s*\\d+\\s*,\\s*\\d+\\s*(,\\s*[\\d.]+\\s*)?\\)$", color):
        return True

    # Fallback: allow named colors; Plotly will validate at render time
    return True


def _build_asset_id_index(asset_ids: List[str]) -> Dict[str, int]:
    """Build O(1) lookup index for asset IDs to their positions."""
    return {asset_id: idx for idx, asset_id in enumerate(asset_ids)}


def _build_relationship_index(
    graph: AssetRelationshipGraph, asset_ids: Iterable[str]
) -> Dict[Tuple[str, str, str], float]:
    """Build optimized relationship index for O(1) lookups with pre-filtering and thread safety.

    This function consolidates relationship data into a single index structure
    that can be efficiently queried for:
    - Checking if a relationship exists (O(1) lookup)
    - Getting relationship strength (O(1) lookup)
    - Detecting bidirectional relationships (O(1) reverse lookup)

    Performance optimizations:
    - Pre-filters graph.relationships to only include relevant source_ids
    - Uses set-based membership tests for O(1) lookups
    - Avoids unnecessary iterations over irrelevant relationships
    - Reduces continue statements by filtering upfront

    Thread Safety:
    ==============
    This function uses a reentrant lock (RLock) to protect concurrent access to graph.relationships
    within this module. However, true thread safety requires coordination across the entire codebase.

    Implementation:
    - Uses threading.RLock (_graph_access_lock) to synchronize access to graph.relationships
    - The lock is reentrant, allowing the same thread to acquire it multiple times safely
    - Creates a snapshot of relationships within the lock to minimize lock hold time

    Thread safety guarantees (with conditions):
    ✓ SAFE: Multiple threads calling visualization functions in this module concurrently
    ✓ SAFE: Concurrent calls to this function with the same graph object
    ⚠ CONDITIONAL: Concurrent modifications to graph.relationships are only safe if:
      - All code that modifies graph.relationships uses the same _graph_access_lock, OR
      - The graph object is treated as immutable after creation (recommended approach)

    Recommended usage patterns for thread safety:
    1. PREFERRED: Treat graph objects as immutable after creation. Build the graph completely
       before passing it to visualization functions. This eliminates the need for locking.
    2. ALTERNATIVE: If you must modify graph.relationships concurrently, ensure all
       modification code acquires _graph_access_lock before accessing graph.relationships.
       This requires coordination across your entire codebase.

    Note: The AssetRelationshipGraph class itself does not implement any locking mechanisms.
    Thread safety for modifications must be managed by the calling code. If other parts of
    your application modify graph.relationships without using _graph_access_lock, race
    conditions may occur.

    Error Handling (addresses review feedback):
    ===========================================
    This function implements comprehensive error handling to ensure robustness:
    - Validates that graph is an AssetRelationshipGraph instance
    - Validates that graph.relationships exists and is a properly formatted dictionary
    - Validates that asset_ids is iterable and contains only strings
    - Validates each relationship tuple has the correct structure (3 elements)
    - Validates data types for target_id (string), rel_type (string), and strength (numeric)
    - Provides detailed error messages indicating the exact location and nature of any issues

    Args:
        graph: The asset relationship graph
        asset_ids: Iterable of asset IDs to include (will be converted to a set for O(1) membership tests)

    Returns:
        Dictionary mapping (source_id, target_id, rel_type) to strength for all relationships

    Raises:
        TypeError: If graph is not an AssetRelationshipGraph instance or if data types are invalid
        ValueError: If graph.relationships has invalid structure or malformed data
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

    # Validate asset_ids is iterable
    try:
        asset_ids_set = set(asset_ids)
    except TypeError as exc:
        raise TypeError(f"Invalid input: asset_ids must be an iterable, got {type(asset_ids).__name__}") from exc

    # Validate asset_ids contains only strings
    if not all(isinstance(aid, str) for aid in asset_ids_set):
        raise ValueError("Invalid input: asset_ids must contain only string values")

    # Thread-safe access to graph.relationships using synchronization lock
    # This protects against concurrent modifications and ensures data consistency
    with _graph_access_lock:
        # Create a snapshot of relationships within the lock to minimize lock hold time
        # Pre-filter to only include relevant source_ids
        try:
            relevant_relationships = {
                source_id: list(rels)  # Create a copy of the list
                for source_id, rels in graph.relationships.items()
                if source_id in asset_ids_set
            }
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError(f"Failed to create snapshot of graph.relationships: {exc}") from exc

    # Build index outside the lock (no shared state access)
    # This minimizes the time the lock is held
    relationship_index: Dict[Tuple[str, str, str], float] = {}

    # Process relationships with comprehensive error handling
    for source_id, rels in relevant_relationships.items():
        # Validate that rels is iterable
        if not isinstance(rels, (list, tuple)):
            raise TypeError(
                f"Invalid graph data: relationships for source_id '{source_id}' must be a list or tuple, "
                f"got {type(rels).__name__}"
            )

        # Process each relationship with validation
        for idx, rel in enumerate(rels):
            # Validate relationship structure
            if not isinstance(rel, (list, tuple)):
                raise TypeError(
                    f"Invalid graph data: relationship at index {idx} for source_id '{source_id}' "
                    f"must be a list or tuple, got {type(rel).__name__}"
                )

            if len(rel) != 3:
                raise ValueError(
                    f"Invalid graph data: relationship at index {idx} for source_id '{source_id}' "
                    f"must have exactly 3 elements (target_id, rel_type, strength), got {len(rel)} elements"
                )

            target_id, rel_type, strength = rel

            # Validate target_id type
            if not isinstance(target_id, str):
                raise TypeError(
                    f"Invalid graph data: target_id at index {idx} for source_id '{source_id}' "
                    f"must be a string, got {type(target_id).__name__}"
                )

            # Validate rel_type type
            if not isinstance(rel_type, str):
                raise TypeError(
                    f"Invalid graph data: rel_type at index {idx} for source_id '{source_id}' "
                    f"must be a string, got {type(rel_type).__name__}"
                )

            # Validate and convert strength to float
            try:
                strength_float = float(strength)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid graph data: strength at index {idx} for source_id '{source_id}' "
                    f"must be numeric (got {type(strength).__name__} with value '{strength}')"
                ) from exc

            # Add to index if target is in asset_ids_set
            if target_id in asset_ids_set:
                relationship_index[(source_id, target_id, rel_type)] = strength_float

    return relationship_index


def _create_node_trace(
    positions: np.ndarray,
    asset_ids: List[str],
    colors: List[str],
    hover_texts: List[str],
) -> go.Scatter3d:
    """Create node trace for 3D visualization with comprehensive input validation.

    Validates all inputs to ensure:
    - positions is a non-empty 2D numpy array with shape (n, 3) containing finite numeric values
    - asset_ids is a non-empty list/tuple of non-empty strings with length matching positions
    - colors is a non-empty list/tuple of valid color strings with length matching positions
    - hover_texts is a non-empty list/tuple of strings with length matching positions
    - All arrays have consistent lengths
    - No duplicate asset IDs

    Args:
        positions: NumPy array of node positions with shape (n, 3) containing finite numeric values
        asset_ids: List of asset ID strings (must be non-empty strings, length must match positions)
        colors: List of node colors (length must match positions)
        hover_texts: List of hover texts (length must match positions)

    Returns:
        Plotly Scatter3d trace for nodes

    Raises:
        ValueError: If input parameters are invalid, have mismatched dimensions, or contain invalid data
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
            f"Length mismatch: asset_ids({len(asset_ids)}), colors({len(colors)}), "
            f"hover_texts({len(hover_texts)}) must all be equal"
        )
    if positions.shape[0] != len(asset_ids):
        raise ValueError(f"positions length ({positions.shape[0]}) must match asset_ids length ({len(asset_ids)})")

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
            line=dict(color="rgba(0,0,0,0.8)", width=2),
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
    num_assets: int, num_relationships: int, base_title: str = "Financial Asset Network"
) -> str:
    """Generate a dynamic title for the visualization based on asset and relationship counts.

    This function creates a consistent title format across different visualization contexts,
    improving modularity and making it easier to customize titles without modifying core logic.

    Args:
        num_assets: Number of assets in the visualization
        num_relationships: Number of relationships displayed
        base_title: Base title text (default: "Financial Asset Network")

    Returns:
        Formatted title string with asset and relationship counts
    """
    return f"{base_title} - {num_assets} Assets, {num_relationships} Relationships"


def _calculate_visible_relationships(relationship_traces: List[go.Scatter3d]) -> int:
    """Calculate the number of visible relationships from traces.

    This helper function extracts the relationship count calculation logic,
    making it reusable and testable independently of the visualization logic.

    Args:
        relationship_traces: List of Scatter3d traces representing relationships

    Returns:
        Number of visible relationships (edges) in the traces
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
    """Prepare layout configuration with dynamic title based on visualization data.

    This function separates layout configuration logic from the main visualization function,
    improving modularity and making it easier to customize layouts in different contexts.

    Args:
        num_assets: Number of assets in the visualization
        relationship_traces: List of relationship traces to count visible relationships
        base_title: Base title text (default: "Financial Asset Network")
        layout_options: Optional layout customization options

    Returns:
        Tuple of (dynamic_title, layout_options) ready for use with _configure_3d_layout
    """
    num_relationships = _calculate_visible_relationships(relationship_traces)
    dynamic_title = _generate_dynamic_title(num_assets, num_relationships, base_title)
    options = layout_options or {}
    return dynamic_title, options


def _add_directional_arrows_to_figure(
    fig: go.Figure, graph: AssetRelationshipGraph, positions: np.ndarray, asset_ids: List[str]
) -> None:
    """Add directional arrows to the figure for unidirectional relationships using batch operations."""
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
            - width (int)
            - height (int)
            - gridcolor (str)
            - bgcolor (str)
            - legend_bgcolor (str)
            - legend_bordercolor (str)
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
    """Validate positions array structure and values."""
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
            f"Invalid graph data: positions must contain finite values (no NaN or Inf). Found {nan_count} NaN and {inf_count} Inf"
        )


def _validate_asset_ids_list(asset_ids: List[str]) -> None:
    """Validate asset_ids list structure and content."""
    if not isinstance(asset_ids, (list, tuple)):
        raise ValueError(f"Invalid graph data: asset_ids must be a list or tuple, got {type(asset_ids).__name__}")
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("Invalid graph data: asset_ids must contain non-empty strings")


def _validate_colors_list(colors: List[str], expected_length: int) -> None:
    """Validate colors list structure, content, and format."""
    if not isinstance(colors, (list, tuple)) or len(colors) != expected_length:
        colors_type = type(colors).__name__
        colors_len = len(colors) if isinstance(colors, (list, tuple)) else "N/A"
        raise ValueError(
            f"Invalid graph data: colors must be a list/tuple of length {expected_length}, "
            f"got {colors_type} with length {colors_len}"
        )
    if not all(isinstance(c, str) and c for c in colors):
        raise ValueError("Invalid graph data: colors must contain non-empty strings")

    for i, color in enumerate(colors):
        if not _is_valid_color_format(color):
            raise ValueError(f"Invalid graph data: colors[{i}] has invalid color format: '{color}'")


def _validate_hover_texts_list(hover_texts: List[str], expected_length: int) -> None:
    """Validate hover_texts list structure and content."""
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
    """Validate visualization data integrity to prevent runtime errors."""
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
    """Create enhanced 3D visualization of asset relationship graph with improved relationship visibility"""
    if not isinstance(graph, AssetRelationshipGraph) or not hasattr(graph, "get_3d_visualization_data_enhanced"):
        raise ValueError("Invalid graph data provided")

    positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

    # Validate visualization data to prevent runtime errors (addresses review feedback)
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
    """Collect and group relationships with directionality info in a single pass."""
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
    """Build edge coordinate lists for relationships using optimized O(1) lookups."""
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
    """Build hover text list for relationships with pre-allocation for performance."""
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
    """Get line style configuration for a relationship with color validation.

    Args:
        rel_type: Relationship type identifier
        is_bidirectional: Whether the relationship is bidirectional

    Returns:
        Dictionary with line style configuration including validated color
    """
    color = REL_TYPE_COLORS[rel_type]
    if not _is_valid_color_format(color):
        logger.warning("Invalid color format for relationship type '%s': '%s'. Using default gray.", rel_type, color)
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
    """Create a single trace for a relationship group with optimized performance."""
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
    """Create separate traces for different types of relationships with enhanced visibility.

    Returns a list of traces for batch addition to figure using fig.add_traces() for optimal performance.
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


def _create_directional_arrows(
    graph: AssetRelationshipGraph, positions: np.ndarray, asset_ids: List[str]
) -> List[go.Scatter3d]:
    """Create arrow markers for unidirectional relationships using vectorized NumPy operations. Returns a list of traces for batch addition to figure."""
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError("Invalid input data: graph must have a relationships dictionary")

    try:
        if positions is None or asset_ids is None:
            raise ValueError("positions and asset_ids must not be None")
        if len(positions) != len(asset_ids):
            raise ValueError("positions and asset_ids must have the same length")
    except TypeError as exc:
        raise ValueError("Invalid input data: positions and asset_ids must support len()") from exc

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

    # Early return optimization: prevent unnecessary computation and memory allocation
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
    """Validate that all filter parameters are boolean values.

    Args:
        filter_params: Dictionary mapping filter parameter names to their boolean values.
            Expected keys: show_same_sector, show_market_cap, show_correlation,
            show_corporate_bond, show_commodity_currency, show_income_comparison,
            show_regulatory, show_all_relationships, toggle_arrows

    Raises:
        TypeError: If any parameter is not a boolean or if filter_params is not a dictionary
    """
    if not isinstance(filter_params, dict):
        raise TypeError(
            f"Invalid filter configuration: filter_params must be a dictionary, " f"got {type(filter_params).__name__}"
        )

    invalid_params = [name for name, value in filter_params.items() if not isinstance(value, bool)]

    if invalid_params:
        raise TypeError(
            f"Invalid filter configuration: The following parameters must be boolean values: "
            f"{', '.join(invalid_params)}"
        )


def _validate_relationship_filters(relationship_filters: Optional[Dict[str, bool]]) -> None:
    """Validate relationship filter dictionary structure and values.

    Args:
        relationship_filters: Optional dictionary mapping relationship types to boolean visibility flags

    Raises:
        TypeError: If relationship_filters is not None and not a dictionary
        ValueError: If relationship_filters contains invalid keys or non-boolean values
    """
    if relationship_filters is None:
        return

    if not isinstance(relationship_filters, dict):
        raise TypeError(
            f"Invalid filter configuration: relationship_filters must be a dictionary or None, "
            f"got {type(relationship_filters).__name__}"
        )

    # Validate all values are boolean
    invalid_values = [key for key, value in relationship_filters.items() if not isinstance(value, bool)]
    if invalid_values:
        raise ValueError(
            f"Invalid filter configuration: relationship_filters must contain only boolean values. "
            f"Invalid keys: {', '.join(invalid_values)}"
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
    """Create 3D visualization with selective relationship filtering.

    This function dynamically creates and adds relationship traces based on optional filters,
    with comprehensive error handling to manage potential issues from invalid filter
    configurations or data inconsistencies.

    Args:
        graph: Asset relationship graph to visualize
        show_same_sector: Show same sector relationships (default: True)
        show_market_cap: Show market cap relationships (default: True)
        show_correlation: Show correlation relationships (default: True)
        show_corporate_bond: Show corporate bond relationships (default: True)
        show_commodity_currency: Show commodity currency relationships (default: True)
        show_income_comparison: Show income comparison relationships (default: True)
        show_regulatory: Show regulatory relationships (default: True)
        show_all_relationships: Master toggle to show all relationships (default: True)
        toggle_arrows: Show directional arrows for unidirectional relationships (default: True)

    Returns:
        Plotly Figure object with 3D visualization

    Raises:
        ValueError: If graph is invalid or missing required methods/attributes
        TypeError: If filter parameters are not boolean values
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

            # Check if all filters are disabled (would result in empty visualization)
            if not any(relationship_filters.values()):
                logger.warning("All relationship filters are disabled. Visualization will show no relationships.")
        else:
            relationship_filters = None
    except (TypeError, ValueError) as exc:
        logger.exception("Failed to build filter configuration: %s", exc)
        raise ValueError(f"Invalid filter configuration: {exc}") from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error building filter configuration: %s", exc)
        raise ValueError("Failed to build filter configuration") from exc

    # Retrieve visualization data with error handling
    try:
        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to retrieve visualization data from graph: %s", exc)
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
            "Unexpected error creating filtered relationship traces (filters: %s): %s", relationship_filters, exc
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
    # Error Handling Strategy: Directional Arrows
    # - Catch TypeError/ValueError for invalid data (log and set empty list)
    # - Catch unexpected errors (log and set empty list to allow visualization to continue)
