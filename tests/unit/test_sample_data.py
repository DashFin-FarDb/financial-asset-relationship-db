"""Unit tests for sample data generation.

This module contains comprehensive unit tests for sample data generation including:
- Sample database creation
- Asset diversity across all asset classes
- Relationship establishment
- Regulatory event generation
- Data consistency and completeness
"""

from src.data.sample_data import create_sample_database
from src.models.financial_models import AssetClass, Bond, Commodity, Currency, Equity


class TestSampleDatabaseCreation:
    """Test cases for sample database creation."""

    def test_create_sample_database_returns_graph(self):
        """Test that create_sample_database returns an AssetRelationshipGraph."""
        graph = create_sample_database()
        assert graph is not None
        assert hasattr(graph, "assets")
        assert hasattr(graph, "relationships")

    def test_sample_database_has_multiple_assets(self):
        """Test that sample database contains multiple assets."""
        graph = create_sample_database()
        assert len(graph.assets) >= 15, "Sample database should have 15+ assets"

    def test_sample_database_has_all_asset_classes(self):
        """Test that sample database includes all asset classes."""
        graph = create_sample_database()

        asset_classes = set()
        for asset in graph.assets.values():
            asset_classes.add(asset.asset_class)

        assert AssetClass.EQUITY in asset_classes
        assert AssetClass.FIXED_INCOME in asset_classes
        assert AssetClass.COMMODITY in asset_classes
        assert AssetClass.CURRENCY in asset_classes

    def test_sample_database_has_technology_equities(self):
        """Test that sample database includes technology equities."""
        graph = create_sample_database()

        tech_equities = [
            asset for asset in graph.assets.values() if isinstance(asset, Equity) and asset.sector == "Technology"
        ]

        assert len(tech_equities) >= 3, "Should have multiple technology companies"

    def test_sample_database_has_bonds(self):
        """Test that sample database includes bond assets."""
        graph = create_sample_database()

        bonds = [asset for asset in graph.assets.values() if isinstance(asset, Bond)]
        assert len(bonds) > 0, "Sample database should include bonds"

    def test_sample_database_has_commodities(self):
        """Test that sample database includes commodity assets."""
        graph = create_sample_database()

        commodities = [asset for asset in graph.assets.values() if isinstance(asset, Commodity)]
        assert len(commodities) > 0, "Sample database should include commodities"

    def test_sample_database_has_currencies(self):
        """Test that sample database includes currency assets."""
        graph = create_sample_database()

        currencies = [asset for asset in graph.assets.values() if isinstance(asset, Currency)]
        assert len(currencies) > 0, "Sample database should include currencies"


class TestSampleAssetProperties:
    """Test cases for sample asset properties."""

    def test_equity_assets_have_valid_prices(self):
        """Test that equity assets have positive prices."""
        graph = create_sample_database()

        equities = [asset for asset in graph.assets.values() if isinstance(asset, Equity)]

        for equity in equities:
            assert equity.price > 0, f"Equity {equity.id} should have positive price"

    def test_equity_assets_have_valid_market_cap(self):
        """Test that equity assets have valid market capitalization."""
        graph = create_sample_database()

        equities = [asset for asset in graph.assets.values() if isinstance(asset, Equity)]

        for equity in equities:
            if equity.market_cap is not None:
                assert equity.market_cap > 0, f"Equity {equity.id} should have positive market cap"

    def test_equity_assets_have_sectors(self):
        """Test that equity assets have sector assignments."""
        graph = create_sample_database()

        equities = [asset for asset in graph.assets.values() if isinstance(asset, Equity)]

        for equity in equities:
            assert equity.sector, f"Equity {equity.id} should have a sector"
            assert len(equity.sector) > 0

    def test_bond_assets_have_yield(self):
        """Test that bond assets have yield information."""
        graph = create_sample_database()

        bonds = [asset for asset in graph.assets.values() if isinstance(asset, Bond)]

        for bond in bonds:
            assert bond.yield_to_maturity is not None, f"Bond {bond.id} should have YTM"
            assert bond.yield_to_maturity >= 0

    def test_bond_assets_have_credit_ratings(self):
        """Test that bond assets have credit ratings."""
        graph = create_sample_database()

        bonds = [asset for asset in graph.assets.values() if isinstance(asset, Bond)]

        for bond in bonds:
            if bond.credit_rating:
                assert bond.credit_rating in [
                    "AAA",
                    "AA",
                    "A",
                    "BBB",
                    "BB",
                    "B",
                ], f"Bond {bond.id} should have valid credit rating"

    def test_commodity_assets_have_contract_info(self):
        """Test that commodity assets have contract information."""
        graph = create_sample_database()

        commodities = [asset for asset in graph.assets.values() if isinstance(asset, Commodity)]

        for commodity in commodities:
            assert (
                commodity.contract_size is not None or commodity.delivery_date is not None
            ), f"Commodity {commodity.id} should have contract information"

    def test_currency_assets_have_exchange_rates(self):
        """Test that currency assets have exchange rate information."""
        graph = create_sample_database()

        currencies = [asset for asset in graph.assets.values() if isinstance(asset, Currency)]

        for currency in currencies:
            assert currency.exchange_rate is not None, f"Currency {currency.id} should have exchange rate"
            assert currency.exchange_rate > 0


