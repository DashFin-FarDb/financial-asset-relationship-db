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

logger = logging.getLogger(__name__)


def create_sample_database() -> AssetRelationshipGraph:
    """Create expanded sample financial database with 15+ assets across all classes"""
    try:
        logger.info("Creating expanded sample financial database")
        graph = AssetRelationshipGraph()

        # Equities - Technology
        apple = Equity(
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
        )

        microsoft = Equity(
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
        )

        nvidia = Equity(
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
        )

        # Equities - Energy
        exxon = Equity(
            id="XOM",
            symbol="XOM",
            name="Exxon Mobil",
            asset_class=AssetClass.EQUITY,
            sector="Energy",
            price=110.00,
            market_cap=450e9,
            pe_ratio=12.3,
            dividend_yield=0.035,
            earnings_per_share=8.95,
        )

        chevron = Equity(
            id="CVX",
            symbol="CVX",
            name="Chevron Corporation",
            asset_class=AssetClass.EQUITY,
            sector="Energy",
            price=155.00,
            market_cap=290e9,
            pe_ratio=14.7,
            dividend_yield=0.031,
            earnings_per_share=10.55,
        )

        # Equities - Finance
        jpmorgan = Equity(
            id="JPM",
            symbol="JPM",
            name="JPMorgan Chase & Co.",
            asset_class=AssetClass.EQUITY,
            sector="Finance",
            price=145.00,
            market_cap=420e9,
            pe_ratio=11.8,
            dividend_yield=0.025,
            earnings_per_share=12.29,
        )

        # Equities - Healthcare
        johnson_and_johnson = Equity(
            id="JNJ",
            symbol="JNJ",
            name="Johnson & Johnson",
            asset_class=AssetClass.EQUITY,
            sector="Healthcare",
            price=165.00,
            market_cap=435e9,
            pe_ratio=15.6,
            dividend_yield=0.029,
            earnings_per_share=10.57,
        )

        # Bonds - Corporate
        apple_bond = Bond(
            id="AAPL_BOND_2030",
            symbol="AAPL30",
            name="Apple Inc. 2030 Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Technology",
            price=102.50,
            yield_to_maturity=0.025,
            coupon_rate=0.02,
            maturity_date="2030-01-15",
            credit_rating="AA+",
            issuer_id="AAPL",
        )

        microsoft_bond = Bond(
            id="MSFT_BOND_2028",
            symbol="MSFT28",
            name="Microsoft Corp. 2028 Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Technology",
            price=103.25,
            yield_to_maturity=0.028,
            coupon_rate=0.023,
            maturity_date="2028-06-15",
            credit_rating="AAA",
            issuer_id="MSFT",
        )

        # Bonds - Government
        us_10y = Bond(
            id="US10Y",
            symbol="US10Y",
            name="US 10-Year Treasury",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Government",
            price=98.50,
            yield_to_maturity=0.042,
            coupon_rate=0.035,
            maturity_date="2034-02-15",
            credit_rating="AAA",
        )

        us_2y = Bond(
            id="US2Y",
            symbol="US2Y",
            name="US 2-Year Treasury",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Government",
            price=99.85,
            yield_to_maturity=0.045,
            coupon_rate=0.04,
            maturity_date="2026-03-31",
            credit_rating="AAA",
        )

        # Commodities - Energy
        crude_oil = Commodity(
            id="CL_CRUDE",
            symbol="CL",
            name="WTI Crude Oil",
            asset_class=AssetClass.COMMODITY,
            sector="Energy",
            price=88.50,
            contract_size=1000,
            volatility=0.35,
        )

        natural_gas = Commodity(
            id="NG_NGAS",
            symbol="NG",
            name="Henry Hub Natural Gas",
            asset_class=AssetClass.COMMODITY,
            sector="Energy",
            price=3.20,
            contract_size=10000,
            volatility=0.45,
        )

        # Commodities - Precious Metals
        gold = Commodity(
            id="GC_GOLD",
            symbol="GC",
            name="COMEX Gold",
            asset_class=AssetClass.COMMODITY,
            sector="Precious Metals",
            price=2050.00,
            contract_size=100,
            volatility=0.15,
        )

        silver = Commodity(
            id="SI_SILVER",
            symbol="SI",
            name="COMEX Silver",
            asset_class=AssetClass.COMMODITY,
            sector="Precious Metals",
            price=24.50,
            contract_size=5000,
            volatility=0.25,
        )

        # Commodities - Agricultural
        corn = Commodity(
            id="ZC_CORN",
            symbol="ZC",
            name="CBOT Corn",
            asset_class=AssetClass.COMMODITY,
            sector="Agricultural",
            price=4.85,
            contract_size=5000,
            volatility=0.30,
        )

        # Currencies - Major Pairs
        usd_eur = Currency(
            id="EURUSD",
            symbol="EUR",
            name="Euro",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.10,
            exchange_rate=1.10,
            country="EU",
            central_bank_rate=0.035,
        )

        usd_jpy = Currency(
            id="USDJPY",
            symbol="JPY",
            name="Japanese Yen",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=150.0,
            exchange_rate=150.0,
            country="Japan",
            central_bank_rate=0.001,
        )

        usd_gbp = Currency(
            id="GBPUSD",
            symbol="GBP",
            name="British Pound",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.28,
            exchange_rate=1.28,
            country="UK",
            central_bank_rate=0.0525,
        )

        # Add all assets to graph
        all_assets = [
            apple,
            microsoft,
            nvidia,
            exxon,
            chevron,
            jpmorgan,
            johnson_and_johnson,
            apple_bond,
            microsoft_bond,
            us_10y,
            us_2y,
            crude_oil,
            natural_gas,
            gold,
            silver,
            corn,
            usd_eur,
            usd_jpy,
            usd_gbp,
        ]

        for asset in all_assets:
            graph.add_asset(asset)

        # Add regulatory events
        tech_earnings = RegulatoryEvent(
            id="AAPL_Q4_2024",
            asset_id="AAPL",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-25",
            description="Q4 2024 Earnings Beat",
            impact_score=0.15,
            related_assets=["MSFT", "NVDA", "AAPL_BOND_2030"],
        )

        energy_dividend = RegulatoryEvent(
            id="XOM_DIV_2024",
            asset_id="XOM",
            event_type=RegulatoryActivity.DIVIDEND_ANNOUNCEMENT,
            date="2024-02-10",
            description="Quarterly Dividend Increase",
            impact_score=0.10,
            related_assets=["CVX", "CL_CRUDE", "NG_NGAS"],
        )

        fed_rate_decision = RegulatoryEvent(
            id="FED_RATE_2024",
            asset_id="US10Y",
            event_type=RegulatoryActivity.SEC_FILING,
            date="2024-03-20",
            description="Federal Reserve Rate Cut",
            impact_score=0.25,
            related_assets=["US2Y", "JPM", "AAPL_BOND_2030", "MSFT_BOND_2028"],
        )

        commodity_volatility = RegulatoryEvent(
            id="ENERGY_VOLATILITY",
            asset_id="CL_CRUDE",
            event_type=RegulatoryActivity.SEC_FILING,
            date="2024-01-15",
            description="Geopolitical Energy Market Disruption",
            impact_score=-0.20,
            related_assets=["NG_NGAS", "XOM", "CVX"],
        )

        graph.add_regulatory_event(tech_earnings)
        graph.add_regulatory_event(energy_dividend)
        graph.add_regulatory_event(fed_rate_decision)
        graph.add_regulatory_event(commodity_volatility)

        # Build all relationships
        graph.build_relationships()

        asset_count = len(graph.assets)
        relationship_count = sum(len(rels) for rels in graph.relationships.values())
        logger.info(
            "Expanded sample database created with %s assets and %s relationships", asset_count, relationship_count
        )
        logger.info(
            "Asset classes covered: Equity (%s), Fixed Income (%s), Commodity (%s), Currency (%s)",
            len([a for a in all_assets if a.asset_class == AssetClass.EQUITY]),
            len([a for a in all_assets if a.asset_class == AssetClass.FIXED_INCOME]),
            len([a for a in all_assets if a.asset_class == AssetClass.COMMODITY]),
            len([a for a in all_assets if a.asset_class == AssetClass.CURRENCY]),
        )

        return graph
    except Exception as e:
        logger.error("Failed to create sample database: %s", e)
        raise
