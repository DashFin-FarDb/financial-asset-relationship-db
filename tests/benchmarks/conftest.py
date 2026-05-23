"""Fixtures for CodSpeed benchmark tests."""

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


def build_mixed_asset_specs(count: int) -> list[dict]:
    """Return a list of keyword-arg dicts for creating a diverse mix of assets.

    The distribution rotates across Equity, Bond, Commodity, and Currency so
    that benchmarks exercise all asset-class code paths.
    """
    specs: list[dict] = []
    for i in range(count):
        idx = i % 4
        if idx == 0:
            specs.append(
                dict(
                    cls=Equity,
                    id=f"EQ_{i}",
                    symbol=f"EQ{i}",
                    name=f"Equity {i}",
                    asset_class=AssetClass.EQUITY,
                    sector="Technology" if i % 8 < 4 else "Finance",
                    price=100.0 + i,
                    market_cap=1e9 + i * 1e6,
                    pe_ratio=20.0 + i * 0.1,
                    dividend_yield=0.01,
                )
            )
        elif idx == 1:
            issuer_id = f"EQ_{i - 1}" if i > 0 else None
            specs.append(
                dict(
                    cls=Bond,
                    id=f"BD_{i}",
                    symbol=f"BD{i}",
                    name=f"Bond {i}",
                    asset_class=AssetClass.FIXED_INCOME,
                    sector="Technology" if i % 8 < 4 else "Government",
                    price=99.0 + i * 0.1,
                    yield_to_maturity=0.03,
                    coupon_rate=0.025,
                    maturity_date="2030-01-15",
                    credit_rating="AA+",
                    issuer_id=issuer_id,
                )
            )
        elif idx == 2:
            specs.append(
                dict(
                    cls=Commodity,
                    id=f"CM_{i}",
                    symbol=f"CM{i}",
                    name=f"Commodity {i}",
                    asset_class=AssetClass.COMMODITY,
                    sector="Energy" if i % 8 < 4 else "Precious Metals",
                    price=50.0 + i,
                    contract_size=1000,
                    volatility=0.25,
                )
            )
        else:
            specs.append(
                dict(
                    cls=Currency,
                    id=f"CU_{i}",
                    symbol=f"CU{i}",
                    name=f"Currency {i}",
                    asset_class=AssetClass.CURRENCY,
                    sector="Forex",
                    price=1.0 + i * 0.01,
                    exchange_rate=1.0 + i * 0.01,
                    country="US",
                    central_bank_rate=0.05,
                )
            )
    return specs


def build_diverse_graph(asset_count: int, event_count: int = 0) -> AssetRelationshipGraph:
    """Build a fresh graph with a representative mix of asset classes.

    Parameters
    ----------
    asset_count:
        Total number of assets to create (spread across all four classes).
    event_count:
        Number of regulatory events to attach. Each event links to up to two
        neighbouring assets.

    Returns
    -------
    AssetRelationshipGraph
        A populated graph with relationships **not yet built** so callers can
        benchmark ``build_relationships()`` independently.
    """
    graph = AssetRelationshipGraph()
    specs = build_mixed_asset_specs(asset_count)

    for spec in specs:
        cls = spec.pop("cls")
        graph.add_asset(cls(**spec))

    asset_ids = list(graph.assets.keys())
    for j in range(min(event_count, asset_count)):
        related = [asset_ids[(j + 1) % len(asset_ids)]]
        if len(asset_ids) > 2:
            related.append(asset_ids[(j + 2) % len(asset_ids)])
        graph.add_regulatory_event(
            RegulatoryEvent(
                id=f"EVT_{j}",
                asset_id=asset_ids[j % len(asset_ids)],
                event_type=RegulatoryActivity.EARNINGS_REPORT,
                date="2024-06-01",
                description=f"Benchmark event {j}",
                impact_score=0.5 - (j % 10) * 0.1,
                related_assets=related,
            )
        )

    return graph
