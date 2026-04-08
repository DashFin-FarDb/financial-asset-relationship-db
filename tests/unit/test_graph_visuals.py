import numpy as np
import plotly.graph_objects as go
import pytest

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_visuals import (
    REL_TYPE_COLORS,
    _build_asset_id_index,
    _build_relationship_index,
    _coerce_asset_ids,
    _create_directional_arrows,
    _create_relationship_traces,
    _get_relationship_color,
    _is_valid_color_format,
    visualize_3d_graph_with_filters,
)


class DummyGraph(AssetRelationshipGraph):
    def __init__(self, relationships):
        # relationships: Dict[str, List[Tuple[str, str, float]]]
        """
        Initialize the DummyGraph with a mapping of asset relationships.

        Parameters:
            relationships (dict): Mapping from source asset ID (str) to a list of relationships.
                Each relationship is a tuple (target_id, relationship_type, weight) where
                `target_id` and `relationship_type` are strings and `weight` is a float.

        Notes:
            The provided mapping is stored on the instance as `self.relationships`.
        """
        super().__init__()
        self.relationships = relationships

    def get_3d_visualization_data_enhanced(self):
        """
        Produce synthetic 3D visualization data for the graph's assets.

        Returns:
            positions (np.ndarray): Float array of shape (n, 3) containing sequential coordinates for n assets.
            asset_ids (List[str]): Sorted list of unique asset IDs discovered from relationship sources and targets.
            colors (List[str]): List of hex color strings for each asset (defaults to "#000000").
            hover_texts (List[str]): List of hover text labels corresponding to each asset ID.
        """
        # Return positions (n,3), asset_ids, colors, hover_texts
        asset_ids = sorted(set(self.relationships.keys()) | {t for v in self.relationships.values() for t, _, _ in v})
        n = len(asset_ids)
        positions = np.arange(n * 3, dtype=float).reshape(n, 3)
        colors = ["#000000"] * n
        hover_texts = asset_ids
        return positions, asset_ids, colors, hover_texts


def test_rel_type_colors_default():
    """Test that the default relationship type colors mapping returns fallback color for unknown types."""
    # Ensure defaultdict provides fallback color, and direct indexing works without KeyError
    assert REL_TYPE_COLORS["unknown_type"] == "#888888"


def test_build_asset_id_index():
    """Test building an index mapping asset IDs to their positions."""
    ids = ["A", "B", "C"]
    idx = _build_asset_id_index(ids)
    assert idx == {"A": 0, "B": 1, "C": 2}


def test_build_relationship_index_filters_to_asset_ids():
    """Test filtering of relationship index to only include specified asset IDs."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.9), ("X", "correlation", 0.5)],
            "C": [("A", "same_sector", 1.0)],
        }
    )
    index = _build_relationship_index(graph, ["A", "B", "C"])
    # Should include only pairs where both ends are in the provided list
    assert ("A", "B", "correlation") in index
    assert ("C", "A", "same_sector") in index
    assert ("A", "X", "correlation") not in index


def test_create_relationship_traces_basic():
    """Test creation of relationship traces, grouping by type and direction."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.9)],
            "B": [("A", "correlation", 0.9)],  # bidirectional
            "C": [("A", "same_sector", 1.0)],  # unidirectional
        }
    )
    positions, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

    traces = _create_relationship_traces(graph, positions, asset_ids)
    # There should be two groups: correlation (bidirectional) and same_sector (unidirectional)
    names = {t.name for t in traces}
    assert any(name == "Correlation (↔)" for name in names)
    assert any(name == "Same Sector (→)" for name in names)

    try:
        corr_trace = next(t for t in traces if t.legendgroup == "correlation")
    except StopIteration:
        return
    assert corr_trace.line.color == REL_TYPE_COLORS["correlation"]


def test_create_directional_arrows_validation_errors():
    """Test validation errors raised by _create_directional_arrows for invalid inputs."""
    graph = DummyGraph({})
    with pytest.raises(TypeError):
        _create_directional_arrows(object(), np.zeros((0, 3)), [])  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        _create_directional_arrows(graph, None, [])  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        _create_directional_arrows(graph, np.zeros((1, 2)), ["A"])  # invalid shape


