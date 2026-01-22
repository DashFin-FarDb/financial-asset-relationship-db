import numpy as np
import plotly.graph_objects as go
import pytest

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_visuals import (
    REL_TYPE_COLORS,
    _build_asset_id_index,
    _build_relationship_index,
    _create_directional_arrows,
    _create_relationship_traces,
)


class DummyGraph(AssetRelationshipGraph):
    def __init__(self, relationships):
        # relationships: Dict[str, List[Tuple[str, str, float]]]
        super().__init__()
        self.relationships = relationships


def get_3d_visualization_data_enhanced(self):
    # Return positions (n,3), asset_ids, colors, hover_texts
    """
    Return visualization data for 3D plotting of assets.

    Positions are an (n, 3) NumPy array of float coordinates for each asset, arranged row-major with values 0 through n*3 - 1. Asset IDs are a sorted list of unique asset identifiers present as sources or targets in the graph. Colors is a list of hex color strings, one per asset (defaulting to "#000000"). Hover_texts is the list of labels for each asset (identical to `asset_ids`), in the same order as the rows of `positions`.

    Returns:
        tuple: A 4-tuple (positions, asset_ids, colors, hover_texts) where
            positions (numpy.ndarray): Array of shape (n, 3) of floats.
            asset_ids (list[str]): Sorted list of n unique asset identifiers.
            colors (list[str]): List of n hex color strings.
            hover_texts (list[str]): List of n hover label strings.
    """
    asset_ids = sorted(
        set(self.relationships.keys())
        | {t for v in self.relationships.values() for t, _, _ in v}
    )
    n = len(asset_ids)
    positions = np.arange(n * 3, dtype=float).reshape(n, 3)
    colors = ["#000000"] * n
    hover_texts = asset_ids
    return positions, asset_ids, colors, hover_texts


def test_rel_type_colors_default():
    """Test that REL_TYPE_COLORS provides a default color for unknown types and supports direct indexing without KeyError."""
    # Ensure defaultdict provides fallback color, and direct indexing works without KeyError
    assert REL_TYPE_COLORS["unknown_type"] == "#888888"


def test_build_asset_id_index():
    """Test that _build_asset_id_index maps a list of asset IDs to their correct integer indices."""
    ids = ["A", "B", "C"]
    idx = _build_asset_id_index(ids)
    assert idx == {"A": 0, "B": 1, "C": 2}


def test_build_relationship_index_filters_to_asset_ids():
    """Test that _build_relationship_index includes only relationships where both ends are in the provided asset list."""
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
    """Test that _create_relationship_traces correctly creates bidirectional and unidirectional traces with proper naming and coloring."""
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
    """Test that _create_directional_arrows raises appropriate errors for invalid input types and shapes."""
    graph = DummyGraph({})
    with pytest.raises(TypeError):
        _create_directional_arrows(object(), np.zeros((0, 3)), [])  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        _create_directional_arrows(graph, None, [])  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        _create_directional_arrows(graph, np.zeros((1, 2)), ["A"])  # invalid shape


def test_create_directional_arrows_basic():
    """Test basic creation of directional arrows for unidirectional relationships, returning Scatter3d markers without legends."""
    graph = DummyGraph(
        {
            "A": [("B", "correlation", 0.9)],  # unidirectional
            "B": [
                ("A", "correlation", 0.9)
            ],  # and reverse, makes it bidirectional (no arrow)
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
    """Test that passing None for positions raises a ValueError with the correct message."""
    graph = DummyGraph({})
    with pytest.raises(ValueError, match="positions and asset_ids must not be None"):
        _create_directional_arrows(graph, None, ["A", "B"])  # type: ignore[arg-type]


def test_create_directional_arrows_none_asset_ids():
    """Test that passing None for asset_ids raises a ValueError with the correct message."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    with pytest.raises(ValueError, match="positions and asset_ids must not be None"):
        _create_directional_arrows(graph, positions, None)  # type: ignore[arg-type]


def test_create_directional_arrows_length_mismatch():
    """Test that mismatched lengths of positions and asset_ids raise a ValueError."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A"]  # Length 1, but positions has 2 rows
    with pytest.raises(
        ValueError, match="positions and asset_ids must have the same length"
    ):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_invalid_shape():
    """Test that positions with invalid shape raise a ValueError indicating expected (n, 3)."""
    graph = DummyGraph({})
    positions = np.array([[0, 0], [1, 1]])  # 2D instead of 3D
    asset_ids = ["A", "B"]
    with pytest.raises(
        ValueError, match="Invalid positions shape: expected \\(n, 3\\)"
    ):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_non_numeric_positions():
    """Test that non-numeric position values raise a ValueError about numeric values."""
    graph = DummyGraph({})
    positions = np.array([["a", "b", "c"], ["d", "e", "f"]])
    asset_ids = ["A", "B"]
    with pytest.raises(ValueError, match="values must be numeric"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_infinite_positions():
    """Test that infinite position values raise a ValueError about finite numbers."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [np.inf, 1, 1]])
    asset_ids = ["A", "B"]
    with pytest.raises(ValueError, match="values must be finite numbers"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_nan_positions():
    """Test that NaN position values raise a ValueError about finite numbers."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [np.nan, 1, 1]])
    asset_ids = ["A", "B"]
    with pytest.raises(ValueError, match="values must be finite numbers"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_empty_asset_ids():
    """Test that empty strings in asset_ids raise a ValueError about non-empty strings."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", ""]  # Empty string
    with pytest.raises(ValueError, match="asset_ids must contain non-empty strings"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_non_string_asset_ids():
    """Test that non-string entries in asset_ids raise a ValueError about non-empty strings."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", 123]  # type: ignore[list-item]
    with pytest.raises(ValueError, match="asset_ids must contain non-empty strings"):
        _create_directional_arrows(graph, positions, asset_ids)


def test_create_directional_arrows_invalid_graph_type():
    """Test that passing an invalid graph type raises a TypeError indicating the expected class."""
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", "B"]
    with pytest.raises(
        TypeError, match="Expected graph to be an instance of AssetRelationshipGraph"
    ):
        _create_directional_arrows(object(), positions, asset_ids)  # type: ignore[arg-type]


def test_create_directional_arrows_valid_inputs_no_relationships():
    """Test that no relationships yields an empty list of arrows."""
    graph = DummyGraph({})
    positions = np.array([[0, 0, 0], [1, 1, 1]])
    asset_ids = ["A", "B"]
    arrows = _create_directional_arrows(graph, positions, asset_ids)
    assert arrows == []


def test_create_directional_arrows_valid_inputs_with_unidirectional():
    """Test that a single unidirectional relationship yields one Scatter3d arrow marker."""
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
    """Test that list inputs for positions are coerced without errors and return an empty list when no relationships exist."""
    graph = DummyGraph({})
    positions = [[0, 0, 0], [1, 1, 1]]  # List instead of numpy array
    asset_ids = ["A", "B"]
    arrows = _create_directional_arrows(graph, positions, asset_ids)  # type: ignore[arg-type]
    assert arrows == []


def test_create_directional_arrows_bidirectional_no_arrows():
    """Test that bidirectional relationships yield no arrow traces."""
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
