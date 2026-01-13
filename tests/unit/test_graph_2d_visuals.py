"""Unit tests for 2D graph visualizations.

This module contains comprehensive unit tests for the graph_2d_visuals module including:
- 2D graph visualization creation
- Layout algorithms (circular, grid, spring)
- Relationship trace creation
- Filtering and display options
- Edge cases and error handling
"""

import plotly.graph_objects as go
import pytest

from src.visualizations.graph_2d_visuals import (
    _create_2d_relationship_traces,
    _create_circular_layout,
    _create_grid_layout,
    _create_spring_layout_2d,
    visualize_2d_graph,
)


def create_relationship_traces_with_defaults(graph, positions, asset_ids, **overrides):
    """Helper to call _create_2d_relationship_traces with default parameters."""
    defaults = {
        "show_same_sector": True,
        "show_market_cap": True,
        "show_correlation": True,
        "show_corporate_bond": True,
        "show_commodity_currency": True,
        "show_income_comparison": True,
        "show_regulatory": True,
        "show_all_relationships": False,
    } | overrides
    return _create_2d_relationship_traces(graph, positions, asset_ids, **defaults)


@pytest.mark.unit
class TestVisualize2DGraph:
    """Test suite for the visualize_2d_graph function."""

    def test_visualize_2d_graph_with_populated_graph(self, populated_graph):
        """Test creating 2D visualization with populated graph."""
        # Execute
        fig = visualize_2d_graph(populated_graph)

        # Assert
        assert isinstance(fig, go.Figure)
        assert "2D Asset Relationship Network" in fig.layout.title.text
        assert fig.layout.plot_bgcolor == "white"
        assert fig.layout.paper_bgcolor == "#F8F9FA"

    def test_visualize_2d_graph_with_empty_graph(self, empty_graph):
        """Test creating 2D visualization with empty graph."""
        # Execute
        fig = visualize_2d_graph(empty_graph)

        # Assert
        assert isinstance(fig, go.Figure)

    def test_visualize_2d_graph_spring_layout(self, populated_graph):
        """Test 2D visualization with spring layout."""
        # Execute
        fig = visualize_2d_graph(populated_graph, layout_type="spring")

        # Assert
        assert isinstance(fig, go.Figure)
        # Verify layout type is mentioned in annotations
        has_layout_info = any("spring" in str(ann.text).lower() for ann in fig.layout.annotations)
        assert has_layout_info, "Layout type should be indicated in figure"

    def test_visualize_2d_graph_circular_layout(self, populated_graph):
        """Test 2D visualization with circular layout."""
        # Execute
        fig = visualize_2d_graph(populated_graph, layout_type="circular")

        # Assert
        assert isinstance(fig, go.Figure)
        has_layout_info = any("circular" in str(ann.text).lower() for ann in fig.layout.annotations)
        assert has_layout_info

    def test_visualize_2d_graph_grid_layout(self, populated_graph):
        """Test 2D visualization with grid layout."""
        # Execute
        fig = visualize_2d_graph(populated_graph, layout_type="grid")

        # Assert
        assert isinstance(fig, go.Figure)
        has_layout_info = any("grid" in str(ann.text).lower() for ann in fig.layout.annotations)
        assert has_layout_info

    def test_visualize_2d_graph_with_relationship_filters(self, populated_graph):
        """Test 2D visualization with selective relationship filtering."""
        # Execute - show only same sector relationships
        fig = visualize_2d_graph(
            populated_graph,
            show_same_sector=True,
            show_market_cap=False,
            show_correlation=False,
            show_corporate_bond=False,
            show_commodity_currency=False,
            show_income_comparison=False,
            show_regulatory=False,
            show_all_relationships=False,
        )

        # Assert
        assert isinstance(fig, go.Figure)

    def test_visualize_2d_graph_show_all_relationships(self, populated_graph):
        """Test showing all relationships regardless of individual filters."""
        # Execute
        fig = visualize_2d_graph(populated_graph, show_all_relationships=True)

        # Assert
        assert isinstance(fig, go.Figure)
        # When show_all is True, should display more traces
        assert len(fig.data) > 0

    def test_visualize_2d_graph_node_sizes(self, populated_graph):
        """Test that node sizes are properly calculated."""
        # Execute
        fig = visualize_2d_graph(populated_graph)

        # Find node trace
        node_traces = [trace for trace in fig.data if hasattr(trace, "mode") and "markers" in trace.mode]
        assert len(node_traces) > 0, "Should have node traces"

        node_trace = node_traces[0]
        if hasattr(node_trace.marker, "size"):
            sizes = node_trace.marker.size
            # Verify sizes are within expected range
            for size in sizes:
                assert 20 <= size <= 50, "Node sizes should be between 20 and 50"

    def test_visualize_2d_graph_preserves_graph_state(self, populated_graph):
        """Test that visualization doesn't modify the graph."""
        initial_asset_count = len(populated_graph.assets)

        # Execute
        visualize_2d_graph(populated_graph)

        # Assert
        assert len(populated_graph.assets) == initial_asset_count


