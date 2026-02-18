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

    try:
        positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
    except Exception as e:
        pytest.fail(f"Failed to get visualization data: {e}")

        assert isinstance(positions, np.ndarray) and positions.shape == (1, 3)
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
        assert len(set(asset_ids)) == 2
        assert set(asset_ids) == {"asset1", "asset2"}
        assert len(colors) == 2
        assert len(hover_texts) == 2

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
    def test_positions_are_numpy_array():
        """Test that positions are returned as numpy array."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]

        positions, _, _, _ = graph.get_3d_visualization_data_enhanced()

        assert isinstance(positions, np.ndarray)
        assert positions.ndim == 2
        assert positions.shape[1] == 3

    @staticmethod
    def test_colors_are_consistent():
        """Test that all nodes get the same color."""
        graph = AssetRelationshipGraph()
        graph.relationships["asset1"] = [("asset2", "correlation", 0.8)]
        graph.relationships["asset2"] = [("asset3", "correlation", 0.7)]

        _, _, colors, _ = graph.get_3d_visualization_data_enhanced()

        assert all(color == "#4ECDC4" for color in colors)

    @staticmethod
    def test_hover_texts_format():
        """Test that hover texts are properly formatted."""
        graph = AssetRelationshipGraph()
        graph.relationships["AAPL"] = [("GOOGL", "correlation", 0.8)]

        _, asset_ids, _, hover_texts = graph.get_3d_visualization_data_enhanced()

        for asset_id, hover_text in zip(asset_ids, hover_texts):
            assert all(hover_text == f"Asset: {asset_id}" for asset_id, hover_text in zip(asset_ids, hover_texts))

    @staticmethod
    def test_asset_ids_are_sorted():
        """Test that asset IDs are returned in sorted order."""
        graph = AssetRelationshipGraph()
        graph.relationships["zebra"] = [("apple", "correlation", 0.8)]
        graph.relationships["banana"] = [("cherry", "correlation", 0.7)]

        _, asset_ids, _, _ = graph.get_3d_visualization_data_enhanced()

        assert asset_ids == sorted(asset_ids)

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

    @staticmethod
    def test_asset_ids_sorted():
        """Test that asset IDs are returned in sorted order."""
        graph = AssetRelationshipGraph()
        # Add relationships in non-sorted order
        graph.relationships["zebra"] = [("apple", "correlation", 0.8)]
        graph.relationships["mango"] = [("banana", "correlation", 0.7)]

        _positions, asset_ids, _colors, _hover_texts = graph.get_3d_visualization_data_enhanced()

        # Verify they are returned as a sorted list of all unique assets
        expected_asset_ids = ["apple", "banana", "mango", "zebra"]
        assert asset_ids == expected_asset_ids


@pytest.mark.unit
class TestAddRelationshipRegression:
    """Regression tests for add_relationship parameter ordering bug."""

    @staticmethod
    def test_relationship_parameters_correct_order():
        """Regression: Verify relationship parameters are stored in correct order.

        This test verifies the fix for a bug where add_relationship was calling
        _append_relationship with parameters in wrong order (strength, rel_type)
        instead of (rel_type, strength).
        """
        graph = AssetRelationshipGraph()

        # Add a relationship with specific type and strength
        graph.add_relationship("source", "target", "correlation", 0.75)

        # Verify the relationship is stored correctly
        assert "source" in graph.relationships
        rels = graph.relationships["source"]
        assert len(rels) == 1

        # Relationship tuple should be (target, rel_type, strength)
        target, rel_type, strength = rels[0]
        assert target == "target"
        assert rel_type == "correlation"
        assert strength == 0.75

    @staticmethod
    def test_bidirectional_relationship_parameters():
        """Regression: Verify bidirectional relationships store parameters correctly."""
        graph = AssetRelationshipGraph()

        # Add bidirectional relationship
        graph.add_relationship("A", "B", "same_sector", 0.7, bidirectional=True)

        # Check forward relationship
        assert "A" in graph.relationships
        forward_rels = graph.relationships["A"]
        assert len(forward_rels) == 1
        target, rel_type, strength = forward_rels[0]
        assert target == "B"
        assert rel_type == "same_sector"
        assert strength == 0.7

        # Check reverse relationship
        assert "B" in graph.relationships
        reverse_rels = graph.relationships["B"]
        assert len(reverse_rels) == 1
        target, rel_type, strength = reverse_rels[0]
        assert target == "A"
        assert rel_type == "same_sector"
        assert strength == 0.7

    @staticmethod
    def test_relationship_type_is_string_not_float():
        """Regression: Ensure relationship type is stored as string, not float."""
        graph = AssetRelationshipGraph()

        # Add relationship with both string rel_type and float strength
        graph.add_relationship("X", "Y", "hedge", 0.5)

        # Verify types are correct
        rels = graph.relationships["X"]
        _target, rel_type, strength = rels[0]

        # The bug would have swapped these, making rel_type a float
        assert isinstance(rel_type, str), "rel_type should be string"
        assert isinstance(strength, (int, float)), "strength should be numeric"
        assert rel_type == "hedge"
        assert strength == 0.5


@pytest.mark.unit
class TestDatabaseUrlHandling:
    """Test cases for database URL configuration."""

    @staticmethod
    def test_graph_init_with_database_url():
        """Test that database URL is stored during initialization."""
        test_url = "postgresql://localhost/testdb"
        graph = AssetRelationshipGraph(database_url=test_url)

        assert graph.database_url == test_url

    @staticmethod
    def test_graph_init_without_database_url():
        """Test that database URL defaults to None."""
        graph = AssetRelationshipGraph()

        assert graph.database_url is None


@pytest.mark.unit
class TestAddAssetMethod:
    """Test cases for add_asset method."""

    @staticmethod
    def test_add_asset_stores_by_id():
        """Test that assets are stored by their ID."""
        from src.models.financial_models import Asset, AssetClass

        graph = AssetRelationshipGraph()
        asset = Asset(
            id="TEST1",
            symbol="TST",
            name="Test Asset",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )

        graph.add_asset(asset)

        assert "TEST1" in graph.assets
        assert graph.assets["TEST1"] == asset

    @staticmethod
    def test_add_asset_overwrites_existing():
        """Test that adding asset with same ID overwrites previous."""
        from src.models.financial_models import Asset, AssetClass

        graph = AssetRelationshipGraph()
        asset1 = Asset(
            id="TEST1",
            symbol="TST",
            name="First Asset",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        asset2 = Asset(
            id="TEST1",
            symbol="TST2",
            name="Second Asset",
            asset_class=AssetClass.EQUITY,
            sector="Finance",
            price=200.0,
        )

        graph.add_asset(asset1)
        graph.add_asset(asset2)

        assert len(graph.assets) == 1
        assert graph.assets["TEST1"].name == "Second Asset"
        assert graph.assets["TEST1"].price == 200.0


@pytest.mark.unit
class TestRegulatoryEventHandling:
    """Test cases for regulatory event management."""

    @staticmethod
    def test_add_regulatory_event():
        """Test that regulatory events can be added to the graph."""
        from src.models.financial_models import RegulatoryActivity, RegulatoryEvent

        graph = AssetRelationshipGraph()
        event = RegulatoryEvent(
            id="EVENT1",
            asset_id="AAPL",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-15",
            description="Q4 earnings release",
            impact_score=0.8,
        )

        graph.add_regulatory_event(event)

        assert len(graph.regulatory_events) == 1
        assert graph.regulatory_events[0] == event

    @staticmethod
    def test_multiple_regulatory_events():
        """Test that multiple regulatory events are stored in order."""
        from src.models.financial_models import RegulatoryActivity, RegulatoryEvent

        graph = AssetRelationshipGraph()
        event1 = RegulatoryEvent(
            id="EVENT1",
            asset_id="AAPL",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-15",
            description="Q4 earnings",
            impact_score=0.8,
        )
        event2 = RegulatoryEvent(
            id="EVENT2",
            asset_id="MSFT",
            event_type=RegulatoryActivity.DIVIDEND_ANNOUNCEMENT,
            date="2024-01-20",
            description="Dividend increase",
            impact_score=0.6,
        )

        graph.add_regulatory_event(event1)
        graph.add_regulatory_event(event2)

        assert len(graph.regulatory_events) == 2
        assert graph.regulatory_events[0].id == "EVENT1"
        assert graph.regulatory_events[1].id == "EVENT2"
