from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Final

import numpy as np
import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_visuals_layout import _configure_3d_layout, _prepare_layout_config
from src.visualizations.graph_visuals_traces import _create_node_trace, _create_relationship_traces
from src.visualizations.graph_visuals_validation import (
    _validate_asset_ids_list,
    _validate_positions_array,
    _validate_visualization_data,
)

logger = logging.getLogger(__name__)

# Precompiled regex patterns for color validation.
_HEX_COLOR_RE: Final[re.Pattern[str]] = re.compile(r"^#(?:[0-9A-Fa-f]{3}){1,2}(?:[0-9A-Fa-f]{2})?$")
_RGB_COLOR_RE: Final[re.Pattern[str]] = re.compile(r"^rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$")
_RGBA_COLOR_RE: Final[re.Pattern[str]] = re.compile(r"^rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(?:0|1|0?\.\d+)\s*\)$")

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


def _get_relationship_color(rel_type: str) -> str:
    """Return the configured color for a given relationship type.

    Falls back to the default color specified by REL_TYPE_COLORS when
    *rel_type* has no explicit entry.
    """
    return REL_TYPE_COLORS[rel_type]


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
    if not isinstance(graph.relationships, dict):
        raise TypeError(
            f"Invalid graph: relationships must be a dict, got {type(graph.relationships).__name__}"
        )

    asset_ids_set = _coerce_asset_ids(asset_ids)

    with _GRAPH_ACCESS_LOCK:
        relevant_relationships: dict[str, list[Any]] = {
            source_id: list(rels)
            for source_id, rels in graph.relationships.items()
            if source_id in asset_ids_set
        }

    relationship_index: dict[tuple[str, str, str], float] = {}
    for source_id, rels in relevant_relationships.items():
        if not isinstance(rels, (list, tuple)):
            raise TypeError(
                f"Invalid graph data: relationships for '{source_id}' must be a list/tuple, "
                f"got {type(rels).__name__}"
            )
        for idx, rel in enumerate(rels):
            if not isinstance(rel, (list, tuple)) or len(rel) != 3:
                raise ValueError(
                    f"Invalid graph data: relationship at index {idx} for '{source_id}' "
                    f"must be a 3-element tuple (target_id, rel_type, strength)"
                )
            target_id, rel_type, strength = rel
            if not isinstance(target_id, str) or not isinstance(rel_type, str):
                raise TypeError(
                    f"Invalid graph data: relationship at index {idx} for '{source_id}' "
                    "must use string target_id and rel_type"
                )
            try:
                strength_float = float(strength)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid graph data: strength at index {idx} for '{source_id}' must be numeric"
                ) from exc
            if target_id in asset_ids_set:
                relationship_index[(source_id, target_id, rel_type)] = strength_float

    return relationship_index


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: list[str],
    relationship_filters: Mapping[str, bool] | None = None,
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
            # Respect relationship filters when generating arrow markers.
            if relationship_filters is not None and not relationship_filters.get(rel_type, True):
                continue
            reverse_key = (target_id, source_id, rel_type)
            if reverse_key not in relationship_index:
                source_indices.append(asset_id_index[source_id])
                target_indices.append(asset_id_index[target_id])
                hover_texts.append(f"Direction: {source_id} → {target_id}<br>Type: {rel_type}")

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
        raise ValueError("Invalid graph data provided: graph must provide get_3d_visualization_data_enhanced")

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
                arrow_traces = _create_directional_arrows(graph, positions, asset_ids, relationship_filters)
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


def visualize_3d_graph(
    graph: AssetRelationshipGraph,
    toggle_arrows: bool = True,
) -> go.Figure:
    """Backward-compatible wrapper for the default 3D visualization."""
    return visualize_3d_graph_with_filters(
        graph=graph,
        show_all_relationships=True,
        toggle_arrows=toggle_arrows,
    )


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

    # Build the relationship_filters mapping inline instead of relying on an undefined helper.
    if show_all_relationships:
        relationship_filters = None
    else:
        relationship_filters = {
            "same_sector": show_same_sector,
            "market_cap_similar": show_market_cap,
            "correlation": show_correlation,
            "corporate_bond_to_equity": show_corporate_bond,
            "commodity_currency": show_commodity_currency,
            "income_comparison": show_income_comparison,
            "regulatory_impact": show_regulatory,
        }

    if relationship_filters is not None and not any(relationship_filters.values()):
        logger.warning("All relationship filters are disabled. Visualization will show no relationships.")

    return _visualize_3d_graph_core(
        graph=graph,
        relationship_filters=relationship_filters,
        toggle_arrows=toggle_arrows,
    )
