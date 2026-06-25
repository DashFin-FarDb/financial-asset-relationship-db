"""Field equality checks for graph lifecycle persisted startup loads."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as graph_lifecycle_providers
from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity, RegulatoryActivity, RegulatoryEvent

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_graph_lifecycle(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    graph_lifecycle.reset_graph()
    yield
    graph_lifecycle.reset_graph()
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()


def _persist_graph(database_url: str, graph: AssetRelationshipGraph) -> None:
    from tests.conftest import enable_sqlite_foreign_keys

    engine = create_engine(database_url)
    enable_sqlite_foreign_keys(engine)
    try:
        init_db(engine)
        session = create_session_factory(engine)()
        try:
            AssetGraphRepository(session).save_graph(graph)
            session.commit()
        finally:
            session.close()
    finally:
        engine.dispose()


def test_lifecycle_persisted_startup_preserves_full_asset_and_event_fields(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lifecycle-fields.db'}"
    graph = AssetRelationshipGraph()
    for asset_id in ("EQ_FULL", "REL_A", "REL_B"):
        graph.add_asset(
            Equity(
                id=asset_id,
                symbol=f"{asset_id}_SYM",
                name=f"{asset_id} Name",
                asset_class=AssetClass.EQUITY,
                sector="Healthcare" if asset_id == "EQ_FULL" else "Technology",
                price=123.45 if asset_id == "EQ_FULL" else 100.0,
                currency="gbp" if asset_id == "EQ_FULL" else "USD",
            )
        )
    graph.add_regulatory_event(
        RegulatoryEvent(
            id="EVENT_FULL",
            asset_id="EQ_FULL",
            event_type=RegulatoryActivity.SEC_FILING,
            date="2025-05-20",
            description="Lifecycle persistence fidelity event",
            impact_score=0.75,
            related_assets=["REL_B", "REL_A", "REL_B"],
        )
    )
    _persist_graph(database_url, graph)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    loaded, startup_source = graph_lifecycle.get_graph_with_startup_source()

    assert startup_source is not None
    assert startup_source.source == graph_lifecycle.GraphStartupSource.PERSISTED
    asset = loaded.assets["EQ_FULL"]
    assert asset.symbol == "EQ_FULL_SYM"
    assert asset.name == "EQ_FULL Name"
    assert asset.sector == "Healthcare"
    assert asset.price == pytest.approx(123.45)
    assert asset.currency == "GBP"
    assert asset.asset_class == AssetClass.EQUITY

    event = loaded.regulatory_events[0]
    assert event.id == "EVENT_FULL"
    assert event.asset_id == "EQ_FULL"
    assert event.impact_score == pytest.approx(0.75)
    assert event.related_assets == ["REL_A", "REL_B"]
    assert event.date == "2025-05-20"
    assert event.description == "Lifecycle persistence fidelity event"
