"""Shared helpers for restart-recovery integration tests."""

from pathlib import Path

from sqlalchemy import create_engine

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity
from tests.integration.facade import AssetGraphRepository, create_session_factory, init_db, session_scope

LOCK_NAME = "graph_rebuild"
LOCK_TTL = 300


def database(tmp_path: Path):
    db_url = f"sqlite:///{tmp_path / 'restart-recovery.db'}"
    engine = create_engine(db_url)
    init_db(engine)
    return db_url, engine, create_session_factory(engine)


def graph() -> AssetRelationshipGraph:
    asset_graph = AssetRelationshipGraph()
    for asset_id in ("ASSET_A", "ASSET_B", "ASSET_C"):
        asset_graph.add_asset(
            Equity(
                id=asset_id,
                symbol=asset_id,
                name=f"{asset_id} Equity",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0,
            )
        )
    asset_graph.add_relationship("ASSET_A", "ASSET_B", "observed", 0.4, bidirectional=False)
    asset_graph.add_relationship("ASSET_B", "ASSET_C", "observed", 0.6, bidirectional=False)
    return asset_graph


def persist_graph(session_factory, asset_graph: AssetRelationshipGraph) -> None:
    with session_scope(session_factory) as session:
        AssetGraphRepository(session).save_graph(asset_graph)


def assert_graph_contents(asset_graph: AssetRelationshipGraph) -> None:
    assert set(asset_graph.assets) == {"ASSET_A", "ASSET_B", "ASSET_C"}
    assert asset_graph.assets["ASSET_A"].name == "ASSET_A Equity"
    assert asset_graph.assets["ASSET_A"].price == 100.0
    assert sum(len(edges) for edges in asset_graph.relationships.values()) == 2
