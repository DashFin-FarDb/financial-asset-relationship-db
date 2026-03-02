from __future__ import annotations

import logging
import re
import threading
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final

import numpy as np
import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph

logger = logging.getLogger(__name__)

# Protect concurrent access to graph.relationships (graph is mutable).
_GRAPH_ACCESS_LOCK: Final[threading.RLock] = threading.RLock()

# Precompiled regex patterns for color validation.
_HEX_COLOR_RE: Final[re.Pattern[str]] = re.compile(
    r"^#(?:[0-9A-Fa-f]{3}){1,2}(?:[0-9A-Fa-f]{2})?$"
)
_RGB_COLOR_RE: Final[re.Pattern[str]] = re.compile(
    r"^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(,\s*[\d.]+\s*)?\)$"
)

# Color and style mapping for relationship types (shared constant).
REL_TYPE_COLORS: Final[defaultdict[str, str]] = defaultdict(
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
    """Return True if *color* looks like a Plotly-acceptable color string.

    Supports hex (#RGB, #RRGGBB, #RRGGBBAA) and rgb/rgba() functions. Named
    colors are allowed and validated by Plotly at render time.

    Args:
        color: Candidate color string.

    Returns:
        True if the format is recognized, otherwise False.
    """
    if not isinstance(color, str) or not color:
        return False

    if _HEX_COLOR_RE.match(color):
        return True

    if _RGB_COLOR_RE.match(color):
        return True

    # Allow named colors (Plotly will validate at render time).
    return True


def _build_asset_id_index(asset_ids: Sequence[str]) -> dict[str, int]:
    """Build an O(1) lookup index for asset IDs to their positions."""
    return {asset_id: idx for idx, asset_id in enumerate(asset_ids)}


def _coerce_asset_ids(asset_ids: Iterable[str]) -> set[str]:
    """Normalize and validate asset IDs to a set of non-empty strings."""
    try:
        asset_ids_set = set(asset_ids)
    except TypeError as exc:
        raise TypeError(
            "Invalid input: asset_ids must be an iterable of strings"
        ) from exc

    if not asset_ids_set:
        raise ValueError("Invalid input: asset_ids must be non-empty")

    if not all(isinstance(aid, str) and aid for aid in asset_ids_set):
        raise ValueError("Invalid input: asset_ids must contain only non-empty strings")

    return asset_ids_set


def _build_relationship_index(
    graph: AssetRelationshipGraph,
    asset_ids: Iterable[str],
) -> dict[tuple[str, str, str], float]:
    """Build an optimized relationship index for O(1) lookups.

    Creates a snapshot of relevant relationships within a reentrant lock to
    guard against concurrent modifications.

    Args:
        graph: The asset relationship graph.
        asset_ids: Iterable of asset IDs to include.

    Returns:
        Mapping from (source_id, target_id, rel_type) to strength for relationships
        whose source and target are both in *asset_ids*.

    Raises:
        TypeError: If *graph* is not an AssetRelationshipGraph or graph data types
            are invalid.
        ValueError: If required graph attributes are missing or relationship rows
            are malformed.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(
            "Invalid input: graph must be an AssetRelationshipGraph instance, "
            f"got {type(graph).__name__}"
        )

    if not hasattr(graph, "relationships"):
        raise ValueError("Invalid graph: missing 'relationships' attribute")

    if not isinstance(graph.relationships, dict):
        raise TypeError(
            "Invalid graph data: graph.relationships must be a dictionary, "
            f"got {type(graph.relationships).__name__}"
        )

    asset_ids_set = _coerce_asset_ids(asset_ids)

    # Snapshot only relevant source IDs, and pre-filter to relevant & well-formed rows.
    with _GRAPH_ACCESS_LOCK:
        try:
            relevant_relationships: dict[str, list[tuple[Any, Any, Any]]] = {
                source_id: [
                    rel
                    for rel in rels
                    if isinstance(rel, (list, tuple))
                    and len(rel) == 3
                    and isinstance(rel[0], str)
                    and rel[0] in asset_ids_set
                ]
                for source_id, rels in graph.relationships.items()
                if source_id in asset_ids_set
            }
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError(
                f"Failed to snapshot graph.relationships: {exc}"
            ) from exc

    relationship_index: dict[tuple[str, str, str], float] = {}

    for source_id, rels in relevant_relationships.items():
        if not isinstance(rels, (list, tuple)):
            raise TypeError(
                "Invalid graph data: relationships for "
                f"'{source_id}' must be a list/tuple, got {type(rels).__name__}"
            )

        for idx, rel in enumerate(rels):
            # rel is already prefiltered to len == 3, but keep strict checks.
            if not isinstance(rel, (list, tuple)) or len(rel) != 3:
                raise ValueError(
                    "Invalid graph data: relationship at index "
                    f"{idx} for '{source_id}' must be a 3-element tuple "
                    "(target_id, rel_type, strength)"
                )

            target_id, rel_type, strength = rel

            if not isinstance(target_id, str) or not isinstance(rel_type, str):
                raise TypeError(
                    "Invalid graph data: relationship at index "
                    f"{idx} for '{source_id}' must use string target_id and rel_type"
                )

            try:
                strength_float = float(strength)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Invalid graph data: strength at index "
                    f"{idx} for '{source_id}' must be numeric"
                ) from exc

            if target_id in asset_ids_set:
                relationship_index[(source_id, target_id, rel_type)] = strength_float

    return relationship_index


def _validate_positions_array(positions: np.ndarray) -> None:
    """Validate positions array structure and values.

    Raises:
        ValueError: If the array is not numeric, not shape (n, 3), or contains NaN/Inf.
    """
    if not isinstance(positions, np.ndarray):
        raise ValueError(
            "Invalid graph data: positions must be a numpy array, "
            f"got {type(positions).__name__}"
        )

    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(
            "Invalid graph data: expected positions to be a (n, 3) numpy array, "
            f"got array with shape {positions.shape}"
        )

    if not np.issubdtype(positions.dtype, np.number):
        raise ValueError(
            "Invalid graph data: positions must contain numeric values, "
            f"got dtype {positions.dtype}"
        )

    if not np.isfinite(positions).all():
        nan_count = int(np.isnan(positions).sum())
        inf_count = int(np.isinf(positions).sum())
        raise ValueError(
            "Invalid graph data: positions must contain finite values (no NaN/Inf). "
            f"Found {nan_count} NaN and {inf_count} Inf"
        )


def _validate_asset_ids_list(asset_ids: Sequence[str]) -> None:
    """Validate asset_ids list structure and content."""
    if not isinstance(asset_ids, (list, tuple)):
        raise ValueError(
            "Invalid graph data: asset_ids must be a list or tuple, got "
            f"{type(asset_ids).__name__}"
        )

    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("Invalid graph data: asset_ids must contain non-empty strings")


def _validate_asset_ids_uniqueness(asset_ids: Sequence[str]) -> None:
    """Validate that asset IDs are unique."""
    if len(set(asset_ids)) == len(asset_ids):
        return

    seen_ids: set[str] = set()
    dup_ids: list[str] = []
    for aid in asset_ids:
        if aid in seen_ids and aid not in dup_ids:
            dup_ids.append(aid)
        else:
            seen_ids.add(aid)

    raise ValueError(
        "Invalid graph data: duplicate asset_ids detected: " + ", ".join(dup_ids)
    )


def _validate_colors_list(colors: Sequence[str], expected_length: int) -> None:
    """Validate colors list structure, content, and format."""
    if not isinstance(colors, (list, tuple)) or len(colors) != expected_length:
        colors_type = type(colors).__name__
        colors_len = len(colors) if isinstance(colors, (list, tuple)) else "N/A"
        raise ValueError(
            "Invalid graph data: colors must be a list/tuple of length "
            f"{expected_length}, got {colors_type} with length {colors_len}"
        )

    if not all(isinstance(c, str) and c for c in colors):
        raise ValueError("Invalid graph data: colors must contain non-empty strings")

    for i, color in enumerate(colors):
        if not _is_valid_color_format(color):
            raise ValueError(
                f"Invalid graph data: colors[{i}] has invalid color format: '{color}'"
            )


def _validate_hover_texts_list(hover_texts: Sequence[str], expected_length: int) -> None:
    """Validate hover_texts list structure and content."""
    if not isinstance(hover_texts, (list, tuple)) or len(hover_texts) != expected_length:
        raise ValueError(
            "Invalid graph data: hover_texts must be a list/tuple of length "
            f"{expected_length}"
        )

    if not all(isinstance(h, str) and h for h in hover_texts):
        raise ValueError("Invalid graph data: hover_texts must contain non-empty strings")


def _validate_visualization_data(
    positions: np.ndarray,
    asset_ids: Sequence[str],
    colors: Sequence[str],
    hover_texts: Sequence[str],
) -> None:
    """Validate visualization data integrity to prevent runtime errors."""
    _validate_positions_array(positions)
    _validate_asset_ids_list(asset_ids)
    _validate_asset_ids_uniqueness(asset_ids)

    n = len(asset_ids)
    if positions.shape[0] != n:
        raise ValueError(
            "Invalid graph data: positions length "
            f"({positions.shape[0]}) does not match asset_ids length ({n})"
        )

    _validate_colors_list(colors, n)
    _validate_hover_texts_list(hover_texts, n)


def _create_node_trace(
    positions: np.ndarray,
    asset_ids: list[str],
    colors: list[str],
    hover_texts: list[str],
) -> go.Scatter3d:
    """Create node trace for 3D visualization."""
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)

    if not asset_ids:
        raise ValueError("Cannot create node trace with empty inputs")

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
    num_assets: int,
    num_relationships: int,
    base_title: str = "Financial Asset Network",
) -> str:
    """Generate a dynamic visualization title with asset and relationship counts."""
    return f"{base_title} - {num_assets} Assets, {num_relationships} Relationships"


def _calculate_visible_relationships(relationship_traces: Sequence[go.Scatter3d]) -> int:
    """Calculate the number of visible relationship edges from traces."""
    try:
        # Each edge is encoded as [x0, x1, None] => 3 elements per edge.
        total = sum(len(getattr(trace, "x", []) or []) for trace in relationship_traces)
        return total // 3
    except Exception:  # pylint: disable=broad-except
        return 0


def _prepare_layout_config(
    num_assets: int,
    relationship_traces: Sequence[go.Scatter3d],
    base_title: str = "Financial Asset Network",
    layout_options: Mapping[str, object] | None = None,
) -> tuple[str, dict[str, object]]:
    """Prepare layout configuration with a dynamic title."""
    num_relationships = _calculate_visible_relationships(relationship_traces)
    dynamic_title = _generate_dynamic_title(num_assets, num_relationships, base_title)
    options: dict[str, object] = dict(layout_options or {})
    return dynamic_title, options


def _configure_3d_layout(
    fig: go.Figure,
    title: str,
    options: Mapping[str, Any] | None = None,
) -> None:
    """Configure the 3D layout for a figure."""
    opts = dict(options or {})
    width = int(opts.get("width", 1200))
    height = int(opts.get("height", 800))
    gridcolor = str(opts.get("gridcolor", "rgba(200, 200, 200, 0.3)"))
    bgcolor = str(opts.get("bgcolor", "rgba(248, 248, 248, 0.95)"))
    legend_bgcolor = str(opts.get("legend_bgcolor", "rgba(255, 255, 255, 0.8)"))
    legend_bordercolor = str(opts.get("legend_bordercolor", "rgba(0, 0, 0, 0.3)"))

    fig.update_layout(
        title={"text": title, "x": 0.5, "xanchor": "center", "font": {"size": 16}},
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


def _build_relationship_filters(
    show_same_sector: bool,
    show_market_cap: bool,
    show_correlation: bool,
    show_corporate_bond: bool,
    show_commodity_currency: bool,
    show_income_comparison: bool,
    show_regulatory: bool,
    show_all_relationships: bool,
) -> dict[str, bool] | None:
    """Build per-relationship-type filter mapping or return None (no filtering)."""
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
    return relationship_filters


def _validate_relationship_filters(relationship_filters: Mapping[str, bool] | None) -> None:
    """Validate relationship filter mapping structure and values."""
    if relationship_filters is None:
        return

    if not isinstance(relationship_filters, Mapping):
        raise TypeError(
            "Invalid filter configuration: relationship_filters must be a mapping or None, "
            f"got {type(relationship_filters).__name__}"
        )

    invalid_keys = [k for k in relationship_filters.keys() if not isinstance(k, str)]
    if invalid_keys:
        raise ValueError("Invalid filter configuration: all filter keys must be strings")

    invalid_values = [k for k, v in relationship_filters.items() if not isinstance(v, bool)]
    if invalid_values:
        raise ValueError(
            "Invalid filter configuration: all filter values must be booleans "
            f"(invalid: {', '.join(invalid_values)})"
        )


def _collect_and_group_relationships(
    graph: AssetRelationshipGraph,
    asset_ids: Iterable[str],
    relationship_filters: Mapping[str, bool] | None = None,
) -> dict[tuple[str, bool], list[dict[str, Any]]]:
    """Collect and group relationships with directionality info in a single pass."""
    relationship_index = _build_relationship_index(graph, asset_ids)

    processed_pairs: set[tuple[str, str, str]] = set()
    relationship_groups: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)

    for (source_id, target_id, rel_type), strength in relationship_index.items():
        if relationship_filters is not None and rel_type in relationship_filters:
            if not relationship_filters[rel_type]:
                continue

        pair_key: tuple[str, str, str] = (
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
            {"source_id": source_id, "target_id": target_id, "strength": float(strength)}
        )

    return relationship_groups


def _build_edge_coordinates_optimized(
    relationships: Sequence[Mapping[str, Any]],
    positions: np.ndarray,
    asset_id_index: Mapping[str, int],
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Build edge coordinate lists using optimized O(1) lookups."""
    num_edges = len(relationships)
    edges_x: list[float | None] = [None] * (num_edges * 3)
    edges_y: list[float | None] = [None] * (num_edges * 3)
    edges_z: list[float | None] = [None] * (num_edges * 3)

    for i, rel in enumerate(relationships):
        source_id = str(rel["source_id"])
        target_id = str(rel["target_id"])

        try:
            source_idx = asset_id_index[source_id]
            target_idx = asset_id_index[target_id]
        except KeyError as exc:
            raise ValueError(
                f"Relationship references unknown asset id: {exc.args[0]}"
            ) from exc

        base_idx = i * 3
        edges_x[base_idx] = float(positions[source_idx, 0])
        edges_x[base_idx + 1] = float(positions[target_idx, 0])

        edges_y[base_idx] = float(positions[source_idx, 1])
        edges_y[base_idx + 1] = float(positions[target_idx, 1])

        edges_z[base_idx] = float(positions[source_idx, 2])
        edges_z[base_idx + 1] = float(positions[target_idx, 2])

    return edges_x, edges_y, edges_z


def _build_hover_texts(
    relationships: Sequence[Mapping[str, Any]],
    rel_type: str,
    is_bidirectional: bool,
) -> list[str | None]:
    """Build hover text list for relationships with pre-allocation for performance."""
    direction_text = "↔" if is_bidirectional else "→"

    num_rels = len(relationships)
    hover_texts: list[str | None] = [None] * (num_rels * 3)

    for i, rel in enumerate(relationships):
        hover_text = (
            f"{rel['source_id']} {direction_text} {rel['target_id']}<br>"
            f"Type: {rel_type}<br>Strength: {float(rel['strength']):.2f}"
        )
        base_idx = i * 3
        hover_texts[base_idx] = hover_text
        hover_texts[base_idx + 1] = hover_text

    return hover_texts


def _get_line_style(rel_type: str, is_bidirectional: bool) -> dict[str, Any]:
    """Get line style configuration for a relationship with color validation."""
    color = REL_TYPE_COLORS[rel_type]
    if not _is_valid_color_format(color):
        logger.warning(
            "Invalid color format for relationship type '%s': '%s'. Using default gray.",
            rel_type,
            color,
        )
        color = "#888888"

    return {
        "color": color,
        "width": 4 if is_bidirectional else 2,
        "dash": "solid" if is_bidirectional else "dash",
    }


def _format_trace_name(rel_type: str, is_bidirectional: bool) -> str:
    """Format trace name for legend."""
    base_name = rel_type.replace("_", " ").title()
    direction_symbol = " (↔)" if is_bidirectional else " (→)"
    return base_name + direction_symbol


def _create_trace_for_group(
    rel_type: str,
    is_bidirectional: bool,
    relationships: list[dict[str, Any]],
    positions: np.ndarray,
    asset_id_index: dict[str, int],
) -> go.Scatter3d:
    """Create a single trace for a relationship group."""
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
    asset_ids: list[str],
    relationship_filters: Mapping[str, bool] | None = None,
) -> list[go.Scatter3d]:
    """Create separate traces for different relationship types."""
    asset_id_index = _build_asset_id_index(asset_ids)
    relationship_groups = _collect_and_group_relationships(
        graph,
        asset_ids,
        relationship_filters,
    )
    return [
        _create_trace_for_group(
            rel_type,
            is_bidirectional,
            rels,
            positions,
            asset_id_index,
        )
        for (rel_type, is_bidirectional), rels in relationship_groups.items()
        if rels
    ]


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: list[str],
) -> list[go.Scatter3d]:
    """Create arrow markers for unidirectional relationships."""
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")

    _validate_positions_array(positions)
    _validate_asset_ids_list(asset_ids)

    if len(positions) != len(asset_ids):
        raise ValueError("positions and asset_ids must have the same length")

    relationship_index = _build_relationship_index(graph, asset_ids)
    asset_id_index = _build_asset_id_index(asset_ids)

    source_indices: list[int] = []
    target_indices: list[int] = []
    hover_texts: list[str] = []

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


