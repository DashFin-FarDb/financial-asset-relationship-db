"""Comprehensive unit tests for simplified AssetRelationshipGraph.

This module tests the simplified implementation of AssetRelationshipGraph
focusing on the minimal interface required for visualization.
"""

import numpy as np
import pytest

from src.logic.asset_graph import AssetRelationshipGraph


class TestAssetRelationshipGraphInit:
    """Test cases for AssetRelationshipGraph initialization."""

    def test_init_creates_empty_relationships(self):
        """Test that initialization creates empty relationships dict."""
        graph = AssetRelationshipGraph()
        assert graph.relationships == {}

    def test_init_relationships_is_dict(self):
        """Test that relationships attribute is a dictionary."""
        graph = AssetRelationshipGraph()
        assert isinstance(graph.relationships, dict)


class TestGet3DVisualizationDataEnhanced:
    """Test cases for get_3d_visualization_data_enhanced method."""

    def test_get_3d_visualization_with_empty_graph(self):
        """Test visualization data generation with empty graph."""
        graph = AssetRelationshipGraph()
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        assert isinstance(positions, np.ndarray)
        # Empty graph returns placeholder values per implementation
        assert len(asset_ids) == 1
        assert asset_ids == ["A"]
        assert len(colors) == 1
        assert isinstance(colors[0], str) and colors[0].startswith("#") and len(colors[0]) in (4, 7)
        assert len(hover) == 1
        assert asset_ids[0] in hover[0]
    def test_get_3d_visualization_with_single_relationship(self):
        """Test visualization data with single relationship."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            "ASSET_A": [("ASSET_B", "related_to", 0.8)]
        }
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        assert len(asset_ids) == 2
        assert "ASSET_A" in asset_ids
        assert "ASSET_B" in asset_ids
        assert positions.shape == (2, 3)
        assert len(colors) == 2
        assert len(hover) == 2

    def test_get_3d_visualization_positions_are_on_circle(self):
        """Test that positions are arranged on a circle."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            "ASSET_A": [("ASSET_B", "related_to", 0.8)],
            "ASSET_B": [("ASSET_C", "related_to", 0.5)]
        }
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        # Check that z-coordinates are all zero (2D circle in x-y plane)
        assert np.allclose(positions[:, 2], 0.0)
        
        # Check that points are roughly on a unit circle
        distances = np.sqrt(positions[:, 0]**2 + positions[:, 1]**2)
        assert np.allclose(distances, 1.0)

    def test_get_3d_visualization_with_bidirectional_relationships(self):
        """Test visualization with bidirectional relationships."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            "ASSET_A": [("ASSET_B", "related_to", 0.8)],
            "ASSET_B": [("ASSET_A", "related_to", 0.8)]
        }
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        # Should only have 2 unique assets despite bidirectional relationship
        assert len(asset_ids) == 2

    def test_get_3d_visualization_colors_are_consistent(self):
        """Test that all colors are the same default color."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            "ASSET_A": [("ASSET_B", "related_to", 0.8)],
            "ASSET_B": [("ASSET_C", "related_to", 0.5)]
        }
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        # All colors should be the default color
        assert all(color == "#4ECDC4" for color in colors)

    def test_get_3d_visualization_hover_text_format(self):
        """Test that hover text follows expected format."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            "ASSET_A": [("ASSET_B", "related_to", 0.8)]
        }
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        for i, asset_id in enumerate(asset_ids):
            assert hover[i] == f"Asset: {asset_id}"

    def test_get_3d_visualization_with_complex_graph(self):
        """Test visualization with complex relationship graph."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            "ASSET_A": [("ASSET_B", "type1", 0.8), ("ASSET_C", "type2", 0.6)],
            "ASSET_B": [("ASSET_D", "type1", 0.7)],
            "ASSET_C": [("ASSET_D", "type3", 0.5), ("ASSET_E", "type1", 0.9)],
            "ASSET_E": [("ASSET_A", "type2", 0.4)]
        }
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        # Should have 5 unique assets
        assert len(asset_ids) == 5
        assert len(set(asset_ids)) == 5
        assert positions.shape[0] == 5

    def test_get_3d_visualization_asset_ids_are_sorted(self):
        """Test that asset IDs are returned in sorted order."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            "ASSET_C": [("ASSET_A", "related_to", 0.8)],
            "ASSET_B": [("ASSET_D", "related_to", 0.5)]
        }
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        assert asset_ids == sorted(asset_ids)

    def test_get_3d_visualization_return_types(self):
        """Test that return values have correct types."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            "ASSET_A": [("ASSET_B", "related_to", 0.8)]
        }
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        assert isinstance(positions, np.ndarray)
        assert isinstance(asset_ids, list)
        assert isinstance(colors, list)
        assert isinstance(hover, list)

    def test_get_3d_visualization_positions_shape(self):
        """Test that positions array has correct shape."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            "ASSET_A": [("ASSET_B", "related_to", 0.8)],
            "ASSET_B": [("ASSET_C", "related_to", 0.5)]
        }
        
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        
        # Positions should be N x 3 (x, y, z coordinates)
        assert positions.ndim == 2
        assert positions.shape[1] == 3
        assert positions.shape[0] == len(asset_ids)