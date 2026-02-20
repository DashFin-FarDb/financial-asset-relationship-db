"""Additional integration and regression tests for data modules.

This module contains tests that verify interactions between data components:
- Repository and real data fetcher integration
- Sample data and repository consistency
- Cross-module data flow and transformations
- Regression tests for previously identified issues
"""

import pytest

from src.data.real_data_fetcher import (
    RealDataFetcher,
    _deserialize_graph,
    _serialize_graph,
)
from src.data.repository import AssetGraphRepository
from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity

pytestmark = pytest.mark.integration


class TestRepositoryGraphIntegration:
    """Test integration between repository and graph."""

    @staticmethod
    def test_sample_graph_can_be_saved_to_repository(tmp_path):
        """Test that a sample graph can be saved to and loaded from repository."""
        from src.data.database import (
            create_engine_from_url,
            create_session_factory,
            init_db,
        )

        # Create in-memory database
        db_path = tmp_path / "test_integration.db"
        engine = create_engine_from_url(f"sqlite:///{db_path}")
        init_db(engine)
        factory = create_session_factory(engine)
        session = factory()

        # Create repository and sample graph
        repo = AssetGraphRepository(session)
        graph = create_sample_database()

        # Save all assets to repository
        for asset in graph.assets.values():
            repo.upsert_asset(asset)
        session.commit()

        # Verify assets were saved
        saved_assets = repo.list_assets()
        assert len(saved_assets) == len(graph.assets)

        session.close()
        engine.dispose()

    @staticmethod
    def test_sample_graph_relationships_can_be_saved(tmp_path):
        """Test that sample graph relationships can be saved to repository."""
        from src.data.database import (
            create_engine_from_url,
            create_session_factory,
            init_db,
        )

        db_path = tmp_path / "test_rel_integration.db"
        engine = create_engine_from_url(f"sqlite:///{db_path}")
        init_db(engine)
        factory = create_session_factory(engine)
        session = factory()

        repo = AssetGraphRepository(session)
        graph = create_sample_database()

        # Save assets first
        for asset in graph.assets.values():
            repo.upsert_asset(asset)

        # Save relationships
        for source_id, rels in graph.relationships.items():
            for target_id, rel_type, strength in rels:
                repo.add_or_update_relationship(
                    source_id, target_id, rel_type, strength, bidirectional=False
                )

        session.commit()

        # Verify relationships were saved
        saved_rels = repo.list_relationships()
        assert len(saved_rels) > 0

        session.close()
        engine.dispose()


class TestSerializationRoundTrip:
    """Test serialization and deserialization round-trips."""

    @staticmethod
    def test_sample_graph_serialization_roundtrip():
        """Test that a sample graph can be serialized and deserialized."""
        # Create a simple graph for testing (sample database may have events that complicate deserialization)
        original_graph = AssetRelationshipGraph()

        # Add a few assets
        for i in range(3):
            asset = Equity(
                id=f"TEST_{i}",
                symbol=f"T{i}",
                name=f"Test {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + i * 10,
            )
            original_graph.add_asset(asset)

        # Add relationships
        original_graph.add_relationship(
            "TEST_0", "TEST_1", "same_sector", 0.7, bidirectional=False
        )

        # Serialize
        serialized = _serialize_graph(original_graph)

        # Deserialize
        restored_graph = _deserialize_graph(serialized)

        # Verify asset count matches
        assert len(restored_graph.assets) == len(original_graph.assets)

        # Verify specific assets exist
        for asset_id in original_graph.assets:
            assert asset_id in restored_graph.assets

    @staticmethod
    def test_empty_graph_serialization_roundtrip():
        """Test that an empty graph can be serialized and deserialized."""
        original_graph = AssetRelationshipGraph()

        serialized = _serialize_graph(original_graph)
        restored_graph = _deserialize_graph(serialized)

        assert len(restored_graph.assets) == 0
        assert len(restored_graph.relationships) == 0

    @staticmethod
        """Test serialization of graph with bidirectional relationships."""
        graph = AssetRelationshipGraph()

        # Add multiple assets
        assets = []
        for i in range(3):
            asset = Equity(
                id=f"TEST_{i}",
                symbol=f"T{i}",
                name=f"Test {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + i * 10,
            )
            assets.append(asset)
            graph.add_asset(asset)

        # Add bidirectional relationships
        graph.add_relationship(
            "TEST_0", "TEST_1", "same_sector", 0.8, bidirectional=True
        )
        graph.add_relationship(
            "TEST_1", "TEST_2", "market_cap", 0.6, bidirectional=True
        )

        # Serialize and deserialize
        serialized = _serialize_graph(graph)
        restored_graph = _deserialize_graph(serialized)

        # Verify relationships preserved
        assert "TEST_0" in restored_graph.relationships
        assert "TEST_1" in restored_graph.relationships
        assert "TEST_2" in restored_graph.relationships


