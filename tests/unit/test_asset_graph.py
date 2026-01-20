"""Unit tests for AssetRelationshipGraph class.

This module contains comprehensive unit tests for the asset_graph module including:
- Graph initialization
- 3D visualization data generation
- Relationship handling
- Edge cases and error handling
"""

import numpy as np
from src.logic.asset_graph import AssetRelationshipGraph

import pytest


@pytest.mark.unit
class TestAssetRelationshipGraphInit:
    """Test suite for AssetRelationshipGraph initialization."""

    def test_init_creates_empty_relationships(self):
        """Test that initialization creates an empty relationships dictionary."""
        graph = AssetRelationshipGraph()

        assert isinstance(graph.relationships, dict)
        assert len(graph.relationships) == 0

    def test_init_relationships_type(self):
        """Test that relationships dictionary has correct type annotation."""
        graph = AssetRelationshipGraph()

        assert hasattr(graph, 'relationships')
        assert isinstance(graph.relationships, dict)


@pytest.mark.unit
class TestGet3DVisualizationDataEnhanced:
    """Test suite for get_3d_visualization_data_enhanced method."""

    def test_empty_graph_returns_placeholder(self):
        """Test that empty graph returns a single placeholder node."""
        graph = AssetRelationshipGraph()

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert positions.shape == (1, 3)
        assert np.allclose(positions, np.zeros((1, 3)))
        assert asset_ids == ["A"]
        assert colors == ["#888888"]
        assert hover_texts == ["Asset A"]

    def test_single_relationship_returns_two_nodes(self):
        """Test graph with single relationship returns two nodes."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert positions.shape == (2, 3)
        assert len(asset_ids) == 2
        assert set(asset_ids) == {"asset1", "asset2"}
        assert len(colors) == 2
        assert len(hover_texts) == 2

    def test_multiple_relationships_circular_layout(self):
        """Test that multiple assets are laid out in a circle."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]
        graph.relationships["asset2"] = [("asset3", "correlation", 0.7)]
        graph.relationships["asset3"] = [("asset1", "correlation", 0.6)]

        positions, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert positions.shape == (3, 3)
        assert len(asset_ids) == 3
        assert set(asset_ids) == {"asset1", "asset2", "asset3"}

        # Check that z-coordinates are all zero (2D circle in 3D space)
        assert np.allclose(positions[:, 2], 0)

        # Check that points are on a unit circle (x^2 + y^2 = 1)
        radii = np.sqrt(positions[:, 0]**2 + positions[:, 1]**2)
        assert np.allclose(radii, 1.0)

    def test_positions_are_numpy_array(self):
        """Test that positions are returned as numpy array."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]

        positions, _, _, _ = graph.get_3d_visualization_data_enhanced()

        assert isinstance(positions, np.ndarray)
        assert positions.ndim == 2
        assert positions.shape[1] == 3

    def test_colors_are_consistent(self):
        """Test that all nodes get the same color."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]
        graph.relationships["asset2"] = [("asset3", "correlation", 0.7)]

        _, _, colors, _ = graph.get_3d_visualization_data_enhanced()

        assert all(color == "#4ECDC4" for color in colors)

    def test_hover_texts_format(self):
        """Test that hover texts are properly formatted."""
        graph = AssetRelationshipGraph()
        graph.relationships["AAPL"] = [("GOOGL", "correlation", 0.8)]

        _, asset_ids, _, hover_texts = graph.get_3d_visualization_data_enhanced()

        for asset_id, hover_text in zip(asset_ids, hover_texts):
            assert hover_text == f"Asset: {asset_id}"

    def test_asset_ids_are_sorted(self):
        """Test that asset IDs are returned in sorted order."""
        graph = AssetRelationshipGraph()
        graph.relationships["zebra"] = [("apple", "correlation", 0.8)]
        graph.relationships["banana"] = [("cherry", "correlation", 0.7)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert asset_ids == sorted(asset_ids)

    def test_bidirectional_relationships_single_nodes(self):
        """Test that bidirectional relationships don't duplicate nodes."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]
        graph.relationships["asset2"] = [("asset1", "correlation", 0.8)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 2
        assert set(asset_ids) == {"asset1", "asset2"}

    def test_complex_graph_with_multiple_targets(self):
        """Test graph where one source has multiple targets."""
        graph = AssetRelationshipGraph()
        graph.relationships["hub"] = [
            ("spoke1", "correlation", 0.8),
            ("spoke2", "correlation", 0.7),
            ("spoke3", "correlation", 0.6)
        ]

        positions, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 4
        assert "hub" in asset_ids
        assert "spoke1" in asset_ids
        assert "spoke2" in asset_ids
        assert "spoke3" in asset_ids
        assert positions.shape == (4, 3)

    def test_isolated_target_nodes(self):
        """Test that target nodes without outgoing relationships are included."""
        graph = AssetRelationshipGraph()
        graph.relationships["source"] = [("target1", "correlation", 0.8)]
        # target1 has no outgoing relationships

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert "source" in asset_ids
        assert "target1" in asset_ids

    def test_return_types(self):
        """Test that all return values have correct types."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert isinstance(positions, np.ndarray)
        assert isinstance(asset_ids, list)
        assert isinstance(colors, list)
        assert isinstance(hover_texts, list)
        assert all(isinstance(aid, str) for aid in asset_ids)
        assert all(isinstance(c, str) for c in colors)
        assert all(isinstance(h, str) for h in hover_texts)

    def test_consistent_list_lengths(self):
        """Test that all returned lists have the same length."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]
        graph.relationships["asset2"] = [("asset3", "correlation", 0.7)]

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        n = len(asset_ids)
        assert positions.shape[0] == n
        assert len(colors) == n
        assert len(hover_texts) == n


# ============================================================================
# Additional Tests for src/logic/asset_graph.py Simplification
# ============================================================================

class TestAssetGraphSimplification:
    """Test suite for simplified AssetRelationshipGraph interface."""
    
    def test_asset_graph_minimal_initialization(self):
        """Test that AssetRelationshipGraph can be initialized with no parameters."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        
        assert graph is not None
        assert hasattr(graph, 'relationships')
        assert isinstance(graph.relationships, dict)
    
    def test_asset_graph_no_database_url_parameter(self):
        """Test that AssetRelationshipGraph no longer takes database_url parameter."""
        from src.logic.asset_graph import AssetRelationshipGraph
        import inspect
        
        # Get __init__ signature
        sig = inspect.signature(AssetRelationshipGraph.__init__)
        params = list(sig.parameters.keys())
        
        # Should only have 'self' parameter
        assert params == ['self']
    
    def test_asset_graph_has_relationships_dict(self):
        """Test that graph has relationships dictionary."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        
        assert hasattr(graph, 'relationships')
        assert isinstance(graph.relationships, dict)
        assert len(graph.relationships) == 0  # Initially empty


class TestGet3DVisualizationDataEnhanced:
    """Test suite for get_3d_visualization_data_enhanced method."""
    
    def test_get_3d_visualization_data_enhanced_exists(self):
        """Test that get_3d_visualization_data_enhanced method exists."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        
        assert hasattr(graph, 'get_3d_visualization_data_enhanced')
        assert callable(graph.get_3d_visualization_data_enhanced)
    
    def test_get_3d_visualization_data_enhanced_return_type(self):
        """Test return type of get_3d_visualization_data_enhanced."""
        from src.logic.asset_graph import AssetRelationshipGraph
        import numpy as np
        
        graph = AssetRelationshipGraph()
        result = graph.get_3d_visualization_data_enhanced()
        
        # Should return tuple of (positions, asset_ids, colors, hover_texts)
        assert isinstance(result, tuple)
        assert len(result) == 4
        
        positions, asset_ids, colors, hover_texts = result
        
        assert isinstance(positions, np.ndarray)
        assert isinstance(asset_ids, list)
        assert isinstance(colors, list)
        assert isinstance(hover_texts, list)
    
    def test_get_3d_visualization_data_enhanced_with_empty_graph(self):
        """Test visualization data for empty graph."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
        
        # Should return single placeholder node for empty graph
        assert len(positions) > 0
        assert len(asset_ids) > 0
        assert len(colors) > 0
        assert len(hover_texts) > 0
    
    def test_get_3d_visualization_data_enhanced_with_relationships(self):
        """Test visualization data when relationships exist."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        
        # Add some relationships
        graph.relationships = {
            'asset1': [('asset2', 'correlation', 0.8)],
            'asset2': [('asset3', 'sector', 0.7)]
        }
        
        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
        
        # Should lay out nodes on a circle
        assert len(positions) >= 2  # At least the assets in relationships
        assert len(asset_ids) == len(positions)
        assert len(colors) == len(positions)
        assert len(hover_texts) == len(positions)
    
    def test_get_3d_visualization_data_positions_are_3d(self):
        """Test that positions are 3D coordinates."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        positions, _, _, _ = graph.get_3d_visualization_data_enhanced()
        
        # Positions should be 2D array with shape (n_nodes, 3)
        assert positions.ndim == 2
        assert positions.shape[1] == 3  # x, y, z coordinates


class TestAssetGraphMinimalInterface:
    """Test that the simplified graph maintains minimal required interface."""
    
    def test_graph_has_relationships_attribute(self):
        """Test that graph has relationships attribute."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        
        assert hasattr(graph, 'relationships')
    
    def test_graph_relationships_is_dict(self):
        """Test that relationships is a dictionary."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        
        assert isinstance(graph.relationships, dict)
    
    def test_graph_relationships_format(self):
        """Test that relationships follow expected format."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        
        # Add test relationship
        graph.relationships['source'] = [('target', 'rel_type', 0.5)]
        
        # Verify format: Dict[source_id, List[(target_id, rel_type, strength)]]
        assert 'source' in graph.relationships
        assert isinstance(graph.relationships['source'], list)
        assert len(graph.relationships['source']) == 1
        
        target_id, rel_type, strength = graph.relationships['source'][0]
        assert isinstance(target_id, str)
        assert isinstance(rel_type, str)
        assert isinstance(strength, (int, float))


class TestAssetGraphDocumentation:
    """Test that docstrings are updated correctly."""
    
    def test_class_docstring_describes_minimal_interface(self):
        """Test that class docstring describes the minimal interface."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        docstring = AssetRelationshipGraph.__doc__
        assert docstring is not None
        assert "Minimal interface" in docstring or "interface" in docstring.lower()
    
    def test_get_3d_visualization_data_enhanced_has_docstring(self):
        """Test that get_3d_visualization_data_enhanced has proper docstring."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        docstring = AssetRelationshipGraph.get_3d_visualization_data_enhanced.__doc__
        assert docstring is not None
        assert "Return positions" in docstring or "visualization" in docstring.lower()
    
    def test_docstring_mentions_compatibility(self):
        """Test that docstring mentions compatibility with visualization code."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        docstring = AssetRelationshipGraph.get_3d_visualization_data_enhanced.__doc__
        assert docstring is not None
        # Should mention compatibility with graph_visuals.py or visualization
        assert "compatible" in docstring.lower() or "visualization" in docstring.lower()


class TestAssetGraphCircularLayout:
    """Test circular layout algorithm in get_3d_visualization_data_enhanced."""
    
    def test_circular_layout_with_multiple_nodes(self):
        """Test that nodes are laid out in a circle."""
        from src.logic.asset_graph import AssetRelationshipGraph
        import numpy as np
        
        graph = AssetRelationshipGraph()
        
        # Add multiple relationships to ensure multiple nodes
        graph.relationships = {
            'a': [('b', 'type1', 0.5)],
            'b': [('c', 'type2', 0.6)],
            'c': [('d', 'type3', 0.7)],
            'd': [('a', 'type4', 0.8)]
        }
        
        positions, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()
        
        # With 4 nodes, they should be evenly distributed on a circle
        assert len(positions) == 4
        
        # Check that distances from origin are approximately equal (circular layout)
        distances = np.sqrt(np.sum(positions[:, :2]**2, axis=1))  # Distance in x-y plane
        
        # All distances should be similar (allowing for floating point differences)
        assert np.std(distances) < 0.1  # Low standard deviation indicates circular layout
    
    def test_placeholder_node_for_empty_relationships(self):
        """Test that single placeholder node is created for empty graph."""
        from src.logic.asset_graph import AssetRelationshipGraph
        
        graph = AssetRelationshipGraph()
        # No relationships added
        
        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
        
        # Should have at least one node (placeholder)
        assert len(positions) >= 1
        assert len(asset_ids) >= 1


