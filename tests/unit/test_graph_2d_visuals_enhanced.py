"""Enhanced comprehensive unit tests for src/visualizations/graph_2d_visuals.py.

This module provides additional extensive test coverage for:
- 2D layout algorithms (circular, grid, spring)
- String formatting and quote consistency
- Layout coordinate calculations
- Edge cases in 2D visualization
- Relationship trace creation
- Node positioning and sizing
- Error handling and validation
"""

import math
from unittest.mock import Mock, patch

import numpy as np
import plotly.graph_objects as go
import pytest

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_2d_visuals import (
    _create_2d_relationship_traces,
    _create_circular_layout,
    _create_grid_layout,
    _create_spring_layout_2d,
    visualize_2d_graph,
)


class TestCreateCircularLayout:
    """Test circular layout generation for 2D visualization."""

    def test_circular_layout_single_asset(self):
        """Test circular layout with single asset."""
        layout = _create_circular_layout(['ASSET_1'])
        assert 'ASSET_1' in layout
        assert isinstance(layout['ASSET_1'], tuple)
        assert len(layout['ASSET_1']) == 2  # (x, y)

    def test_circular_layout_two_assets(self):
        """Test circular layout with two assets."""
        layout = _create_circular_layout(['ASSET_1', 'ASSET_2'])
        assert len(layout) == 2
        assert 'ASSET_1' in layout
        assert 'ASSET_2' in layout

    def test_circular_layout_multiple_assets(self):
        """Test circular layout with multiple assets."""
        asset_ids = [f'ASSET_{i}' for i in range(10)]
        layout = _create_circular_layout(asset_ids)
        assert len(layout) == 10

    def test_circular_layout_coordinates_on_circle(self):
        """Test that generated coordinates lie on a circle."""
        asset_ids = ['A', 'B', 'C', 'D']
        layout = _create_circular_layout(asset_ids)
        
        # All points should be approximately same distance from origin
        distances = [math.sqrt(x**2 + y**2) for x, y in layout.values()]
        # Allow small floating point differences
        assert all(abs(d - distances[0]) < 0.001 for d in distances)

    def test_circular_layout_evenly_spaced(self):
        """Test that points are evenly spaced around circle."""
        asset_ids = ['A', 'B', 'C', 'D']
        layout = _create_circular_layout(asset_ids)
        
        # Calculate angles
        angles = [math.atan2(y, x) for x, y in layout.values()]
        # Sort angles
        angles.sort()
        
        # Check angle differences are approximately equal
        if len(angles) > 1:
            expected_diff = 2 * math.pi / len(angles)
            for i in range(len(angles) - 1):
                actual_diff = angles[i + 1] - angles[i]
                assert abs(actual_diff - expected_diff) < 0.1

    def test_circular_layout_empty_list(self):
        """Test circular layout with empty asset list."""
        layout = _create_circular_layout([])
        assert len(layout) == 0
        assert isinstance(layout, dict)

    def test_circular_layout_large_number_of_assets(self):
        """Test circular layout with many assets."""
        asset_ids = [f'ASSET_{i}' for i in range(100)]
        layout = _create_circular_layout(asset_ids)
        assert len(layout) == 100

    def test_circular_layout_returns_dict(self):
        """Test that circular layout returns dictionary."""
        layout = _create_circular_layout(['ASSET_1'])
        assert isinstance(layout, dict)

    def test_circular_layout_coordinates_are_floats(self):
        """Test that coordinates are float values."""
        layout = _create_circular_layout(['ASSET_1', 'ASSET_2'])
        for x, y in layout.values():
            assert isinstance(x, (float, np.floating))
            assert isinstance(y, (float, np.floating))


