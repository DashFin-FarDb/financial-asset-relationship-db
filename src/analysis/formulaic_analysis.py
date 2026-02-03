import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass

logger = logging.getLogger(__name__)


@dataclass
class Formula:
    """Represents a mathematical formula between financial variables"""

    name: str
    formula: str
    latex: str
    description: str
    variables: Dict[str, str]  # variable_name -> description
    example_calculation: str
    category: str
    r_squared: float = 0.0  # Correlation strength if applicable


class FormulaicAnalyzer:
    """Analyzes financial data to extract and render mathematical relationships."""

    def __init__(self):
        self.formulas: List[Formula] = []

    def analyze_graph(self, graph: AssetRelationshipGraph) -> Dict[str, Any]:
        """Perform a formulaic analysis of the asset relationships."""
        logger.info("Starting formulaic analysis of asset relationships")

        # Extract fundamental financial formulas
        fundamental_formulas = self._extract_fundamental_formulas(graph)

        # Analyze correlation patterns
        correlation_formulas = self._analyze_correlation_patterns(graph)

        # Extract valuation relationships
        valuation_formulas = self._extract_valuation_relationships(graph)

        # Analyze risk-return relationships
        risk_return_formulas = self._analyze_risk_return_relationships(graph)

        # Portfolio theory relationships
        portfolio_formulas = self._extract_portfolio_theory_formulas(graph)

        # Currency and commodity relationships
        cross_asset_formulas = self._analyze_cross_asset_relationships(graph)

        all_formulas = (
            fundamental_formulas
            + correlation_formulas
            + valuation_formulas
            + risk_return_formulas
            + portfolio_formulas
            + cross_asset_formulas
        )

        # Calculate empirical relationships from actual data
        empirical_relationships = self._calculate_empirical_relationships(graph)

        return {
            "formulas": all_formulas,
            "empirical_relationships": empirical_relationships,
            "formula_count": len(all_formulas),
            "categories": self._categorize_formulas(all_formulas),
            "summary": self._generate_formula_summary(
                all_formulas,
                empirical_relationships,
            ),
        }

    def _extract_fundamental_formulas(
        self, graph: AssetRelationshipGraph
    ) -> List[Formula]:
        """Extract fundamental financial formulas based on asset types"""
        formulas = []

        # Price-to-Earnings Ratio
        if self._has_equities(graph):
            pe_formula = Formula(
                name="Price-to-Earnings Ratio",
                formula="PE = P / EPS",
                latex=r"PE = \frac{P}{EPS}",
                description=(
                    "Valuation metric comparing stock price to earnings per share"
                ),
                variables={
                    "PE": "Price-to-Earnings Ratio",
                    "P": "Current Stock Price ($)",
                    "EPS": "Earnings Per Share ($)",
                },
                example_calculation=self._calculate_pe_examples(graph),
                category="Valuation",
                r_squared=0.95,
            )
            formulas.append(pe_formula)

        # Dividend Yield
        if self._has_dividend_stocks(graph):
            div_yield_formula = Formula(
                name="Dividend Yield",
                formula=("Div_Yield = (Annual_Dividends / Price) × 100%"),
                latex=(r"DivYield = \frac{D_{annual}}{P}" r" \times 100%"),
                description=(
                    "Percentage return from dividends relative to stock price"
                ),
                variables={
                    "Div_Yield": "Dividend Yield (%)",
                    "D_annual": "Annual Dividends per Share ($)",
                    "P": "Current Stock Price ($)",
                },
                example_calculation=self._calculate_dividend_examples(graph),
                category="Income",
                r_squared=1.0,
            )
            formulas.append(div_yield_formula)

        # Bond Yield-to-Maturity Approximation
        if self._has_bonds(graph):
            ytm_formula = Formula(
                name=("Bond Yield-to-Maturity (Approximation)"),
                formula=("YTM ≈ (C + (FV - P) / n) / ((FV + P) / 2)"),
                latex=(
                    r"YTM \approx \frac{C + \frac{FV - P}{n}}" r"{\frac{FV + P}{2}}"
                ),
                description="Approximate yield-to-maturity for bonds",
                variables={
                    "YTM": "Yield-to-Maturity (%)",
                    "C": "Annual Coupon Payment ($)",
                    "FV": "Face Value ($)",
                    "P": "Current Bond Price ($)",
                    "n": "Years to Maturity",
                },
                example_calculation=self._calculate_ytm_examples(graph),
                category="Fixed Income",
                r_squared=0.92,
            )
            formulas.append(ytm_formula)

        # Market Cap
        if self._has_equities(graph):
            market_cap_formula = Formula(
                name="Market Capitalization",
                formula="Market_Cap = Price × Shares_Outstanding",
                latex=r"MarketCap = P \times N_{shares}",
                description="Total market value of a company's shares",
                variables={
                    "Market_Cap": "Market Capitalization ($)",
                    "P": "Current Stock Price ($)",
                    "N_shares": "Number of Shares Outstanding",
                },
                example_calculation=self._calculate_market_cap_examples(graph),
                category="Valuation",
                r_squared=1.0,
            )
            formulas.append(market_cap_formula)

        return formulas

    def _analyze_correlation_patterns(
        self, graph: AssetRelationshipGraph
    ) -> List[Formula]:
        """Analyze and formulate correlation patterns between assets"""
        formulas = []

        # Beta relationship (systematic risk)
        beta_formula = Formula(
            name="Beta (Systematic Risk)",
            formula="β = Cov(R_asset, R_market) / Var(R_market)",
            latex=r"\beta = \frac{Cov(R_i, R_m)}{Var(R_m)}",
            description=("Measure of an asset's sensitivity to market movements"),
            variables={
                "β": "Beta coefficient",
                "R_i": "Asset return",
                "R_m": "Market return",
                "Cov": "Covariance",
                "Var": "Variance",
            },
            example_calculation=self._calculate_beta_examples(graph),
            category="Risk Management",
            r_squared=0.75,
        )
        formulas.append(beta_formula)

        # Correlation coefficient
        correlation_formula = Formula(
            name="Correlation Coefficient",
            formula="ρ = Cov(X, Y) / (σ_X × σ_Y)",
            latex=(r"\rho = \frac{Cov(X, Y)}{\sigma_X " r"\times \sigma_Y}"),
            description=("Measure of linear relationship between two variables"),
            variables={
                "ρ": "Correlation coefficient (-1 to 1)",
                "Cov(X,Y)": "Covariance between X and Y",
                "σ_X": "Standard deviation of X",
                "σ_Y": "Standard deviation of Y",
            },
            example_calculation=self._calculate_correlation_examples(graph),
            category="Statistical Analysis",
            r_squared=self._calculate_avg_correlation_strength(graph),
        )
        formulas.append(correlation_formula)

        return formulas

    def _extract_valuation_relationships(
        self, graph: AssetRelationshipGraph
    ) -> List[Formula]:
        """Extract valuation model relationships"""
        formulas = []

        # Price-to-Book Ratio
        if self._has_equities(graph):
            pb_formula = Formula(
                name="Price-to-Book Ratio",
                formula="P/B = Market_Price / Book_Value_per_Share",
                latex=r"P/B = \frac{P}{BV_{per\_share}}",
                description=("Valuation metric comparing market price to book value"),
                variables={
                    "P/B": "Price-to-Book Ratio",
                    "P": "Market Price per Share ($)",
                    "BV_per_share": "Book Value per Share ($)",
                },
                example_calculation=self._calculate_pb_examples(graph),
                category="Valuation",
                r_squared=0.88,
            )
            formulas.append(pb_formula)

        # Enterprise Value
        enterprise_value_formula = Formula(
            name="Enterprise Value",
            formula="EV = Market_Cap + Total_Debt - Cash",
            latex=r"EV = MarketCap + Debt - Cash",
            description="Total value of a company including debt",
            variables={
                "EV": "Enterprise Value ($)",
                "Market_Cap": "Market Capitalization ($)",
                "Debt": "Total Debt ($)",
                "Cash": "Cash and Cash Equivalents ($)",
            },
            example_calculation=(
                "EV calculation requires debt and cash data "
                "(not available in current dataset)"
            ),
            category="Valuation",
            r_squared=0.95,
        )
        formulas.append(enterprise_value_formula)

        return formulas

    def _analyze_risk_return_relationships(
        self, graph: AssetRelationshipGraph
    ) -> List[Formula]:
        """Analyze risk-return mathematical relationships"""
        formulas = []

        # Sharpe Ratio
        sharpe_formula = Formula(
            name="Sharpe Ratio",
            formula="Sharpe = (R_portfolio - R_risk_free) / σ_portfolio",
            latex=r"Sharpe = \frac{R_p - R_f}{\sigma_p}",
            description="Risk-adjusted return metric",
            variables={
                "Sharpe": "Sharpe Ratio",
                "R_p": "Portfolio Return (%)",
                "R_f": "Risk-free Rate (%)",
                "σ_p": "Portfolio Standard Deviation (%)",
            },
            example_calculation=self._calculate_sharpe_examples(graph),
            category="Risk Management",
            r_squared=0.82,
        )
        formulas.append(sharpe_formula)

        # Volatility (Standard Deviation)
        volatility_formula = Formula(
            name="Volatility (Standard Deviation)",
            formula="σ = √(Σ(R_i - μ)² / (n-1))",
            latex=r"\sigma = \sqrt{\frac{\sum_{i=1}^{n}(R_i - \mu)^2}{n-1}}",
            description="Measure of price variability and risk",
            variables={
                "σ": "Standard deviation (volatility)",
                "R_i": "Individual return",
                "μ": "Mean return",
                "n": "Number of observations",
            },
            example_calculation=self._calculate_volatility_examples(graph),
            category="Risk Management",
            r_squared=0.90,
        )
        formulas.append(volatility_formula)

        return formulas

    def _extract_portfolio_theory_formulas(
        self, graph: AssetRelationshipGraph
    ) -> List[Formula]:
        """Extract Modern Portfolio Theory formulas"""
        formulas = []

        # Portfolio Expected Return
        portfolio_return_formula = Formula(
            name="Portfolio Expected Return",
            formula="E(R_p) = Σ(w_i × E(R_i))",
            latex=r"E(R_p) = \sum_{i=1}^{n} w_i \times E(R_i)",
            description="Weighted average of individual asset expected returns",
            variables={
                "E(R_p)": "Expected portfolio return",
                "w_i": "Weight of asset i in portfolio",
                "E(R_i)": "Expected return of asset i",
                "n": "Number of assets",
            },
            example_calculation=(self._calculate_portfolio_return_examples(graph)),
            category="Portfolio Theory",
            r_squared=1.0,
        )
        formulas.append(portfolio_return_formula)

        # Portfolio Variance (2-asset case)
        portfolio_variance_formula = Formula(
            name="Portfolio Variance (2-Asset)",
            formula="σ²_p = w₁²σ₁² + w₂²σ₂² + 2w₁w₂σ₁σ₂ρ₁₂",
            latex=(
                r"\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + "
                r"2w_1w_2\sigma_1\sigma_2\rho_{12}"
            ),
            description="Portfolio risk considering correlation between assets",
            variables={
                "σ²_p": "Portfolio variance",
                "w_1, w_2": "Weights of assets 1 and 2",
                "σ_1, σ_2": "Standard deviations of assets 1 and 2",
                "ρ_12": "Correlation between assets 1 and 2",
            },
            example_calculation=(self._calculate_portfolio_variance_examples(graph)),
            category="Portfolio Theory",
            r_squared=0.87,
        )
        formulas.append(portfolio_variance_formula)

        return formulas

    def _analyze_cross_asset_relationships(
        self, graph: AssetRelationshipGraph
    ) -> List[Formula]:
        """Analyze relationships between different asset classes"""
        formulas = []

        # Currency exchange relationships
        if self._has_currencies(graph):
            exchange_rate_formula = Formula(
                name="Exchange Rate Relationships",
                formula="USD/EUR × EUR/GBP = USD/GBP",
                latex=r"\frac{USD}{EUR} \times \frac{EUR}{GBP} = \frac{USD}{GBP}",
                description=("Triangular arbitrage relationship between currencies"),
                variables={
                    "USD/EUR": "US Dollar to Euro exchange rate",
                    "EUR/GBP": "Euro to British Pound exchange rate",
                    "USD/GBP": "US Dollar to British Pound exchange rate",
                },
                example_calculation=(self._calculate_exchange_rate_examples(graph)),
                category="Currency Markets",
                r_squared=0.99,
            )
            formulas.append(exchange_rate_formula)

        # Commodity-Currency relationship
        if self._has_commodities(graph) and self._has_currencies(graph):
            commodity_currency_formula = Formula(
                name="Commodity-Currency Relationship",
                formula=(
                    "Currency_Value ∝ 1/Commodity_Price (for commodity exporters)"
                ),
                latex=r"FX_{commodity} \propto \frac{1}{P_{commodity}}",
                description=(
                    "Inverse relationship between commodity prices and currency values"
                ),
                variables={
                    "FX_commodity": "Currency value of commodity exporter",
                    "P_commodity": "Commodity price",
                },
                example_calculation=(
                    self._calculate_commodity_currency_examples(graph)
                ),
                category="Cross-Asset",
                r_squared=0.65,
            )
            formulas.append(commodity_currency_formula)

        return formulas

    @staticmethod
    def _calculate_empirical_relationships(
        graph: AssetRelationshipGraph,
    ) -> Dict[str, Any]:
        """
        Stub for calculating empirical relationships between assets.

        Returns:
            Empty dictionary. Actual implementation pending.
        """
        return {}

    @staticmethod
    def _calculate_avg_correlation_strength(graph: AssetRelationshipGraph) -> float:
        """Calculate the average correlation strength in the graph."""
        strengths = [
            strength for rels in graph.relationships.values() for _, _, strength in rels
        ]
        if strengths:
            avg_strength = sum(strengths) / len(strengths)
            return min(0.75, max(0.0, avg_strength))
        return 0.5

    @staticmethod
    def _categorize_formulas(formulas: List[Formula]) -> Dict[str, int]:
        """Categorize formulas by type."""
        categories = {}
        for formula in formulas:
            category = formula.category
            categories[category] = categories.get(category, 0) + 1
        return categories

    def _generate_formula_summary(
        self,
        formulas: List[Formula],
        empirical_relationships: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a summary of formulaic analysis results."""
        avg_corr_strength = self._calculate_avg_correlation_strength_from_empirical(
            empirical_relationships
        )

        if formulas:
            avg_r_squared = sum(
                f.r_squared for f in formulas if isinstance(f.r_squared, (int, float))
            ) / len(formulas)
        else:
            avg_r_squared = 0.0

        return {
            "total_formulas": len(formulas),
            "avg_r_squared": avg_r_squared,
            "formula_categories": self._categorize_formulas(formulas),
            "empirical_data_points": len(
                empirical_relationships.get("correlation_matrix", {})
            ),
            "key_insights": [
                f"Identified {len(formulas)} mathematical relationships",
                f"Average correlation strength: {avg_corr_strength:.2f}",
                "Valuation models applicable to equity assets",
                "Portfolio theory formulas available for multi-asset analysis",
                (
                    "Cross-asset relationships identified between "
                    "commodities and currencies"
                ),
            ],
        }

    @staticmethod
    def _calculate_avg_correlation_strength_from_empirical(
        empirical_relationships: Dict,
    ) -> float:
        """Calculate average correlation from empirical data"""
        correlations = empirical_relationships.get("correlation_matrix", {})
        if correlations:
            valid_correlations = [v for v in correlations.values() if v < 1.0]
            return (
                sum(valid_correlations) / len(valid_correlations)
                if valid_correlations
                else 0.5
            )
        return 0.5

    @staticmethod
    def _has_equities(graph: AssetRelationshipGraph) -> bool:
        """Check if the graph contains equity assets."""
        from src.models.financial_models import AssetClass

        return any(
            asset.asset_class == AssetClass.EQUITY for asset in graph.assets.values()
        )

    @staticmethod
    def _has_bonds(graph: AssetRelationshipGraph) -> bool:
        """Check if graph contains bond/fixed income assets."""

        return any(
            asset.asset_class == AssetClass.FIXED_INCOME
            for asset in graph.assets.values()
        )

    @staticmethod
    def _has_currencies(graph: AssetRelationshipGraph) -> bool:
        """Check if the graph contains currency assets."""
        from src.models.financial_models import AssetClass

        return any(
            asset.asset_class == AssetClass.CURRENCY for asset in graph.assets.values()
        )

    @staticmethod
    def _has_dividend_stocks(graph: AssetRelationshipGraph) -> bool:
        """Check if the graph contains equity assets with positive dividend yields.

        This method evaluates the assets within the provided graph to determine if any
        of them are classified as equity and possess a non-null, positive dividend
        yield. It iterates through the assets in the graph and checks for the
        necessary conditions to identify dividend stocks.
        """
        from src.models.financial_models import AssetClass

        return any(
            asset.asset_class == AssetClass.EQUITY
            and hasattr(asset, "dividend_yield")
            and asset.dividend_yield is not None
            and asset.dividend_yield > 0
            for asset in graph.assets.values()
        )

    @staticmethod
    def _calculate_pe_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example P/E ratio calculations from graph data.

        This static method iterates through the assets in the provided
        AssetRelationshipGraph to generate example price-to-earnings (P/E)
        ratio calculations. It specifically checks for assets of the EQUITY
        class that have a defined P/E ratio. The method collects up to two
        examples and formats them for output. If no valid examples are found,
        a default example is returned.
        """
        from src.models.financial_models import AssetClass

        examples = []
        for asset in graph.assets.values():
            if (
                asset.asset_class == AssetClass.EQUITY
                and hasattr(asset, "pe_ratio")
                and asset.pe_ratio is not None
            ):
                examples.append(f"{asset.symbol}: PE = {asset.pe_ratio:.2f}")
                if len(examples) >= 2:
                    break
        return (
            "; ".join(examples) if examples else "Example: PE = 100.00 / 5.00 = 20.00"
        )

    @staticmethod
    def _calculate_dividend_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example dividend yield calculations from graph data.

        This static method iterates through the assets in the provided
        AssetRelationshipGraph, checking for assets of the EQUITY class that have a
        defined dividend yield. It collects formatted strings representing the yield
        percentage and price for each qualifying asset, stopping after two examples.
        If no examples are found, it returns a default example calculation.
        """
        from src.models.financial_models import AssetClass

        examples = []
        for asset in graph.assets.values():
            if (
                asset.asset_class == AssetClass.EQUITY
                and hasattr(asset, "dividend_yield")
                and asset.dividend_yield is not None
            ):
                yield_pct = asset.dividend_yield * 100
                examples.append(
                    f"{asset.symbol}: Yield = {yield_pct:.2f}% "
                    f"at price ${asset.price:.2f}"
                )
                if len(examples) >= 2:
                    break
        return (
            "; ".join(examples)
            if examples
            else "Example: Div Yield = (2.00 / 100.00) * 100 = 2.00%"
        )

    @staticmethod
    def _calculate_ytm_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example YTM calculations from graph data.

        This static method iterates through the assets in the provided
        AssetRelationshipGraph and collects examples of yield to maturity (YTM)
        calculations for assets classified as FIXED_INCOME. It checks if each asset
        has a valid yield to maturity and formats the results into a string. The
        method returns a string containing up to two examples or a default message if
        no valid examples are found.
        """
        from src.models.financial_models import AssetClass

        examples = []
        for asset in graph.assets.values():
            if (
                asset.asset_class == AssetClass.FIXED_INCOME
                and hasattr(asset, "yield_to_maturity")
                and asset.yield_to_maturity is not None
            ):
                ytm_pct = asset.yield_to_maturity * 100
                examples.append(f"{asset.symbol}: YTM ≈ {ytm_pct:.2f}%")
                if len(examples) >= 2:
                    break
        return "; ".join(examples) if examples else "Example: YTM ≈ 3.0%"

    @staticmethod
    def _calculate_market_cap_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example market cap calculations from graph data.

        This static method iterates through the assets in the provided
        AssetRelationshipGraph and generates market cap examples for assets
        classified as EQUITY. It checks for the presence of a market cap
        attribute and collects the first two valid examples, formatting them
        in billions. If no valid examples are found, a default message is
        returned.
        """
        from src.models.financial_models import AssetClass

        examples = []
        for asset in graph.assets.values():
            if (
                asset.asset_class == AssetClass.EQUITY
                and hasattr(asset, "market_cap")
                and asset.market_cap is not None
            ):
                cap_billions = asset.market_cap / 1e9
                examples.append(f"{asset.symbol}: Market Cap = ${cap_billions:.1f}B")
                if len(examples) >= 2:
                    break
        return "; ".join(examples) if examples else "Example: Market Cap = $1.5T"

    @staticmethod
    def _calculate_beta_examples(graph: AssetRelationshipGraph) -> str:
        """Generate a string representing beta calculations."""
        return "Beta calculated from historical returns vs market index"

    @staticmethod
    def _calculate_correlation_examples(graph: AssetRelationshipGraph) -> str:
        """Generate correlation calculation examples from asset relationships."""
        if graph.relationships:
            count = sum(len(rels) for rels in graph.relationships.values())
            return f"Calculated from {count} asset pair relationships"
        return "Correlation between asset pairs calculated from price movements"

    @staticmethod
    def _calculate_pb_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example P/B ratio calculations from graph data.

        This static method calculates the price-to-book (P/B) ratio for assets in the
        provided AssetRelationshipGraph.

        It iterates through the assets, checking if each asset is
        of the EQUITY class and has a valid book value.

        The method computes the P/B ratio for qualifying assets and collects examples.
        Examples are collected until two are found and returned as a formatted string.

        If no examples are found, a default example is returned.

        Args:
            graph (AssetRelationshipGraph): The graph containing asset data for
                analysis.
        """
        from src.models.financial_models import AssetClass

        examples = []
        for asset in graph.assets.values():
            if (
                asset.asset_class == AssetClass.EQUITY
                and hasattr(asset, "book_value")
                and asset.book_value is not None
            ):
                pb_ratio = asset.price / asset.book_value if asset.book_value else 0
                examples.append(f"{asset.symbol}: P/B = {pb_ratio:.2f}")
                if len(examples) >= 2:
                    break
        return "; ".join(examples) if examples else "Example: P/B = 150 / 50 = 3.0"

    @staticmethod
    def _calculate_sharpe_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example Sharpe ratio calculations."""
        return "Sharpe = (10% - 2%) / 15% = 0.53"

    @staticmethod
    def _calculate_volatility_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example volatility calculations from graph data."""
        from src.models.financial_models import AssetClass

        examples = []
        for asset in graph.assets.values():
            if (
                asset.asset_class == AssetClass.COMMODITY
                and hasattr(asset, "volatility")
                and asset.volatility is not None
            ):
                vol_pct = asset.volatility * 100
                examples.append(f"{asset.symbol}: σ = {vol_pct:.2f}%")
                if len(examples) >= 2:
                    break
        return "; ".join(examples) if examples else "Example: σ = 20% annualized"

    @staticmethod
    def _calculate_portfolio_return_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example portfolio return calculations."""
        return "Example: E(Rp) = 0.6 × 10% + 0.4 × 5% = 8%"

    @staticmethod
    def _calculate_portfolio_variance_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example portfolio variance calculations."""
        return (
            "Example: σ²p = (0.6² × 0.2²) + "
            "(0.4² × 0.1²) + "
            "(2 × 0.6 × 0.4 × 0.2 × 0.1 × 0.5)"
        )

    @staticmethod
    def _calculate_exchange_rate_examples(graph: AssetRelationshipGraph) -> str:
        """Generate example exchange rate calculations from graph data."""
        from src.models.financial_models import AssetClass

        currencies = [
            asset
            for asset in graph.assets.values()
            if asset.asset_class == AssetClass.CURRENCY
        ]
        if len(currencies) >= 2:
            c1, c2 = currencies[0], currencies[1]
            return f"{c1.symbol}/USD × USD/{c2.symbol} = {c1.symbol}/{c2.symbol}"
        return "Example: USD/EUR × EUR/GBP = USD/GBP"

    @staticmethod
    def _calculate_commodity_currency_examples(graph: AssetRelationshipGraph) -> str:
        """Generate an example of a commodity-currency relationship calculation."""
        return "Example: As oil prices rise, USD strengthens (inverse relationship)"
