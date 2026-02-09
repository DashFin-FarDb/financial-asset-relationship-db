"""Unit tests for AssetRelationshipGraph class.

This module contains comprehensive unit tests for the asset_graph module including:
- Graph initialization
- 3D visualization data generation
- Relationship handling
- Edge cases and error handling
"""

import numpy as np
import pytest

from src.logic.asset_graph import AssetRelationshipGraph


@pytest.mark.unit
class TestAssetRelationshipGraphInit:
    """Test suite for AssetRelationshipGraph initialization."""

    @staticmethod
    def test_init_creates_empty_relationships():
        """Test that initialization creates an empty relationships dictionary."""
        graph = AssetRelationshipGraph()

        assert isinstance(graph.relationships, dict)
        assert len(graph.relationships) == 0

    @staticmethod
    def test_init_relationships_type():
        """Test that relationships dictionary has correct type annotation."""
        graph = AssetRelationshipGraph()

        assert hasattr(graph, "relationships")
        assert isinstance(graph.relationships, dict)


@pytest.mark.unit
class TestGet3DVisualizationDataEnhanced:
    """Test suite for get_3d_visualization_data_enhanced method."""

    @staticmethod
    def test_empty_graph_returns_placeholder():
        """Test that empty graph returns a single placeholder node."""
        graph = AssetRelationshipGraph()

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert positions.shape == (1, 3)
        assert np.allclose(positions, np.zeros((1, 3)))
        assert asset_ids == ["A"]
        assert colors == ["#888888"]
        assert hover_texts == ["Asset A"]

    @staticmethod
    def test_single_relationship_returns_two_nodes():
        """Test graph with single relationship returns two nodes."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert positions.shape == (2, 3)
        assert len(asset_ids) == 2
        assert set(asset_ids) == {"asset1", "asset2"}
        assert len(colors) == 2
        assert len(hover_texts) == 2

    @staticmethod
    @staticmethod
    def test_multiple_relationships_circular_layout():
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
        radii = np.sqrt(positions[:, 0] ** 2 + positions[:, 1] ** 2)
        assert np.allclose(radii, 1.0)

    @staticmethod
    @staticmethod
    def test_positions_are_numpy_array():
        """Test that positions are returned as numpy array."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]

        positions, _, _, _ = graph.get_3d_visualization_data_enhanced()

        assert isinstance(positions, np.ndarray)
        assert positions.ndim == 2
        assert positions.shape[1] == 3

    @staticmethod
    @staticmethod
    def test_colors_are_consistent():
        """Test that all nodes get the same color."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]
        graph.relationships["asset2"] = [("asset3", "correlation", 0.7)]

        _, _, colors, _ = graph.get_3d_visualization_data_enhanced()

        assert all(color == "#4ECDC4" for color in colors)

    @staticmethod
    @staticmethod
    def test_hover_texts_format():
        """Test that hover texts are properly formatted."""
        graph = AssetRelationshipGraph()
        graph.relationships["AAPL"] = [("GOOGL", "correlation", 0.8)]

        _, asset_ids, _, hover_texts = graph.get_3d_visualization_data_enhanced()

        for asset_id, hover_text in zip(asset_ids, hover_texts):
            assert hover_text == f"Asset: {asset_id}"

    @staticmethod
    @staticmethod
    def test_asset_ids_are_sorted():
        """Test that asset IDs are returned in sorted order."""
        graph = AssetRelationshipGraph()
        graph.relationships["zebra"] = [("apple", "correlation", 0.8)]
        graph.relationships["banana"] = [("cherry", "correlation", 0.7)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert asset_ids == sorted(asset_ids)

    @staticmethod
    @staticmethod
    def test_bidirectional_relationships_single_nodes():
        """Test that bidirectional relationships don't duplicate nodes."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]
        graph.relationships["asset2"] = [("asset1", "correlation", 0.8)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 2
        assert set(asset_ids) == {"asset1", "asset2"}

    @staticmethod
    @staticmethod
    def test_complex_graph_with_multiple_targets():
        """Test graph where one source has multiple targets."""
        graph = AssetRelationshipGraph()
        graph.relationships["hub"] = [
            ("spoke1", "correlation", 0.8),
            ("spoke2", "correlation", 0.7),
            ("spoke3", "correlation", 0.6),
        ]

        positions, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 4
        assert "hub" in asset_ids
        assert "spoke1" in asset_ids
        assert "spoke2" in asset_ids
        assert "spoke3" in asset_ids
        assert positions.shape == (4, 3)

    @staticmethod
    def test_isolated_target_nodes():
        """Test that target nodes without outgoing relationships are included."""
        graph = AssetRelationshipGraph()
        graph.relationships["source"] = [("target1", "correlation", 0.8)]
        # target1 has no outgoing relationships

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert "source" in asset_ids
        assert "target1" in asset_ids

    @staticmethod
    def test_return_types():
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

    @staticmethod
    def test_consistent_list_lengths():
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
class TestAssetRelationshipGraphEdgeCases:
    """Test edge cases and boundary conditions for AssetRelationshipGraph."""

    @staticmethod
    def test_large_graph_performance():
        """Test that large graphs can be processed efficiently."""
        graph = AssetRelationshipGraph()

        # Create a large graph with 100 nodes
        for i in range(100):
            for j in range(i + 1, min(i + 5, 100)):
                if f"asset{i}" not in graph.relationships:
                    graph.relationships[f"asset{i}"] = []
                graph.relationships[f"asset{i}"].append(
                    (f"asset{j}", "correlation", 0.5 + (j - i) * 0.1)
                )

        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 100
        assert positions.shape == (100, 3)
        assert len(colors) == 100
        assert len(hover_texts) == 100

    @staticmethod
    def test_special_characters_in_asset_ids():
        """Test handling of special characters in asset IDs."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset-1"] = [("asset_2", "correlation", 0.8)]
        graph.relationships["asset_2"] = [("asset.3", "correlation", 0.7)]

        _, asset_ids, _, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert "asset-1" in asset_ids
        assert "asset_2" in asset_ids
        assert "asset.3" in asset_ids
        assert any("-" in hover for hover in hover_texts)

    @staticmethod
    def test_unicode_asset_ids():
        """Test handling of Unicode characters in asset IDs."""
        graph = AssetRelationshipGraph()
        graph.relationships["资产1"] = [("資產2", "correlation", 0.8)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert "资产1" in asset_ids
        assert "資產2" in asset_ids

    @staticmethod
    def test_empty_relationship_list():
        """Test handling of asset with empty relationship list."""
        graph = AssetRelationshipGraph()
        graph.relationships["lonely_asset"] = []

        positions, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        # Should return placeholder for empty graph
        assert positions.shape == (1, 3)
        assert asset_ids == ["A"]

    @staticmethod
    def test_self_referential_relationship():
        """Test handling of self-referential relationships."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset1", "correlation", 1.0)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 1
        assert "asset1" in asset_ids

    @staticmethod
    def test_zero_strength_relationships():
        """Test handling of relationships with zero strength."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.0)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 2
        assert set(asset_ids) == {"asset1", "asset2"}

    @staticmethod
    def test_negative_strength_relationships():
        """Test handling of relationships with negative strength."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", -0.8)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 2
        assert set(asset_ids) == {"asset1", "asset2"}

    @staticmethod
    def test_very_high_strength_relationships():
        """Test handling of relationships with strength > 1."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 1.5)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 2

    @staticmethod
    def test_disconnected_components():
        """Test graph with multiple disconnected components."""
        graph = AssetRelationshipGraph()
        # Component 1
        graph.relationships["A1"] = [("A2", "correlation", 0.8)]
        # Component 2
        graph.relationships["B1"] = [("B2", "correlation", 0.7)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 4
        assert set(asset_ids) == {"A1", "A2", "B1", "B2"}

    @staticmethod
    def test_star_topology():
        """Test graph with star topology (one central hub)."""
        graph = AssetRelationshipGraph()
        graph.relationships["hub"] = [
            (f"spoke{i}", "correlation", 0.5 + i * 0.05)
            for i in range(10)
        ]

        positions, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 11  # 1 hub + 10 spokes
        assert "hub" in asset_ids
        assert positions.shape == (11, 3)

    @staticmethod
    def test_chain_topology():
        """Test graph with linear chain topology."""
        graph = AssetRelationshipGraph()
        for i in range(5):
            graph.relationships[f"node{i}"] = [(f"node{i+1}", "correlation", 0.8)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 6  # node0 through node5
        assert all(f"node{i}" in asset_ids for i in range(6))

    @staticmethod
    def test_fully_connected_graph():
        """Test fully connected graph (complete graph)."""
        graph = AssetRelationshipGraph()
        nodes = ["A", "B", "C", "D"]

        for i, source in enumerate(nodes):
            graph.relationships[source] = [
                (target, "correlation", 0.8)
                for j, target in enumerate(nodes)
                if i != j
            ]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 4
        assert set(asset_ids) == set(nodes)

    @staticmethod
    def test_very_long_asset_id():
        """Test handling of very long asset IDs."""
        graph = AssetRelationshipGraph()
        long_id = "A" * 1000
        graph.relationships[long_id] = [("B", "correlation", 0.8)]

        _, asset_ids, _, hover_texts = graph.get_3d_visualization_data_enhanced()

        assert long_id in asset_ids
        assert any(long_id in hover for hover in hover_texts)

    @staticmethod
    def test_empty_string_asset_id():
        """Test handling of empty string as asset ID."""
        graph = AssetRelationshipGraph()
        graph.relationships[""] = [("asset1", "correlation", 0.8)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        # Empty string should be included as valid ID
        assert "" in asset_ids
        assert "asset1" in asset_ids

    @staticmethod
    def test_duplicate_relationships():
        """Test handling of duplicate relationships."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [
            ("asset2", "correlation", 0.8),
            ("asset2", "correlation", 0.9),  # Duplicate target
        ]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        # Should still work, nodes not duplicated
        assert len([aid for aid in asset_ids if aid == "asset2"]) == 1

    @staticmethod
    def test_circular_layout_angles():
        """Test that circular layout produces evenly distributed angles."""
        graph = AssetRelationshipGraph()
        n = 8
        for i in range(n):
            graph.relationships[f"asset{i}"] = [(f"asset{(i+1)%n}", "correlation", 0.8)]

        positions, _, _, _ = graph.get_3d_visualization_data_enhanced()

        # Calculate angles
        angles = np.arctan2(positions[:, 1], positions[:, 0])
        # Sort angles
        angles = np.sort(angles)

        # Check angular spacing is approximately uniform
        angle_diffs = np.diff(angles)
        expected_diff = 2 * np.pi / n
        # Allow some tolerance
        assert np.allclose(angle_diffs, expected_diff, atol=0.1)

    @staticmethod
    def test_3d_positions_z_coordinate():
        """Test that z-coordinates are set to zero for circular layout."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]

        positions, _, _, _ = graph.get_3d_visualization_data_enhanced()

        # All z-coordinates should be 0
        assert np.allclose(positions[:, 2], 0)

    @staticmethod
    def test_positions_finite():
        """Test that all positions are finite (no NaN or inf)."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]
        graph.relationships["asset2"] = [("asset3", "correlation", 0.7)]

        positions, _, _, _ = graph.get_3d_visualization_data_enhanced()

        assert np.all(np.isfinite(positions))
        assert not np.any(np.isnan(positions))
        assert not np.any(np.isinf(positions))

    @staticmethod
    def test_relationship_types_preserved():
        """Test that different relationship types don't affect layout."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [
            ("asset2", "correlation", 0.8),
            ("asset3", "same_sector", 0.9),
        ]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert len(asset_ids) == 3
        assert set(asset_ids) == {"asset1", "asset2", "asset3"}

    @staticmethod
    def test_multiple_relationship_types_same_pair():
        """Test multiple relationship types between same asset pair."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [
            ("asset2", "correlation", 0.8),
            ("asset2", "same_sector", 0.9),
        ]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        # Should not duplicate nodes
        assert len(asset_ids) == 2
        assert set(asset_ids) == {"asset1", "asset2"}