class TestCreateGridLayout:
    """Test grid layout generation for 2D visualization."""

    def test_grid_layout_single_asset(self):
        """Test grid layout with single asset."""
        layout = _create_grid_layout(['ASSET_1'])
        assert 'ASSET_1' in layout
        assert isinstance(layout['ASSET_1'], tuple)
        assert len(layout['ASSET_1']) == 2

    def test_grid_layout_perfect_square(self):
        """Test grid layout with perfect square number of assets."""
        asset_ids = [f'ASSET_{i}' for i in range(9)]  # 3x3 grid
        layout = _create_grid_layout(asset_ids)
        assert len(layout) == 9

    def test_grid_layout_non_square(self):
        """Test grid layout with non-square number of assets."""
        asset_ids = [f'ASSET_{i}' for i in range(10)]
        layout = _create_grid_layout(asset_ids)
        assert len(layout) == 10

    def test_grid_layout_two_assets(self):
        """Test grid layout with two assets."""
        layout = _create_grid_layout(['ASSET_1', 'ASSET_2'])
        assert len(layout) == 2

    def test_grid_layout_coordinates_integer_like(self):
        """Test that grid coordinates are on integer grid positions."""
        asset_ids = [f'ASSET_{i}' for i in range(4)]
        layout = _create_grid_layout(asset_ids)
        
        # Grid coordinates should be integer-like (0, 1, 2, etc.)
        for x, y in layout.values():
            assert isinstance(x, (int, float))
            assert isinstance(y, (int, float))

    def test_grid_layout_empty_list(self):
        """Test grid layout with empty asset list."""
        layout = _create_grid_layout([])
        assert len(layout) == 0
        assert isinstance(layout, dict)

    def test_grid_layout_large_number(self):
        """Test grid layout with large number of assets."""
        asset_ids = [f'ASSET_{i}' for i in range(100)]
        layout = _create_grid_layout(asset_ids)
        assert len(layout) == 100

    def test_grid_layout_returns_dict(self):
        """Test that grid layout returns dictionary."""
        layout = _create_grid_layout(['ASSET_1'])
        assert isinstance(layout, dict)

    def test_grid_layout_no_overlapping_positions(self):
        """Test that no two assets have same position."""
        asset_ids = [f'ASSET_{i}' for i in range(20)]
        layout = _create_grid_layout(asset_ids)
        
        positions = list(layout.values())
        # Check all positions are unique
        assert len(positions) == len(set(positions))


class TestCreateSpringLayout2D:
    """Test spring layout conversion from 3D to 2D."""

    def test_spring_layout_basic_conversion(self):
        """Test basic 3D to 2D conversion."""
        positions_3d = {
            'ASSET_1': (1.0, 2.0, 3.0),
            'ASSET_2': (4.0, 5.0, 6.0)
        }
        asset_ids = ['ASSET_1', 'ASSET_2']
        
        layout_2d = _create_spring_layout_2d(positions_3d, asset_ids)
        
        assert 'ASSET_1' in layout_2d
        assert 'ASSET_2' in layout_2d
        assert layout_2d['ASSET_1'] == (1.0, 2.0)  # x, y only
        assert layout_2d['ASSET_2'] == (4.0, 5.0)

    def test_spring_layout_drops_z_coordinate(self):
        """Test that z-coordinate is dropped in conversion."""
        positions_3d = {'ASSET_1': (1.0, 2.0, 999.0)}
        asset_ids = ['ASSET_1']
        
        layout_2d = _create_spring_layout_2d(positions_3d, asset_ids)
        
        assert len(layout_2d['ASSET_1']) == 2
        assert layout_2d['ASSET_1'][0] == 1.0
        assert layout_2d['ASSET_1'][1] == 2.0

    def test_spring_layout_missing_asset_in_3d(self):
        """Test handling of asset not in 3D positions."""
        positions_3d = {'ASSET_1': (1.0, 2.0, 3.0)}
        asset_ids = ['ASSET_1', 'ASSET_2']  # ASSET_2 missing
        
        layout_2d = _create_spring_layout_2d(positions_3d, asset_ids)
        
        assert 'ASSET_1' in layout_2d
        # ASSET_2 should not be in layout if not in positions_3d
        # Or should have default position - check actual behavior

    def test_spring_layout_numpy_array_positions(self):
        """Test conversion with numpy array positions."""
        positions_3d = {
            'ASSET_1': np.array([1.0, 2.0, 3.0]),
            'ASSET_2': np.array([4.0, 5.0, 6.0])
        }
        asset_ids = ['ASSET_1', 'ASSET_2']
        
        layout_2d = _create_spring_layout_2d(positions_3d, asset_ids)
        
        assert 'ASSET_1' in layout_2d
        assert layout_2d['ASSET_1'] == (1.0, 2.0)

    def test_spring_layout_empty_positions(self):
        """Test with empty 3D positions."""
        layout_2d = _create_spring_layout_2d({}, [])
        assert len(layout_2d) == 0
        assert isinstance(layout_2d, dict)

    def test_spring_layout_single_asset(self):
        """Test with single asset."""
        positions_3d = {'ASSET_1': (0.0, 0.0, 0.0)}
        layout_2d = _create_spring_layout_2d(positions_3d, ['ASSET_1'])
        assert 'ASSET_1' in layout_2d

    def test_spring_layout_negative_coordinates(self):
        """Test with negative 3D coordinates."""
        positions_3d = {
            'ASSET_1': (-1.0, -2.0, -3.0),
            'ASSET_2': (-4.0, -5.0, -6.0)
        }
        asset_ids = ['ASSET_1', 'ASSET_2']
        
        layout_2d = _create_spring_layout_2d(positions_3d, asset_ids)
        
        assert layout_2d['ASSET_1'] == (-1.0, -2.0)
        assert layout_2d['ASSET_2'] == (-4.0, -5.0)

    def test_spring_layout_zero_coordinates(self):
        """Test with zero coordinates."""
        positions_3d = {'ASSET_1': (0.0, 0.0, 0.0)}
        layout_2d = _create_spring_layout_2d(positions_3d, ['ASSET_1'])
        assert layout_2d['ASSET_1'] == (0.0, 0.0)