def test_create_directional_arrows_basic():
    """Test basic functionality of _create_directional_arrows with unidirectional arrows."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.9)],  # unidirectional
            "B": [("A", "correlation", 0.9)],  # and reverse, makes it bidirectional (no arrow)
            "C": [("A", "same_sector", 1.0)],  # unidirectional
        }
    )
    positions, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

    # Remove one side to ensure a unidirectional exists
    graph.relationships["B"] = []

    arrows = _create_directional_arrows(graph, positions, asset_ids)
    assert isinstance(arrows, list)
    if arrows:
        arrow_trace = arrows[0]
        assert isinstance(arrow_trace, go.Scatter3d)
        assert arrow_trace.mode == "markers"
        assert arrow_trace.showlegend is False


def test_create_directional_arrows_none_positions():
    """Test that passing None for positions raises a ValueError."""
    graph = DummyGraph({})
    with pytest.raises(ValueError, match="positions must be a numpy array"):
        _create_directional_arrows(graph, None, ["A", "B"])  # type: ignore[arg-type]


def test_create_directional_arrows_none_asset_ids():
    """Test that passing None for asset_ids raises a ValueError."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    with pytest.raises(ValueError, match="asset_ids must be a list or tuple"):
        _create_directional_arrows(graph, positions, None)  # type: ignore[arg-type]


def test_create_directional_arrows_length_mismatch():
    """Test that mismatched lengths of positions and asset_ids raises a ValueError."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A"]  # Length 1, but positions has 2 rows
    with pytest.raises(ValueError, match="positions and asset_ids must have the same length"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_invalid_shape():
    """Test that invalid shape of positions raises a ValueError."""
    graph = DummyGraph({})
    positions = np.array([[0, 0], [1, 1]])  # 2D instead of 3D
    asset_ids = ["A", "B"]
    with pytest.raises(ValueError, match="expected positions to be a \\(n, 3\\) numpy array"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_non_numeric_positions():
    """Test that non-numeric position values raise a ValueError."""
    graph = DummyGraph({})
    positions = np.array([["a", "b", "c"], ["d", "e", "f"]])
    asset_ids = ["A", "B"]
    with pytest.raises(ValueError, match="positions must contain numeric values"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_infinite_positions():
    """Test that infinite numbers in positions raise a ValueError."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [np.inf, 1, 1]])
    asset_ids = ["A", "B"]
    with pytest.raises(ValueError, match="positions must contain finite values"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_nan_positions():
    """Test that NaN values in positions raise a ValueError."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [np.nan, 1, 1]])
    asset_ids = ["A", "B"]
    with pytest.raises(ValueError, match="positions must contain finite values"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_empty_asset_ids():
    """Test that empty strings in asset_ids raise a ValueError."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", ""]  # Empty string
    with pytest.raises(ValueError, match="asset_ids must contain non-empty strings"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_non_string_asset_ids():
    """Test that non-string asset_ids raise a ValueError."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", 123]  # type: ignore[list-item]
    with pytest.raises(ValueError, match="asset_ids must contain non-empty strings"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_invalid_graph_type():
    """Test that passing invalid graph type raises a TypeError."""
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", "B"]
    with pytest.raises(TypeError, match="Expected graph to be an instance of AssetRelationshipGraph"):
        _create_directional_arrows(object(), positions, asset_ids)  # type: ignore[arg-type]


def test_create_directional_arrows_valid_inputs_no_relationships():
    """Test that valid inputs with no relationships returns an empty list."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", "B"]
    arrows = _create_directional_arrows(graph, positions, asset_ids)
    assert arrows == []


