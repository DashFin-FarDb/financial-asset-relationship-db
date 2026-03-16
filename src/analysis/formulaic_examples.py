from __future__ import annotations

from collections.abc import Callable

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass


def _is_equity_with_pe_ratio(asset: object) -> bool:
    """
    Determine whether an asset is an equity that exposes a defined P/E ratio.

    Parameters:
        asset (object): Asset-like object expected to have `asset_class` and `pe_ratio` attributes.

    Returns:
        True if the asset's `asset_class` is `AssetClass.EQUITY` and `pe_ratio` is not None, False otherwise.
    """
    if getattr(asset, "asset_class", None) != AssetClass.EQUITY:
        return False
    return getattr(asset, "pe_ratio", None) is not None


def _is_equity_with_dividend_yield(asset: object) -> bool:
    """
    Determine whether an asset is an equity with a defined dividend yield.

    Parameters:
        asset (object): Asset-like object expected to have `asset_class` and `dividend_yield` attributes.

    Returns:
        True if the asset's `asset_class` is `AssetClass.EQUITY` and `dividend_yield` is not None, False otherwise.
    """
    if getattr(asset, "asset_class", None) != AssetClass.EQUITY:
        return False
    return getattr(asset, "dividend_yield", None) is not None


def _is_bond_with_ytm(asset: object) -> bool:
    """
    Identify fixed-income assets that have a defined yield-to-maturity.

    Parameters:
        asset (object): Object expected to have `asset_class` and `yield_to_maturity` attributes.

    Returns:
        bool: `True` if `asset.asset_class` is `AssetClass.FIXED_INCOME` and `asset.yield_to_maturity` is not `None`, `False` otherwise.
    """
    if getattr(asset, "asset_class", None) != AssetClass.FIXED_INCOME:
        return False
    return getattr(asset, "yield_to_maturity", None) is not None


def _is_equity_with_market_cap(asset: object) -> bool:
    """
    Determine whether an asset is an equity with a defined market capitalization.

    Returns:
        True if the asset's class is `AssetClass.EQUITY` and its `market_cap` attribute is not None, False otherwise.
    """
    if getattr(asset, "asset_class", None) != AssetClass.EQUITY:
        return False
    return getattr(asset, "market_cap", None) is not None


def _is_equity_with_book_value(asset: object) -> bool:
    """
    Check whether an asset is an equity with a defined book value.

    Returns:
        `true` if the asset is an equity and has a non-null `book_value`, `false` otherwise.
    """
    if getattr(asset, "asset_class", None) != AssetClass.EQUITY:
        return False
    return getattr(asset, "book_value", None) is not None


def _is_commodity_with_volatility(asset: object) -> bool:
    """
    Check if an asset is a commodity that exposes a defined volatility attribute.

    Parameters:
        asset (object): The asset object to inspect.

    Returns:
        bool: `true` if the asset's `asset_class` is `AssetClass.COMMODITY` and its `volatility` attribute is not `None`, `false` otherwise.
    """
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
    """
    Collect formatted example strings for assets that satisfy a predicate.

    Parameters:
        graph (AssetRelationshipGraph): Source graph whose assets will be inspected.
        predicate (Callable[[object], bool]): Function that returns `True` for assets to include.
        formatter (Callable[[object], str]): Function that produces a formatted string for a matching asset.
        limit (int, optional): Maximum number of examples to collect. Defaults to 2.

    Returns:
        list[str]: Collected formatted strings from up to `limit` matching assets.
    """
    examples: list[str] = []
    for asset in graph.assets.values():
        if not predicate(asset):
            continue
        examples.append(formatter(asset))
        if len(examples) >= limit:
            break
    return examples


def has_equities(graph: AssetRelationshipGraph) -> bool:
    """
    Determine whether the graph contains at least one equity asset.

    Returns:
        `true` if the graph contains one or more assets with class `AssetClass.EQUITY`, `false` otherwise.
    """
    return any(asset.asset_class == AssetClass.EQUITY for asset in graph.assets.values())