@pytest.mark.unit
class TestLayoutAlgorithms:
    """Test suite for layout algorithms."""

    @staticmethod
    def test_create_circular_layout_empty_list():
        """Test circular layout with empty asset list."""
        # Execute
        positions = _create_circular_layout([])

        # Assert
        assert isinstance(positions, dict)
        assert len(positions) == 0

    @staticmethod
    def test_create_circular_layout_single_asset():
        """Test circular layout with one asset."""
        # Execute
        positions = _create_circular_layout(["ASSET_1"])

        # Assert
        assert len(positions) == 1
        assert "ASSET_1" in positions
        x, y = positions["ASSET_1"]
        assert isinstance(x, float)
        assert isinstance(y, float)

    @staticmethod
    def test_create_circular_layout_multiple_assets():
        """Test circular layout with multiple assets."""
        # Execute
        asset_ids = ["AAPL", "MSFT", "GOOGL", "AMZN"]

        # Execute
        positions = _create_circular_layout(asset_ids)

        # Assert
        assert len(positions) == 4
        for asset_id in asset_ids:
            assert asset_id in positions
            x, y = positions[asset_id]
            # Verify positions are roughly on unit circle
            distance = (x**2 + y**2) ** 0.5
            assert abs(distance - 1.0) < 0.01

    def test_create_grid_layout_empty_list(self):
        """Test grid layout with empty asset list."""
        # Execute
        positions = _create_grid_layout([])

        # Assert
        assert isinstance(positions, dict)
        assert len(positions) == 0

    def test_create_grid_layout_single_asset(self):
        """Test grid layout with one asset."""
        # Execute
        positions = _create_grid_layout(["ASSET_1"])

        # Assert
        assert len(positions) == 1
        assert "ASSET_1" in positions

    def test_create_grid_layout_multiple_assets(self):
        """Test grid layout with multiple assets."""
        asset_ids = [f"ASSET_{i}" for i in range(9)]

        # Execute
        positions = _create_grid_layout(asset_ids)

        # Assert
        assert len(positions) == 9
        # With 9 assets, should form a 3x3 grid
        x_coords = [pos[0] for pos in positions.values()]
        y_coords = [pos[1] for pos in positions.values()]

        # Verify we have grid-like structure
        assert len(set(x_coords)) <= 3  # At most 3 columns
        assert len(set(y_coords)) <= 3  # At most 3 rows

    def test_create_spring_layout_2d_empty_dict(self):
        """Test spring layout conversion with empty positions."""
        # Execute
        positions = _create_spring_layout_2d({}, [])

        # Assert
        assert isinstance(positions, dict)
        assert len(positions) == 0

    def test_create_spring_layout_2d_conversion(self):
        """Test conversion from 3D to 2D positions."""
        positions_3d = {
            "ASSET_1": (1.0, 2.0, 3.0),
            "ASSET_2": (4.0, 5.0, 6.0),
        }
        asset_ids = ["ASSET_1", "ASSET_2"]

        # Execute
        positions_2d = _create_spring_layout_2d(positions_3d, asset_ids)

        # Assert
        assert len(positions_2d) == 2
        assert positions_2d["ASSET_1"] == (1.0, 2.0)  # z-coordinate dropped
        assert positions_2d["ASSET_2"] == (4.0, 5.0)

    def test_create_spring_layout_2d_with_numpy_array(self):
        """Test spring layout with numpy array positions."""
        import numpy as np

        positions_3d = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        asset_ids = ["ASSET_1", "ASSET_2"]

        # Convert to dict format
        positions_dict = {asset_ids[i]: positions_3d[i] for i in range(len(asset_ids))}

        # Execute
        positions_2d = _create_spring_layout_2d(positions_dict, asset_ids)

        # Assert
        assert len(positions_2d) == 2