def test_create_directional_arrows_valid_inputs_with_unidirectional():
    """Test that valid inputs with a single unidirectional relationship returns one arrow."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.9)],
        }
    )
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", "B"]
    arrows = _create_directional_arrows(graph, positions, asset_ids)
    assert len(arrows) == 1
    assert isinstance(arrows[0], go.Scatter3d)
    assert arrows[0].mode == "markers"


def test_create_directional_arrows_type_coercion():
    """Test that passing a list for positions raises a ValueError (numpy array required)."""
    graph = DummyGraph({})
    positions = [[0, 0, 0], [1, 1, 1]]  # List instead of numpy array
    asset_ids = ["A", "B"]
    with pytest.raises(ValueError, match="positions must be a numpy array"):
        _create_directional_arrows(graph, positions, asset_ids)  # type: ignore[arg-type]


def test_create_directional_arrows_bidirectional_no_arrows():
    """Test that bidirectional relationships produce no arrows."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.9)],
            "B": [("A", "correlation", 0.9)],
        }
    )
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", "B"]
    arrows = _create_directional_arrows(graph, positions, asset_ids)
    assert arrows == []


# ---------------------------------------------------------------------------
# Tests for _get_relationship_color (new function)
# ---------------------------------------------------------------------------


def test_get_relationship_color_known_types():
    """All explicitly configured relationship types return their specific color."""
    assert _get_relationship_color("same_sector") == "#FF6B6B"
    assert _get_relationship_color("market_cap_similar") == "#4ECDC4"
    assert _get_relationship_color("correlation") == "#45B7D1"
    assert _get_relationship_color("corporate_bond_to_equity") == "#96CEB4"
    assert _get_relationship_color("commodity_currency") == "#FFEAA7"
    assert _get_relationship_color("income_comparison") == "#DDA0DD"
    assert _get_relationship_color("regulatory_impact") == "#FFA07A"


def test_get_relationship_color_unknown_type_returns_default():
    """Unknown relationship types should fall back to the default gray."""
    assert _get_relationship_color("nonexistent_type") == "#888888"


def test_get_relationship_color_empty_string_returns_default():
    """Empty string key falls back to the default color."""
    assert _get_relationship_color("") == "#888888"


def test_get_relationship_color_matches_rel_type_colors():
    """_get_relationship_color is consistent with REL_TYPE_COLORS lookup."""
    for rel_type in ["same_sector", "correlation", "unknown_xyz"]:
        assert _get_relationship_color(rel_type) == REL_TYPE_COLORS[rel_type]


# ---------------------------------------------------------------------------
# Tests for _is_valid_color_format (modified: named colors now require [A-Za-z]+)
# ---------------------------------------------------------------------------


def test_is_valid_color_format_hex_3():
    """Three-digit hex colors are valid."""
    assert _is_valid_color_format("#RGB") is False  # not hex digits
    assert _is_valid_color_format("#abc") is True
    assert _is_valid_color_format("#123") is True
    assert _is_valid_color_format("#FFF") is True


def test_is_valid_color_format_hex_6():
    """Six-digit hex colors are valid."""
    assert _is_valid_color_format("#aabbcc") is True
    assert _is_valid_color_format("#AABBCC") is True
    assert _is_valid_color_format("#000000") is True
    assert _is_valid_color_format("#ffffff") is True


def test_is_valid_color_format_hex_8():
    """Eight-digit hex colors (with alpha) are valid."""
    assert _is_valid_color_format("#aabbccdd") is True
    assert _is_valid_color_format("#AABBCCDD") is True
    assert _is_valid_color_format("#00000000") is True


def test_is_valid_color_format_hex_invalid():
    """Malformed hex strings are rejected."""
    assert _is_valid_color_format("#") is False
    assert _is_valid_color_format("#12") is False  # only 2 digits
    assert _is_valid_color_format("#12345") is False  # 5 digits (ambiguous)
    assert _is_valid_color_format("#ggg") is False  # non-hex letters
    assert _is_valid_color_format("##aabbcc") is False  # double hash


def test_is_valid_color_format_rgb():
    """Valid rgb() strings are accepted."""
    assert _is_valid_color_format("rgb(0,0,0)") is True
    assert _is_valid_color_format("rgb(255, 128, 64)") is True
    assert _is_valid_color_format("rgb( 0 , 0 , 0 )") is True


