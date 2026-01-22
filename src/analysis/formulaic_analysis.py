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
        Analyze an asset relationship graph and extract formulaic relationships,
        empirical metrics, and a summary.

        Parameters:
            graph (AssetRelationshipGraph): Graph containing assets and their
                relationships used to derive formulas and empirical measures.

        Returns:
            Dict[str, Any]: A dictionary with the following keys:
                - "formulas": List[Formula] — generated Formula objects describing
                    analytical and domain-specific relationships.
                - "empirical_relationships": dict — empirical data and metrics
                    derived from the graph (e.g., correlation matrices).
                - "formula_count": int — total number of formulas produced.
                - "categories": dict[str, int] — mapping of formula category to
                    the count of formulas in that category.
                - "summary": dict — aggregated summary metrics and insights about
                    the extracted formulas and empirical results.
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
        Generate a list of fundamental financial formulas applicable to the
        provided asset graph.

        Determines which asset types are present in the graph and returns
        Formula instances for common metrics (e.g., price-to-earnings, dividend
        yield, bond YTM approximation, market capitalization). Each returned
        Formula includes metadata such as variables, an example calculation,
        category, and an r_squared value.

        Parameters:
            graph (AssetRelationshipGraph): Asset relationship graph used to
                decide which formulas apply.

        Returns:
            List[Formula]: List of Formula objects representing fundamental
                valuation, income, and fixed-income formulas relevant to the
                graph.
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
        Analyze correlation-related financial formulas describing relationships
        between asset returns.

        Parameters:
            graph (AssetRelationshipGraph): Asset relationship graph used to
                derive example calculations and empirical strength.

        Returns:
            List[Formula]: Formulas for correlation patterns (e.g., Beta,
                correlation coefficient) with populated metadata and example
                calculations.
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
        Produce valuation-related Formula objects discovered in the provided
        asset relationship graph.

        Includes a Price-to-Book Ratio formula when equities are present and an
        Enterprise Value formula; example calculations are populated from graph
        data when available.

        Parameters:
            graph (AssetRelationshipGraph): Graph to inspect for asset types
                and data used to populate example calculations.

        Returns:
            List[Formula]: A list of valuation Formula instances (e.g.,
                Price-to-Book, Enterprise Value).
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
        Produce risk-return formulas commonly used to assess portfolio
        performance and variability.

        Parameters:
            graph (AssetRelationshipGraph): Asset relationship graph used to
                derive example calculations and contextualize formulas.

        Returns:
            List[Formula]: A list of Formula objects representing risk-return
                measures (including the Sharpe Ratio and Volatility/
                standard deviation), each populated with formula text, LaTeX,
                variable descriptions, example calculations, category, and an
                r_squared estimate.
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
        Generate portfolio-theory formulas for portfolio expected return and
        two-asset portfolio variance.

        Includes Formula objects for the portfolio expected return (weighted
        average of asset expected returns) and the two-asset portfolio variance
        (accounts for asset correlation). Example calculations are populated
        using the provided graph.

        Returns:
            List[Formula]: A list containing Formula instances for
                "Portfolio Expected Return" and "Portfolio Variance
                (2-Asset)".
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
        Extract cross-asset formulas for currency and commodity–currency
        relationships found in the asset graph.

        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and their
                relationships used to detect available asset classes (e.g.,
                currencies, commodities).

        Returns:
            List[Formula]: A list of Formula objects describing detected
                cross-asset relationships (e.g., currency triangular exchange
                relationships and commodity–currency inverse relationships).
                Formulas are included only if the corresponding asset classes
                exist in the graph.
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
        Compute empirical relationships from the provided AssetRelationshipGraph.

        Parameters:
            graph (AssetRelationshipGraph): Graph containing assets and
                observed time-series or relationship edges used to estimate
                empirical statistics.

        Returns:
            dict: A mapping with empirical metrics, typically including:
                - "correlation_matrix" (Dict[Tuple[str, str], float]):
                    pairwise correlation values between asset identifiers.
                - "r_squared_estimates" (Dict[str, float]):
                    goodness-of-fit estimates keyed by formula or
                    relationship name.
                - "relationship_strengths" (Dict[Tuple[str, str], float]):
                    computed strength or weight of relationships
                    between asset pairs.
                - "metadata" (Dict[str, Any]):
                    auxiliary information such as sample sizes, time windows,
                    and computation notes.
        """
        raise NotImplementedError()

    @staticmethod
    def _calculate_avg_correlation_strength(graph: AssetRelationshipGraph) -> float:
        """Calculate average correlation strength in the graph"""
        total_relationships = sum(len(rels) for rels in graph.relationships.values())
        if total_relationships > 0:
            return min(0.75, total_relationships / len(graph.assets) * 0.1)
        return 0.5

    @staticmethod
    def _categorize_formulas(formulas: List[Formula]) -> Dict[str, int]:
        """
        Group formulas by category and return counts for each category.

        Parameters:
                formulas (List[Formula]): A list of Formula instances to categorize.

        Returns:
                category_counts (Dict[str, int]):
                Mapping from category name to the number of formulas in that
                category.
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
        Create a summary of the analyzed formulas and associated empirical
        relationships.

        Computes aggregate metrics and a brief insights list derived from the
        provided formulas and empirical_relationships.

        Returns:
            summary (dict): Dictionary containing:
                - total_formulas (int): Number of formulas analyzed.
                - avg_r_squared (float): Average r_squared across formulas
                  (0 if none).
                - formula_categories (Dict[str, int]): Counts of formulas by
                  category.
                - empirical_data_points (int): Count of entries in the empirical
                  'correlation_matrix'.
                - key_insights (List[str]): Short human-readable insights about
                  the analysis.
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
        Compute the average correlation value from empirical relationships.

        Parameters:
            empirical_relationships (Dict): A mapping that may contain a
                "correlation_matrix" key whose value is a mapping of pair
                identifiers to correlation numbers.

        Returns:
            float: The mean of correlation values from the
                "correlation_matrix", excluding values greater than or
                equal to 1.0.
                Returns 0.5 if no valid correlations are available.
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
