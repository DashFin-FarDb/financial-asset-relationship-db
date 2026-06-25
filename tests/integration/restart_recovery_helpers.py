"""Shared helpers for restart-recovery integration tests."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

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
_ASSET_SPECS: tuple[tuple[str, str, AssetClass, str, float], ...] = (
    ("ASSET_A", "ASSET_A Equity", AssetClass.EQUITY, "Technology", 100.0),
    ("ASSET_B", "ASSET_B Equity", AssetClass.EQUITY, "Technology", 100.0),
    ("ASSET_C", "ASSET_C Equity", AssetClass.EQUITY, "Technology", 100.0),
)
_RELATIONSHIP_SPECS: tuple[tuple[str, str, str, float], ...] = (
    ("ASSET_A", "ASSET_B", "observed", 0.4),
    ("ASSET_B", "ASSET_C", "observed", 0.6),
)


def database(tmp_path: Path) -> tuple[str, Engine, sessionmaker[Session]]:
    """Create an initialized restart-recovery database and session factory.

    The returned URL is suitable for startup configuration, while the engine and
    session factory let tests seed persisted graph state and dispose resources.
    """
    db_url = f"sqlite:///{tmp_path / 'restart-recovery.db'}"
    engine = create_engine(db_url)
    init_db(engine)
    return db_url, engine, create_session_factory(engine)


def graph() -> AssetRelationshipGraph:
    """Build the deterministic graph expected to survive restart recovery.

    The graph intentionally includes three assets and two directed relationships
    so tests can verify persistence fidelity across startup load boundaries.
    """
    asset_graph = AssetRelationshipGraph()
    for asset_id, name, asset_class, sector, price in _ASSET_SPECS:
        asset_graph.add_asset(
            Equity(
                id=asset_id,
                symbol=asset_id,
                name=name,
                asset_class=asset_class,
                sector=sector,
                price=price,
            )
        )
    for source_id, target_id, relationship_type, strength in _RELATIONSHIP_SPECS:
        asset_graph.add_relationship(
            source_id,
            target_id,
            relationship_type,
            strength,
            bidirectional=False,
        )
    return asset_graph


def persist_graph(session_factory: sessionmaker[Session], asset_graph: AssetRelationshipGraph) -> None:
    """Persist restart-recovery graph truth through the repository boundary."""
    with session_scope(session_factory) as session:
        AssetGraphRepository(session).save_graph(asset_graph)


def assert_graph_contents(asset_graph: AssetRelationshipGraph) -> None:
    """Assert the restart-recovery graph loaded with full asset and edge fidelity."""
    expected_assets = {
        asset_id: (asset_id, name, asset_class, sector, price)
        for asset_id, name, asset_class, sector, price in _ASSET_SPECS
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
    assert relationships == set(_RELATIONSHIP_SPECS)
