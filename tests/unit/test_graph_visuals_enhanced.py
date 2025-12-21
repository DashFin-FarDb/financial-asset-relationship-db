"""Enhanced comprehensive unit tests for src/visualizations/graph_visuals.py.

This module provides additional extensive test coverage for:
- Color format validation with various formats
- String formatting and quote style handling
- Error message formatting and multi-line strings
- Parameter validation edge cases
- Thread-safety in relationship building
- Filter parameter validation
- Edge cases in visualization data
- Boundary conditions and error handling
"""

import re
from unittest.mock import Mock, patch

import numpy as np
import plotly.graph_objects as go
import pytest

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_visuals import (
    _build_relationship_index,
    _create_node_trace,
    _generate_dynamic_title,
    _is_valid_color_format,
    _validate_asset_ids_list,
    _validate_colors_list,
    _validate_filter_parameters,
    _validate_hover_texts_list,
    _validate_positions_array,
    _validate_relationship_filters,
    _validate_visualization_data,
    visualize_3d_graph,
    visualize_3d_graph_with_filters,
)


class TestIsValidColorFormat:
    """Test color format validation with comprehensive format coverage."""

    def test_valid_hex_color_3_digit(self):
        """Test valid 3-digit hex color."""
        assert _is_valid_color_format('#fff') is True
        assert _is_valid_color_format('#000') is True
        assert _is_valid_color_format('#abc') is True

    def test_valid_hex_color_6_digit(self):
        """Test valid 6-digit hex color."""
        assert _is_valid_color_format('#ffffff') is True
        assert _is_valid_color_format('#000000') is True
        assert _is_valid_color_format('#1a2b3c') is True

    def test_valid_hex_color_8_digit_with_alpha(self):
        """Test valid 8-digit hex color with alpha channel."""
        assert _is_valid_color_format('#ffffffff') is True
        assert _is_valid_color_format('#00000080') is True

    def test_valid_hex_color_mixed_case(self):
        """Test hex colors with mixed case."""
        assert _is_valid_color_format('#AbCdEf') is True
        assert _is_valid_color_format('#ABC') is True

    def test_valid_rgb_color(self):
        """Test valid rgb() format."""
        assert _is_valid_color_format('rgb(255, 255, 255)') is True
        assert _is_valid_color_format('rgb(0, 0, 0)') is True
        assert _is_valid_color_format('rgb(128, 64, 32)') is True

    def test_valid_rgba_color(self):
        """Test valid rgba() format."""
        assert _is_valid_color_format('rgba(255, 255, 255, 1.0)') is True
        assert _is_valid_color_format('rgba(0, 0, 0, 0.5)') is True

    def test_valid_named_colors(self):
        """Test valid CSS named colors."""
        assert _is_valid_color_format('red') is True
        assert _is_valid_color_format('blue') is True
        assert _is_valid_color_format('green') is True
        assert _is_valid_color_format('transparent') is True

    def test_invalid_hex_color_wrong_length(self):
        """Test invalid hex color with wrong length."""
        assert _is_valid_color_format('#ff') is False
        assert _is_valid_color_format('#fffffff') is False

    def test_invalid_hex_color_no_hash(self):
        """Test hex color without hash symbol."""
        assert _is_valid_color_format('ffffff') is False

    def test_invalid_hex_color_invalid_chars(self):
        """Test hex color with invalid characters."""
        assert _is_valid_color_format('#gggggg') is False
        assert _is_valid_color_format('#xyz') is False

    def test_invalid_empty_string(self):
        """Test empty string is invalid."""
        assert _is_valid_color_format('') is False

    def test_invalid_none_value(self):
        """Test None value is invalid."""
        assert _is_valid_color_format(None) is False

    def test_invalid_numeric_value(self):
        """Test numeric value is invalid."""
        assert _is_valid_color_format(123) is False

    def test_valid_color_with_spaces(self):
        """Test color formats with extra spaces."""
        # Note: This tests the actual behavior
        assert isinstance(_is_valid_color_format('rgb(255, 255, 255)'), bool)