def test_is_valid_color_format_rgb_invalid():
    """Malformed rgb() strings are rejected."""
    assert _is_valid_color_format("rgb(0,0)") is False  # only 2 args
    assert _is_valid_color_format("rgb(0,0,0,0)") is False  # 4 args (use rgba)
    assert _is_valid_color_format("rgb(a,b,c)") is False  # non-numeric
    assert _is_valid_color_format("RGB(0,0,0)") is False  # uppercase


def test_is_valid_color_format_rgba():
    """Valid rgba() strings are accepted."""
    assert _is_valid_color_format("rgba(0,0,0,0)") is True
    assert _is_valid_color_format("rgba(0,0,0,1)") is True
    assert _is_valid_color_format("rgba(255, 128, 64, 0.5)") is True
    assert _is_valid_color_format("rgba(0, 0, 0, 0.0)") is True
    assert _is_valid_color_format("rgba(0, 0, 0, .9)") is True


def test_is_valid_color_format_rgba_invalid():
    """Malformed rgba() strings are rejected."""
    assert _is_valid_color_format("rgba(0,0,0,1.5)") is False  # alpha > 1
    assert _is_valid_color_format("rgba(0,0,0,-0.5)") is False  # negative alpha
    assert _is_valid_color_format("rgba(0,0,0)") is False  # missing alpha
    assert _is_valid_color_format("rgba(a,b,c,0)") is False  # non-numeric


def test_is_valid_color_format_named_colors_only_alpha():
    """Named colors consisting solely of alpha characters are valid."""
    assert _is_valid_color_format("red") is True
    assert _is_valid_color_format("blue") is True
    assert _is_valid_color_format("Green") is True
    assert _is_valid_color_format("cornflowerblue") is True


def test_is_valid_color_format_named_colors_with_non_alpha_rejected():
    """Named color strings with non-alpha characters are rejected (new behavior)."""
    # These would have returned True in the old code but are now rejected
    assert _is_valid_color_format("red123") is False
    assert _is_valid_color_format("my-color") is False
    assert _is_valid_color_format("color name") is False
    assert _is_valid_color_format("color_name") is False


def test_is_valid_color_format_non_string():
    """Non-string inputs return False."""
    assert _is_valid_color_format(None) is False  # type: ignore[arg-type]
    assert _is_valid_color_format(123) is False  # type: ignore[arg-type]
    assert _is_valid_color_format([]) is False  # type: ignore[arg-type]


def test_is_valid_color_format_empty_string():
    """Empty string returns False."""
    assert _is_valid_color_format("") is False


# ---------------------------------------------------------------------------
# Tests for _coerce_asset_ids (new function)
# ---------------------------------------------------------------------------


def test_coerce_asset_ids_basic():
    """Valid list of strings returns a set."""
    result = _coerce_asset_ids(["A", "B", "C"])
    assert result == {"A", "B", "C"}


def test_coerce_asset_ids_deduplicates():
    """Duplicate IDs are collapsed into a set."""
    result = _coerce_asset_ids(["A", "B", "A"])
    assert result == {"A", "B"}


def test_coerce_asset_ids_accepts_any_iterable():
    """Any iterable of strings (tuple, generator) is accepted."""
    assert _coerce_asset_ids(("X", "Y")) == {"X", "Y"}
    assert _coerce_asset_ids(["P", "Q"]) == {"P", "Q"}


def test_coerce_asset_ids_rejects_single_string():
    """Passing a bare string raises TypeError (prevents accidental character iteration)."""
    with pytest.raises(TypeError, match="not a single string"):
        _coerce_asset_ids("ABC")  # type: ignore[arg-type]


def test_coerce_asset_ids_rejects_bytes():
    """Passing bytes raises TypeError."""
    with pytest.raises(TypeError, match="not a single string"):
        _coerce_asset_ids(b"ABC")  # type: ignore[arg-type]


def test_coerce_asset_ids_rejects_empty_iterable():
    """Empty iterable raises ValueError."""
    with pytest.raises(ValueError, match="must be non-empty"):
        _coerce_asset_ids([])