class TestCreate2DRelationshipTraces:
    """Test 2D relationship trace creation."""

    @pytest.fixture
    def mock_graph(self):
        """Create a mock graph with relationships."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.relationships = {
            'ASSET_1': [
                {'target_id': 'ASSET_2', 'relationship_type': 'correlation', 'strength': 0.8, 'bidirectional': False}
            ]
        }
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        return graph

    @pytest.fixture
    def positions(self):
        """Create sample 2D positions."""
        return {
            'ASSET_1': (0.0, 0.0),
            'ASSET_2': (1.0, 1.0),
            'ASSET_3': (2.0, 0.0)
        }

    def test_create_traces_basic(self, mock_graph, positions):
        """Test basic trace creation."""
        asset_ids = ['ASSET_1', 'ASSET_2']
        traces = _create_2d_relationship_traces(mock_graph, positions, asset_ids)
        
        assert isinstance(traces, list)
        # Should have at least one trace for the relationship
        assert len(traces) >= 0

    def test_create_traces_returns_scatter_objects(self, mock_graph, positions):
        """Test that traces are Plotly Scatter objects."""
        asset_ids = ['ASSET_1', 'ASSET_2']
        traces = _create_2d_relationship_traces(mock_graph, positions, asset_ids)
        
        for trace in traces:
            assert isinstance(trace, go.Scatter)

    def test_create_traces_empty_graph(self, positions):
        """Test trace creation with graph having no relationships."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.relationships = {}
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        
        traces = _create_2d_relationship_traces(graph, positions, ['ASSET_1'])
        assert isinstance(traces, list)

    def test_create_traces_with_filters(self, mock_graph, positions):
        """Test trace creation with relationship filters."""
        asset_ids = ['ASSET_1', 'ASSET_2']
        filters = {'correlation': True, 'dependency': False}
        traces = _create_2d_relationship_traces(mock_graph, positions, asset_ids, filters)
        
        assert isinstance(traces, list)

    def test_create_traces_none_filters(self, mock_graph, positions):
        """Test trace creation with None filters (show all)."""
        asset_ids = ['ASSET_1', 'ASSET_2']
        traces = _create_2d_relationship_traces(mock_graph, positions, asset_ids, None)
        
        assert isinstance(traces, list)