class TestBuildRelationshipIndex:
    """Test relationship index building with various graph states."""

    @pytest.fixture
    def mock_graph(self):
        """Create a mock AssetRelationshipGraph."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.relationships = {
            'ASSET_1': [
                {'target_id': 'ASSET_2', 'relationship_type': 'correlation', 'strength': 0.8},
                {'target_id': 'ASSET_3', 'relationship_type': 'dependency', 'strength': 0.6}
            ],
            'ASSET_2': [
                {'target_id': 'ASSET_3', 'relationship_type': 'correlation', 'strength': 0.7}
            ]
        }
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        return graph

    def test_build_relationship_index_basic(self, mock_graph):
        """Test building basic relationship index."""
        asset_ids = ['ASSET_1', 'ASSET_2', 'ASSET_3']
        index = _build_relationship_index(mock_graph, asset_ids)
        
        assert isinstance(index, dict)
        assert 'ASSET_1' in index

    def test_build_relationship_index_filters_non_included_assets(self, mock_graph):
        """Test that relationships to non-included assets are filtered."""
        asset_ids = ['ASSET_1', 'ASSET_2']  # Exclude ASSET_3
        index = _build_relationship_index(mock_graph, asset_ids)
        
        # Relationships to ASSET_3 should be filtered out
        if 'ASSET_1' in index:
            targets = [rel['target_id'] for rel in index['ASSET_1']]
            assert 'ASSET_3' not in targets or len([t for t in targets if t == 'ASSET_3']) == 0

    def test_build_relationship_index_invalid_graph_type(self):
        """Test with invalid graph type raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            _build_relationship_index("not_a_graph", ['ASSET_1'])
        
        assert "must be an AssetRelationshipGraph instance" in str(exc_info.value)

    def test_build_relationship_index_graph_without_relationships(self):
        """Test graph without relationships attribute raises TypeError."""
        graph = Mock(spec=AssetRelationshipGraph)
        del graph.relationships  # Remove relationships attribute
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        
        with pytest.raises(TypeError):
            _build_relationship_index(graph, ['ASSET_1'])

    def test_build_relationship_index_non_dict_relationships(self):
        """Test graph with non-dict relationships raises TypeError."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.relationships = []  # Should be dict, not list
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        
        with pytest.raises(TypeError):
            _build_relationship_index(graph, ['ASSET_1'])

    def test_build_relationship_index_non_iterable_asset_ids(self, mock_graph):
        """Test with non-iterable asset_ids raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            _build_relationship_index(mock_graph, 123)
        
        assert "asset_ids must be an iterable" in str(exc_info.value)

    def test_build_relationship_index_non_string_asset_ids(self, mock_graph):
        """Test with non-string asset IDs raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _build_relationship_index(mock_graph, [123, 456])
        
        assert "must contain only strings" in str(exc_info.value)

    def test_build_relationship_index_empty_asset_ids(self, mock_graph):
        """Test with empty asset_ids list."""
        index = _build_relationship_index(mock_graph, [])
        assert isinstance(index, dict)
        assert len(index) == 0

    def test_build_relationship_index_single_asset(self, mock_graph):
        """Test with single asset in list."""
        index = _build_relationship_index(mock_graph, ['ASSET_1'])
        assert isinstance(index, dict)


class TestValidatePositionsArray:
    """Test numpy array validation for positions."""

    def test_validate_positions_valid_array(self):
        """Test validation passes for valid positions array."""
        positions = np.array([[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]])
        # Should not raise
        _validate_positions_array(positions)

    def test_validate_positions_not_numpy_array(self):
        """Test validation fails for non-numpy array."""
        with pytest.raises(ValueError) as exc_info:
            _validate_positions_array([[0, 1, 2]])
        
        assert "must be a numpy array" in str(exc_info.value)

    def test_validate_positions_wrong_dimensions(self):
        """Test validation fails for wrong number of dimensions."""
        positions = np.array([0.0, 1.0, 2.0])  # 1D array
        with pytest.raises(ValueError) as exc_info:
            _validate_positions_array(positions)
        
        assert "Expected positions to be a (n, 3) numpy array" in str(exc_info.value)

    def test_validate_positions_wrong_shape(self):
        """Test validation fails for wrong shape."""
        positions = np.array([[0.0, 1.0], [2.0, 3.0]])  # (n, 2) instead of (n, 3)
        with pytest.raises(ValueError) as exc_info:
            _validate_positions_array(positions)
        
        assert "Expected positions to be a (n, 3) numpy array" in str(exc_info.value)

    def test_validate_positions_non_numeric_dtype(self):
        """Test validation fails for non-numeric dtype."""
        positions = np.array([['a', 'b', 'c']], dtype=object)
        with pytest.raises(ValueError) as exc_info:
            _validate_positions_array(positions)
        
        assert "must contain numeric values" in str(exc_info.value)

    def test_validate_positions_with_nan(self):
        """Test validation fails with NaN values."""
        positions = np.array([[0.0, np.nan, 2.0], [3.0, 4.0, 5.0]])
        with pytest.raises(ValueError) as exc_info:
            _validate_positions_array(positions)
        
        assert "contains non-finite values" in str(exc_info.value)

    def test_validate_positions_with_inf(self):
        """Test validation fails with infinite values."""
        positions = np.array([[0.0, np.inf, 2.0], [3.0, 4.0, 5.0]])
        with pytest.raises(ValueError) as exc_info:
            _validate_positions_array(positions)
        
        assert "contains non-finite values" in str(exc_info.value)

    def test_validate_positions_with_negative_inf(self):
        """Test validation fails with negative infinite values."""
        positions = np.array([[0.0, -np.inf, 2.0]])
        with pytest.raises(ValueError) as exc_info:
            _validate_positions_array(positions)
        
        assert "contains non-finite values" in str(exc_info.value)

    def test_validate_positions_empty_array(self):
        """Test validation with empty but correctly shaped array."""
        positions = np.empty((0, 3))
        # Should not raise
        _validate_positions_array(positions)

    def test_validate_positions_large_array(self):
        """Test validation with large array."""
        positions = np.random.randn(10000, 3)
        # Should not raise
        _validate_positions_array(positions)


class TestValidateAssetIdsList:
    """Test asset IDs list validation."""

    def test_validate_asset_ids_valid_list(self):
        """Test validation passes for valid asset IDs."""
        asset_ids = ['ASSET_1', 'ASSET_2', 'ASSET_3']
        # Should not raise
        _validate_asset_ids_list(asset_ids)

    def test_validate_asset_ids_valid_tuple(self):
        """Test validation passes for tuple of asset IDs."""
        asset_ids = ('ASSET_1', 'ASSET_2')
        # Should not raise
        _validate_asset_ids_list(asset_ids)

    def test_validate_asset_ids_not_list_or_tuple(self):
        """Test validation fails for non-list/tuple."""
        with pytest.raises(ValueError) as exc_info:
            _validate_asset_ids_list("not_a_list")
        
        assert "must be a list or tuple" in str(exc_info.value)

    def test_validate_asset_ids_contains_non_string(self):
        """Test validation fails with non-string elements."""
        with pytest.raises(ValueError) as exc_info:
            _validate_asset_ids_list(['ASSET_1', 123, 'ASSET_3'])
        
        assert "must contain non-empty strings" in str(exc_info.value)

    def test_validate_asset_ids_contains_empty_string(self):
        """Test validation fails with empty string."""
        with pytest.raises(ValueError) as exc_info:
            _validate_asset_ids_list(['ASSET_1', '', 'ASSET_3'])
        
        assert "must contain non-empty strings" in str(exc_info.value)

    def test_validate_asset_ids_empty_list(self):
        """Test validation passes for empty list."""
        # Should not raise
        _validate_asset_ids_list([])

    def test_validate_asset_ids_single_element(self):
        """Test validation passes for single element."""
        # Should not raise
        _validate_asset_ids_list(['ASSET_1'])


class TestValidateColorsList:
    """Test colors list validation."""

    def test_validate_colors_valid_list(self):
        """Test validation passes for valid colors."""
        colors = ['#ff0000', '#00ff00', '#0000ff']
        # Should not raise
        _validate_colors_list(colors, 3)

    def test_validate_colors_wrong_length(self):
        """Test validation fails with wrong length."""
        colors = ['#ff0000', '#00ff00']
        with pytest.raises(ValueError) as exc_info:
            _validate_colors_list(colors, 3)
        
        assert "must be a list/tuple of length 3" in str(exc_info.value)

    def test_validate_colors_not_list(self):
        """Test validation fails for non-list."""
        with pytest.raises(ValueError) as exc_info:
            _validate_colors_list("not_a_list", 3)
        
        assert "must be a list/tuple" in str(exc_info.value)

    def test_validate_colors_contains_non_string(self):
        """Test validation fails with non-string elements."""
        colors = ['#ff0000', 123, '#0000ff']
        with pytest.raises(ValueError) as exc_info:
            _validate_colors_list(colors, 3)
        
        assert "must contain strings" in str(exc_info.value)

    def test_validate_colors_contains_empty_string(self):
        """Test validation fails with empty string."""
        colors = ['#ff0000', '', '#0000ff']
        with pytest.raises(ValueError) as exc_info:
            _validate_colors_list(colors, 3)
        
        assert "must contain non-empty strings" in str(exc_info.value)

    def test_validate_colors_invalid_format(self):
        """Test validation fails with invalid color format."""
        colors = ['#ff0000', 'invalid_color', '#0000ff']
        with pytest.raises(ValueError) as exc_info:
            _validate_colors_list(colors, 3)
        
        assert "Invalid color format" in str(exc_info.value)


class TestValidateHoverTextsList:
    """Test hover texts list validation."""

    def test_validate_hover_texts_valid_list(self):
        """Test validation passes for valid hover texts."""
        hover_texts = ['Asset 1', 'Asset 2', 'Asset 3']
        # Should not raise
        _validate_hover_texts_list(hover_texts, 3)

    def test_validate_hover_texts_wrong_length(self):
        """Test validation fails with wrong length."""
        hover_texts = ['Asset 1', 'Asset 2']
        with pytest.raises(ValueError) as exc_info:
            _validate_hover_texts_list(hover_texts, 3)
        
        assert "must be a list/tuple of length 3" in str(exc_info.value)

    def test_validate_hover_texts_not_list(self):
        """Test validation fails for non-list."""
        with pytest.raises(ValueError) as exc_info:
            _validate_hover_texts_list("not_a_list", 3)
        
        assert "must be a list/tuple of length 3" in str(exc_info.value)

    def test_validate_hover_texts_contains_non_string(self):
        """Test validation fails with non-string elements."""
        hover_texts = ['Asset 1', 123, 'Asset 3']
        with pytest.raises(ValueError) as exc_info:
            _validate_hover_texts_list(hover_texts, 3)
        
        assert "must contain non-empty strings" in str(exc_info.value)

    def test_validate_hover_texts_contains_empty_string(self):
        """Test validation fails with empty string."""
        hover_texts = ['Asset 1', '', 'Asset 3']
        with pytest.raises(ValueError) as exc_info:
            _validate_hover_texts_list(hover_texts, 3)
        
        assert "must contain non-empty strings" in str(exc_info.value)


class TestValidateFilterParameters:
    """Test filter parameter validation."""

    def test_validate_filter_parameters_valid_dict(self):
        """Test validation passes for valid filter parameters."""
        filters = {'show_correlation': True, 'show_dependency': False}
        # Should not raise
        _validate_filter_parameters(filters)

    def test_validate_filter_parameters_not_dict(self):
        """Test validation fails for non-dict."""
        with pytest.raises(TypeError) as exc_info:
            _validate_filter_parameters(['not', 'a', 'dict'])
        
        assert "must be a dictionary" in str(exc_info.value)

    def test_validate_filter_parameters_non_boolean_values(self):
        """Test validation fails with non-boolean values."""
        filters = {'show_correlation': True, 'show_dependency': 'not_bool'}
        with pytest.raises(TypeError) as exc_info:
            _validate_filter_parameters(filters)
        
        assert "must have boolean values" in str(exc_info.value)

    def test_validate_filter_parameters_empty_dict(self):
        """Test validation passes for empty dict."""
        # Should not raise
        _validate_filter_parameters({})

    def test_validate_filter_parameters_numeric_value(self):
        """Test validation fails with numeric value."""
        filters = {'show_correlation': 1}
        with pytest.raises(TypeError):
            _validate_filter_parameters(filters)


class TestValidateRelationshipFilters:
    """Test relationship filter validation."""

    def test_validate_relationship_filters_valid_dict(self):
        """Test validation passes for valid filters."""
        filters = {'correlation': True, 'dependency': False}
        # Should not raise
        _validate_relationship_filters(filters)

    def test_validate_relationship_filters_none(self):
        """Test validation passes for None."""
        # Should not raise
        _validate_relationship_filters(None)

    def test_validate_relationship_filters_not_dict(self):
        """Test validation fails for non-dict."""
        with pytest.raises(ValueError) as exc_info:
            _validate_relationship_filters(['not', 'dict'])
        
        assert "must be a dictionary or None" in str(exc_info.value)

    def test_validate_relationship_filters_non_boolean_values(self):
        """Test validation fails with non-boolean values."""
        filters = {'correlation': True, 'dependency': 'yes'}
        with pytest.raises(ValueError) as exc_info:
            _validate_relationship_filters(filters)
        
        assert "must contain only boolean values" in str(exc_info.value)

    def test_validate_relationship_filters_non_string_keys(self):
        """Test validation fails with non-string keys."""
        filters = {123: True, 'correlation': False}
        with pytest.raises(ValueError) as exc_info:
            _validate_relationship_filters(filters)
        
        assert "keys must be strings" in str(exc_info.value)

    def test_validate_relationship_filters_empty_dict(self):
        """Test validation passes for empty dict."""
        # Should not raise
        _validate_relationship_filters({})


class TestGenerateDynamicTitle:
    """Test dynamic title generation."""

    def test_generate_dynamic_title_basic(self):
        """Test basic title generation."""
        title = _generate_dynamic_title(10, 25)
        assert isinstance(title, str)
        assert '10' in title
        assert '25' in title

    def test_generate_dynamic_title_with_custom_base(self):
        """Test title generation with custom base title."""
        title = _generate_dynamic_title(5, 15, base_title="Custom Network")
        assert "Custom Network" in title
        assert '5' in title
        assert '15' in title

    def test_generate_dynamic_title_zero_assets(self):
        """Test title with zero assets."""
        title = _generate_dynamic_title(0, 0)
        assert isinstance(title, str)
        assert '0' in title

    def test_generate_dynamic_title_large_numbers(self):
        """Test title with large numbers."""
        title = _generate_dynamic_title(10000, 50000)
        assert '10000' in title or '10,000' in title
        assert '50000' in title or '50,000' in title

    def test_generate_dynamic_title_singular_vs_plural(self):
        """Test title handles singular vs plural correctly."""
        title_singular = _generate_dynamic_title(1, 1)
        title_plural = _generate_dynamic_title(2, 2)
        assert isinstance(title_singular, str)
        assert isinstance(title_plural, str)


class TestValidateVisualizationData:
    """Test complete visualization data validation."""

    def test_validate_visualization_data_valid(self):
        """Test validation passes for valid data."""
        positions = np.array([[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]])
        asset_ids = ['ASSET_1', 'ASSET_2']
        colors = ['#ff0000', '#00ff00']
        hover_texts = ['Asset 1', 'Asset 2']
        
        # Should not raise
        _validate_visualization_data(positions, asset_ids, colors, hover_texts)

    def test_validate_visualization_data_length_mismatch(self):
        """Test validation fails with length mismatch."""
        positions = np.array([[0.0, 1.0, 2.0]])
        asset_ids = ['ASSET_1', 'ASSET_2']  # Mismatch
        colors = ['#ff0000']
        hover_texts = ['Asset 1']
        
        with pytest.raises(ValueError) as exc_info:
            _validate_visualization_data(positions, asset_ids, colors, hover_texts)
        
        assert "must all be equal" in str(exc_info.value)


class TestVisualize3dGraphEdgeCases:
    """Test edge cases in 3D graph visualization."""

    @pytest.fixture
    def minimal_graph(self):
        """Create a minimal valid graph for testing."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.get_3d_visualization_data_enhanced = Mock(return_value=(
            np.array([[0.0, 1.0, 2.0]]),
            ['ASSET_1'],
            ['#ff0000'],
            ['Asset 1']
        ))
        graph.relationships = {}
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        return graph

    def test_visualize_3d_graph_invalid_graph_type(self):
        """Test visualization with invalid graph type."""
        with pytest.raises(ValueError) as exc_info:
            visualize_3d_graph("not_a_graph")
        
        assert "Invalid graph data provided" in str(exc_info.value)

    def test_visualize_3d_graph_graph_without_method(self):
        """Test visualization with graph missing required method."""
        graph = Mock(spec=AssetRelationshipGraph)
        # Don't add the required method
        
        with pytest.raises(ValueError):
            visualize_3d_graph(graph)

    def test_visualize_3d_graph_minimal_valid_graph(self, minimal_graph):
        """Test visualization with minimal valid graph."""
        fig = visualize_3d_graph(minimal_graph)
        assert isinstance(fig, go.Figure)

    def test_visualize_3d_graph_returns_figure(self, minimal_graph):
        """Test that visualization returns Plotly Figure."""
        fig = visualize_3d_graph(minimal_graph)
        assert isinstance(fig, go.Figure)
        assert hasattr(fig, 'data')
        assert hasattr(fig, 'layout')


