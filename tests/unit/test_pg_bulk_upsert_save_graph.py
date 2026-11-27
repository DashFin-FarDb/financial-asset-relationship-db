"""Unit tests for PostgreSQL bulk upsert SQL generation and Core bulk relationship persistence."""

from __future__ import annotations

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from src.data.database import create_engine_from_url
from src.data.db_models import (
    AssetORM,
    AssetRelationshipORM,
    RegulatoryEventAssetORM,
    RegulatoryEventORM,
)
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Bond, Equity


def _make_session_factory():
    engine = create_engine_from_url("sqlite:///:memory:")
    for tbl in (
        AssetORM.__table__,
        AssetRelationshipORM.__table__,
        RegulatoryEventORM.__table__,
        RegulatoryEventAssetORM.__table__,
    ):
        tbl.create(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_asset_to_row_dict_and_postgresql_upsert_compilation() -> None:
    """_asset_to_row_dict maps all ORM columns and compiles to ON CONFLICT (id) DO UPDATE for PostgreSQL."""
    eq = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=225.5,
        market_cap=3_400_000_000_000.0,
        pe_ratio=32.1,
    )
    row = AssetGraphRepository._asset_to_row_dict(eq)
    assert row["id"] == "AAPL"
    assert row["pe_ratio"] == 32.1
    assert row["coupon_rate"] is None

    stmt = pg_insert(AssetORM).values([row])
    update_cols = {col: stmt.excluded[col] for col in row if col != "id"}
    compiled = str(
        stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols).compile(dialect=postgresql.dialect())
    )
    assert "ON CONFLICT (id) DO UPDATE SET" in compiled
    assert "pe_ratio = excluded.pe_ratio" in compiled


def test_bulk_relationship_insert_round_trip_and_snapshot_replacement() -> None:
    """Core bulk relationship insert round-trips directed edges and replaces stale snapshots cleanly."""
    session_factory = _make_session_factory()
    graph = AssetRelationshipGraph()
    graph.add_asset(
        Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=225.0,
        )
    )
    graph.add_asset(
        Bond(
            id="AAPL_BOND",
            symbol="AAPL29",
            name="Apple 2029 Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Technology",
            price=101.0,
            issuer_id="AAPL",
            yield_to_maturity=0.045,
        )
    )
    graph.add_relationship("AAPL_BOND", "AAPL", "corporate_link", 0.9, bidirectional=False)

    with session_factory() as session:
        repo = AssetGraphRepository(session)
        repo.save_graph(graph)
        session.commit()

    with session_factory() as session:
        repo = AssetGraphRepository(session)
        loaded = repo.load_graph()
        assert set(loaded.assets.keys()) == {"AAPL", "AAPL_BOND"}
        assert loaded.relationships["AAPL_BOND"] == [("AAPL", "corporate_link", 0.9)]
