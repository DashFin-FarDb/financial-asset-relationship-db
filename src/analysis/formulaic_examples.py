from __future__ import annotations

from collections.abc import Callable

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass


def _is_equity_with_pe_ratio(asset: object) -> bool:
    """Return True for equity assets that expose a non-null PE ratio."""
    if getattr(asset, "asset_class", None) != AssetClass.EQUITY:
        return False
    return getattr(asset, "pe_ratio", None) is not None


def _is_equity_with_dividend_yield(asset: object) -> bool:
    """Return True for equity assets that expose a non-null dividend yield."""
    if getattr(asset, "asset_class", None) != AssetClass.EQUITY:
        return False
    return getattr(asset, "dividend_yield", None) is not None


def _is_bond_with_ytm(asset: object) -> bool:
    """Return True for fixed-income assets with a non-null YTM value."""
    if getattr(asset, "asset_class", None) != AssetClass.FIXED_INCOME:
        return False
    return getattr(asset, "yield_to_maturity", None) is not None


def _is_equity_with_market_cap(asset: object) -> bool:
    """Return True for equity assets that expose a non-null market cap."""
    if getattr(asset, "asset_class", None) != AssetClass.EQUITY:
        return False
    return getattr(asset, "market_cap", None) is not None


def _is_equity_with_book_value(asset: object) -> bool:
    """Return True for equity assets that expose a non-null book value."""
    if getattr(asset, "asset_class", None) != AssetClass.EQUITY:
        return False
    return getattr(asset, "book_value", None) is not None


def _is_commodity_with_volatility(asset: object) -> bool:
    """Return True for commodity assets with non-null volatility."""
    if getattr(asset, "asset_class", None) != AssetClass.COMMODITY:
        return False
    return getattr(asset, "volatility", None) is not None


def _collect_formatted_examples(
    graph: AssetRelationshipGraph,
    predicate: Callable[[object], bool],
    formatter: Callable[[object], str],
    *,
    limit: int = 2,
) -> list[str]:
    """Collect up to `limit` formatted examples matching predicate."""
    examples: list[str] = []
    for asset in graph.assets.values():
        if not predicate(asset):
            continue
        examples.append(formatter(asset))
        if len(examples) >= limit:
            break
    return examples


def has_equities(graph: AssetRelationshipGraph) -> bool:
    """Return True when the graph contains at least one equity asset."""
    return any(asset.asset_class == AssetClass.EQUITY for asset in graph.assets.values())


def has_bonds(graph: AssetRelationshipGraph) -> bool:
    """Return True when the graph contains at least one fixed-income asset."""
    return any(asset.asset_class == AssetClass.FIXED_INCOME for asset in graph.assets.values())


def has_commodities(graph: AssetRelationshipGraph) -> bool:
    """Return True when the graph contains at least one commodity asset."""
    return any(asset.asset_class == AssetClass.COMMODITY for asset in graph.assets.values())


def has_currencies(graph: AssetRelationshipGraph) -> bool:
    """Return True when the graph contains at least one currency asset."""
    return any(asset.asset_class == AssetClass.CURRENCY for asset in graph.assets.values())


def has_dividend_stocks(graph: AssetRelationshipGraph) -> bool:
    """Return True when the graph has equity assets with positive dividends."""
    return any(
        asset.asset_class == AssetClass.EQUITY
        and hasattr(asset, "dividend_yield")
        and asset.dividend_yield is not None
        and asset.dividend_yield > 0
        for asset in graph.assets.values()
    )


def calculate_pe_examples(graph: AssetRelationshipGraph) -> str:
    """Build formatted P/E ratio examples from equity assets."""
    examples: list[str] = []
    for asset in graph.assets.values():
        if _is_equity_with_pe_ratio(asset):
            pe_ratio = float(getattr(asset, "pe_ratio"))
            examples.append(f"{asset.symbol}: PE = {pe_ratio:.2f}")
            if len(examples) >= 2:
                break
    return "; ".join(examples) if examples else "Example: PE = 100.00 / 5.00 = 20.00"


def calculate_dividend_examples(graph: AssetRelationshipGraph) -> str:
    """Build formatted dividend-yield examples from equity assets.

    Returns:
        Formatted string with up to 2 dividend yield examples,
        or a default example.
    """
    examples: list[str] = []
    for asset in graph.assets.values():
        if _is_equity_with_dividend_yield(asset):
            dividend_yield = float(getattr(asset, "dividend_yield"))
            yield_pct = dividend_yield * 100
            examples.append(f"{asset.symbol}: Yield = {yield_pct:.2f}% at price ${asset.price:.2f}")
            if len(examples) >= 2:
                break
    return "; ".join(examples) if examples else "Example: Div Yield = (2.00 / 100.00) * 100 = 2.00%"