def test_coerce_asset_ids_rejects_empty_string_elements():
    """Iterable containing empty strings raises ValueError."""
    with pytest.raises(ValueError, match="non-empty strings"):
        _coerce_asset_ids(["A", ""])


def test_coerce_asset_ids_rejects_non_string_elements():
    """Iterable containing non-string elements raises ValueError."""
    with pytest.raises(ValueError, match="non-empty strings"):
        _coerce_asset_ids(["A", 42])  # type: ignore[list-item]


def test_coerce_asset_ids_rejects_none():
    """None raises TypeError (not iterable)."""
    with pytest.raises(TypeError):
        _coerce_asset_ids(None)  # type: ignore[arg-type]


def test_coerce_asset_ids_returns_set_type():
    """Return value is always a set."""
    result = _coerce_asset_ids(["Z"])
    assert isinstance(result, set)


# ---------------------------------------------------------------------------
# Additional tests for _build_relationship_index (simplified/modified)
# ---------------------------------------------------------------------------


def test_build_relationship_index_type_error_non_graph():
    """Passing a non-AssetRelationshipGraph raises TypeError."""
    with pytest.raises(TypeError, match="AssetRelationshipGraph"):
        _build_relationship_index(object(), ["A"])  # type: ignore[arg-type]


def test_build_relationship_index_type_error_non_dict_relationships():
    """graph.relationships must be a dict; otherwise TypeError is raised."""

    class BadGraph(AssetRelationshipGraph):
        def __init__(self):
            super().__init__()
            self.relationships = "not-a-dict"

    with pytest.raises(TypeError, match="dictionary"):
        _build_relationship_index(BadGraph(), ["A"])


def test_build_relationship_index_value_error_missing_relationships():
    """graph without a 'relationships' attribute raises ValueError."""

    class NoRelGraph(AssetRelationshipGraph):
        def __init__(self):
            super().__init__()
            # Ensure the instance mimics a graph missing `relationships`
            if hasattr(self, "relationships"):
                del self.relationships

    graph = NoRelGraph()

    with pytest.raises(ValueError, match="relationships"):
        _build_relationship_index(graph, ["A"])


def test_build_relationship_index_excludes_external_targets():
    """Relationships whose target is not in asset_ids are excluded."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.9), ("Z", "correlation", 0.5)],
        }
    )
    index = _build_relationship_index(graph, ["A", "B"])
    assert ("A", "B", "correlation") in index
    assert ("A", "Z", "correlation") not in index


def test_build_relationship_index_strength_as_float():
    """Relationship strength values are stored as floats."""
    graph = DummyGraph(
        {
            "A": [("B", "same_sector", 1)],  # integer strength
        }
    )
    index = _build_relationship_index(graph, ["A", "B"])
    val = index[("A", "B", "same_sector")]
    assert isinstance(val, float)
    assert np.isclose(val, 1.0)


def test_build_relationship_index_empty_relationships():
    """Graph with empty relationships dict returns an empty index."""
    graph = DummyGraph({})
    index = _build_relationship_index(graph, ["A", "B"])
    assert index == {}


def test_build_relationship_index_no_matching_asset_ids():
    """No relationships are indexed when asset_ids don't overlap with graph data."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.9)],
        }
    )
    index = _build_relationship_index(graph, ["X", "Y"])
    assert index == {}


# ---------------------------------------------------------------------------
# Tests for visualize_3d_graph_with_filters (modified validation logic)
# ---------------------------------------------------------------------------


def test_visualize_3d_graph_with_filters_raises_type_error_for_non_graph():
    """Passing a non-AssetRelationshipGraph raises TypeError (not ValueError)."""
    with pytest.raises(TypeError, match="AssetRelationshipGraph"):
        visualize_3d_graph_with_filters(object())  # type: ignore[arg-type]


