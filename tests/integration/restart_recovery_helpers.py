"""Shared helpers for restart-recovery integration tests."""

from pathlib import Path

from sqlalchemy import create_engine

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity
from tests.integration.facade import (
    AssetGraphRepository,
    create_session_factory,
    init_db,
    session_scope,
)

LOCK_NAME = "graph_rebuild"
LOCK_TTL = 300


def database(tmp_path: Path):
    """Create an isolated restart-recovery database."""
    db_url = f"sqlite:///{tmp_path / 'restart-recovery.db'}"
    engine = create_engine(db_url)
    init_db(engine)
    return db_url, engine, create_session_factory(engine)


def graph() -> AssetRelationshipGraph:
    """Build a deterministic graph for restart-recovery persistence tests."""
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
    asset_graph.add_relationship(
        "ASSET_A",
        "ASSET_B",
        "observed",
        0.4,
        bidirectional=False,
    )
    asset_graph.add_relationship(
        "ASSET_B",
        "ASSET_C",
        "observed",
        0.6,
        bidirectional=False,
    )
    return asset_graph


def persist_graph(session_factory, asset_graph: AssetRelationshipGraph) -> None:
    """Persist a graph through the repository seam used by restart tests."""
    with session_scope(session_factory) as session:
        AssetGraphRepository(session).save_graph(asset_graph)


def assert_graph_contents(asset_graph: AssetRelationshipGraph) -> None:
    """Assert persisted graph fidelity for assets and directed relationships."""
    expected_assets = {
        "ASSET_A": ("ASSET_A", "ASSET_A Equity", AssetClass.EQUITY, "Technology", 100.0),
        "ASSET_B": ("ASSET_B", "ASSET_B Equity", AssetClass.EQUITY, "Technology", 100.0),
        "ASSET_C": ("ASSET_C", "ASSET_C Equity", AssetClass.EQUITY, "Technology", 100.0),
    }
    assert set(asset_graph.assets) == set(expected_assets)
    for asset_id, expected in expected_assets.items():
        asset = asset_graph.assets[asset_id]
        assert (
            asset.symbol,
            asset.name,
            asset.asset_class,
            asset.sector,
            asset.price,
        ) == expected

    relationships = {
        (source_id, target_id, relationship_type, strength)
        for source_id, edges in asset_graph.relationships.items()
        for target_id, relationship_type, strength in edges
    }
    assert relationships == {
        ("ASSET_A", "ASSET_B", "observed", 0.4),
        ("ASSET_B", "ASSET_C", "observed", 0.6),
    }