@pytest.mark.unit
class TestRelationshipTraces:
    """Test suite for relationship trace creation."""

    def test_create_2d_relationship_traces_with_relationships(self, populated_graph):
        """Test creating relationship traces with existing relationships."""
        # Add some relationships
        populated_graph.add_relationship("TEST_AAPL", "TEST_BOND", "corporate_bond_to_equity", 0.8)

        # Create positions
        positions = {"TEST_AAPL": (0, 0), "TEST_BOND": (1, 1), "TEST_GOLD": (2, 2), "TEST_EUR": (3, 3)}
        asset_ids = list(positions.keys())

        # Execute
        traces = create_relationship_traces_with_defaults(
            populated_graph,
            positions,
            asset_ids,
        )

        # Assert
        assert isinstance(traces, list)

    def test_create_2d_relationship_traces_show_all(self, populated_graph):
        """Test creating traces with show_all_relationships=True."""
        positions = {"TEST_AAPL": (0, 0), "TEST_BOND": (1, 1)}
        asset_ids = list(positions.keys())

        # Execute
        traces = create_relationship_traces_with_defaults(
            populated_graph,
            positions,
            asset_ids,
            show_same_sector=False,
            show_market_cap=False,
            show_correlation=False,
            show_corporate_bond=False,
            show_commodity_currency=False,
            show_income_comparison=False,
            show_regulatory=False,
            show_all_relationships=True,
        )

        # Assert
        assert isinstance(traces, list)

    def test_create_2d_relationship_traces_selective_filtering(self, populated_graph):
        """Test selective relationship filtering."""
        positions = {"TEST_AAPL": (0, 0), "TEST_BOND": (1, 1)}
        asset_ids = list(positions.keys())

        # Execute - only show corporate bond relationships
        traces = create_relationship_traces_with_defaults(
            populated_graph,
            positions,
            asset_ids,
            show_same_sector=False,
            show_market_cap=False,
            show_correlation=False,
            show_corporate_bond=True,
            show_commodity_currency=False,
            show_income_comparison=False,
            show_regulatory=False,
            show_all_relationships=False,
        )

        # Assert
        assert isinstance(traces, list)

    def test_create_2d_relationship_traces_empty_graph(self, empty_graph):
        """Test creating traces with empty graph."""
        positions = {}
        asset_ids = []

        # Execute
        traces = create_relationship_traces_with_defaults(
            empty_graph,
            positions,
            asset_ids,
        )

        # Assert
        assert isinstance(traces, list)
        assert len(traces) == 0


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_visualize_2d_graph_with_single_asset(self, empty_graph, sample_equity):
        """Test 2D visualization with only one asset."""
        empty_graph.add_asset(sample_equity)

        # Execute
        fig = visualize_2d_graph(empty_graph)

        # Assert
        assert isinstance(fig, go.Figure)

    def test_circular_layout_with_many_assets(self):
        """Test circular layout with many assets."""
        asset_ids = [f"ASSET_{i}" for i in range(100)]

        # Execute
        positions = _create_circular_layout(asset_ids)

        # Assert
        assert len(positions) == 100
        # Verify all positions are on unit circle
        for pos in positions.values():
            distance = (pos[0] ** 2 + pos[1] ** 2) ** 0.5
            assert abs(distance - 1.0) < 0.01

    def test_grid_layout_with_non_square_number(self):
        """Test grid layout with non-perfect-square number of assets."""
        asset_ids = [f"ASSET_{i}" for i in range(7)]

        # Execute
        positions = _create_grid_layout(asset_ids)

        # Assert
        assert len(positions) == 7

    def test_visualize_2d_graph_with_invalid_layout_type(self, populated_graph):
        """Test that invalid layout type defaults to spring."""
        # Execute - use invalid layout type
        fig = visualize_2d_graph(populated_graph, layout_type="invalid")

        # Assert - should still create valid figure (defaults to spring)
        assert isinstance(fig, go.Figure)

    def test_relationship_traces_with_missing_assets_in_positions(self, populated_graph):
        """Test creating traces when some assets in relationships aren't in positions."""
        # Add relationship
        populated_graph.add_relationship("TEST_AAPL", "TEST_BOND", "corporate_bond_to_equity", 0.8)

        # Create positions without TEST_BOND
        positions = {"TEST_AAPL": (0, 0)}
        asset_ids = ["TEST_AAPL"]

        # Execute - should handle missing assets gracefully
        traces = _create_2d_relationship_traces(
            populated_graph,
            positions,
            asset_ids,
            show_same_sector=True,
            show_market_cap=True,
            show_correlation=True,
            show_corporate_bond=True,
            show_commodity_currency=True,
            show_income_comparison=True,
            show_regulatory=True,
            show_all_relationships=False,
        )

        # Assert
        assert isinstance(traces, list)