class TestSampleRelationships:
    """Test cases for sample database relationships."""

    def test_sample_database_has_relationships(self):
        """Test that sample database includes relationships."""
        graph = create_sample_database()
        assert len(graph.relationships) > 0, "Sample database should have relationships"

    def test_relationships_have_valid_strength(self):
        """Test that all relationships have valid strength values."""
        graph = create_sample_database()

        for _source_id, rels in graph.relationships.items():
            for _target_id, _rel_type, strength in rels:
                assert 0 <= strength <= 1, f"Relationship {_source_id} -> {_target_id} has invalid strength {strength}"

    def test_same_sector_relationships_exist(self):
        """Test that same-sector relationships are established."""
        graph = create_sample_database()

        # Look for same_sector relationships
        same_sector_found = False
        for _source_id, rels in graph.relationships.items():
            for _target_id, rel_type, _strength in rels:
                if rel_type == "same_sector":
                    same_sector_found = True
                    break
            if same_sector_found:
                break

        assert same_sector_found, "Sample database should have same_sector relationships"

    def test_corporate_bond_relationships_exist(self):
        """Test that corporate bond relationships are established."""
        graph = create_sample_database()

        # Look for corporate_bond relationships
        bond_rel_found = False
        for _source_id, rels in graph.relationships.items():
            for _target_id, rel_type, _strength in rels:
                if rel_type == "corporate_bond":
                    bond_rel_found = True
                    break
            if bond_rel_found:
                break

        # Bonds may not always be in sample data, so this is optional
        # Just verify the structure is there if bonds exist
        bonds = [asset for asset in graph.assets.values() if isinstance(asset, Bond)]
        if len(bonds) > 0:
            assert bond_rel_found or len(bonds) == 0, "If bonds exist, corporate_bond relationships should be present"


class TestSampleRegulatoryEvents:
    """Test cases for sample regulatory events."""

    def test_sample_database_may_have_regulatory_events(self):
        """Test that sample database can contain regulatory events."""
        graph = create_sample_database()
        # Events are optional in sample data, just verify the structure
        assert hasattr(graph, "regulatory_events")

    def test_regulatory_events_have_valid_impact_scores(self):
        """Test that regulatory events have valid impact scores."""
        graph = create_sample_database()

        if len(graph.regulatory_events) > 0:
            for event in graph.regulatory_events:
                assert -1 <= event.impact_score <= 1, f"Event {event.id} has invalid impact score {event.impact_score}"

    def test_regulatory_events_linked_to_assets(self):
        """Test that regulatory events are linked to existing assets."""
        graph = create_sample_database()

        if len(graph.regulatory_events) > 0:
            for event in graph.regulatory_events:
                assert (
                    event.asset_id in graph.assets
                ), f"Event {event.id} references non-existent asset {event.asset_id}"


