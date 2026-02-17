"""Integration tests covering repository CRUD flows using migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.data.repository import AssetGraphRepository
from src.models.financial_models import (
    AssetClass,
    Bond,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)

pytest.importorskip("sqlalchemy")


def _apply_migration(database_path: Path) -> None:
    """
    Apply database migrations by executing the initial SQL script.

    The migration script is static/trusted (repository-owned), not user-controlled.
    """
    migrations_path = (
        Path(__file__).resolve().parents[2] / "migrations" / "001_initial.sql"
    )
    sql = migrations_path.read_text(encoding="utf-8")

    # executescript() is required for multi-statement DDL migrations.
    with sqlite3.connect(database_path) as connection:
        connection.executescript(sql)  # nosec pythonsecurity:S3649


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """
    Provide a SQLAlchemy session connected to a temporary SQLite database
    with initial migrations applied.
    """
    db_path = tmp_path / "repository.db"
    _apply_migration(db_path)

    engine: Engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False)

    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_asset_crud_flow(db_session: Session) -> None:
    """CRUD operations for Asset entities: create, read, update, delete."""
    repo = AssetGraphRepository(db_session)

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
    db_session.commit()
    db_session.expire_all()

    assets = repo.get_assets_map()
    assert assets["EQ1"].name == "Equity One"  # nosec B101

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
    db_session.commit()
    db_session.expire_all()

    assets = repo.get_assets_map()
    assert assets["EQ1"].price == pytest.approx(120.0)  # nosec B101
    assert assets["EQ1"].market_cap == pytest.approx(1_200_000.0)  # nosec B101

    repo.delete_asset("EQ1")
    db_session.commit()
    db_session.expire_all()

    assets = repo.get_assets_map()
    assert "EQ1" not in assets  # nosec B101


def test_relationship_and_event_crud_flow(db_session: Session) -> None:
    """CRUD operations for relationships and regulatory events."""
    repo = AssetGraphRepository(db_session)

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
    db_session.commit()
    db_session.expire_all()

    # NOTE: The original test inserted strength=0.5 but asserted 0.8.
    # Align the setup with the assertion so this is a meaningful CRUD check.
    repo.add_or_update_relationship(
        "PARENT",
        "PARENT_BOND",
        "test",
        0.8,
        bidirectional=False,
    )
    db_session.commit()
    db_session.expire_all()

    relationships = repo.list_relationships()
    assert len(relationships) == 1  # nosec B101
    assert relationships[0].strength == pytest.approx(0.8)  # nosec B101

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
    db_session.commit()
    db_session.expire_all()

    events = repo.list_regulatory_events()
    assert len(events) == 1  # nosec B101
    assert events[0].related_assets == ["PARENT_BOND"]  # nosec B101

    repo.delete_regulatory_event("EVT1")
    db_session.commit()
    db_session.expire_all()
    assert repo.list_regulatory_events() == []  # nosec B101

    repo.delete_relationship("PARENT", "PARENT_BOND", "test")
    db_session.commit()
    db_session.expire_all()
    assert repo.list_relationships() == []  # nosec B101
