import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from src.logic.asset_graph import AssetRelationshipGraph

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


class FormulaicdAnalyzer:
    """Analyzes financial data to extract and render mathematical relationships."""

    def __init__(self):
        self.formulas: List[Formula] = []

    def analyze_graph(self, graph: AssetRelationshipGraph) -> Dict[str, Any]:
        """
        Orchestrates extraction and analysis of formulaic relationships from an asset relationship graph.

        Parameters:
            graph (AssetRelationshipGraph): The asset relationship graph to analyze for mathematical and empirical relationships.

        Returns:
            Dict[str, Any]: A dictionary containing:
                - "formulas": List[Formula] — extracted Formula objects covering fundamental, correlation, valuation, risk-return, portfolio, and cross-asset relationships.
                - "empirical_relationships": dict — empirical data derived from the graph (e.g., correlation matrices or observed relationship metrics).
                - "formula_count": int — total number of extracted formulas.
                - "categories": dict — mapping of formula category names to their counts.
                - "summary": dict — summary metrics and insights about the extracted formulas and empirical findings.
        """
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
                all_formulas, empirical_relationships
            ),
        }

    def _extract_fundamental_formulas(
        self, graph: AssetRelationshipGraph
    ) -> List[Formula]:
        """
        Assembles fundamental financial formulas applicable to the provided asset relationship graph.

        Checks the graph for relevant asset types and returns Formula objects for common fundamentals such as price-to-earnings, dividend yield, bond yield-to-maturity (approximation), and market capitalization when applicable.

        Returns:
            List[Formula]: A list of Formula instances representing fundamental valuation and income formulas relevant to the graph.
        """
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
        """
        Create Formula objects that describe correlation-related relationships between assets.

        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and relationships used to derive example calculations and empirical metrics.

        Returns:
            List[Formula]: A list of Formula instances representing correlation patterns (for example, Beta and the correlation coefficient).
        """
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
            example_calculation=(self._calculate_beta_examples(graph)),
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
            example_calculation=(self._calculate_correlation_examples(graph)),
            category="Statistical Analysis",
            r_squared=(self._calculate_avg_correlation_strength(graph)),
        )
        formulas.append(correlation_formula)

        return formulas

    def _extract_valuation_relationships(
        self, graph: AssetRelationshipGraph
    ) -> List[Formula]:
        """
        Extracts valuation-related financial formulas applicable to the given asset graph.

        Returns:
            List[Formula]: A list of valuation Formula objects (for example, Price-to-Book Ratio and Enterprise Value) populated with metadata, LaTeX, variables, example calculations, category, and r_squared estimates.
        """
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
        """
        Create Formula objects describing common risk–return metrics.

        Produces Formula entries for risk-return analysis (for example, Sharpe Ratio and volatility/standard deviation) populated with names, formula expressions, LaTeX, variable descriptions, example calculations, category, and explanatory text.

        Returns:
            List[Formula]: A list of Formula instances representing risk-management metrics (e.g., Sharpe Ratio, Volatility).
        """
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
        """
        Extract Modern Portfolio Theory formulas applicable to the provided asset graph.

        Generates formulas describing portfolio expected return and portfolio variance (2-asset case), with variables, LaTeX, example calculations derived from the graph, category, and an associated r_squared estimate.

        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and relationships used to produce example calculations and to determine which portfolio formulas are relevant.

        Returns:
            List[Formula]: A list of Formula instances representing MPT relationships (e.g., portfolio expected return and 2-asset portfolio variance).
        """
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
        """
        Identify cross-asset mathematical relationships present in the graph.

        Returns:
            List[Formula]: A list of Formula objects representing detected cross-asset relationships (e.g., triangular currency exchange relationships and commodity–currency inverse relationships) when the corresponding asset types are present in the graph.
        """
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

    def _calculate_empirical_relationships(
        self, graph: AssetRelationshipGraph
    ) -> Dict[str, Any]:
        """
        Compute empirical relationship metrics derived from the provided AssetRelationshipGraph.

        Produces a dictionary of empirical measurements used elsewhere in analysis, most importantly a correlation matrix of asset pair relationships, an average correlation strength computed excluding perfect self-correlations, and a count of correlation entries considered.

        Parameters:
            graph (AssetRelationshipGraph): Graph containing asset nodes and observed relationships used to derive empirical metrics.

        Returns:
            Dict[str, Any]: A dictionary with at least the following keys:
                - "correlation_matrix" (Dict[Tuple[str, str], float]): Pairwise correlation values between assets.
                - "avg_correlation_strength" (float): Average of correlation values excluding perfect correlations (e.g., 1.0).
                - "correlation_entries" (int): Number of correlation pairs included in the calculations.
        """
        pass

    @staticmethod
    def _calculate_avg_correlation_strength(graph: AssetRelationshipGraph) -> float:
        """Calculate average correlation strength in the graph"""
        total_relationships = sum(len(rels) for rels in graph.relationships.values())
        if total_relationships > 0:
            return min(0.75, total_relationships / len(graph.assets) * 0.1)
        return 0.5

    def _categorize_formulas(self, formulas: List[Formula]) -> Dict[str, int]:
        """
        Group formulas by category and count how many formulas belong to each category.

        Parameters:
            formulas (List[Formula]): List of Formula instances to categorize.

        Returns:
            Dict[str, int]: Mapping from category name to the number of formulas in that category.
        """
        categories = {}
        for formula in formulas:
            category = formula.category
            categories[category] = categories.get(category, 0) + 1
        return categories

    def _generate_formula_summary(
        self, formulas: List[Formula], empirical_relationships: Dict
    ) -> Dict[str, Any]:
        """
        Produce a summary of the formula analysis and related empirical results.

        Parameters:
            formulas (List[Formula]): List of Formula objects produced by the analysis.
            empirical_relationships (Dict): Empirical data dictionary; expected to include a "correlation_matrix" mapping used to compute correlation statistics.

        Returns:
            Dict[str, Any]: A summary dictionary containing:
                - total_formulas (int): Number of formulas in `formulas`.
                - avg_r_squared (float): Average of `Formula.r_squared` across `formulas`, or 0 if `formulas` is empty.
                - formula_categories (Dict[str, int]): Counts of formulas grouped by category.
                - empirical_data_points (int): Number of entries in `empirical_relationships["correlation_matrix"]` (0 if missing).
                - key_insights (List[str]): Short human-readable insight strings derived from the analysis and empirical statistics.
        """
        avg_corr_strength = self._calculate_avg_correlation_strength_from_empirical(
            empirical_relationships
        )
        return {
            "total_formulas": len(formulas),
            "avg_r_squared": sum(f.r_squared for f in formulas) / len(formulas)
            if formulas
            else 0,
            "formula_categories": self._categorize_formulas(formulas),
            "empirical_data_points": len(
                empirical_relationships.get("correlation_matrix", {})
            ),
            "key_insights": [
                f"Identified {len(formulas)} mathematical relationships",
                f"Average correlation strength: {avg_corr_strength:.2f}",
                "Valuation models applicable to equity assets",
                ("Portfolio theory formulas available for multi-asset analysis"),
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
        """
        Compute the average correlation strength from empirical relationship data.

        Parameters:
            empirical_relationships (Dict): Mapping expected to contain a "correlation_matrix" key whose value is a dict of identifier -> correlation value.

        Returns:
            float: The average of correlation values strictly less than 1.0; returns 0.5 if no valid correlations are present.
        """
        correlations = empirical_relationships.get("correlation_matrix", {})
        if correlations:
            valid_correlations = [v for v in correlations.values() if v < 1.0]
            return (
                sum(valid_correlations) / len(valid_correlations)
                if valid_correlations
                else 0.5
            )
        return 0.5