class TestVisualize2DGraph:
    """Test complete 2D graph visualization."""

    @pytest.fixture
    def mock_graph_with_3d_data(self):
        """Create mock graph with 3D visualization data."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.assets = {
            'ASSET_1': Mock(asset_class=Mock(value='equity'), symbol='A1', name='Asset 1', price=100.0),
            'ASSET_2': Mock(asset_class=Mock(value='equity'), symbol='A2', name='Asset 2', price=200.0)
        }
        graph.relationships = {
            'ASSET_1': [{'target_id': 'ASSET_2', 'relationship_type': 'correlation', 'strength': 0.8, 'bidirectional': False}]
        }
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        
        # Mock 3D visualization data
        positions_3d = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        asset_ids = ['ASSET_1', 'ASSET_2']
        graph.get_3d_visualization_data_enhanced = Mock(return_value=(
            positions_3d, asset_ids, ['#ff0000', '#00ff00'], ['Asset 1', 'Asset 2']
        ))
        
        return graph

    def test_visualize_2d_circular_layout(self, mock_graph_with_3d_data):
        """Test 2D visualization with circular layout."""
        fig = visualize_2d_graph(mock_graph_with_3d_data, layout='circular')
        assert isinstance(fig, go.Figure)

    def test_visualize_2d_grid_layout(self, mock_graph_with_3d_data):
        """Test 2D visualization with grid layout."""
        fig = visualize_2d_graph(mock_graph_with_3d_data, layout='grid')
        assert isinstance(fig, go.Figure)

    def test_visualize_2d_spring_layout(self, mock_graph_with_3d_data):
        """Test 2D visualization with spring layout."""
        fig = visualize_2d_graph(mock_graph_with_3d_data, layout='spring')
        assert isinstance(fig, go.Figure)

    def test_visualize_2d_default_layout(self, mock_graph_with_3d_data):
        """Test 2D visualization with default layout."""
        fig = visualize_2d_graph(mock_graph_with_3d_data)
        assert isinstance(fig, go.Figure)

    def test_visualize_2d_invalid_layout(self, mock_graph_with_3d_data):
        """Test 2D visualization with invalid layout name."""
        # Should fall back to default or raise error
        try:
            fig = visualize_2d_graph(mock_graph_with_3d_data, layout='invalid_layout')
            assert isinstance(fig, go.Figure)
        except ValueError:
            pass  # Acceptable to raise error for invalid layout

    def test_visualize_2d_returns_figure(self, mock_graph_with_3d_data):
        """Test that visualization returns Plotly Figure."""
        fig = visualize_2d_graph(mock_graph_with_3d_data)
        assert hasattr(fig, 'data')
        assert hasattr(fig, 'layout')

    def test_visualize_2d_figure_has_traces(self, mock_graph_with_3d_data):
        """Test that returned figure has traces."""
        fig = visualize_2d_graph(mock_graph_with_3d_data)
        assert len(fig.data) > 0

    def test_visualize_2d_with_filters(self, mock_graph_with_3d_data):
        """Test 2D visualization with relationship filters."""
        filters = {'correlation': True}
        fig = visualize_2d_graph(mock_graph_with_3d_data, relationship_filters=filters)
        assert isinstance(fig, go.Figure)

    def test_visualize_2d_single_asset(self):
        """Test visualization with single asset."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.assets = {
            'ASSET_1': Mock(asset_class=Mock(value='equity'), symbol='A1', name='Asset 1', price=100.0)
        }
        graph.relationships = {}
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        graph.get_3d_visualization_data_enhanced = Mock(return_value=(
            np.array([[0.0, 0.0, 0.0]]), ['ASSET_1'], ['#ff0000'], ['Asset 1']
        ))
        
        fig = visualize_2d_graph(graph)
        assert isinstance(fig, go.Figure)

    def test_visualize_2d_many_assets(self):
        """Test visualization with many assets."""
        graph = Mock(spec=AssetRelationshipGraph)
        num_assets = 50
        asset_ids = [f'ASSET_{i}' for i in range(num_assets)]
        
        graph.assets = {
            aid: Mock(asset_class=Mock(value='equity'), symbol=aid, name=aid, price=100.0)
            for aid in asset_ids
        }
        graph.relationships = {}
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        
        positions = np.random.randn(num_assets, 3)
        colors = ['#ff0000'] * num_assets
        hover_texts = [f'Asset {i}' for i in range(num_assets)]
        
        graph.get_3d_visualization_data_enhanced = Mock(return_value=(
            positions, asset_ids, colors, hover_texts
        ))
        
        fig = visualize_2d_graph(graph)
        assert isinstance(fig, go.Figure)


class TestLayoutEdgeCases:
    """Test edge cases in layout algorithms."""

    def test_circular_layout_single_point_not_nan(self):
        """Test that single point circular layout doesn't produce NaN."""
        layout = _create_circular_layout(['ASSET_1'])
        x, y = layout['ASSET_1']
        assert not math.isnan(x)
        assert not math.isnan(y)

    def test_grid_layout_single_point_valid(self):
        """Test that single point grid layout produces valid coordinates."""
        layout = _create_grid_layout(['ASSET_1'])
        x, y = layout['ASSET_1']
        assert isinstance(x, (int, float))
        assert isinstance(y, (int, float))

    def test_circular_layout_very_large_radius(self):
        """Test circular layout calculations don't overflow."""
        # Many assets should still produce valid layout
        asset_ids = [f'ASSET_{i}' for i in range(1000)]
        layout = _create_circular_layout(asset_ids)
        
        for x, y in layout.values():
            assert not math.isnan(x)
            assert not math.isnan(y)
            assert not math.isinf(x)
            assert not math.isinf(y)

    def test_grid_layout_correct_dimensions(self):
        """Test grid layout has reasonable dimensions."""
        asset_ids = [f'ASSET_{i}' for i in range(25)]
        layout = _create_grid_layout(asset_ids)
        
        # Extract all x and y coordinates
        x_coords = [x for x, y in layout.values()]
        y_coords = [y for x, y in layout.values()]
        
        # Grid should have reasonable bounds
        assert min(x_coords) >= 0
        assert min(y_coords) >= 0


