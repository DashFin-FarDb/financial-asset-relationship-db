"""Shared fixtures and graph builders for snapshot attestation unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text

from src.data.database import configure_sqlite_engine, create_session_factory, init_db
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import (
    AssetClass,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)


def create_sample_equity_pair() -> tuple[Equity, Equity]:
    """Create a deterministic pair of equities (AAPL, MSFT) for testing."""
    eq_a = Equity(
        id="AAPL",
        symbol="AAPL.US",
        name="Apple Inc. Fixture",
        asset_class=AssetClass.EQUITY,
        sector="Consumer Electronics",
        price=192.25,
        currency="USD",
        market_cap=2900000000000.0,
    )
    eq_b = Equity(
        id="MSFT",
        symbol="MSFT.US",
        name="Microsoft Corporation Fixture",
        asset_class=AssetClass.EQUITY,
        sector="Software Infrastructure",
        price=415.50,
        currency="USD",
        market_cap=3150000000000.0,
    )
    return eq_a, eq_b


def create_sample_test_graph() -> AssetRelationshipGraph:
    """Create a deterministic graph with assets, relationships, and regulatory events."""
    graph = AssetRelationshipGraph()
    aapl, msft = create_sample_equity_pair()
    graph.add_asset(aapl)
    graph.add_asset(msft)
    graph.add_relationship("AAPL", "MSFT", "same_sector", 0.50, bidirectional=True)
    reg_event = RegulatoryEvent(
        id="REG-001",
        asset_id="AAPL",
        event_type=RegulatoryActivity.REGULATORY_FILING,
        date="2026-04-10",
        description="Annual 10-K filing",
        impact_score=0.10,
        related_assets=["MSFT"],
    )
    graph.add_regulatory_event(reg_event)
    return graph


def setup_disposable_sqlite_db(
    tmp_path: Path,
    prefix: str = "test_gate",
    *,
    wal_mode: bool = False,
) -> tuple[str, Any]:
    """Initialize a disposable SQLite test database with session factory."""
    db_file = tmp_path / f"{prefix}_{uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"
    engine = configure_sqlite_engine(create_engine(db_url, future=True))
    if wal_mode:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.commit()
    init_db(engine)
    session_factory = create_session_factory(engine)
    return db_url, session_factory