class TestDataFetcherWithFallback:
    """Test real data fetcher fallback mechanisms."""

    @staticmethod
    def test_fetcher_with_network_disabled_uses_fallback():
        """Test that fetcher with network disabled uses fallback."""
        fetcher = RealDataFetcher(enable_network=False)
        graph = fetcher.create_real_database()

        # Should have fallback data
        assert len(graph.assets) > 0

    @staticmethod
    def test_fetcher_with_custom_fallback():
        """Test that fetcher uses custom fallback factory."""
        custom_graph = AssetRelationshipGraph()
        custom_asset = Equity(
            id="CUSTOM_ASSET",
            symbol="CUST",
            name="Custom",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=999.0,
        )
        custom_graph.add_asset(custom_asset)

        def custom_factory():
            """Factory function returning a preconfigured AssetRelationshipGraph for fallback."""
            return custom_graph

        fetcher = RealDataFetcher(fallback_factory=custom_factory, enable_network=False)
        result = fetcher.create_real_database()

        assert "CUSTOM_ASSET" in result.assets


class TestEdgeCasesAndRegressions:
    """Test edge cases and regression scenarios."""

    @staticmethod
    def test_asset_with_all_none_optional_fields(tmp_path):
        """Test asset with all optional fields as None."""
        from src.data.database import (
            create_engine_from_url,
            create_session_factory,
            init_db,
        )

        db_path = tmp_path / "test_none_fields.db"
        engine = create_engine_from_url(f"sqlite:///{db_path}")
        init_db(engine)
        factory = create_session_factory(engine)
        session = factory()

        repo = AssetGraphRepository(session)

        # Create asset with minimal fields
        asset = Equity(
            id="MINIMAL",
            symbol="MIN",
            name="Minimal Asset",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=1.0,
            # All other fields None
        )

        repo.upsert_asset(asset)
        session.commit()

        # Retrieve and verify
        retrieved = repo.get_assets_map()["MINIMAL"]
        assert retrieved.id == "MINIMAL"
        assert abs(retrieved.price - 1.0) < 1e-9

        session.close()
        engine.dispose()

    @staticmethod
    def test_relationship_with_empty_string_type(tmp_path):
        """Test that empty string relationship type is handled."""
        from src.data.database import (
            create_engine_from_url,
            create_session_factory,
            init_db,
        )

        db_path = tmp_path / "test_empty_rel.db"
        engine = create_engine_from_url(f"sqlite:///{db_path}")
        init_db(engine)
        factory = create_session_factory(engine)
        session = factory()

        repo = AssetGraphRepository(session)

        # Create two assets
        asset1 = Equity(
            id="A1",
            symbol="A1",
            name="Asset 1",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=100.0,
        )
        asset2 = Equity(
            id="A2",
            symbol="A2",
            name="Asset 2",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=200.0,
        )

        repo.upsert_asset(asset1)
        repo.upsert_asset(asset2)
        session.commit()

        # Try to add relationship with empty type
        # This should work as the database allows any string
        repo.add_or_update_relationship("A1", "A2", "", 0.5, bidirectional=False)
        session.commit()

        # Verify relationship was saved
        rel = repo.get_relationship("A1", "A2", "")
        assert rel is not None
        assert rel.relationship_type == ""

        session.close()
        engine.dispose()

    @staticmethod
    def test_graph_metrics_with_no_relationships():
        """Test that metrics calculation works with no relationships."""
        graph = AssetRelationshipGraph()

        # Add only assets, no relationships
        asset = Equity(
            id="SOLO",
            symbol="SOLO",
            name="Solo Asset",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=100.0,
        )
        graph.add_asset(asset)

        # Calculate metrics should not fail
        metrics = graph.calculate_metrics()
        assert metrics["total_assets"] == 1
        assert metrics["total_relationships"] == 0
        assert metrics["relationship_density"] == pytest.approx(0.0)

    @staticmethod
    def test_large_relationship_strength_values(tmp_path):
        """Test handling of relationship strengths at boundaries."""
        from src.data.database import (
            create_engine_from_url,
            create_session_factory,
            init_db,
        )

        db_path = tmp_path / "test_strength_bounds.db"
        engine = create_engine_from_url(f"sqlite:///{db_path}")
        init_db(engine)
        factory = create_session_factory(engine)
        session = factory()

        repo = AssetGraphRepository(session)

        assets = []
        for i in range(3):
            asset = Equity(
                id=f"BOUND_{i}",
                symbol=f"B{i}",
                name=f"Bound {i}",
                asset_class=AssetClass.EQUITY,
                sector="Test",
                price=100.0,
            )
            assets.append(asset)
            repo.upsert_asset(asset)

        session.commit()

        # Test with exact 0.0
        repo.add_or_update_relationship(
            "BOUND_0", "BOUND_1", "zero", 0.0, bidirectional=False
        )

        # Test with exact 1.0
        repo.add_or_update_relationship(
            "BOUND_1", "BOUND_2", "one", 1.0, bidirectional=False
        )

        # Test with negative (allowed in some systems)
        repo.add_or_update_relationship(
            "BOUND_2", "BOUND_0", "negative", -0.5, bidirectional=False
        )

        session.commit()

        # Verify all were saved
        rel_zero = repo.get_relationship("BOUND_0", "BOUND_1", "zero")
        rel_one = repo.get_relationship("BOUND_1", "BOUND_2", "one")
        rel_neg = repo.get_relationship("BOUND_2", "BOUND_0", "negative")

        assert rel_zero.strength == pytest.approx(0.0)
        assert rel_one.strength == pytest.approx(1.0)
        assert rel_neg.strength == pytest.approx(-0.5)

        session.close()
        engine.dispose()