def test_visualize_3d_graph_with_filters_raises_type_error_for_non_bool_filter():
    """Non-boolean filter parameters raise TypeError."""
    graph = DummyGraph({})
    with pytest.raises(TypeError, match="boolean"):
        visualize_3d_graph_with_filters(graph, show_same_sector=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="boolean"):
        visualize_3d_graph_with_filters(graph, show_market_cap="yes")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="boolean"):
        visualize_3d_graph_with_filters(graph, toggle_arrows=0)  # type: ignore[arg-type]


def test_visualize_3d_graph_with_filters_returns_figure():
    """Valid graph with default parameters produces a Plotly Figure."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.9)],
            "B": [("A", "correlation", 0.9)],
        }
    )
    fig = visualize_3d_graph_with_filters(graph)
    assert isinstance(fig, go.Figure)


def test_visualize_3d_graph_with_filters_show_all_relationships_true_passes_none_filters():
    """When show_all_relationships=True no filter is applied (full graph rendered)."""
    graph = DummyGraph(
        {
            "A": [("B", "same_sector", 1.0)],
        }
    )
    # Should not raise; all relationship types should appear
    fig = visualize_3d_graph_with_filters(graph, show_all_relationships=True)
    assert isinstance(fig, go.Figure)


def test_visualize_3d_graph_with_filters_show_all_false_applies_filters():
    """When show_all_relationships=False, a filter dict is built and applied."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.8)],
            "B": [("A", "correlation", 0.8)],
            "C": [("A", "same_sector", 1.0)],
        }
    )
    # Disable correlation; only same_sector should remain
    fig = visualize_3d_graph_with_filters(
        graph,
        show_all_relationships=False,
        show_correlation=False,
        show_same_sector=True,
    )
    assert isinstance(fig, go.Figure)


def test_visualize_3d_graph_with_filters_all_disabled_still_returns_figure(caplog):
    """All filters disabled still returns a Figure but logs a warning."""
    import logging

    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.8)],
        }
    )
    with caplog.at_level(logging.WARNING, logger="src.visualizations.graph_visuals"):
        fig = visualize_3d_graph_with_filters(
            graph,
            show_all_relationships=False,
            show_same_sector=False,
            show_market_cap=False,
            show_correlation=False,
            show_corporate_bond=False,
            show_commodity_currency=False,
            show_income_comparison=False,
            show_regulatory=False,
        )
    assert isinstance(fig, go.Figure)
    assert any("All relationship filters are disabled" in r.message for r in caplog.records)


def test_visualize_3d_graph_with_filters_toggle_arrows_false():
    """toggle_arrows=False disables arrow traces in the output figure."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.8)],
        }
    )
    fig = visualize_3d_graph_with_filters(graph, toggle_arrows=False)
    assert isinstance(fig, go.Figure)
    arrow_traces = [t for t in fig.data if getattr(t, "name", None) == "Direction Arrows"]
    assert arrow_traces == []


def test_visualize_3d_graph_with_filters_toggle_arrows_true_adds_arrows():
    """toggle_arrows=True adds arrow traces for unidirectional relationships."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.8)],  # unidirectional
        }
    )
    fig = visualize_3d_graph_with_filters(graph, toggle_arrows=True)
    assert isinstance(fig, go.Figure)
    arrow_traces = [t for t in fig.data if getattr(t, "name", None) == "Direction Arrows"]
    assert len(arrow_traces) >= 1


def test_visualize_3d_graph_with_filters_no_relationships():
    """Graph with no relationships still produces a valid Figure."""

    class SingleNodeGraph(AssetRelationshipGraph):
        def __init__(self):
            super().__init__()

            self.relationships = {}

        def get_3d_visualization_data_enhanced(self):
            positions = np.array([[0.0, 0.0, 0.0]])
            asset_ids = ["SOLO"]
            colors = ["#FF6B6B"]

            hover_texts = ["SOLO"]
            return positions, asset_ids, colors, hover_texts

    fig = visualize_3d_graph_with_filters(SingleNodeGraph())
    assert isinstance(fig, go.Figure)


def test_visualize_3d_graph_with_filters_none_graph():
    """None as graph raises TypeError."""
    with pytest.raises(TypeError):
        visualize_3d_graph_with_filters(None)  # type: ignore[arg-type]