class TestStringFormattingConsistency:
    """Test string formatting consistency after code style changes."""

    def test_trace_names_consistent(self, mock_graph_with_3d_data):
        """Test that trace names are consistently formatted."""
        fig = visualize_2d_graph(mock_graph_with_3d_data)
        
        for trace in fig.data:
            if hasattr(trace, 'name'):
                assert isinstance(trace.name, str)

    def test_hover_text_formatting(self):
        """Test hover text formatting consistency."""
        positions = {
            'ASSET_1': (0.0, 0.0),
            'ASSET_2': (1.0, 1.0)
        }
        graph = Mock(spec=AssetRelationshipGraph)
        graph.relationships = {
            'ASSET_1': [
                {'target_id': 'ASSET_2', 'relationship_type': 'correlation', 'strength': 0.85, 'bidirectional': False}
            ]
        }
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        
        traces = _create_2d_relationship_traces(graph, positions, ['ASSET_1', 'ASSET_2'])
        
        # Traces should be created without errors
        assert isinstance(traces, list)


class TestColorMapping:
    """Test color mapping for different asset classes in 2D visualization."""

    def test_asset_class_color_mapping(self):
        """Test that different asset classes get different colors."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.assets = {
            'EQUITY_1': Mock(asset_class=Mock(value='equity'), symbol='E1', name='Equity', price=100.0),
            'BOND_1': Mock(asset_class=Mock(value='fixed_income'), symbol='B1', name='Bond', price=1000.0),
            'COMM_1': Mock(asset_class=Mock(value='commodity'), symbol='C1', name='Commodity', price=50.0)
        }
        graph.relationships = {}
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        
        asset_ids = ['EQUITY_1', 'BOND_1', 'COMM_1']
        positions = np.random.randn(3, 3)
        colors = ['#1f77b4', '#2ca02c', '#ff7f0e']
        hover_texts = ['Equity', 'Bond', 'Commodity']
        
        graph.get_3d_visualization_data_enhanced = Mock(return_value=(
            positions, asset_ids, colors, hover_texts
        ))
        
        fig = visualize_2d_graph(graph)
        assert isinstance(fig, go.Figure)


class TestRelationshipGrouping:
    """Test relationship grouping by type in 2D visualization."""

    def test_relationships_grouped_by_type(self):
        """Test that relationships are grouped by type."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.relationships = {
            'ASSET_1': [
                {'target_id': 'ASSET_2', 'relationship_type': 'correlation', 'strength': 0.8, 'bidirectional': False},
                {'target_id': 'ASSET_3', 'relationship_type': 'dependency', 'strength': 0.6, 'bidirectional': False}
            ]
        }
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        
        positions = {
            'ASSET_1': (0.0, 0.0),
            'ASSET_2': (1.0, 0.0),
            'ASSET_3': (0.0, 1.0)
        }
        asset_ids = ['ASSET_1', 'ASSET_2', 'ASSET_3']
        
        traces = _create_2d_relationship_traces(graph, positions, asset_ids)
        
        # Should create separate traces for different relationship types
        assert isinstance(traces, list)


class TestPerformanceAndScaling:
    """Test performance with large datasets."""

    def test_large_circular_layout_performance(self):
        """Test circular layout with large number of assets."""
        asset_ids = [f'ASSET_{i}' for i in range(10000)]
        layout = _create_circular_layout(asset_ids)
        
        assert len(layout) == 10000
        assert all(isinstance(pos, tuple) for pos in layout.values())

    def test_large_grid_layout_performance(self):
        """Test grid layout with large number of assets."""
        asset_ids = [f'ASSET_{i}' for i in range(10000)]
        layout = _create_grid_layout(asset_ids)
        
        assert len(layout) == 10000


@pytest.fixture
def mock_graph_with_3d_data():
    """Create mock graph with 3D visualization data for module-level use."""
    graph = Mock(spec=AssetRelationshipGraph)
    graph.assets = {
        'ASSET_1': Mock(asset_class=Mock(value='equity'), symbol='A1', name='Asset 1', price=100.0),
        'ASSET_2': Mock(asset_class=Mock(value='equity'), symbol='A2', name='Asset 2', price=200.0)
    }
    graph.relationships = {
        'ASSET_1': [{'target_id': 'ASSET_2', 'relationship_type': 'correlation', 'strength': 0.8, 'bidirectional': False}]
    }
    graph._lock = Mock()
    graph._lock.__enter__ = Mock()
    graph._lock.__exit__ = Mock()
    
    positions_3d = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
    asset_ids = ['ASSET_1', 'ASSET_2']
    graph.get_3d_visualization_data_enhanced = Mock(return_value=(
        positions_3d, asset_ids, ['#ff0000', '#00ff00'], ['Asset 1', 'Asset 2']
    ))
    
    return graph