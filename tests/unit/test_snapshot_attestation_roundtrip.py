"""Disposable SQLite round-trip test for snapshot attestation digests.

Verifies that an in-memory graph and the graph reloaded through AssetGraphRepository
produce identical canonical attestation digests under RFC 8785 (JCS).
Includes bidirectional relationships, nullable fields, and regulatory events.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine

from src.data.database import configure_sqlite_engine, create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.snapshot_attestation import (
    compute_graph_snapshot_hash,
    compute_repository_snapshot_hash,
    generate_snapshot_canonical_payload,
)
from src.models.financial_models import (
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)

pytestmark = pytest.mark.unit


def test_snapshot_attestation_sqlite_roundtrip(tmp_path: Path) -> None:
    """A published graph and its reloaded repository graph produce identical attestation digests."""
    db_path = tmp_path / "roundtrip_test.db"
    engine = configure_sqlite_engine(create_engine(f"sqlite:///{db_path}", future=True))
    init_db(engine)
    session_factory = create_session_factory(engine)

    # 1. Construct in-memory graph with diverse asset classes, nullables, bidirectional rels, events
    graph = AssetRelationshipGraph()

    # Asset with typical Equity nullable attributes (bond/commodity fields are None)
    aapl = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=180.50,
        market_cap=3000000000000.0,
        currency="USD",
        pe_ratio=28.5,
        dividend_yield=0.0055,
        earnings_per_share=6.42,
    )
    msft = Equity(
        id="MSFT",
        symbol="MSFT",
        name="Microsoft Corporation",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=420.10,
        market_cap=3100000000000.0,
        currency="USD",
        pe_ratio=35.1,
        dividend_yield=0.0072,
        earnings_per_share=11.05,
    )
    # Bond with specific nullable attributes
    corp_bond = Bond(
        id="CORP-BOND-1",
        symbol="CBND1",
        name="Corporate Bond 1",
        asset_class=AssetClass.FIXED_INCOME,
        sector="Corporate",
        price=98.50,
        currency="USD",
        yield_to_maturity=0.052,
        coupon_rate=0.048,
        maturity_date="2030-12-31",
        credit_rating="AA",
        issuer_id="AAPL",
    )
    # Commodity with contract size and delivery date
    gold = Commodity(
        id="GOLD",
        symbol="GC",
        name="Gold Futures",
        asset_class=AssetClass.COMMODITY,
        sector="Metals",
        price=2350.20,
        currency="USD",
        contract_size=100,
        delivery_date="2026-12-01",
        volatility=0.15,
    )
    # Currency with country and central bank rate
    eurusd = Currency(
        id="EURUSD",
        symbol="EUR/USD",
        name="Euro / US Dollar",
        asset_class=AssetClass.CURRENCY,
        sector="Foreign Exchange",
        price=1.0850,
        currency="USD",
        exchange_rate=1.0850,
        country="EU",
        central_bank_rate=0.040,
    )

    graph.add_asset(aapl)
    graph.add_asset(msft)
    graph.add_asset(corp_bond)
    graph.add_asset(gold)
    graph.add_asset(eurusd)

    # Relationships:
    # Bidirectional relationship between AAPL and MSFT
    graph.add_relationship("AAPL", "MSFT", "same_sector", 0.50, bidirectional=True)
    # Directed relationship between CORP-BOND-1 and AAPL
    graph.add_relationship("CORP-BOND-1", "AAPL", "corporate_link", 0.85, bidirectional=False)

    # Regulatory events:
    reg_event_1 = RegulatoryEvent(
        id="REG-001",
        asset_id="AAPL",
        event_type=RegulatoryActivity.REGULATORY_FILING,
        date="2026-04-10",
        description="Antitrust fine imposed by European Commission",
        impact_score=-0.25,
        related_assets=["MSFT"],
    )
    reg_event_2 = RegulatoryEvent(
        id="REG-002",
        asset_id="CORP-BOND-1",
        event_type=RegulatoryActivity.COMPLIANCE_UPDATE,
        date="2026-05-01",
        description="New disclosure requirement for corporate debt",
        impact_score=-0.05,
        related_assets=[],
    )
    graph.add_regulatory_event(reg_event_1)
    graph.add_regulatory_event(reg_event_2)

    # 2. Compute canonical payload and hash for published in-memory graph
    published_canon_str, published_canon_bytes = generate_snapshot_canonical_payload(
        assets=graph.assets.values(),
        relationships=[
            {
                "source_id": s,
                "target_id": t,
                "relationship_type": r,
                "strength": strg,
                "bidirectional": False,
            }
            for s, targets in graph.relationships.items()
            for t, r, strg in targets
        ],
        regulatory_events=graph.regulatory_events,
    )
    published_hash = compute_graph_snapshot_hash(graph)

    # 3. Persist graph snapshot into SQLite via AssetGraphRepository
    with session_factory() as session:
        repo = AssetGraphRepository(session)
        repo.save_graph(graph)
        session.commit()

    # 4. Reload from database and compute canonical payload and hash
    with session_factory() as session:
        repo = AssetGraphRepository(session)
        loaded_graph = repo.load_graph()
        repo_hash = compute_repository_snapshot_hash(repo)

    loaded_hash = compute_graph_snapshot_hash(loaded_graph)

    loaded_canon_str, loaded_canon_bytes = generate_snapshot_canonical_payload(
        assets=loaded_graph.assets.values(),
        relationships=[
            {
                "source_id": s,
                "target_id": t,
                "relationship_type": r,
                "strength": strg,
                "bidirectional": False,
            }
            for s, targets in loaded_graph.relationships.items()
            for t, r, strg in targets
        ],
        regulatory_events=loaded_graph.regulatory_events,
    )

    # 5. Invariant verification
    if published_hash != loaded_hash:
        pytest.fail(
            f"Snapshot attestation digest mismatch!\n"
            f"Published hash: {published_hash}\n"
            f"Loaded hash:    {loaded_hash}\n"
            f"Diff:\nPublished:\n{published_canon_str}\nLoaded:\n{loaded_canon_str}"
        )

    assert published_canon_bytes == loaded_canon_bytes
    assert published_canon_str == loaded_canon_str
    assert published_hash == loaded_hash
    assert published_hash == repo_hash

    # Clean up engine
    engine.dispose()
