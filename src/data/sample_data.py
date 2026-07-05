"""Build sample asset graph data for local development and demos."""

import logging

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
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

logger = logging.getLogger(__name__)


def _get_sample_equities() -> list[Equity]:
    """Return a list of sample Equity assets."""
    return [
        Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.00,
            market_cap=2.4e12,
            pe_ratio=25.5,
            dividend_yield=0.005,
            earnings_per_share=5.89,
        ),
        Equity(
            id="MSFT",
            symbol="MSFT",
            name="Microsoft Corporation",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=320.00,
            market_cap=2.3e12,
            pe_ratio=28.2,
            dividend_yield=0.007,
            earnings_per_share=11.34,
        ),
        Equity(
            id="NVDA",
            symbol="NVDA",
            name="NVIDIA Corporation",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=450.00,
            market_cap=1.1e12,
            pe_ratio=45.8,
            dividend_yield=0.002,
            earnings_per_share=9.82,
        ),
        Equity(
            id="XOM",
            symbol="XOM",
            name="Exxon Mobil",
            asset_class=AssetClass.EQUITY,
            sector="Energy",
            price=110.00,
            market_cap=450e9,
            pe_ratio=12.3,
            dividend_yield=0.032,
            earnings_per_share=8.94,
        ),
        Equity(
            id="CVX",
            symbol="CVX",
            name="Chevron Corporation",
            asset_class=AssetClass.EQUITY,
            sector="Energy",
            price=160.00,
            market_cap=300e9,
            pe_ratio=11.5,
            dividend_yield=0.038,
            earnings_per_share=13.91,
        ),
        Equity(
            id="JPM",
            symbol="JPM",
            name="JPMorgan Chase & Co.",
            asset_class=AssetClass.EQUITY,
            sector="Financials",
            price=145.00,
            market_cap=420e9,
            pe_ratio=10.2,
            dividend_yield=0.028,
            earnings_per_share=14.21,
        ),
        Equity(
            id="JNJ",
            symbol="JNJ",
            name="Johnson & Johnson",
            asset_class=AssetClass.EQUITY,
            sector="Healthcare",
            price=165.00,
            market_cap=430e9,
            pe_ratio=34.5,
            dividend_yield=0.028,
            earnings_per_share=4.78,
        ),
    ]


def _get_sample_bonds() -> list[Bond]:
    """Return a list of sample Bond assets."""
    return [
        Bond(
            id="AAPL_BOND_2030",
            symbol="AAPL30",
            name="Apple 2030 Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Technology",
            price=98.50,
            yield_to_maturity=0.045,
            coupon_rate=0.04,
            maturity_date="2030-01-01",
            credit_rating="AA+",
            issuer_id="AAPL",
        ),
        Bond(
            id="MSFT_BOND_2028",
            symbol="MSFT28",
            name="Microsoft 2028 Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Technology",
            price=102.10,
            yield_to_maturity=0.038,
            coupon_rate=0.04,
            maturity_date="2028-06-15",
            credit_rating="AAA",
            issuer_id="MSFT",
        ),
        Bond(
            id="US_10Y",
            symbol="US10Y",
            name="US Treasury 10-Year Note",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Government",
            price=95.00,
            yield_to_maturity=0.042,
            coupon_rate=0.04,
            maturity_date="2033-08-15",
            credit_rating="AAA",
        ),
        Bond(
            id="US_2Y",
            symbol="US2Y",
            name="US Treasury 2-Year Note",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Government",
            price=98.00,
            yield_to_maturity=0.048,
            coupon_rate=0.05,
            maturity_date="2025-08-15",
            credit_rating="AAA",
        ),
    ]


def _get_sample_commodities() -> list[Commodity]:
    """Return a list of sample Commodity assets."""
    return [
        Commodity(
            id="CL_F",
            symbol="CL=F",
            name="Crude Oil WTI",
            asset_class=AssetClass.COMMODITY,
            sector="Energy",
            price=82.00,
            contract_size=1000,
            volatility=0.25,
        ),
        Commodity(
            id="NG_F",
            symbol="NG=F",
            name="Natural Gas",
            asset_class=AssetClass.COMMODITY,
            sector="Energy",
            price=2.80,
            contract_size=10000,
            volatility=0.45,
        ),
        Commodity(
            id="GC_F",
            symbol="GC=F",
            name="Gold",
            asset_class=AssetClass.COMMODITY,
            sector="Precious Metals",
            price=1950.00,
            contract_size=100,
            volatility=0.15,
        ),
        Commodity(
            id="SI_F",
            symbol="SI=F",
            name="Silver",
            asset_class=AssetClass.COMMODITY,
            sector="Precious Metals",
            price=23.50,
            contract_size=5000,
            volatility=0.20,
        ),
        Commodity(
            id="ZC_F",
            symbol="ZC=F",
            name="Corn",
            asset_class=AssetClass.COMMODITY,
            sector="Agriculture",
            price=480.00,
            contract_size=5000,
            volatility=0.18,
        ),
    ]


