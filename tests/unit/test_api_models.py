"""
Comprehensive unit tests for api/models.py

Tests cover Pydantic models for API requests and responses,
validation, serialization, and edge cases.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.models import (
    AssetResponse,
    MetricsResponse,
    RelationshipResponse,
    User,
    UserInDB,
    VisualizationDataResponse,
)


class TestUserModel:
    """Test User Pydantic model."""

    def test_user_minimal_fields(self):
        """User model works with minimal required fields."""
        user = User(username="testuser")

        assert user.username == "testuser"
        assert user.email is None
        assert user.full_name is None
        assert user.disabled is False  # Default value

    def test_user_all_fields(self):
        """User model works with all fields populated."""
        user = User(
            username="fulluser",
            email="full@example.com",
            full_name="Full Name",
            disabled=True,
        )

        assert user.username == "fulluser"
        assert user.email == "full@example.com"
        assert user.full_name == "Full Name"
        assert user.disabled is True

    def test_user_default_disabled_is_false(self):
        """User model defaults disabled to False."""
        user = User(username="user")

        assert user.disabled is False

    def test_user_serialization(self):
        """User model serializes to dict correctly."""
        user = User(
            username="serializeuser",
            email="serialize@example.com",
            full_name="Serialize User",
            disabled=False,
        )

        data = user.model_dump()

        assert data["username"] == "serializeuser"
        assert data["email"] == "serialize@example.com"
        assert data["full_name"] == "Serialize User"
        assert data["disabled"] is False

    def test_user_from_dict(self):
        """User model can be created from dict."""
        data = {
            "username": "dictuser",
            "email": "dict@example.com",
            "full_name": "Dict User",
            "disabled": True,
        }

        user = User(**data)

        assert user.username == "dictuser"
        assert user.email == "dict@example.com"

    def test_user_missing_username_raises_error(self):
        """User model requires username field."""
        with pytest.raises(ValidationError) as exc_info:
            User()

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("username",) for e in errors)


class TestUserInDBModel:
    """Test UserInDB Pydantic model."""

    def test_user_in_db_minimal_fields(self):
        """UserInDB model works with minimal required fields."""
        user = UserInDB(username="dbuser", hashed_password="hashed123")

        assert user.username == "dbuser"
        assert user.hashed_password == "hashed123"
        assert user.email is None
        assert user.full_name is None
        assert user.disabled is False

    def test_user_in_db_all_fields(self):
        """UserInDB model works with all fields populated."""
        user = UserInDB(
            username="fulldbuser",
            email="fulldb@example.com",
            full_name="Full DB User",
            disabled=True,
            hashed_password="securehashedpassword",
        )

        assert user.username == "fulldbuser"
        assert user.email == "fulldb@example.com"
        assert user.full_name == "Full DB User"
        assert user.disabled is True
        assert user.hashed_password == "securehashedpassword"

    def test_user_in_db_requires_hashed_password(self):
        """UserInDB model requires hashed_password field."""
        with pytest.raises(ValidationError) as exc_info:
            UserInDB(username="user")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("hashed_password",) for e in errors)

    def test_user_in_db_serialization_excludes_password(self):
        """UserInDB serialization should include hashed_password by default."""
        user = UserInDB(username="user", hashed_password="hash")

        data = user.model_dump()

        # hashed_password should be included by default
        assert "hashed_password" in data
        assert data["hashed_password"] == "hash"


class TestAssetResponseModel:
    """Test AssetResponse Pydantic model."""

    def test_asset_response_minimal_fields(self):
        """AssetResponse model works with minimal required fields."""
        asset = AssetResponse(
            id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            asset_class="EQUITY",
            sector="Technology",
            price=150.0,
        )

        assert asset.id == "AAPL"
        assert asset.symbol == "AAPL"
        assert asset.name == "Apple Inc."
        assert asset.asset_class == "EQUITY"
        assert asset.sector == "Technology"
        assert asset.price == 150.0
        assert asset.market_cap is None  # Default
        assert asset.currency == "USD"  # Default
        assert asset.additional_fields == {}  # Default

    def test_asset_response_all_fields(self):
        """AssetResponse model works with all fields populated."""
        asset = AssetResponse(
            id="GOOGL",
            symbol="GOOGL",
            name="Alphabet Inc.",
            asset_class="EQUITY",
            sector="Technology",
            price=2800.0,
            market_cap=1_500_000_000_000.0,
            currency="USD",
            additional_fields={"exchange": "NASDAQ", "country": "US"},
        )

        assert asset.id == "GOOGL"
        assert asset.symbol == "GOOGL"
        assert asset.name == "Alphabet Inc."
        assert asset.market_cap == 1_500_000_000_000.0
        assert asset.currency == "USD"
        assert asset.additional_fields == {"exchange": "NASDAQ", "country": "US"}

    def test_asset_response_default_currency(self):
        """AssetResponse model defaults currency to USD."""
        asset = AssetResponse(
            id="TEST",
            symbol="TEST",
            name="Test Asset",
            asset_class="EQUITY",
            sector="Test",
            price=100.0,
        )

        assert asset.currency == "USD"

    def test_asset_response_empty_additional_fields(self):
        """AssetResponse model defaults additional_fields to empty dict."""
        asset = AssetResponse(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class="EQUITY",
            sector="Test",
            price=100.0,
        )

        assert asset.additional_fields == {}

    def test_asset_response_custom_currency(self):
        """AssetResponse model accepts custom currency."""
        asset = AssetResponse(
            id="EUR-USD",
            symbol="EUR-USD",
            name="Euro to US Dollar",
            asset_class="CURRENCY",
            sector="FX",
            price=1.08,
            currency="EUR",
        )

        assert asset.currency == "EUR"

    def test_asset_response_serialization(self):
        """AssetResponse serializes to dict correctly."""
        asset = AssetResponse(
            id="BTC-USD",
            symbol="BTC-USD",
            name="Bitcoin",
            asset_class="CRYPTO",
            sector="Cryptocurrency",
            price=45000.0,
            market_cap=850_000_000_000.0,
        )

        data = asset.model_dump()

        assert data["id"] == "BTC-USD"
        assert data["symbol"] == "BTC-USD"
        assert data["price"] == 45000.0
        assert data["market_cap"] == 850_000_000_000.0


class TestRelationshipResponseModel:
    """Test RelationshipResponse Pydantic model."""

    def test_relationship_response_all_fields(self):
        """RelationshipResponse model works with all required fields."""
        relationship = RelationshipResponse(
            source_id="AAPL",
            target_id="MSFT",
            relationship_type="sector_affinity",
            strength=0.85,
        )

        assert relationship.source_id == "AAPL"
        assert relationship.target_id == "MSFT"
        assert relationship.relationship_type == "sector_affinity"
        assert relationship.strength == 0.85

    def test_relationship_response_strength_as_int(self):
        """RelationshipResponse accepts integer strength."""
        relationship = RelationshipResponse(
            source_id="A",
            target_id="B",
            relationship_type="test",
            strength=1,
        )

        assert relationship.strength == 1.0

    def test_relationship_response_strength_range(self):
        """RelationshipResponse accepts various strength values."""
        # Test minimum
        rel_min = RelationshipResponse(
            source_id="A",
            target_id="B",
            relationship_type="weak",
            strength=0.0,
        )
        assert rel_min.strength == 0.0

        # Test maximum
        rel_max = RelationshipResponse(
            source_id="A",
            target_id="B",
            relationship_type="strong",
            strength=1.0,
        )
        assert rel_max.strength == 1.0

        # Test decimal
        rel_decimal = RelationshipResponse(
            source_id="A",
            target_id="B",
            relationship_type="medium",
            strength=0.567,
        )
        assert rel_decimal.strength == 0.567

    def test_relationship_response_missing_fields_raises_error(self):
        """RelationshipResponse requires all fields."""
        with pytest.raises(ValidationError):
            RelationshipResponse(
                source_id="A",
                target_id="B",
                # Missing relationship_type and strength
            )


class TestMetricsResponseModel:
    """Test MetricsResponse Pydantic model."""

    def test_metrics_response_minimal(self):
        """MetricsResponse model works with minimal fields."""
        metrics = MetricsResponse(
            total_assets=100,
            total_relationships=450,
            asset_classes={"EQUITY": 60, "BOND": 40},
            avg_degree=4.5,
            max_degree=15,
            network_density=0.045,
        )

        assert metrics.total_assets == 100
        assert metrics.total_relationships == 450
        assert metrics.asset_classes == {"EQUITY": 60, "BOND": 40}
        assert metrics.avg_degree == 4.5
        assert metrics.max_degree == 15
        assert metrics.network_density == 0.045
        assert metrics.relationship_density == 0.0  # Default

    def test_metrics_response_with_relationship_density(self):
        """MetricsResponse model accepts relationship_density."""
        metrics = MetricsResponse(
            total_assets=50,
            total_relationships=200,
            asset_classes={"EQUITY": 50},
            avg_degree=4.0,
            max_degree=10,
            network_density=0.08,
            relationship_density=0.12,
        )

        assert metrics.relationship_density == 0.12

    def test_metrics_response_empty_asset_classes(self):
        """MetricsResponse allows empty asset_classes dict."""
        metrics = MetricsResponse(
            total_assets=0,
            total_relationships=0,
            asset_classes={},
            avg_degree=0.0,
            max_degree=0,
            network_density=0.0,
        )

        assert metrics.asset_classes == {}

    def test_metrics_response_multiple_asset_classes(self):
        """MetricsResponse handles multiple asset classes."""
        metrics = MetricsResponse(
            total_assets=200,
            total_relationships=800,
            asset_classes={
                "EQUITY": 80,
                "BOND": 50,
                "COMMODITY": 30,
                "CURRENCY": 20,
                "DERIVATIVE": 20,
            },
            avg_degree=4.0,
            max_degree=20,
            network_density=0.04,
        )

        assert len(metrics.asset_classes) == 5
        assert metrics.asset_classes["EQUITY"] == 80
        assert metrics.asset_classes["COMMODITY"] == 30

    def test_metrics_response_serialization(self):
        """MetricsResponse serializes correctly."""
        metrics = MetricsResponse(
            total_assets=10,
            total_relationships=20,
            asset_classes={"TEST": 10},
            avg_degree=2.0,
            max_degree=5,
            network_density=0.2,
            relationship_density=0.3,
        )

        data = metrics.model_dump()

        assert data["total_assets"] == 10
        assert data["total_relationships"] == 20
        assert data["relationship_density"] == 0.3


class TestVisualizationDataResponseModel:
    """Test VisualizationDataResponse Pydantic model."""

    def test_visualization_data_response_empty(self):
        """VisualizationDataResponse works with empty lists."""
        viz = VisualizationDataResponse(nodes=[], edges=[])

        assert viz.nodes == []
        assert viz.edges == []

    def test_visualization_data_response_with_nodes_and_edges(self):
        """VisualizationDataResponse accepts nodes and edges."""
        nodes = [
            {"id": "A", "label": "Asset A", "x": 0, "y": 0, "z": 0},
            {"id": "B", "label": "Asset B", "x": 1, "y": 1, "z": 1},
        ]
        edges = [
            {"source": "A", "target": "B", "strength": 0.8},
        ]

        viz = VisualizationDataResponse(nodes=nodes, edges=edges)

        assert len(viz.nodes) == 2
        assert len(viz.edges) == 1
        assert viz.nodes[0]["id"] == "A"
        assert viz.edges[0]["source"] == "A"

    def test_visualization_data_response_large_dataset(self):
        """VisualizationDataResponse handles large datasets."""
        nodes = [{"id": str(i), "label": f"Node {i}"} for i in range(1000)]
        edges = [
            {"source": str(i), "target": str(i + 1), "strength": 0.5}
            for i in range(999)
        ]

        viz = VisualizationDataResponse(nodes=nodes, edges=edges)

        assert len(viz.nodes) == 1000
        assert len(viz.edges) == 999

    def test_visualization_data_response_serialization(self):
        """VisualizationDataResponse serializes correctly."""
        viz = VisualizationDataResponse(
            nodes=[{"id": "A"}],
            edges=[{"source": "A", "target": "B"}],
        )

        data = viz.model_dump()

        assert "nodes" in data
        assert "edges" in data
        assert data["nodes"][0]["id"] == "A"


class TestEdgeCasesAndValidation:
    """Test edge cases and validation scenarios."""

    def test_asset_response_negative_price(self):
        """AssetResponse accepts negative prices (for certain instruments)."""
        asset = AssetResponse(
            id="NEG",
            symbol="NEG",
            name="Negative Price Asset",
            asset_class="DERIVATIVE",
            sector="Special",
            price=-10.0,
        )

        assert asset.price == -10.0

    def test_asset_response_zero_price(self):
        """AssetResponse accepts zero price."""
        asset = AssetResponse(
            id="ZERO",
            symbol="ZERO",
            name="Zero Price",
            asset_class="EQUITY",
            sector="Test",
            price=0.0,
        )

        assert asset.price == 0.0

    def test_asset_response_very_large_market_cap(self):
        """AssetResponse handles very large market cap values."""
        asset = AssetResponse(
            id="HUGE",
            symbol="HUGE",
            name="Huge Cap",
            asset_class="EQUITY",
            sector="Tech",
            price=1000.0,
            market_cap=10_000_000_000_000.0,  # 10 trillion
        )

        assert asset.market_cap == 10_000_000_000_000.0

    def test_relationship_response_strength_negative(self):
        """RelationshipResponse accepts negative strength values."""
        relationship = RelationshipResponse(
            source_id="A",
            target_id="B",
            relationship_type="inverse",
            strength=-0.5,
        )

        assert relationship.strength == -0.5

    def test_metrics_response_zero_values(self):
        """MetricsResponse handles all zero values."""
        metrics = MetricsResponse(
            total_assets=0,
            total_relationships=0,
            asset_classes={},
            avg_degree=0.0,
            max_degree=0,
            network_density=0.0,
            relationship_density=0.0,
        )

        assert metrics.total_assets == 0
        assert metrics.avg_degree == 0.0

    def test_user_unicode_in_fields(self):
        """User model handles unicode characters."""
        user = User(
            username="用户",
            email="user@例え.jp",
            full_name="テスト ユーザー",
        )

        assert user.username == "用户"
        assert "例え" in user.email
        assert user.full_name == "テスト ユーザー"

    def test_asset_response_special_characters_in_name(self):
        """AssetResponse handles special characters in name."""
        asset = AssetResponse(
            id="SPECIAL",
            symbol="SPECIAL",
            name="Asset & Co. (NYSE: TEST) - \"Special\"",
            asset_class="EQUITY",
            sector="Test & Dev",
            price=100.0,
        )

        assert "Asset & Co." in asset.name
        assert "(NYSE: TEST)" in asset.name

    def test_visualization_data_nested_dict_values(self):
        """VisualizationDataResponse handles nested dictionaries."""
        nodes = [
            {
                "id": "A",
                "metadata": {
                    "sector": "Tech",
                    "stats": {"price": 100, "volume": 1000},
                },
            }
        ]

        viz = VisualizationDataResponse(nodes=nodes, edges=[])

        assert viz.nodes[0]["metadata"]["sector"] == "Tech"
        assert viz.nodes[0]["metadata"]["stats"]["price"] == 100

    def test_metrics_response_fractional_counts(self):
        """MetricsResponse accepts float for avg_degree."""
        metrics = MetricsResponse(
            total_assets=100,
            total_relationships=333,
            asset_classes={"EQUITY": 100},
            avg_degree=3.33,
            max_degree=10,
            network_density=0.033,
        )

        assert metrics.avg_degree == 3.33

    def test_asset_response_additional_fields_complex(self):
        """AssetResponse handles complex additional_fields."""
        asset = AssetResponse(
            id="COMPLEX",
            symbol="COMPLEX",
            name="Complex Asset",
            asset_class="EQUITY",
            sector="Test",
            price=100.0,
            additional_fields={
                "metadata": {
                    "created": "2024-01-01",
                    "tags": ["tech", "growth"],
                },
                "financials": {"revenue": 1_000_000, "profit": 200_000},
            },
        )

        assert "metadata" in asset.additional_fields
        assert asset.additional_fields["metadata"]["tags"] == ["tech", "growth"]
        assert asset.additional_fields["financials"]["revenue"] == 1_000_000