def _visualize_3d_graph_core(
    graph: AssetRelationshipGraph,
    relationship_filters: Mapping[str, bool] | None,
    toggle_arrows: bool,
) -> go.Figure:
    """Core visualization pipeline used by public wrappers."""
    if not hasattr(graph, "get_3d_visualization_data_enhanced"):
        raise ValueError(
            "Invalid graph data provided: graph must provide get_3d_visualization_data_enhanced"
        )

    try:
        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to retrieve visualization data from graph: %s", exc)
        raise ValueError("Failed to retrieve graph visualization data") from exc

    _validate_visualization_data(positions, asset_ids, colors, hover_texts)

    fig = go.Figure()

    try:
        relationship_traces = _create_relationship_traces(
            graph,
            positions,
            asset_ids,
            relationship_filters,
        )
    except (TypeError, ValueError) as exc:
        logger.exception(
            "Failed to create relationship traces (filters: %s): %s",
            relationship_filters,
            exc,
        )
        raise ValueError(f"Failed to create relationship traces: {exc}") from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Unexpected error creating relationship traces (filters: %s): %s",
            relationship_filters,
            exc,
        )
        relationship_traces = []

    if relationship_traces:
        try:
            fig.add_traces(relationship_traces)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to add relationship traces to figure: %s", exc)

    if toggle_arrows:
        try:
            arrow_traces = _create_directional_arrows(graph, positions, asset_ids)
        except (TypeError, ValueError) as exc:
            logger.exception("Failed to create directional arrows: %s", exc)
            arrow_traces = []
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error creating directional arrows: %s", exc)
            arrow_traces = []

        if arrow_traces:
            try:
                fig.add_traces(arrow_traces)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Failed to add directional arrows to figure: %s", exc)

    node_trace = _create_node_trace(positions, asset_ids, colors, hover_texts)
    fig.add_trace(node_trace)

    dynamic_title, options = _prepare_layout_config(len(asset_ids), relationship_traces)
    _configure_3d_layout(fig, dynamic_title, options)

    return fig


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
    """Create 3D visualization with selective relationship filtering."""
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("graph must be an AssetRelationshipGraph instance")

    filter_params = (
        show_same_sector,
        show_market_cap,
        show_correlation,
        show_corporate_bond,
        show_commodity_currency,
        show_income_comparison,
        show_regulatory,
        show_all_relationships,
        toggle_arrows,
    )
    if not all(isinstance(v, bool) for v in filter_params):
        raise TypeError("All filter parameters must be boolean values")

    relationship_filters = _build_relationship_filters(
        show_same_sector=show_same_sector,
        show_market_cap=show_market_cap,
        show_correlation=show_correlation,
        show_corporate_bond=show_corporate_bond,
        show_commodity_currency=show_commodity_currency,
        show_income_comparison=show_income_comparison,
        show_regulatory=show_regulatory,
        show_all_relationships=show_all_relationships,
    )

    if relationship_filters is not None and not any(relationship_filters.values()):
        logger.warning(
            "All relationship filters are disabled. Visualization will show no relationships."
        )

    return _visualize_3d_graph_core(
        graph=graph,
        relationship_filters=relationship_filters,
        toggle_arrows=toggle_arrows,
    )
