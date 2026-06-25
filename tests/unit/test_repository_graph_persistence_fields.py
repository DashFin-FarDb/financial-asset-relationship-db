"""Field equality checks for repository graph persistence."""

import pytest
from sqlalchemy import create_engine

from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity, RegulatoryActivity, RegulatoryEvent
from tests.conftest import enable_sqlite_foreign_keys

pytestmark = pytest.mark.unit


def test_repository_round_trip_preserves_asset_fields(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'fields.db'}")
    enable_sqlite_foreign_keys(engine)
    init_db(engine)
    factory = create_session_factory(engine)
    session = factory()
    try:
        repo = AssetGraphRepository(session)
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="EQ_FULL",
                symbol="EQF",
                name="Full Fidelity Equity",
                asset_class=AssetClass.EQUITY,
                sector="Healthcare",
                price=123.45,
                currency="gbp",
            )
        )
        repo.save_graph(graph)
        session.commit()
    finally:
        session.close()

    reader_session = factory()
    try:
        loaded = AssetGraphRepository(reader_session).load_graph()
    finally:
        reader_session.close()
        engine.dispose()

    asset = loaded.assets["EQ_FULL"]
    assert asset.symbol == "EQF"
    assert asset.name == "Full Fidelity Equity"
    assert asset.sector == "Healthcare"
    assert asset.price == pytest.approx(123.45)
    assert asset.currency == "GBP"
    assert asset.asset_class == AssetClass.EQUITY


def test_repository_round_trip_preserves_regulatory_event_fields(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    enable_sqlite_foreign_keys(engine)
    init_db(engine)
    factory = create_session_factory(engine)
    session = factory()
    try:
        repo = AssetGraphRepository(session)
        graph = AssetRelationshipGraph()
        for asset_id in ("EQ_FULL", "REL_A", "REL_B"):
            graph.add_asset(
                Equity(
                    id=asset_id,
                    symbol=asset_id,
                    name=f"{asset_id} Equity",
                    asset_class=AssetClass.EQUITY,
                    sector="Technology",
                    price=100.0,
                )
            )
        graph.add_regulatory_event(
            RegulatoryEvent(
                id="EVENT_FULL",
                asset_id="EQ_FULL",
                event_type=RegulatoryActivity.SEC_FILING,
                date="2025-05-20",
                description="Field-level persistence fidelity event",
                impact_score=-0.25,
                related_assets=["REL_B", "REL_A", "REL_B"],
            )
        )
        repo.save_graph(graph)
        session.commit()
    finally:
        session.close()

    reader_session = factory()
    try:
        loaded = AssetGraphRepository(reader_session).load_graph()
    finally:
        reader_session.close()
        engine.dispose()

    event = loaded.regulatory_events[0]
    assert event.id == "EVENT_FULL"
    assert event.asset_id == "EQ_FULL"
    assert event.event_type == RegulatoryActivity.SEC_FILING
    assert event.impact_score == pytest.approx(-0.25)
    assert event.related_assets == ["REL_A", "REL_B"]
    assert event.date == "2025-05-20"
    assert event.description == "Field-level persistence fidelity event"