def _get_sample_currencies() -> list[Currency]:
    """Return a list of sample Currency assets."""
    return [
        Currency(
            id="EURUSD",
            symbol="EUR",
            name="Euro",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.08,
            exchange_rate=1.08,
            country="Eurozone",
            central_bank_rate=0.04,
        ),
        Currency(
            id="USDJPY",
            symbol="JPY",
            name="Japanese Yen",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=150.0,
            exchange_rate=150.0,
            country="Japan",
            central_bank_rate=0.001,
        ),
        Currency(
            id="GBPUSD",
            symbol="GBP",
            name="British Pound",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.28,
            exchange_rate=1.28,
            country="UK",
            central_bank_rate=0.0525,
        ),
    ]


def _get_sample_regulatory_events() -> list[RegulatoryEvent]:
    """Return a list of sample RegulatoryEvent objects."""
    return [
        RegulatoryEvent(
            id="AAPL_Q4_2024",
            asset_id="AAPL",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-25",
            description="Q4 2024 Earnings Beat",
            impact_score=0.15,
            related_assets=["MSFT", "NVDA", "AAPL_BOND_2030"],
        ),
        RegulatoryEvent(
            id="US_RATE_HIKE_2023",
            asset_id="US_10Y",
            event_type=RegulatoryActivity.REGULATORY_FILING,
            date="2023-07-26",
            description="Federal Reserve 25bp Rate Hike",
            impact_score=-0.25,
            related_assets=["US_2Y", "EURUSD", "GBPUSD", "USDJPY", "AAPL", "MSFT", "XOM", "JPM", "GC_F"],
        ),
        RegulatoryEvent(
            id="TECH_ANTITRUST_2023",
            asset_id="AAPL",
            event_type=RegulatoryActivity.LEGAL_PROCEEDING,
            date="2023-09-15",
            description="EU Antitrust Investigation",
            impact_score=-0.40,
            related_assets=["MSFT"],
        ),
        RegulatoryEvent(
            id="OPEC_CUT_2023",
            asset_id="CL_F",
            event_type=RegulatoryActivity.COMPLIANCE_UPDATE,
            date="2023-11-30",
            description="OPEC+ Production Cut",
            impact_score=0.60,
            related_assets=["XOM", "CVX"],
        ),
        RegulatoryEvent(
            id="JPM_DIVIDEND_2024",
            asset_id="JPM",
            event_type=RegulatoryActivity.DIVIDEND_ANNOUNCEMENT,
            date="2024-02-10",
            description="Dividend Increased by 5%",
            impact_score=0.20,
            related_assets=[],
        ),
    ]


def create_sample_database() -> AssetRelationshipGraph:
    """
    Create an in-memory sample graph populated with diversified financial assets and regulatory events.

    Returns:
        AssetRelationshipGraph: Populated graph containing the sample assets, registered
            regulatory events, and their established relationships.
    """
    try:
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="sample_graph_creation_initiated",
                message="Creating expanded sample financial database",
            ),
        )
        from src.config.settings import get_settings

        settings = get_settings()
        graph = AssetRelationshipGraph(
            same_sector_strength=settings.same_sector_strength,
            corporate_bond_strength=settings.corporate_bond_strength,
        )

        all_assets = _get_sample_equities() + _get_sample_bonds() + _get_sample_commodities() + _get_sample_currencies()
        for asset in all_assets:
            graph.add_asset(asset)

        for event in _get_sample_regulatory_events():
            graph.add_regulatory_event(event)

        graph.build_relationships()

        # Add some custom empirical relationships
        graph.relationships["AAPL"].append(("MSFT", "competitor", 0.3))
        graph.relationships["MSFT"].append(("AAPL", "competitor", 0.3))

        graph.relationships["XOM"].append(("CVX", "competitor", 0.2))
        graph.relationships["CVX"].append(("XOM", "competitor", 0.2))

        graph.relationships["AAPL"].append(("AAPL_BOND_2030", "corporate_link", settings.corporate_bond_strength))
        graph.relationships["MSFT"].append(("MSFT_BOND_2028", "corporate_link", settings.corporate_bond_strength))

        graph.relationships["US_10Y"].append(("US_2Y", "yield_curve", 0.9))
        graph.relationships["US_2Y"].append(("US_10Y", "yield_curve", 0.9))

        graph.relationships["CL_F"].append(("XOM", "cost_input", 0.7))
        graph.relationships["CL_F"].append(("CVX", "cost_input", 0.7))
        graph.relationships["NG_F"].append(("XOM", "cost_input", 0.5))

        graph.relationships["GC_F"].append(("SI_F", "correlation", 0.85))
        graph.relationships["SI_F"].append(("GC_F", "correlation", 0.85))

        graph.relationships["EURUSD"].append(("GBPUSD", "correlation", 0.75))
        graph.relationships["USDJPY"].append(("US_10Y", "correlation", 0.65))

        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="sample_graph_creation_completed",
                message=(
                    f"Sample database created with {len(graph.assets)} assets and "
                    f"{sum(len(rels) for rels in graph.relationships.values())} relationships"
                ),
            ),
        )
        return graph

    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="sample_graph_creation_failed",
                message=f"Failed to create sample database: {type(e).__name__}",
                metadata={"error": type(e).__name__},
            ),
        )
        raise
