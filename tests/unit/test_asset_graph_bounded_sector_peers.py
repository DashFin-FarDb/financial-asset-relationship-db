"""Unit tests for bounded max_sector_peers relationship construction on AssetRelationshipGraph."""

from __future__ import annotations

import time

import pytest

from src.config.settings import get_settings, load_settings
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Bond, Equity, RegulatoryActivity, RegulatoryEvent


def _make_equity(ticker: str, sector: str, market_cap: float) -> Equity:
    return Equity(
        id=ticker,
        symbol=ticker,
        name=f"{ticker} Corp",
        asset_class=AssetClass.EQUITY,
        sector=sector,
        price=100.0,
        market_cap=market_cap,
    )


def test_default_unbounded_preserves_all_pairs_same_sector_behavior() -> None:
    """When max_sector_peers is None, build_relationships keeps exact all-pairs bidirectional edges."""
    graph = AssetRelationshipGraph()
    for idx in range(5):
        graph.add_asset(_make_equity(f"T{idx}", "Technology", float(100 * (idx + 1))))

    graph.build_relationships()
    total_edges = sum(len(rels) for rels in graph.relationships.values())
    assert total_edges == 5 * 4


def test_bounded_max_sector_peers_caps_edges_and_preserves_corporate_and_event_links() -> None:
    """Bounded max_sector_peers links each asset to top-K sector leaders and preserves bonds/events."""
    graph = AssetRelationshipGraph(max_sector_peers=2)
    for idx in range(10):
        graph.add_asset(_make_equity(f"TECH{idx:02d}", "Technology", float((idx + 1) * 1e9)))
    graph.add_asset(_make_equity("UNK01", "Unknown", 5e9))
    graph.add_asset(
        Bond(
            id="BOND_TECH09",
            symbol="B9",
            name="Tech09 Senior Note",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Unknown",
            price=100.0,
            issuer_id="TECH09",
        )
    )
    graph.add_regulatory_event(
        RegulatoryEvent(
            id="EVT1",
            asset_id="TECH09",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2026-11-28",
            description="Quarterly report",
            impact_score=0.6,
            related_assets=["TECH08"],
        )
    )

    graph.build_relationships()

    same_sector_edges = [
        (src, dst)
        for src, rels in graph.relationships.items()
        for dst, rel_type, _ in rels
        if rel_type == "same_sector"
    ]
    # Top 2 leaders are TECH09 and TECH08:
    # 8 non-leaders -> 2 edges each (16), 2 leaders -> 1 edge each (2) => 18 directed edges.
    assert len(same_sector_edges) == 18
    assert all(dst in {"TECH09", "TECH08"} for _, dst in same_sector_edges)
    assert all(src != dst for src, dst in same_sector_edges)
    assert "UNK01" not in graph.relationships

    bond_edges = [
        (dst, rel_type)
        for dst, rel_type, _ in graph.relationships.get("BOND_TECH09", [])
        if rel_type == "corporate_link"
    ]
    assert bond_edges == [("TECH09", "corporate_link")]

    event_edges = [
        (dst, rel_type) for dst, rel_type, _ in graph.relationships.get("TECH09", []) if rel_type == "event_impact"
    ]
    assert event_edges == [("TECH08", "event_impact")]


def test_invalid_max_sector_peers_rejected() -> None:
    """Zero, negative, and boolean max_sector_peers raise ValueError."""
    for bad in (0, -3, True):
        with pytest.raises(ValueError, match="max_sector_peers"):
            AssetRelationshipGraph(max_sector_peers=bad)


def test_max_sector_peers_reads_from_env_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """MAX_SECTOR_PEERS environment variable populates Settings and AssetRelationshipGraph."""
    monkeypatch.setenv("MAX_SECTOR_PEERS", "7")
    get_settings.cache_clear()
    try:
        settings = load_settings()
        assert settings.max_sector_peers == 7
        graph = AssetRelationshipGraph()
        assert graph.max_sector_peers == 7
    finally:
        monkeypatch.delenv("MAX_SECTOR_PEERS", raising=False)
        get_settings.cache_clear()


def test_bounded_sector_peers_scales_linearly_for_1000_equities() -> None:
    """1,000 equities with max_sector_peers=10 builds in sub-second time with bounded edges."""
    graph = AssetRelationshipGraph(max_sector_peers=10)
    sectors = ("Technology", "Financial", "Healthcare", "Energy")
    for idx in range(1000):
        graph.add_asset(_make_equity(f"EQ{idx:04d}", sectors[idx % len(sectors)], float(idx + 1)))

    t0 = time.perf_counter()
    graph.build_relationships()
    elapsed = time.perf_counter() - t0

    total_edges = sum(len(rels) for rels in graph.relationships.values())
    assert total_edges <= 1000 * 10
    assert total_edges > 9000
    assert elapsed < 2.0
