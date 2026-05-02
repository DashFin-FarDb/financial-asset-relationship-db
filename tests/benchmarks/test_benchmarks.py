"""CodSpeed performance benchmarks for the financial-asset-relationship-db.

These tests are **excluded** from regular pytest runs (via ``norecursedirs``
in ``pyproject.toml``) and are only executed by the CodSpeed CI workflow with
``pytest tests/benchmarks/ --codspeed``.
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

from .conftest import build_diverse_graph
# ---------------------------------------------------------------------------
# Model validation benchmarks
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_bench_model_validation_mixed(benchmark):
    """Benchmark creating a diverse set of model instances.

    Creates 200 instances (50 of each asset class) per iteration to produce a
    measurable workload that exercises all validation paths.
    """

    def _create_mixed_models():
        for i in range(50):
            Equity(
                id=f"EQ_{i}",
                symbol=f"EQ{i}",
                name=f"Equity {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + i,
                market_cap=1e9,
                pe_ratio=25.0,
                dividend_yield=0.01,
            )
            Bond(
                id=f"BD_{i}",
                symbol=f"BD{i}",
                name=f"Bond {i}",
                asset_class=AssetClass.FIXED_INCOME,
                sector="Government",
                price=99.0,
                yield_to_maturity=0.03,
                coupon_rate=0.025,
                maturity_date="2030-01-15",
                credit_rating="AAA",
            )
            Commodity(
                id=f"CM_{i}",
                symbol=f"CM{i}",
                name=f"Commodity {i}",
                asset_class=AssetClass.COMMODITY,
                sector="Energy",
                price=80.0,
                contract_size=1000,
                volatility=0.3,
            )
            Currency(
                id=f"CU_{i}",
                symbol=f"CU{i}",
                name=f"Currency {i}",
                asset_class=AssetClass.CURRENCY,
                sector="Forex",
                price=1.10,
                exchange_rate=1.10,
                country="EU",
                central_bank_rate=0.04,
            )

    benchmark(_create_mixed_models)


@pytest.mark.benchmark
def test_bench_regulatory_event_validation(benchmark):
    """Benchmark RegulatoryEvent validation over 100 instances."""

    def _create_events():
        for i in range(100):
            RegulatoryEvent(
                id=f"EVT_{i}",
                asset_id=f"ASSET_{i}",
                event_type=RegulatoryActivity.EARNINGS_REPORT,
                date="2024-06-15",
                description=f"Event {i}",
                impact_score=0.5 - (i % 10) * 0.1,
                related_assets=[f"REL_{i}"],
            )

    benchmark(_create_events)


# ---------------------------------------------------------------------------
# Graph construction benchmarks
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_bench_build_relationships_small(benchmark):
    """Benchmark build_relationships on a small mixed-asset graph (20 assets, 4 events)."""

    def _build():
        graph = build_diverse_graph(asset_count=20, event_count=4)
        graph.build_relationships()
        return graph

    result = benchmark(_build)
    assert len(result.assets) == 20


@pytest.mark.benchmark
def test_bench_build_relationships_medium(benchmark):
    """Benchmark build_relationships on a medium mixed-asset graph (80 assets, 10 events)."""

    def _build():
        graph = build_diverse_graph(asset_count=80, event_count=10)
        graph.build_relationships()
        return graph

    result = benchmark(_build)
    assert len(result.assets) == 80


@pytest.mark.benchmark
def test_bench_build_relationships_large(benchmark):
    """Benchmark build_relationships on a large mixed-asset graph (200 assets, 20 events).

    Uses a diverse mix of Equity, Bond, Commodity, and Currency instances to
    reflect real-world graph composition.
    """

    def _build():
        graph = build_diverse_graph(asset_count=200, event_count=20)
        graph.build_relationships()
        return graph

    result = benchmark(_build)
    assert len(result.assets) == 200


# ---------------------------------------------------------------------------
# Metrics calculation benchmarks
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_bench_calculate_metrics_small(benchmark):
    """Benchmark calculate_metrics on a small graph (20 assets)."""

    def _metrics():
        graph = build_diverse_graph(asset_count=20, event_count=4)
        graph.build_relationships()
        return graph.calculate_metrics()

    metrics = benchmark(_metrics)
    assert metrics["total_assets"] > 0


@pytest.mark.benchmark
def test_bench_calculate_metrics_large(benchmark):
    """Benchmark calculate_metrics on a large mixed-asset graph (200 assets, 20 events)."""

    def _metrics():
        graph = build_diverse_graph(asset_count=200, event_count=20)
        graph.build_relationships()
        return graph.calculate_metrics()

    metrics = benchmark(_metrics)
    assert metrics["total_assets"] > 0


# ---------------------------------------------------------------------------
# Sample database benchmark
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_bench_create_sample_database(benchmark):
    """Benchmark the full create_sample_database workflow (19 assets, 4 events)."""
    graph = benchmark(create_sample_database)
    assert len(graph.assets) == 19
    assert len(graph.regulatory_events) == 4


# ---------------------------------------------------------------------------
# Visualization data benchmark
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_bench_3d_visualization_data(benchmark):
    """Benchmark 3D visualization data generation on a large mixed-asset graph."""

    def _viz():
        graph = build_diverse_graph(asset_count=100, event_count=10)
        graph.build_relationships()
        return graph.get_3d_visualization_data_enhanced()

    positions, asset_ids, colors, hover = benchmark(_viz)
    assert len(asset_ids) > 0


# ---------------------------------------------------------------------------
# Relationship addition benchmark
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_bench_add_relationships_bulk(benchmark):
    """Benchmark adding 500 relationships to a graph with various argument forms."""

    def _add_rels():
        graph = build_diverse_graph(asset_count=50)
        ids = list(graph.assets.keys())
        for i in range(500):
            src = ids[i % len(ids)]
            tgt = ids[(i + 1) % len(ids)]
            if src != tgt:
                graph.add_relationship(src, tgt, f"bench_rel_{i % 5}", 0.5 + (i % 5) * 0.1)
        return graph

    result = benchmark(_add_rels)
    assert len(result.relationships) > 0
