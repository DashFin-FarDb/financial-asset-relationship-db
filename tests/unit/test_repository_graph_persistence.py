"""Unit tests for repository graph persistence helpers."""

import pytest
from sqlalchemy import create_engine  # pylint: disable=import-error

from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import (
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)
from tests.conftest import enable_sqlite_foreign_keys

pytestmark = pytest.mark.unit


@pytest.fixture
def repository_factory(tmp_path):
    """Provide a factory for creating repository instances."""
    db_path = tmp_path / "graph_persistence.db"
    engine = create_engine(f"sqlite:///{db_path}")
    enable_sqlite_foreign_keys(engine)
    init_db(engine)
    factory = create_session_factory(engine)

    sessions = []

    def make_repository() -> AssetGraphRepository:
        """Create a repository with a fresh SQLAlchemy session."""
        session = factory()
        sessions.append(session)
        return AssetGraphRepository(session)

    yield make_repository

    for session in sessions:
        session.close()
    engine.dispose()


def _equity(asset_id: str, symbol: str, sector: str = "Technology") -> Equity:
    """Build a minimal equity asset for graph persistence tests."""
    return Equity(
        id=asset_id,
        symbol=symbol,
        name=f"{symbol} Equity",
        asset_class=AssetClass.EQUITY,
        sector=sector,
        price=100.0,
    )


def _event(
    event_id: str,
    asset_id: str,
    related_assets: list[str] | None = None,
) -> RegulatoryEvent:
    """Build a regulatory event for graph persistence tests."""
    return RegulatoryEvent(
        id=event_id,
        asset_id=asset_id,
        event_type=RegulatoryActivity.SEC_FILING,
        date="2024-01-15",
        description=f"{event_id} filing",
        impact_score=0.5,
        related_assets=related_assets or [],
    )


def _relationship_strength(
    graph: AssetRelationshipGraph,
    source_id: str,
    target_id: str,
    relationship_type: str,
) -> float:
    """Return the strength for one graph relationship."""
    for target, rel_type, strength in graph.relationships.get(source_id, []):
        if target == target_id and rel_type == relationship_type:
            return strength
    raise AssertionError(f"Missing relationship {source_id}->{target_id} ({relationship_type})")


def _relationship_count(
    graph: AssetRelationshipGraph,
    source_id: str,
    target_id: str,
    relationship_type: str,
) -> int:
    """Return the number of matching graph relationships."""
    return sum(
        1
        for target, rel_type, _ in graph.relationships.get(source_id, [])
        if target == target_id and rel_type == relationship_type
    )


