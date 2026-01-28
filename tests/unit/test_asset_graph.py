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


@pytest.mark.unit
class TestGet3DVisualizationDataEnhancedComprehensive:
    """Comprehensive test suite for get_3d_visualization_data_enhanced with various scenarios."""

    def test_single_relationship_creates_two_nodes(self):
        """Test that a single relationship creates two nodes in circular layout."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'ASSET_A': [('ASSET_B', 'correlation', 0.8)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert positions.shape == (2, 3)
        assert len(asset_ids) == 2
        assert len(colors) == 2
        assert len(hover_texts) == 2
        assert 'ASSET_A' in asset_ids
        assert 'ASSET_B' in asset_ids

    def test_multiple_relationships_circular_layout(self):
        """Test that multiple relationships create correct circular layout."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [('B', 'type1', 0.5), ('C', 'type2', 0.7)],
            'B': [('D', 'type3', 0.6)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should have 4 unique nodes: A, B, C, D
        assert positions.shape == (4, 3)
        assert len(asset_ids) == 4
        assert len(set(asset_ids)) == 4  # All unique
        assert set(asset_ids) == {'A', 'B', 'C', 'D'}

    def test_positions_are_on_circle(self):
        """Test that node positions lie on a unit circle in the XY plane."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [('B', 'rel', 0.5)],
            'B': [('C', 'rel', 0.5)],
            'C': [('D', 'rel', 0.5)]
        }

        positions, _, _, _ = graph.get_3d_visualization_data_enhanced()

        # Check that all points are on unit circle (distance from origin in XY plane)
        xy_distances = np.sqrt(positions[:, 0]**2 + positions[:, 1]**2)
        assert np.allclose(xy_distances, 1.0, atol=1e-10)

        # Check that Z coordinates are all zero
        assert np.allclose(positions[:, 2], 0.0)

    def test_positions_evenly_distributed(self):
        """Test that nodes are evenly distributed around the circle."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [('B', 'rel', 0.5)],
            'B': [('C', 'rel', 0.5)],
            'C': [('D', 'rel', 0.5)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        n = len(asset_ids)
        # Calculate angles from positions
        angles = np.arctan2(positions[:, 1], positions[:, 0])
        # Sort angles
        angles_sorted = np.sort(angles)

        # Differences between consecutive angles, including wrap-around
        angle_diffs = np.diff(np.r_[angles_sorted, angles_sorted[0] + 2 * np.pi])

        # All differences should be approximately equal to 2π/n
        expected_diff = 2 * np.pi / n
        assert np.allclose(angle_diffs, expected_diff, atol=1e-6)

    def test_asset_ids_are_sorted(self):
        """Test that asset IDs are returned in sorted order."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'ZEBRA': [('APPLE', 'rel', 0.5)],
            'BANANA': [('CHERRY', 'rel', 0.5)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        expected_order = sorted(['ZEBRA', 'APPLE', 'BANANA', 'CHERRY'])
        assert asset_ids == expected_order

    def test_all_nodes_use_same_color(self):
        """Test that all nodes use the same default color."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [('B', 'rel', 0.5)],
            'B': [('C', 'rel', 0.5)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # All colors should be the same
        assert len(set(colors)) == 1
        assert colors[0] == "#4ECDC4"

    def test_hover_texts_match_asset_ids(self):
        """Test that hover texts correctly reference asset IDs."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'AAPL': [('GOOGL', 'sector', 0.8)],
            'MSFT': [('AAPL', 'correlation', 0.7)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        for aid, hover in zip(asset_ids, hover_texts):
            assert aid in hover
            assert hover.startswith("Asset: ")

    def test_bidirectional_relationships_no_duplicate_nodes(self):
        """Test that bidirectional relationships don't create duplicate nodes."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [('B', 'rel1', 0.5)],
            'B': [('A', 'rel2', 0.6)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should only have 2 unique nodes
        assert len(asset_ids) == 2
        assert set(asset_ids) == {'A', 'B'}

    def test_self_referential_relationship(self):
        """Test handling of self-referential relationships."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [('A', 'self', 1.0)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should only have 1 node
        assert len(asset_ids) == 1
        assert asset_ids[0] == 'A'

    def test_isolated_nodes_in_relationships(self):
        """Test nodes that appear only as sources or targets."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'SOURCE_ONLY': [('TARGET_1', 'rel', 0.5), ('TARGET_2', 'rel', 0.6)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should have all 3 nodes
        assert len(asset_ids) == 3
        assert set(asset_ids) == {'SOURCE_ONLY', 'TARGET_1', 'TARGET_2'}

    def test_large_number_of_nodes(self):
        """Test with a large number of nodes."""
        graph = AssetRelationshipGraph()
        # Create 100 nodes with relationships
        for i in range(100):
            graph.relationships[f'NODE_{i}'] = [(f'NODE_{(i+1) % 100}', 'next', 0.5)]

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert positions.shape == (100, 3)
        assert len(asset_ids) == 100
        assert len(colors) == 100
        assert len(hover_texts) == 100

        # Verify circular layout
        xy_distances = np.sqrt(positions[:, 0]**2 + positions[:, 1]**2)
        assert np.allclose(xy_distances, 1.0, atol=1e-10)

    def test_positions_shape_matches_counts(self):
        """
        Verify that the number of position rows equals the number of assets and that each position has three coordinates; also ensure colors and hover_texts lengths match the asset count.
        """
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [('B', 'r1', 0.5)],
            'C': [('D', 'r2', 0.6)],
            'E': [('F', 'r3', 0.7)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        n_assets = len(asset_ids)
        assert positions.shape[0] == n_assets
        assert positions.shape[1] == 3  # 3D coordinates
        assert len(colors) == n_assets
        assert len(hover_texts) == n_assets

    def test_empty_relationship_lists(self):
        """Test handling of empty relationship lists in the dictionary."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [],  # Empty relationship list
            'B': [('C', 'rel', 0.5)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should still include 'A' as it's a key, plus 'B' and 'C'
        assert 'A' in asset_ids
        assert 'B' in asset_ids
        assert 'C' in asset_ids
        assert len(asset_ids) == 3  # Ensure total count matches expected

    def test_numeric_asset_ids(self):
        """Test with numeric string asset IDs."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            '100': [('200', 'rel', 0.5)],
            '50': [('75', 'rel', 0.6)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Asset IDs are sorted lexicographically (as strings)
        assert asset_ids == sorted(['100', '200', '50', '75'])

    def test_special_characters_in_asset_ids(self):
        """Test with special characters in asset IDs."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'ASSET-1': [('ASSET_2', 'rel', 0.5)],
            'ASSET.3': [('ASSET@4', 'rel', 0.6)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 4
        for aid in ['ASSET-1', 'ASSET_2', 'ASSET.3', 'ASSET@4']:
            assert aid in asset_ids

    def test_relationship_metadata_not_affect_output(self):
        """Test that relationship type and strength don't affect visualization output."""
        graph1 = AssetRelationshipGraph()
        graph1.relationships = {
            'A': [('B', 'type1', 0.1)],
            'B': [('C', 'type2', 0.9)]
        }

        graph2 = AssetRelationshipGraph()
        graph2.relationships = {
            'A': [('B', 'different_type', 0.999)],
            'B': [('C', 'another_type', 0.001)]
        }

        pos1, ids1, colors1, hover1 = graph1.get_3d_visualization_data_enhanced()
        pos2, ids2, colors2, hover2 = graph2.get_3d_visualization_data_enhanced()

        # Positions and IDs should be identical
        assert np.allclose(pos1, pos2)
        assert ids1 == ids2
        assert colors1 == colors2

    def test_positions_dtype_is_float(self):
        """Test that positions array has float dtype."""
        graph = AssetRelationshipGraph()
        graph.relationships = {'A': [('B', 'rel', 0.5)]}

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert positions.dtype == np.float64 or positions.dtype == np.float32

    def test_returns_numpy_array_not_list(self):
        """Test that positions are returned as numpy array, not list."""
        graph = AssetRelationshipGraph()
        graph.relationships = {'A': [('B', 'rel', 0.5)]}

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert isinstance(positions, np.ndarray)
        assert isinstance(asset_ids, list)
        assert isinstance(colors, list)
        assert isinstance(hover_texts, list)


@pytest.mark.unit
class TestAssetRelationshipGraphEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_node_with_self_loop(self):
        """Test graph with single node pointing to itself."""
        graph = AssetRelationshipGraph()
        graph.relationships = {'ONLY': [('ONLY', 'self_ref', 1.0)]}

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 1
        assert asset_ids[0] == 'ONLY'
        # Single point should be at origin or on circle
        assert positions.shape == (1, 3)

    def test_empty_string_asset_id(self):
        """Test handling of empty string as asset ID."""
        graph = AssetRelationshipGraph()
        graph.relationships = {'': [('A', 'rel', 0.5)]}

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert '' in asset_ids
        assert 'A' in asset_ids

    def test_unicode_asset_ids(self):
        """Test with Unicode characters in asset IDs."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            '资产A': [('アセットB', 'rel', 0.5)],
            'Актив_C': [('자산D', 'rel', 0.6)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 4
        assert '资产A' in asset_ids
        assert 'アセットB' in asset_ids

    def test_very_long_asset_id(self):
        """Test with very long asset ID strings."""
        long_id = 'A' * 1000
        graph = AssetRelationshipGraph()
        graph.relationships = {long_id: [('B', 'rel', 0.5)]}

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert long_id in asset_ids
        assert len(asset_ids) == 2  # Ensure both nodes are present
        assert any(long_id in hover for hover in hover_texts)

    def test_relationship_strength_zero(self):
        """Test relationships with zero strength."""
        graph = AssetRelationshipGraph()
        graph.relationships = {'A': [('B', 'weak', 0.0)]}

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should still include both nodes
        assert len(asset_ids) == 2
        assert set(asset_ids) == {'A', 'B'}  # Ensure both nodes are present

    def test_relationship_strength_negative(self):
        """Test relationships with negative strength."""
        graph = AssetRelationshipGraph()
        graph.relationships = {'A': [('B', 'inverse', -0.5)]}

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should still include both nodes
        assert len(asset_ids) == 2

    def test_relationship_strength_greater_than_one(self):
        """Test relationships with strength > 1.0."""
        graph = AssetRelationshipGraph()
        graph.relationships = {'A': [('B', 'strong', 5.0)]}

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should still include both nodes
        assert len(asset_ids) == 2

    def test_duplicate_relationships_same_pair(self):
        """
        Verify that multiple relationship entries between the same asset pair produce only two unique nodes in the visualization output.
        
        Asserts that the list of asset IDs returned by get_3d_visualization_data_enhanced contains exactly the two distinct assets involved ('A' and 'B') and no duplicate entries.
        """
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [
                ('B', 'rel1', 0.5),
                ('B', 'rel2', 0.7),
                ('B', 'rel3', 0.9)
            ]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should only have 2 unique nodes
        assert len(asset_ids) == 2
        assert set(asset_ids) == {'A', 'B'}

    def test_complex_graph_structure(self):
        """Test complex graph with multiple interconnected nodes."""
        graph = AssetRelationshipGraph()
        # Create a fully connected graph with 5 nodes
        nodes = ['A', 'B', 'C', 'D', 'E']
        for source in nodes:
            graph.relationships[source] = [
                (target, f'rel_{source}_{target}', 0.5)
                for target in nodes if target != source
            ]

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 5
        assert set(asset_ids) == set(nodes)
        # All points should be on unit circle
        xy_distances = np.sqrt(positions[:, 0]**2 + positions[:, 1]**2)
        assert np.allclose(xy_distances, 1.0)


@pytest.mark.unit
class TestAssetRelationshipGraphConsistency:
    """Test consistency and determinism of the graph methods."""

    def test_repeated_calls_same_result(self):
        """Test that calling method multiple times returns same result."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [('B', 'rel', 0.5)],
            'C': [('D', 'rel', 0.6)]
        }

        result1 = graph.get_3d_visualization_data_enhanced()
        result2 = graph.get_3d_visualization_data_enhanced()

        pos1, ids1, colors1, hover1 = result1
        pos2, ids2, colors2, hover2 = result2

        assert np.allclose(pos1, pos2)
        assert ids1 == ids2
        assert colors1 == colors2
        assert hover1 == hover2

    def test_modification_affects_subsequent_calls(self):
        """Test that modifying relationships affects subsequent calls."""
        graph = AssetRelationshipGraph()
        graph.relationships = {'A': [('B', 'rel', 0.5)]}

        pos1, ids1, _, _ = graph.get_3d_visualization_data_enhanced()

        # Modify relationships
        graph.relationships['C'] = [('D', 'rel', 0.6)]

        pos2, ids2, _, _ = graph.get_3d_visualization_data_enhanced()

        # Results should be different
        assert not np.array_equal(pos1, pos2)
        assert ids1 != ids2
        assert len(ids2) > len(ids1)

    def test_clearing_relationships(self):
        """Test behavior when relationships are cleared."""
        graph = AssetRelationshipGraph()
        graph.relationships = {'A': [('B', 'rel', 0.5)]}

        # Clear relationships
        graph.relationships = {}

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        # Should return placeholder
        assert asset_ids == ["A"]
        assert len(positions) == 1


@pytest.mark.unit  
class TestAssetRelationshipGraphTypeValidation:
    """Test type validation and error handling."""

    def test_positions_are_3d(self):
        """Test that positions always have 3 dimensions."""
        graph = AssetRelationshipGraph()
        
        # Test with empty graph
        pos_empty, _, _, _ = graph.get_3d_visualization_data_enhanced()
        assert pos_empty.shape[1] == 3

        # Test with nodes
        graph.relationships = {'A': [('B', 'rel', 0.5)]}
        pos_nodes, _, _, _ = graph.get_3d_visualization_data_enhanced()
        assert pos_nodes.shape[1] == 3

    def test_return_tuple_length(self):
        """Test that method always returns 4-tuple."""
        graph = AssetRelationshipGraph()
        
        result = graph.get_3d_visualization_data_enhanced()
        assert isinstance(result, tuple)
        assert len(result) == 4

        graph.relationships = {'A': [('B', 'rel', 0.5)]}
        result = graph.get_3d_visualization_data_enhanced()
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_all_lists_same_length(self):
        """Test that asset_ids, colors, and hover_texts have same length."""
        graph = AssetRelationshipGraph()
        graph.relationships = {
            'A': [('B', 'rel', 0.5)],
            'C': [('D', 'rel', 0.6)],
            'E': [('F', 'rel', 0.7)]
        }

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == len(colors)
        assert len(colors) == len(hover_texts)
        assert positions.shape[0] == len(asset_ids)
