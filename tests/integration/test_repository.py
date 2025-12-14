"""Integration tests covering repository CRUD flows using migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.repository import AssetGraphRepository
from src.models.financial_models import AssetClass, Bond, Equity, RegulatoryActivity, RegulatoryEvent


def _apply_migration(database_path: Path) -> None:
    sql = Path("migrations/001_initial.sql").read_text(encoding="utf-8")
    with sqlite3.connect(database_path) as connection:
        connection.executescript(sql)


@pytest.fixture
def session(tmp_path):
    db_path = tmp_path / "repository.db"
    _apply_migration(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_asset_crud_flow(session):
    repo = AssetGraphRepository(session)

    equity = Equity(
        id="EQ1",
        symbol="EQ1",
        name="Equity One",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=100.0,
        market_cap=1_000_000.0,
        pe_ratio=20.0,
    )

    repo.upsert_asset(equity)
    session.commit()
    session.expire_all()

    assets = repo.get_assets_map()
    assert assets["EQ1"].name == "Equity One"

    updated_equity = Equity(
        id="EQ1",
        symbol="EQ1",
        name="Equity One",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=120.0,
        market_cap=1_200_000.0,
        pe_ratio=22.0,
    )

    repo.upsert_asset(updated_equity)
    session.commit()
    session.expire_all()

    assets = repo.get_assets_map()
    assert assets["EQ1"].price == pytest.approx(120.0)
    assert assets["EQ1"].market_cap == pytest.approx(1_200_000.0)

    repo.delete_asset("EQ1")
    session.commit()
    session.expire_all()

    assets = repo.get_assets_map()
    assert "EQ1" not in assets


def test_relationship_and_event_crud_flow(session):
    repo = AssetGraphRepository(session)

    parent_equity = Equity(
        id="PARENT",
        symbol="PRT",
        name="Parent Corp",
        asset_class=AssetClass.EQUITY,
        sector="Industrial",
        price=90.0,
        market_cap=500_000.0,
        dividend_yield=0.02,
    )
    bond = Bond(
        id="PARENT_BOND",
        symbol="PRTB",
        name="Parent Bond",
        asset_class=AssetClass.FIXED_INCOME,
        sector="Industrial",
        price=101.0,
        yield_to_maturity=0.03,
        coupon_rate=0.028,
        maturity_date="2030-01-01",
        credit_rating="AA",
        issuer_id="PARENT",
    )

    repo.upsert_asset(parent_equity)
    repo.upsert_asset(bond)
    session.commit()
    session.expire_all()

    repo.add_or_update_relationship("PARENT", "PARENT_BOND", "test", 0.5, False)
    repo.add_or_update_relationship("PARENT", "PARENT_BOND", "test", 0.8, False)
    session.commit()
    session.expire_all()

    relationships = repo.list_relationships()
    assert len(relationships) == 1
    assert relationships[0].strength == pytest.approx(0.8)

    event = RegulatoryEvent(
        id="EVT1",
        asset_id="PARENT",
        event_type=RegulatoryActivity.EARNINGS_REPORT,
        date="2024-01-15",
        description="Q4 earnings",
        impact_score=0.6,
        related_assets=["PARENT_BOND"],
    )

    repo.upsert_regulatory_event(event)
    session.commit()
    session.expire_all()

    events = repo.list_regulatory_events()
    assert len(events) == 1
    assert events[0].related_assets == ["PARENT_BOND"]

    repo.delete_regulatory_event("EVT1")
    session.commit()
    session.expire_all()

    assert repo.list_regulatory_events() == []

    repo.delete_relationship("PARENT", "PARENT_BOND", "test")
    session.commit()
    session.expire_all()

    assert repo.list_relationships() == []