@pytest.mark.unit
class TestGraphPersistenceRoundTrip:
    """Test graph snapshot persistence and reconstruction."""

    @staticmethod
    def test_save_load_graph_round_trip_preserves_assets_relationships_and_events(
        repository_factory,
    ) -> None:
        """Save and load graph truth without deriving extra relationships."""
        repository = repository_factory()
        graph = AssetRelationshipGraph()
        for asset in (
            _equity("ASSET_A", "A"),
            _equity("ASSET_B", "B"),
            _equity("ASSET_C", "C"),
        ):
            graph.add_asset(asset)

        graph.add_relationship("ASSET_A", "ASSET_B", "directed_alpha", 0.4)
        graph.add_relationship("ASSET_B", "ASSET_A", "directed_alpha", 0.9)
        graph.add_relationship("ASSET_A", "ASSET_C", "directed_beta", -0.2)
        graph.add_regulatory_event(_event("EVENT_A", "ASSET_A", ["ASSET_C", "ASSET_B", "ASSET_B"]))

        repository.save_graph(graph)
        repository.session.commit()

        reader = repository_factory()
        loaded = reader.load_graph()

        assert set(loaded.assets) == {"ASSET_A", "ASSET_B", "ASSET_C"}
        assert _relationship_strength(loaded, "ASSET_A", "ASSET_B", "directed_alpha") == pytest.approx(0.4)
        assert _relationship_strength(loaded, "ASSET_B", "ASSET_A", "directed_alpha") == pytest.approx(0.9)
        assert _relationship_strength(loaded, "ASSET_A", "ASSET_C", "directed_beta") == pytest.approx(-0.2)
        assert "ASSET_C" not in loaded.relationships

        assert len(loaded.regulatory_events) == 1
        loaded_event = loaded.regulatory_events[0]
        assert loaded_event.id == "EVENT_A"
        assert loaded_event.asset_id == "ASSET_A"
        assert loaded_event.event_type == RegulatoryActivity.SEC_FILING
        assert loaded_event.date == "2024-01-15"
        assert loaded_event.description == "EVENT_A filing"
        assert loaded_event.impact_score == pytest.approx(0.5)
        assert loaded_event.related_assets == ["ASSET_B", "ASSET_C"]

    @staticmethod
    def test_save_graph_replaces_previous_snapshot_and_removes_stale_rows(
        repository_factory,
    ) -> None:
        """Save a smaller graph and remove rows absent from the new snapshot."""
        repository = repository_factory()
        first_graph = AssetRelationshipGraph()
        for asset in (
            _equity("KEEP", "KEEP"),
            _equity("REMOVE", "REMOVE"),
            _equity("RELATED", "RELATED"),
        ):
            first_graph.add_asset(asset)
        first_graph.add_relationship("KEEP", "REMOVE", "old_edge", 0.6)
        first_graph.add_regulatory_event(_event("OLD_EVENT", "REMOVE", ["KEEP"]))

        repository.save_graph(first_graph)
        repository.session.commit()

        second_graph = AssetRelationshipGraph()
        for asset in (_equity("KEEP", "KEEP"), _equity("RELATED", "RELATED")):
            second_graph.add_asset(asset)
        second_graph.add_relationship("KEEP", "RELATED", "new_edge", 0.7)
        second_graph.add_regulatory_event(_event("NEW_EVENT", "KEEP", ["RELATED"]))

        repository.save_graph(second_graph)
        repository.session.commit()

        reader = repository_factory()
        loaded = reader.load_graph()
        relationships = reader.list_relationships()
        events = reader.list_regulatory_events()

        assert set(loaded.assets) == {"KEEP", "RELATED"}
        assert "REMOVE" not in loaded.assets
        assert [(rel.source_id, rel.target_id, rel.relationship_type) for rel in relationships] == [
            ("KEEP", "RELATED", "new_edge")
        ]
        assert all("REMOVE" not in {rel.source_id, rel.target_id} for rel in relationships)
        assert [event.id for event in events] == ["NEW_EVENT"]
        assert all(event.asset_id != "REMOVE" for event in events)

    @staticmethod
    def test_load_graph_expands_legacy_bidirectional_row_without_explicit_reverse(
        repository_factory,
    ) -> None:
        """Expand one legacy bidirectional row when no explicit reverse exists."""
        repository = repository_factory()
        repository.upsert_asset(_equity("LEGACY_A", "LA"))
        repository.upsert_asset(_equity("LEGACY_B", "LB"))
        repository.add_or_update_relationship(
            "LEGACY_A",
            "LEGACY_B",
            "same_sector",
            0.7,
            bidirectional=True,
        )
        repository.session.commit()

        reader = repository_factory()
        loaded = reader.load_graph()

        assert _relationship_strength(loaded, "LEGACY_A", "LEGACY_B", "same_sector") == pytest.approx(0.7)
        assert _relationship_strength(loaded, "LEGACY_B", "LEGACY_A", "same_sector") == pytest.approx(0.7)

    @staticmethod
    def test_load_graph_preserves_explicit_reverse_strength_over_legacy_expansion(
        repository_factory,
    ) -> None:
        """Keep an explicit reverse row instead of synthesizing a duplicate."""
        repository = repository_factory()
        repository.upsert_asset(_equity("PAIR_A", "PA"))
        repository.upsert_asset(_equity("PAIR_B", "PB"))
        repository.add_or_update_relationship(
            "PAIR_A",
            "PAIR_B",
            "same_sector",
            0.7,
            bidirectional=True,
        )
        repository.add_or_update_relationship(
            "PAIR_B",
            "PAIR_A",
            "same_sector",
            0.2,
            bidirectional=False,
        )
        repository.session.commit()

        reader = repository_factory()
        loaded = reader.load_graph()

        assert _relationship_count(loaded, "PAIR_A", "PAIR_B", "same_sector") == 1
        assert _relationship_count(loaded, "PAIR_B", "PAIR_A", "same_sector") == 1
        assert _relationship_strength(loaded, "PAIR_A", "PAIR_B", "same_sector") == pytest.approx(0.7)
        assert _relationship_strength(loaded, "PAIR_B", "PAIR_A", "same_sector") == pytest.approx(0.2)

        normalizer = repository_factory()
        normalizer.save_graph(loaded)
        normalizer.session.commit()

        verifier = repository_factory()
        relationship_records = verifier.list_relationships()
        assert len(relationship_records) == 2
        assert all(not record.bidirectional for record in relationship_records)
        persisted_strengths = {
            (record.source_id, record.target_id, record.relationship_type): record.strength
            for record in relationship_records
        }
        assert persisted_strengths.keys() == {
            ("PAIR_A", "PAIR_B", "same_sector"),
            ("PAIR_B", "PAIR_A", "same_sector"),
        }
        assert persisted_strengths[("PAIR_A", "PAIR_B", "same_sector")] == pytest.approx(0.7)
        assert persisted_strengths[("PAIR_B", "PAIR_A", "same_sector")] == pytest.approx(0.2)

        reloaded = verifier.load_graph()
        assert _relationship_count(reloaded, "PAIR_A", "PAIR_B", "same_sector") == 1
        assert _relationship_count(reloaded, "PAIR_B", "PAIR_A", "same_sector") == 1
        assert _relationship_strength(reloaded, "PAIR_A", "PAIR_B", "same_sector") == pytest.approx(0.7)
        assert _relationship_strength(reloaded, "PAIR_B", "PAIR_A", "same_sector") == pytest.approx(0.2)

    @staticmethod
    def test_replace_regulatory_events_rejects_duplicate_ids_before_deleting_existing_rows(
        repository_factory,
    ) -> None:
        """Reject duplicate incoming event IDs before destructive replacement."""
        repository = repository_factory()
        repository.upsert_asset(_equity("EVENT_ASSET", "EA"))
        repository.upsert_regulatory_event(_event("EXISTING_EVENT", "EVENT_ASSET"))
        repository.session.commit()

        with pytest.raises(ValueError, match="duplicate event IDs"):
            repository.replace_regulatory_events(
                [
                    _event("DUP_EVENT", "EVENT_ASSET"),
                    _event("OTHER_EVENT", "EVENT_ASSET"),
                    _event("DUP_EVENT", "EVENT_ASSET"),
                ]
            )

        events = repository.list_regulatory_events()
        assert [event.id for event in events] == ["EXISTING_EVENT"]
        assert all(event.id != "DUP_EVENT" for event in events)

    @staticmethod
    def test_upsert_assets_reuses_created_orm_for_duplicate_incoming_ids(
        repository_factory,
    ) -> None:
        """Use one ORM row for duplicate incoming IDs and keep last value."""
        repository = repository_factory()
        first_asset = _equity("DUP_ASSET", "FIRST")
        second_asset = _equity("DUP_ASSET", "SECOND", sector="Finance")
        second_asset.price = 250.0
        second_asset.name = "Second Equity"

        repository.upsert_assets([first_asset, second_asset])
        repository.session.commit()

        assets = repository.list_assets()
        assert len(assets) == 1
        assert assets[0].id == "DUP_ASSET"
        assert assets[0].symbol == "SECOND"
        assert assets[0].name == "Second Equity"
        assert assets[0].sector == "Finance"
        assert assets[0].price == pytest.approx(250.0)

    @staticmethod
    def test_save_load_graph_preserves_bond_commodity_and_currency_subtypes(repository_factory) -> None:
        """Persist and restore non-equity asset subtypes without losing fields."""
        repository = repository_factory()
        graph = AssetRelationshipGraph()
        bond = Bond(
            id="BOND_1",
            symbol="B1",
            name="Bond One",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Finance",
            price=101.5,
            yield_to_maturity=0.031,
            coupon_rate=0.028,
            maturity_date="2031-06-01",
            credit_rating="AA",
            issuer_id="ISSUER_1",
        )
        commodity = Commodity(
            id="COMMODITY_1",
            symbol="C1",
            name="Commodity One",
            asset_class=AssetClass.COMMODITY,
            sector="Materials",
            price=55.0,
            contract_size=100.0,
            delivery_date="2025-09-30",
            volatility=0.25,
        )
        currency = Currency(
            id="CURRENCY_1",
            symbol="CU1",
            name="Currency One",
            asset_class=AssetClass.CURRENCY,
            sector="Currency",
            price=1.05,
            exchange_rate=1.05,
            country="Eurozone",
            central_bank_rate=0.04,
        )
        for asset in (bond, commodity, currency):
            graph.add_asset(asset)

        repository.save_graph(graph)
        repository.session.commit()

        loaded = repository_factory().load_graph()
        loaded_bond = loaded.assets["BOND_1"]
        loaded_commodity = loaded.assets["COMMODITY_1"]
        loaded_currency = loaded.assets["CURRENCY_1"]

        assert isinstance(loaded_bond, Bond)
        assert loaded_bond.issuer_id == "ISSUER_1"
        assert loaded_bond.yield_to_maturity == pytest.approx(0.031)
        assert loaded_bond.coupon_rate == pytest.approx(0.028)
        assert loaded_bond.maturity_date == "2031-06-01"
        assert loaded_bond.credit_rating == "AA"
        assert isinstance(loaded_commodity, Commodity)
        assert loaded_commodity.contract_size == pytest.approx(100.0)
        assert loaded_commodity.delivery_date == "2025-09-30"
        assert loaded_commodity.volatility == pytest.approx(0.25)
        assert isinstance(loaded_currency, Currency)
        assert loaded_currency.exchange_rate == pytest.approx(1.05)
        assert loaded_currency.country == "Eurozone"
        assert loaded_currency.central_bank_rate == pytest.approx(0.04)

    @staticmethod
    def test_save_graph_replaces_existing_snapshot_with_empty_graph(repository_factory) -> None:
        """Saving an empty graph should remove all previously persisted rows."""
        repository = repository_factory()
        graph = AssetRelationshipGraph()
        graph.add_asset(_equity("KEEP", "KEEP"))
        graph.add_regulatory_event(_event("KEEP_EVENT", "KEEP"))
        graph.add_relationship("KEEP", "KEEP", "self", 0.0)

        repository.save_graph(graph)
        repository.session.commit()

        repository.save_graph(AssetRelationshipGraph())
        repository.session.commit()

        reloaded = repository_factory().load_graph()
        assert reloaded.assets == {}
        assert reloaded.relationships == {}
        assert reloaded.regulatory_events == []

    @staticmethod
    def test_save_graph_handles_assets_only_graph(repository_factory) -> None:
        """Saving assets without relationships or events should round-trip cleanly."""
        repository = repository_factory()
        graph = AssetRelationshipGraph()
        graph.add_asset(_equity("ASSET_ONLY_1", "A1"))
        graph.add_asset(_equity("ASSET_ONLY_2", "A2", sector="Healthcare"))
        repository.save_graph(graph)
        repository.session.commit()

        loaded = repository_factory().load_graph()
        assert set(loaded.assets) == {"ASSET_ONLY_1", "ASSET_ONLY_2"}
        assert loaded.relationships == {}
        assert loaded.regulatory_events == []

    @staticmethod
    def test_save_graph_preserves_empty_related_assets_on_regulatory_events(repository_factory) -> None:
        """Events with no related assets should persist as empty collections."""
        repository = repository_factory()
        graph = AssetRelationshipGraph()
        graph.add_asset(_equity("EVENT_ONLY", "EO"))
        graph.add_regulatory_event(_event("EVENT_EMPTY", "EVENT_ONLY", []))
        repository.save_graph(graph)
        repository.session.commit()

        loaded_event = repository_factory().list_regulatory_events()[0]
        assert loaded_event.related_assets == []

    @staticmethod
    def test_replace_relationships_supports_boundary_strengths(repository_factory) -> None:
        """Relationship persistence should round-trip boundary strength values."""
        repository = repository_factory()
        graph = AssetRelationshipGraph()
        graph.add_asset(_equity("SRC", "SRC"))
        graph.add_asset(_equity("DST", "DST"))
        graph.add_relationship("SRC", "DST", "boundary_zero", 0.0)
        graph.add_relationship("SRC", "DST", "boundary_one", 1.0)
        graph.add_relationship("SRC", "DST", "boundary_negative", -1.0)

        repository.save_graph(graph)
        repository.session.commit()

        strengths = {record.relationship_type: record.strength for record in repository.list_relationships()}
        assert strengths == {
            "boundary_zero": pytest.approx(0.0),
            "boundary_one": pytest.approx(1.0),
            "boundary_negative": pytest.approx(-1.0),
        }
