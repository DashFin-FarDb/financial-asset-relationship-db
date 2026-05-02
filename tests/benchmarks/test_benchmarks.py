"""Performance benchmarks for the financial asset relationship database.

These benchmarks measure the performance of core operations in the asset graph,
including graph construction, relationship building, metrics calculation, and
visualization data generation.
"""

import pytest

from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import (
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)


def _build_large_graph(num_assets: int) -> AssetRelationshipGraph:
    """Build a graph with the given number of assets across multiple sectors."""
    graph = AssetRelationshipGraph()
    sectors = ["Technology", "Energy", "Finance", "Healthcare", "Consumer"]
    for i in range(num_assets):
        sector = sectors[i % len(sectors)]
        equity = Equity(
            id=f"EQ_{i}",
            symbol=f"SYM{i}",
            name=f"Company {i}",
            asset_class=AssetClass.EQUITY,
            sector=sector,
            price=100.0 + i,
            market_cap=1e9 + i * 1e6,
            pe_ratio=15.0 + (i % 20),
            dividend_yield=0.02,
        )
        graph.add_asset(equity)
    return graph


@pytest.mark.benchmark
def test_bench_create_sample_database(benchmark):
    """Benchmark the creation of the full sample database with all assets and relationships."""

    @benchmark
    def _():
        create_sample_database()


@pytest.mark.benchmark
def test_bench_build_relationships_small(benchmark):
    """Benchmark building relationships for a small graph (19 assets, sample data)."""
    graph = create_sample_database()
    # Reset relationships so we can re-build them
    graph.relationships = {}

    @benchmark
    def _():
        graph.relationships = {}
        graph.build_relationships()


@pytest.mark.benchmark
def test_bench_build_relationships_medium(benchmark):
    """Benchmark building relationships for a medium graph (50 assets)."""
    graph = _build_large_graph(50)

    @benchmark
    def _():
        graph.relationships = {}
        graph.build_relationships()


@pytest.mark.benchmark
def test_bench_build_relationships_large(benchmark):
    """Benchmark building relationships for a large graph (200 assets)."""
    graph = _build_large_graph(200)

    @benchmark
    def _():
        graph.relationships = {}
        graph.build_relationships()


@pytest.mark.benchmark
def test_bench_calculate_metrics(benchmark):
    """Benchmark metrics calculation on the sample database."""
    graph = create_sample_database()

    @benchmark
    def _():
        graph.calculate_metrics()


@pytest.mark.benchmark
def test_bench_calculate_metrics_large(benchmark):
    """Benchmark metrics calculation on a large graph (200 assets)."""
    graph = _build_large_graph(200)
    graph.build_relationships()

    @benchmark
    def _():
        graph.calculate_metrics()


@pytest.mark.benchmark
def test_bench_get_3d_visualization_data(benchmark):
    """Benchmark 3D visualization data generation."""
    graph = create_sample_database()

    @benchmark
    def _():
        graph.get_3d_visualization_data_enhanced()


@pytest.mark.benchmark
def test_bench_add_assets_batch(benchmark):
    """Benchmark adding 100 assets to an empty graph."""

    @benchmark
    def _():
        graph = AssetRelationshipGraph()
        for i in range(100):
            equity = Equity(
                id=f"EQ_{i}",
                symbol=f"SYM{i}",
                name=f"Company {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + i,
            )
            graph.add_asset(equity)


@pytest.mark.benchmark
def test_bench_add_relationships_batch(benchmark):
    """Benchmark adding relationships directly to a graph."""
    graph = _build_large_graph(50)

    @benchmark
    def _():
        graph.relationships = {}
        for i in range(49):
            graph.add_relationship(
                f"EQ_{i}",
                f"EQ_{i + 1}",
                "sequential_link",
                0.5,
                bidirectional=True,
            )


@pytest.mark.benchmark
def test_bench_regulatory_event_processing(benchmark):
    """Benchmark processing regulatory events with related assets."""
    graph = _build_large_graph(50)

    events = []
    for i in range(10):
        related = [f"EQ_{j}" for j in range(i + 1, min(i + 6, 50))]
        event = RegulatoryEvent(
            id=f"EVT_{i}",
            asset_id=f"EQ_{i}",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-01",
            description=f"Event {i}",
            impact_score=0.5,
            related_assets=related,
        )
        events.append(event)

    @benchmark
    def _():
        graph.regulatory_events = []
        graph.relationships = {}
        for event in events:
            graph.add_regulatory_event(event)
        graph.build_relationships()


@pytest.mark.benchmark
def test_bench_asset_model_creation(benchmark):
    """Benchmark creating diverse financial model instances."""

    @benchmark
    def _():
        Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
            market_cap=2.4e12,
            pe_ratio=25.5,
            dividend_yield=0.005,
            earnings_per_share=5.89,
        )
        Bond(
            id="BOND1",
            symbol="B1",
            name="Corp Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Technology",
            price=102.5,
            yield_to_maturity=0.025,
            coupon_rate=0.02,
            maturity_date="2030-01-15",
            credit_rating="AA+",
            issuer_id="AAPL",
        )
        Commodity(
            id="GOLD",
            symbol="GC",
            name="Gold",
            asset_class=AssetClass.COMMODITY,
            sector="Metals",
            price=2050.0,
            contract_size=100,
            volatility=0.15,
        )
        Currency(
            id="EUR",
            symbol="EUR",
            name="Euro",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.10,
            exchange_rate=1.10,
            country="EU",
            central_bank_rate=0.035,
        )