@pytest.mark.unit
class TestAssetRelationshipGraphMemory:
    """Test memory efficiency and resource management."""

    @staticmethod
    def test_positions_memory_layout():
        """Test that positions array uses efficient memory layout."""
        graph = AssetRelationshipGraph()
        for i in range(50):
            graph.relationships[f"asset{i}"] = [(f"asset{i+1}", "correlation", 0.8)]

        positions, _, _, _ = graph.get_3d_visualization_data_enhanced()

        # Check C-contiguous for efficient access
        assert positions.flags['C_CONTIGUOUS']

    @staticmethod
    def test_no_memory_leaks_repeated_calls():
        """Test that repeated calls don't leak memory."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]

        # Call multiple times
        for _ in range(100):
            positions, _, _, _ = graph.get_3d_visualization_data_enhanced()

        # Should complete without errors
        assert positions.shape == (2, 3)


@pytest.mark.unit
class TestAssetRelationshipGraphDataIntegrity:
    """Test data integrity and consistency."""

    @staticmethod
    def test_asset_ids_unique():
        """Test that returned asset IDs are unique."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [
            ("asset2", "correlation", 0.8),
            ("asset3", "correlation", 0.7),
        ]
        graph.relationships["asset2"] = [("asset3", "correlation", 0.6)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        # Check uniqueness
        assert len(asset_ids) == len(set(asset_ids))

    @staticmethod
    def test_colors_valid_hex():
        """Test that all colors are valid hex color codes."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]

        _, _, colors, _ = graph.get_3d_visualization_data_enhanced()

        hex_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
        assert all(hex_pattern.match(color) for color in colors)

    @staticmethod
    def test_hover_text_contains_asset_id():
        """Test that hover text contains corresponding asset ID."""
        graph = AssetRelationshipGraph()
        graph.relationships["AAPL"] = [("MSFT", "correlation", 0.8)]

        _, asset_ids, _, hover_texts = graph.get_3d_visualization_data_enhanced()

        for asset_id, hover_text in zip(asset_ids, hover_texts):
            assert asset_id in hover_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


import re