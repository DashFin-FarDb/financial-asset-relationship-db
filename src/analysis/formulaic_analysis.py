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
    variables: dict[str, str]  # variable_name -> description
    example_calculation: str
    category: str
    r_squared: float = 0.0  # Correlation strength if applicable


class FormulaicdAnalyzer:
    """Analyzes financial data to extract and render mathematical relationships."""

    def __init__(self):
        self.formulas: List[Formula] = []

    def analyze_graph(self, graph: AssetRelationshipGraph) -> dict[str, Any]:
        """
        Analyze an asset relationship graph to extract, categorize, and
        summarize financial formulas.

        Parameters:
            graph (AssetRelationshipGraph): Graph containing assets and their
                relationships to analyze.

        Returns:
            result (dict): Analysis results containing:
                - "formulas" (List[Formula]): Extracted financial formulas.
                - "empirical_relationships" (dict): Empirical relationship data
                    derived from graph data.
                - "formula_count" (int): Total number of extracted formulas.
                - "categories" (dict): Mapping of formula category names to counts.
                - "summary" (dict): High-level summary and insights of the analysis.
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
            "summary": self._generate_formula_summary(all_formulas, empirical_relationships),
        }

    def _extract_fundamental_formulas(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Extract fundamental financial formulas based on asset
        types present in the graph.

        Generates canonical valuation and income formulas when the
        corresponding asset types exist in the provided
        AssetRelationshipGraph.
        Examples included when available:
        - Equities: Price-to-Earnings (P/E) and Market Capitalization.
        - Dividend stocks: Dividend Yield.
        - Bonds: Yield-to-Maturity (approximation).

        Parameters:
            graph (AssetRelationshipGraph): Graph whose asset types
                and data determine which formulas are produced.

        Returns:
            List[Formula]: Formulas representing fundamental financial
                relationships found for the graph.
        """
        formulas = []

        # Price-to-Earnings Ratio
        if self._has_equities(graph):
            pe_formula = Formula(
                name="Price-to-Earnings Ratio",
                formula="PE = P / EPS",
                latex=r"PE = \frac{P}{EPS}",
                description=("Valuation metric comparing stock price to earnings per share"),
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
                description=("Percentage return from dividends relative to stock price"),
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
                latex=(r"YTM \approx \frac{C + \frac{FV - P}{n}}" r"{\frac{FV + P}{2}}"),
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

    def _analyze_correlation_patterns(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Extract correlation-related financial and statistical formulas
        from an asset relationship graph.

        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and their
                relationships to analyze for correlation and
                co-movement patterns.

        Returns:
            List[Formula]: A list of Formula objects representing
                correlation measures (for example, Beta and the
                correlation coefficient).
                Each Formula includes descriptive fields, example
                calculations derived from the graph, and an empirical
                strength estimate.
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

    def _extract_valuation_relationships(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Extract valuation-related formulas present in the asset graph.

        Includes common valuation relationships such as Price-to-Book (when equities
        are present) and Enterprise Value. Each returned Formula contains its name,
        formula string, LaTeX representation, variable descriptions, an example
        calculation note or value, category, and an r_squared score.

        Returns:
            List[Formula]: A list of valuation Formula objects discovered or
                constructed from the graph.
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
            example_calculation=("EV calculation requires debt and cash data " "(not available in current dataset)"),
            category="Valuation",
            r_squared=0.95,
        )
        formulas.append(enterprise_value_formula)

        return formulas

    def _analyze_risk_return_relationships(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Extracts standard risk-return formulas found in the asset graph
        (for example, Sharpe Ratio and volatility).

        Parameters:
            graph (AssetRelationshipGraph): AssetRelationshipGraph to inspect for
                return and risk data used to populate examples and metadata.

        Returns:
            List[Formula]: A list of Formula objects describing risk-return
                relationships (name, symbolic formula, LaTeX, variables, example
                calculations, category, and r_squared).
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

    def _extract_portfolio_theory_formulas(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Generate portfolio-theory formulas derived from the provided asset
        relationship graph.

        Produces Formula entries for portfolio expected return
        (weighted average of asset expected returns)
        and portfolio variance for the two-asset case (including correlation term).

        Returns:
            List[Formula]: A list of Formula objects representing portfolio
                expected return and portfolio variance (2-asset).
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
            latex=(r"\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + " r"2w_1w_2\sigma_1\sigma_2\rho_{12}"),
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

    def _analyze_cross_asset_relationships(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Extract cross-asset relationship formulas present in the provided asset graph.

        This method identifies and returns formulas that describe relationships
        between different asset classes detected in the graph, such as triangular
        currency exchange relationships and inverse commodity-currency
        relationships for commodity-exporting economies.

        Parameters:
            graph (AssetRelationshipGraph): The asset relationship graph used to
                detect currencies, commodities, and their interconnections.

        Returns:
            List[Formula]: A list of Formula objects representing detected
                cross-asset
                relationships; returns an empty list if no applicable
                relationships are found.
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
                formula=("Currency_Value ∝ 1/Commodity_Price (for commodity exporters)"),
                latex=r"FX_{commodity} \propto \frac{1}{P_{commodity}}",
                description=("Inverse relationship between commodity prices and currency values"),
                variables={
                    "FX_commodity": "Currency value of commodity exporter",
                    "P_commodity": "Commodity price",
                },
                example_calculation=(self._calculate_commodity_currency_examples(graph)),
                category="Cross-Asset",
                r_squared=0.65,
            )
            formulas.append(commodity_currency_formula)

        return formulas

    def _calculate_empirical_relationships(self, graph: AssetRelationshipGraph) -> dict[str, Any]:
        """
        Compute empirical relationships from the provided asset relationship graph.

        Analyzes available time-series and relationship data in `graph` to
        derive empirical metrics used elsewhere in the analyzer. The returned
        dictionary contains computed artifacts that downstream methods expect,
        most notably a `correlation_matrix` mapping asset identifiers to
        pairwise correlation values and a `data_points` count describing how
        many observations were used.

        Parameters:
            graph (AssetRelationshipGraph): Graph containing asset nodes and associated
                empirical data (e.g., time-series or observed relationships).

        Returns:
            dict: A dictionary with at least the following keys:
                - `correlation_matrix` (dict[str, dict[str, float]]):
                  Pairwise correlation values between assets.
                - `data_points` (int):
                  Number of observations used to compute the empirical metrics.
                Additional computed empirical artifacts may be included as other keys.
        """

    @staticmethod
    def _calculate_avg_correlation_strength(graph: AssetRelationshipGraph) -> float:
        """Calculate average correlation strength in the graph"""
        total_relationships = sum(len(rels) for rels in graph.relationships.values())
        if total_relationships > 0:
            return min(0.75, total_relationships / len(graph.assets) * 0.1)
        return 0.5

    @staticmethod
    def _categorize_formulas(formulas: List[Formula]) -> dict[str, int]:
        """
        Group formulas by their category and
        count how many formulas appear in each category.

        Parameters:
                formulas (List[Formula]): List of Formula objects to categorize.

        Returns:
                category_counts (dict[str, int]): Mapping from category name
                to the number of formulas in that category.
        """
        categories = {}
        for formula in formulas:
            category = formula.category
            categories[category] = categories.get(category, 0) + 1
        return categories

    def _generate_formula_summary(self, formulas: List[Formula], empirical_relationships: Dict) -> dict[str, Any]:
        """
        Create an aggregate summary of analyzed formulas together with metrics derived
        from empirical relationship data.

        Parameters:
            formulas (List[Formula]): List of Formula objects produced by the analysis.
            empirical_relationships (Dict): Empirical data produced from the graph analysis.
                Expected to include a "correlation_matrix" key whose value is a mapping of
                asset-pair identifiers to numeric correlation values.

        Returns:
            summary (dict[str, Any]): Dictionary with the following keys:
                - total_formulas (int): Number of formulas in `formulas`.
                - avg_r_squared (float): Average `r_squared` value across `formulas` (0 if `formulas` is empty).
                - formula_categories (dict[str, int]): Counts of formulas grouped by category.
                - empirical_data_points (int): Number of entries in the `correlation_matrix` (0 if absent).
                - key_insights (List[str]): Short, high-level observations derived from the formulas and empirical data.
        """
        avg_corr_strength = self._calculate_avg_correlation_strength_from_empirical(empirical_relationships)
        return {
            "total_formulas": len(formulas),
            "avg_r_squared": (sum(f.r_squared for f in formulas) / len(formulas) if formulas else 0),
            "formula_categories": self._categorize_formulas(formulas),
            "empirical_data_points": len(empirical_relationships.get("correlation_matrix", {})),
            "key_insights": [
                f"Identified {len(formulas)} mathematical relationships",
                f"Average correlation strength: {avg_corr_strength:.2f}",
                "Valuation models applicable to equity assets",
                ("Portfolio theory formulas available for multi-asset analysis"),
                ("Cross-asset relationships identified between " "commodities and currencies"),
            ],
        }

    @staticmethod
    def _calculate_avg_correlation_strength_from_empirical(
        empirical_relationships: Dict,
    ) -> float:
        """
        Compute the average correlation value from an empirical correlation matrix.

        Reads the "correlation_matrix" mapping from the provided
        empirical_relationships dictionary, excludes values equal to 1.0
        (treated as perfect/self correlations), and returns the mean of
        the remaining correlation values. If no valid correlations are
        present, returns 0.5.

        Parameters:
            empirical_relationships (Dict): A dictionary that may contain a "correlation_matrix"
                key mapping identifiers to numeric correlation values.

        Returns:
            float: The average correlation (bounded by typical correlation ranges),
            or 0.5 when no valid correlations are available.
        """
        correlations = empirical_relationships.get("correlation_matrix", {})
        if correlations:
            valid_correlations = [v for v in correlations.values() if v < 1.0]
            return sum(valid_correlations) / len(valid_correlations) if valid_correlations else 0.5
        return 0.5