class TestVisualize3dGraphWithFilters:
    """Test 3D graph visualization with filters."""

    @pytest.fixture
    def filterable_graph(self):
        """Create a graph suitable for filter testing."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.get_3d_visualization_data_enhanced = Mock(return_value=(
            np.array([[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]]),
            ['ASSET_1', 'ASSET_2'],
            ['#ff0000', '#00ff00'],
            ['Asset 1', 'Asset 2']
        ))
        graph.relationships = {
            'ASSET_1': [{'target_id': 'ASSET_2', 'relationship_type': 'correlation', 'strength': 0.8}]
        }
        graph._lock = Mock()
        graph._lock.__enter__ = Mock()
        graph._lock.__exit__ = Mock()
        return graph

    def test_visualize_with_filters_none_filters(self, filterable_graph):
        """Test visualization with no filters (None)."""
        fig = visualize_3d_graph_with_filters(filterable_graph, show_all_relationships=True)
        assert isinstance(fig, go.Figure)

    def test_visualize_with_filters_empty_dict(self, filterable_graph):
        """Test visualization with empty filter dict."""
        fig = visualize_3d_graph_with_filters(filterable_graph, relationship_filters={})
        assert isinstance(fig, go.Figure)

    def test_visualize_with_filters_specific_types(self, filterable_graph):
        """Test visualization with specific relationship type filters."""
        filters = {'correlation': True, 'dependency': False}
        fig = visualize_3d_graph_with_filters(filterable_graph, relationship_filters=filters)
        assert isinstance(fig, go.Figure)

    def test_visualize_with_filters_invalid_graph_type(self):
        """Test filtered visualization with invalid graph type."""
        with pytest.raises(ValueError) as exc_info:
            visualize_3d_graph_with_filters("not_a_graph")
        
        assert "Invalid graph data provided" in str(exc_info.value)

    def test_visualize_with_filters_invalid_filter_type(self, filterable_graph):
        """Test with invalid filter parameter type."""
        with pytest.raises(ValueError):
            visualize_3d_graph_with_filters(filterable_graph, relationship_filters="invalid")


class TestStringFormattingConsistency:
    """Test string formatting consistency after code style changes."""

    def test_error_messages_use_consistent_quotes(self):
        """Test that error messages maintain quote consistency."""
        # Test a validation function's error message
        try:
            _validate_positions_array([[0, 1, 2]])
        except ValueError as e:
            error_msg = str(e)
            # Error message should be well-formed
            assert len(error_msg) > 0
            assert "must be a numpy array" in error_msg

    def test_multi_line_string_formatting(self):
        """Test multi-line string formatting in error messages."""
        try:
            positions = np.array([[0.0, 1.0]])  # Wrong shape
            _validate_positions_array(positions)
        except ValueError as e:
            error_msg = str(e)
            # Multi-line error messages should be properly formatted
            assert "Expected positions to be a (n, 3) numpy array" in error_msg

    def test_f_string_formatting_in_errors(self):
        """Test f-string formatting in error messages."""
        try:
            _validate_asset_ids_list("not_a_list")
        except ValueError as e:
            error_msg = str(e)
            # Should contain type information
            assert "list or tuple" in error_msg


class TestConcurrencyAndThreadSafety:
    """Test thread-safety aspects of visualization functions."""

    @pytest.fixture
    def thread_safe_graph(self):
        """Create a graph with proper locking for thread tests."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.relationships = {
            'ASSET_1': [{'target_id': 'ASSET_2', 'relationship_type': 'correlation', 'strength': 0.8}]
        }
        graph._lock = Mock()
        graph._lock.__enter__ = Mock(return_value=None)
        graph._lock.__exit__ = Mock(return_value=None)
        return graph

    def test_build_relationship_index_acquires_lock(self, thread_safe_graph):
        """Test that relationship index building acquires lock."""
        asset_ids = ['ASSET_1', 'ASSET_2']
        _build_relationship_index(thread_safe_graph, asset_ids)
        
        # Verify lock was acquired
        thread_safe_graph._lock.__enter__.assert_called()
        thread_safe_graph._lock.__exit__.assert_called()


class TestBoundaryConditions:
    """Test boundary conditions and extreme values."""

    def test_validate_positions_maximum_size(self):
        """Test validation with very large position array."""
        # Create large array
        positions = np.random.randn(100000, 3)
        # Should not raise
        _validate_positions_array(positions)

    def test_validate_positions_single_point(self):
        """Test validation with single point."""
        positions = np.array([[0.0, 0.0, 0.0]])
        # Should not raise
        _validate_positions_array(positions)

    def test_generate_title_maximum_numbers(self):
        """Test title generation with maximum integer values."""
        import sys
        max_int = sys.maxsize
        title = _generate_dynamic_title(max_int, max_int)
        assert isinstance(title, str)

    def test_validate_colors_many_colors(self):
        """Test color validation with many colors."""
        colors = ['#ff0000'] * 10000
        # Should not raise
        _validate_colors_list(colors, 10000)

    def test_validate_asset_ids_very_long_names(self):
        """Test asset ID validation with very long names."""
        long_name = 'A' * 10000
        asset_ids = [long_name]
        # Should not raise
        _validate_asset_ids_list(asset_ids)