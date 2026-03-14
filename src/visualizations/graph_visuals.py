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
from src.visualizations.graph_visuals_layout import _configure_3d_layout, _prepare_layout_config
from src.visualizations.graph_visuals_traces import _create_node_trace, _create_relationship_traces
from src.visualizations.graph_visuals_validation import (
    _validate_asset_ids_list,
    _validate_positions_array,
    _validate_visualization_data,
)

logger = logging.getLogger(__name__)

# Protect concurrent access to graph.relationships (graph is mutable).
_GRAPH_ACCESS_LOCK: Final[threading.RLock] = threading.RLock()

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
        return True

    if _RGB_COLOR_RE.match(color):
        return True

    if _RGBA_COLOR_RE.match(color):
        return True

    # Allow simple named colours while rejecting malformed tokens.
    return bool(re.fullmatch(r"[A-Za-z]+", color))


def _build_asset_id_index(asset_ids: Sequence[str]) -> dict[str, int]:
    """Build an O(1) lookup index for asset IDs to their positions."""
    return {asset_id: idx for idx, asset_id in enumerate(asset_ids)}


def _coerce_asset_ids(asset_ids: Iterable[str]) -> set[str]:
    """Normalize and validate asset IDs to a set of non-empty strings."""
    if isinstance(asset_ids, (str, bytes)):
        raise TypeError("Invalid input: asset_ids must be an iterable of strings, not a single string")

    try:
        asset_ids_set = set(asset_ids)
    except TypeError as exc:
        raise TypeError("Invalid input: asset_ids must be an iterable of strings") from exc

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
        raise TypeError(f"Invalid input: graph must be an AssetRelationshipGraph instance, got {type(graph).__name__}")

    if not hasattr(graph, "relationships"):
        raise ValueError("Invalid graph: missing 'relationships' attribute")

    if not isinstance(graph.relationships, dict):
        raise TypeError(
    def _create_directional_arrows(
        graph: AssetRelationshipGraph,
        positions: np.ndarray,
        asset_ids: list[str],
        relationship_filters: Mapping[str, bool] | None=None,
    ) -> list[go.Scatter3d]:
        """Create arrow markers for unidirectional relationships."""
        if not isinstance(graph, AssetRelationshipGraph):
            raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")

        _validate_positions_array(positions)
        _validate_asset_ids_list(asset_ids)

        if len(positions) != len(asset_ids):
            raise ValueError("positions and asset_ids must have the same length")

        relationship_index=_build_relationship_index(graph, asset_ids)
        asset_id_index=_build_asset_id_index(asset_ids)

        source_indices: list[int]=[]
        target_indices: list[int]=[]
        hover_texts: list[str]=[]

        for (source_id, target_id, rel_type), _ in relationship_index.items():
            # Respect relationship filters when generating arrow markers.
            if relationship_filters is not None and not relationship_filters.get(rel_type, True):
                continue
            reverse_key=(target_id, source_id, rel_type)
            if reverse_key not in relationship_index:
                source_indices.append(asset_id_index[source_id])
                target_indices.append(asset_id_index[target_id])
                hover_texts.append(f"Direction: {source_id} → {target_id}<br>Type: {rel_type}")

        if not source_indices:
            return []

        src_idx_arr=np.asarray(source_indices, dtype=int)
        tgt_idx_arr=np.asarray(target_indices, dtype=int)

        source_positions=positions[src_idx_arr]
        target_positions=positions[tgt_idx_arr]
        arrow_positions=source_positions + 0.7 * (target_positions - source_positions)

        arrow_trace=go.Scatter3d(
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
            positions, asset_ids, colors, hover_texts=graph.get_3d_visualization_data_enhanced()
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to retrieve visualization data from graph: %s", exc)
            raise ValueError("Failed to retrieve graph visualization data") from exc

        _validate_visualization_data(positions, asset_ids, colors, hover_texts)

        fig=go.Figure()

        try:
            relationship_traces=_create_relationship_traces(
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
            relationship_traces=[]

        if relationship_traces:
            try:
                fig.add_traces(relationship_traces)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Failed to add relationship traces to figure: %s", exc)

        if toggle_arrows:
            try:
                arrow_traces=_create_directional_arrows(graph, positions, asset_ids, relationship_filters)
            except (TypeError, ValueError) as exc:
                logger.exception("Failed to create directional arrows: %s", exc)
                arrow_traces=[]
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Unexpected error creating directional arrows: %s", exc)
                arrow_traces=[]

            if arrow_traces:
                try:
                    fig.add_traces(arrow_traces)
                except Exception as exc:  # pylint: disable=broad-except
                    logger.exception("Failed to add directional arrows to figure: %s", exc)

        node_trace=_create_node_trace(positions, asset_ids, colors, hover_texts)
        fig.add_trace(node_trace)

        dynamic_title, options=_prepare_layout_config(len(asset_ids), relationship_traces)
        _configure_3d_layout(fig, dynamic_title, options)

        return fig


def visualize_3d_graph_with_filters(
    graph: AssetRelationshipGraph,
    show_same_sector: bool=True,
    show_market_cap: bool=True,
    show_correlation: bool=True,
    show_corporate_bond: bool=True,
    show_commodity_currency: bool=True,
    show_income_comparison: bool=True,
    show_regulatory: bool=True,
    show_all_relationships: bool=True,
    toggle_arrows: bool=True,
) -> go.Figure:
    """Create 3D visualization with selective relationship filtering."""
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("graph must be an AssetRelationshipGraph instance")

    filter_params=(
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
        relationship_filters=None
    else:
        relationship_filters={
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