class TestSampleDataConsistency:
    """Test cases for data consistency in sample database."""

    def test_all_assets_have_unique_ids(self):
        """Test that all assets have unique IDs."""
        graph = create_sample_database()

        ids = [asset.id for asset in graph.assets.values()]
        assert len(ids) == len(set(ids)), "All asset IDs should be unique"

    def test_all_assets_have_symbols(self):
        """Test that all assets have symbols."""
        graph = create_sample_database()

        for asset in graph.assets.values():
            assert asset.symbol, f"Asset {asset.id} should have a symbol"
            assert len(asset.symbol) > 0

    def test_all_assets_have_names(self):
        """Test that all assets have names."""
        graph = create_sample_database()

        for asset in graph.assets.values():
            assert asset.name, f"Asset {asset.id} should have a name"
            assert len(asset.name) > 0

    def test_relationship_targets_exist(self):
        """Test that all relationship targets reference existing assets."""
        graph = create_sample_database()

        for source_id, rels in graph.relationships.items():
            assert source_id in graph.assets, f"Source {source_id} should exist in assets"
            for target_id, _rel_type, _strength in rels:
                assert target_id in graph.assets, f"Target {target_id} in relationship should exist in assets"

    def test_bond_issuer_references_valid_asset(self):
        """Test that bond issuers reference valid assets when specified."""
        graph = create_sample_database()

        bonds = [asset for asset in graph.assets.values() if isinstance(asset, Bond)]

        for bond in bonds:
            if bond.issuer_id:
                assert bond.issuer_id in graph.assets, f"Bond {bond.id} issuer {bond.issuer_id} should exist in assets"


class TestSampleDatabaseMetrics:
    """Test cases for sample database metrics."""

    def test_sample_database_has_sufficient_density(self):
        """Test that sample database has reasonable relationship density."""
        graph = create_sample_database()

        metrics = graph.calculate_metrics()

        # Should have some relationships
        assert metrics["total_relationships"] > 0
        assert metrics["relationship_density"] > 0

    def test_sample_database_metrics_structure(self):
        """Test that metrics have expected structure."""
        graph = create_sample_database()

        metrics = graph.calculate_metrics()

        assert "total_assets" in metrics
        assert "total_relationships" in metrics
        assert "average_relationship_strength" in metrics
        assert "asset_class_distribution" in metrics
        assert "relationship_distribution" in metrics

    def test_asset_class_distribution_matches_assets(self):
        """Test that asset class distribution matches actual assets."""
        graph = create_sample_database()

        metrics = graph.calculate_metrics()

        # Count actual assets by class
        actual_counts = {}
        for asset in graph.assets.values():
            class_name = asset.asset_class.value
            actual_counts[class_name] = actual_counts.get(class_name, 0) + 1

        # Compare with metrics
        for asset_class, count in metrics["asset_class_distribution"].items():
            assert actual_counts.get(asset_class, 0) == count


class TestSampleDataReproducibility:
    """Test cases for sample data reproducibility."""

    def test_multiple_calls_produce_consistent_asset_count(self):
        """Test that multiple calls produce same number of assets."""
        graph1 = create_sample_database()
        graph2 = create_sample_database()

        assert len(graph1.assets) == len(graph2.assets)

    def test_multiple_calls_produce_same_asset_ids(self):
        """Test that multiple calls produce same asset IDs."""
        graph1 = create_sample_database()
        graph2 = create_sample_database()

        ids1 = set(graph1.assets.keys())
        ids2 = set(graph2.assets.keys())

        assert ids1 == ids2, "Sample database should produce consistent asset IDs"


class TestEdgeCases:
    """Test edge cases in sample data generation."""

    def test_sample_database_handles_metrics_calculation(self):
        """Test that sample database can calculate metrics without error."""
        graph = create_sample_database()

        # Should not raise any exceptions
        metrics = graph.calculate_metrics()
        assert metrics is not None

    def test_sample_database_can_be_serialized(self):
        """Test that sample database structure supports serialization."""
        graph = create_sample_database()

        # Verify all assets have serializable properties
        for asset in graph.assets.values():
            assert hasattr(asset, "id")
            assert hasattr(asset, "symbol")
            assert hasattr(asset, "name")
            assert hasattr(asset, "price")