def calculate_ytm_examples(graph: AssetRelationshipGraph) -> str:
    """Build formatted yield-to-maturity examples from bond assets."""
    examples: list[str] = []
    for asset in graph.assets.values():
        if _is_bond_with_ytm(asset):
            ytm = float(getattr(asset, "yield_to_maturity"))
            ytm_pct = ytm * 100
            examples.append(f"{asset.symbol}: YTM ≈ {ytm_pct:.2f}%")
            if len(examples) >= 2:
                break
    return "; ".join(examples) if examples else "Example: YTM ≈ 3.0%"


def calculate_market_cap_examples(graph: AssetRelationshipGraph) -> str:
    """Build formatted market-cap examples from equity assets."""
    examples: list[str] = []
    for asset in graph.assets.values():
        if _is_equity_with_market_cap(asset):
            market_cap = float(getattr(asset, "market_cap"))
            cap_billions = market_cap / 1e9
            examples.append(f"{asset.symbol}: Market Cap = ${cap_billions:.1f}B")
            if len(examples) >= 2:
                break
    return "; ".join(examples) if examples else "Example: Market Cap = $1.5T"


def calculate_beta_examples(graph: AssetRelationshipGraph) -> str:
    """Return a representative beta-calculation example string."""
    _ = graph
    return "Beta calculated from historical returns vs market index"


def calculate_correlation_examples(graph: AssetRelationshipGraph) -> str:
    """Return a correlation example based on graph relationships."""
    if graph.relationships:
        count = sum(len(rels) for rels in graph.relationships.values())
        return f"Calculated from {count} asset pair relationships"
    return "Correlation between asset pairs calculated from price movements"


def calculate_pb_examples(graph: AssetRelationshipGraph) -> str:
    """Build formatted price-to-book examples from equity assets."""

    def _format_pb(asset: object) -> str:
        book_value = float(getattr(asset, "book_value"))
        pb_ratio = getattr(asset, "price") / book_value if book_value else 0
        return f"{getattr(asset, 'symbol')}: P/B = {pb_ratio:.2f}"

    examples = _collect_formatted_examples(
        graph,
        _is_equity_with_book_value,
        _format_pb,
    )
    return "; ".join(examples) if examples else "Example: P/B = 150 / 50 = 3.0"


def calculate_sharpe_examples(graph: AssetRelationshipGraph) -> str:
    """Return a representative Sharpe-ratio example string."""
    _ = graph
    return "Sharpe = (10% - 2%) / 15% = 0.53"


def calculate_volatility_examples(graph: AssetRelationshipGraph) -> str:
    """Build formatted volatility examples from commodity assets."""
    examples: list[str] = []
    for asset in graph.assets.values():
        if _is_commodity_with_volatility(asset):
            volatility = float(getattr(asset, "volatility"))
            vol_pct = volatility * 100
            examples.append(f"{asset.symbol}: σ = {vol_pct:.2f}%")
            if len(examples) >= 2:
                break
    return "; ".join(examples) if examples else "Example: σ = 20% annualized"


def calculate_portfolio_return_examples(graph: AssetRelationshipGraph) -> str:
    """Return a representative expected portfolio return example string."""
    _ = graph
    return "Example: E(Rp) = 0.6 × 10% + 0.4 × 5% = 8%"


def calculate_portfolio_variance_examples(graph: AssetRelationshipGraph) -> str:
    """Return a portfolio variance example string."""
    _ = graph
    return "Example: σ²p = (0.6² × 0.2²) + (0.4² × 0.1²) + (2 × 0.6 × 0.4 × 0.2 × 0.1 × 0.5)"


def calculate_exchange_rate_examples(graph: AssetRelationshipGraph) -> str:
    """Build an exchange-rate example from available currency assets."""
    currencies = [asset for asset in graph.assets.values() if asset.asset_class == AssetClass.CURRENCY]
    if len(currencies) >= 2:
        c1, c2 = currencies[0], currencies[1]
        return f"{c1.symbol}/USD × USD/{c2.symbol} = {c1.symbol}/{c2.symbol}"
    return "Example: USD/EUR × EUR/GBP = USD/GBP"


def calculate_commodity_currency_examples(graph: AssetRelationshipGraph) -> str:
    """Return a commodity-currency example string."""
    _ = graph
    return "Example: As oil prices rise, USD strengthens (inverse relationship)"