def has_bonds(graph: AssetRelationshipGraph) -> bool:
    """
    Detects whether the graph contains any fixed-income assets.

    Returns:
        True if the graph contains at least one fixed-income asset, False otherwise.
    """
    return any(asset.asset_class == AssetClass.FIXED_INCOME for asset in graph.assets.values())


def has_commodities(graph: AssetRelationshipGraph) -> bool:
    """
    Determine whether the graph contains any commodity assets.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to inspect.

    Returns:
        `true` if at least one asset in the graph has class `COMMODITY`, `false` otherwise.
    """
    return any(asset.asset_class == AssetClass.COMMODITY for asset in graph.assets.values())


def has_currencies(graph: AssetRelationshipGraph) -> bool:
    """
    Determine if the graph contains at least one currency asset.

    Returns:
        `true` if the graph contains at least one asset with class `CURRENCY`, `false` otherwise.
    """
    return any(asset.asset_class == AssetClass.CURRENCY for asset in graph.assets.values())


def has_dividend_stocks(graph: AssetRelationshipGraph) -> bool:
    """
    Detects whether the graph contains equity assets with a positive dividend yield.

    Returns:
        `true` if at least one equity asset has `dividend_yield` greater than 0, `false` otherwise.
    """
    return any(
        asset.asset_class == AssetClass.EQUITY
        and hasattr(asset, "dividend_yield")
        and asset.dividend_yield is not None
        and asset.dividend_yield > 0
        for asset in graph.assets.values()
    )


def calculate_pe_examples(graph: AssetRelationshipGraph) -> str:
    """
    Generate human-readable examples of price-to-earnings (P/E) ratios for equity assets.

    Collects up to two formatted examples in the form "SYMBOL: PE = X.XX" from equities that have a defined P/E ratio and returns them joined by "; ". If no suitable equities are found, returns a default illustrative example.

    Returns:
        str: Joined example strings (e.g. "AAPL: PE = 15.23; MSFT: PE = 20.10") or a default illustrative example when no P/E data is available.
    """
    examples: list[str] = []
    for asset in graph.assets.values():
        if _is_equity_with_pe_ratio(asset):
            pe_ratio = float(getattr(asset, "pe_ratio"))
            examples.append(f"{asset.symbol}: PE = {pe_ratio:.2f}")
            if len(examples) >= 2:
                break
    return "; ".join(examples) if examples else "Example: PE = 100.00 / 5.00 = 20.00"