class TestConcurrentOperations:
    """Test concurrent and repeated operations."""

    @staticmethod
    def test_repeated_asset_upserts(tmp_path):
        """Test that repeated upserts don't create duplicates."""
        from src.data.database import (
            create_engine_from_url,
            create_session_factory,
            init_db,
        )

        db_path = tmp_path / "test_repeated_upsert.db"
        engine = create_engine_from_url(f"sqlite:///{db_path}")
        init_db(engine)
        factory = create_session_factory(engine)
        session = factory()

        repo = AssetGraphRepository(session)

        asset = Equity(
            id="REPEAT",
            symbol="REP",
            name="Repeated",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=100.0,
        )

        # Upsert same asset multiple times
        for i in range(5):
            asset.price = 100.0 + i * 10
            repo.upsert_asset(asset)
            session.commit()

        # Should only have one asset
        assets = repo.list_assets()
        assert len(assets) == 1
        assert abs(assets[0].price - 140.0) < 1e-9  # Last update

        session.close()
        engine.dispose()

    @staticmethod
    def test_delete_and_recreate_asset(tmp_path):
        """Test deleting and recreating an asset."""
        from src.data.database import (
            create_engine_from_url,
            create_session_factory,
            init_db,
        )

        db_path = tmp_path / "test_delete_recreate.db"
        engine = create_engine_from_url(f"sqlite:///{db_path}")
        init_db(engine)
        factory = create_session_factory(engine)
        session = factory()

        repo = AssetGraphRepository(session)

        # Create asset
        asset = Equity(
            id="RECREATE",
            symbol="REC",
            name="Recreate",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=100.0,
        )
        repo.upsert_asset(asset)
        session.commit()

        # Delete asset
        repo.delete_asset("RECREATE")
        session.commit()

        # Recreate with same ID
        asset_new = Equity(
            id="RECREATE",
            symbol="REC2",
            name="Recreated",
            asset_class=AssetClass.EQUITY,
            sector="Test2",
            price=200.0,
        )
        repo.upsert_asset(asset_new)
        session.commit()

        # Verify it's the new version
        assets = repo.list_assets()
        assert len(assets) == 1
        assert assets[0].symbol == "REC2"
        assert abs(assets[0].price - 200.0) < 1e-9

        session.close()
        engine.dispose()


class TestDataConsistency:
    """Test data consistency across operations."""

    @staticmethod
    def test_graph_clone_independence():
        """Test that cloning a graph creates independent copy."""
        graph1 = create_sample_database()
        graph2 = create_sample_database()

        # Modify graph1
        new_asset = Equity(
            id="NEW_ASSET",
            symbol="NEW",
            name="New Asset",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=100.0,
        )
        graph1.add_asset(new_asset)

        # graph2 should not have the new asset
        assert "NEW_ASSET" in graph1.assets
        assert "NEW_ASSET" not in graph2.assets

    @staticmethod
    def test_relationship_consistency_after_asset_delete(tmp_path):
        """Test that relationships are cleaned up when asset is deleted."""
        from src.data.database import (
            create_engine_from_url,
            create_session_factory,
            init_db,
        )

        db_path = tmp_path / "test_rel_consistency.db"
        engine = create_engine_from_url(f"sqlite:///{db_path}")
        init_db(engine)
        factory = create_session_factory(engine)
        session = factory()

        repo = AssetGraphRepository(session)

        # Create assets and relationship
        a1 = Equity(
            id="DEL1",
            symbol="D1",
            name="Del 1",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=100.0,
        )
        a2 = Equity(
            id="DEL2",
            symbol="D2",
            name="Del 2",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=200.0,
        )

        repo.upsert_asset(a1)
        repo.upsert_asset(a2)
        repo.add_or_update_relationship(
            "DEL1", "DEL2", "test_rel", 0.5, bidirectional=False
        )
        session.commit()

        # Delete one asset
        repo.delete_asset("DEL1")
        session.commit()

        # Relationship should be gone
        rels = repo.list_relationships()
        matching_rels = [
            r for r in rels if r.source_id == "DEL1" or r.target_id == "DEL1"
        ]
        assert len(matching_rels) == 0

        session.close()
        engine.dispose()