def calculate_dividend_examples(graph: AssetRelationshipGraph) -> str:
    """
    Builds up to two formatted dividend-yield examples from equity assets in the graph.

    Each example is formatted as "SYMBOL: Yield = X.XX% at price $Y.YY". If no equity with a dividend yield is found, returns the illustrative default string "Example: Div Yield = (2.00 / 100.00) * 100 = 2.00%".

    Returns:
        A single string containing up to two examples joined by "; ", or the default illustrative example when none are available.
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
    """
    Create up to two formatted yield-to-maturity example strings from bond assets in the graph.

    Returns:
        a joined string of examples (e.g., "TRES: YTM ≈ 3.25%; BNDX: YTM ≈ 2.10%") if any bonds with YTM are found, or the default string "Example: YTM ≈ 3.0%" otherwise.
    """
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
    """
    Create up to two formatted market-cap example strings using equity assets found in the graph.

    Each example is formatted as "SYMBOL: Market Cap = $X.XB" (billions) and examples are joined with "; ". If no qualifying equities are present, returns the fallback string "Example: Market Cap = $1.5T".

    Returns:
        A string containing up to two joined market-cap examples or a default example when none are available.
    """
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
    """
    Provide a short, representative example illustrating how an asset's beta is calculated.

    Returns:
        A human-readable example string describing beta calculation (e.g., "Beta calculated from historical returns vs market index").
    """
    _ = graph
    return "Beta calculated from historical returns vs market index"


def calculate_correlation_examples(graph: AssetRelationshipGraph) -> str:
    """
    Generate a concise example sentence describing how correlations were derived from the asset graph.

    Returns:
        str: An example sentence. If the graph has relationship entries, returns
        "Calculated from N asset pair relationships" where N is the total number of
        relationships; otherwise returns a general description that correlations are
        calculated from price movements.
    """
    if graph.relationships:
        count = sum(len(rels) for rels in graph.relationships.values())
        return f"Calculated from {count} asset pair relationships"
    return "Correlation between asset pairs calculated from price movements"


def calculate_pb_examples(graph: AssetRelationshipGraph) -> str:
    """
    Builds formatted price-to-book (P/B) examples from equity assets in the graph.

    Scans the provided AssetRelationshipGraph for equities that have a defined book_value and formats up to two examples as "SYMBOL: P/B = X.XX". If no suitable equities are found, returns a default illustrative example.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing assets to inspect for equity book values.

    Returns:
        A string with up to two formatted examples separated by "; ", or a default illustrative example if none are available.
    """

    def _format_pb(asset: object) -> str:
        """
        Format an asset's price-to-book (P/B) ratio as a one-line string.

        Parameters:
            asset (object): Asset-like object with attributes `symbol`, `price`, and `book_value`.

        Returns:
            str: Formatted string "SYMBOL: P/B = X.XX". If `book_value` is zero or equivalent, the ratio is formatted as 0.00.
        """
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
    """
    Provide a representative example of a Sharpe ratio calculation.

    Returns:
        example (str): A human-readable Sharpe ratio example string, e.g. "Sharpe = (10% - 2%) / 15% = 0.53".
    """
    _ = graph
    return "Sharpe = (10% - 2%) / 15% = 0.53"


def calculate_volatility_examples(graph: AssetRelationshipGraph) -> str:
    """
    Builds up to two formatted volatility (σ) examples from commodity assets in the graph.

    Returns:
        A semicolon-separated string of examples formatted as "SYMBOL: σ = X.XX%". If no commodity volatility values are available, returns the default example "Example: σ = 20% annualized".
    """
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
    """
    Provide a representative example illustrating how to calculate an expected portfolio return as a weighted average of asset returns.

    Returns:
        A formatted example string showing a weighted-average expected return, e.g. "Example: E(Rp) = 0.6 × 10% + 0.4 × 5% = 8%".
    """
    _ = graph
    return "Example: E(Rp) = 0.6 × 10% + 0.4 × 5% = 8%"


def calculate_portfolio_variance_examples(graph: AssetRelationshipGraph) -> str:
    """
    Provide a concise example illustrating the calculation of portfolio variance for a two-asset portfolio.

    Returns:
        A formatted example string showing portfolio variance computed from asset weights, individual variances, and their covariance (e.g. "σ²p = (w1² × σ1²) + (w2² × σ2²) + (2 × w1 × w2 × σ1 × σ2 × ρ)").
    """
    _ = graph
    return "Example: σ²p = (0.6² × 0.2²) + (0.4² × 0.1²) + (2 × 0.6 × 0.4 × 0.2 × 0.1 × 0.5)"


def calculate_exchange_rate_examples(graph: AssetRelationshipGraph) -> str:
    """
    Generate a concise exchange-rate example using two currency assets from the graph.

    If the graph contains two or more currency assets, the example combines the first two into a cross-rate (e.g., "USD/EUR × EUR/GBP = USD/GBP"). If fewer than two currencies are present, a default illustrative example is returned.

    Returns:
        formatted_example (str): An exchange-rate example string (e.g., "USD/EUR × EUR/GBP = USD/GBP").
    """
    currencies = [asset for asset in graph.assets.values() if asset.asset_class == AssetClass.CURRENCY]
    if len(currencies) >= 2:
        c1, c2 = currencies[0], currencies[1]
        return f"{c1.symbol}/USD × USD/{c2.symbol} = {c1.symbol}/{c2.symbol}"
    return "Example: USD/EUR × EUR/GBP = USD/GBP"


def calculate_commodity_currency_examples(graph: AssetRelationshipGraph) -> str:
    """
    Illustrates a typical relationship between commodity prices and currency strength.

    Returns:
        A short example sentence describing how movements in a commodity's price (for example, oil) can be associated with changes in a currency's strength.
    """
    _ = graph
    return "Example: As oil prices rise, USD strengthens (inverse relationship)"
