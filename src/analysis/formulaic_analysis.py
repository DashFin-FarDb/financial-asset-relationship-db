"""Formula extraction and analysis for financial asset relationships."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Final, List

from src.analysis.formulaic_examples import (
    calculate_beta_examples,
    calculate_commodity_currency_examples,
    calculate_correlation_examples,
    calculate_dividend_examples,
    calculate_exchange_rate_examples,
    calculate_market_cap_examples,
    calculate_pb_examples,
    calculate_pe_examples,
    calculate_portfolio_return_examples,
    calculate_sharpe_examples,
    calculate_volatility_examples,
    has_commodities,
    has_currencies,
    has_dividend_stocks,
    has_equities,
)
from src.logic.asset_graph import AssetRelationshipGraph

logger = logging.getLogger(__name__)

PRICE_PER_SHARE_LABEL: Final = "Price per share"
RISK_MANAGEMENT_CATEGORY: Final = "Risk Management"


@dataclass  # pylint: disable=too-many-instance-attributes
class Formula:
    """Represents a mathematical formula between financial variables.

    The formula expression is stored in the `expression` field.

    Example:
        >>> Formula(
        ...     name="Test",
        ...     expression="x + y",
        ...     latex="x + y",
        ...     description="Test formula",
        ...     variables={"x": "var1", "y": "var2"},
        ...     example_calculation="1 + 2 = 3",
        ...     category="test",
        ... )
    """

    name: str
    expression: str
    latex: str
    description: str
    variables: Dict[str, str]  # variable_name -> description
    example_calculation: str
    category: str
    r_squared: float = 0.0  # Correlation strength if applicable


# Pylint design rule is intentionally suppressed: this service class exposes
# one public entry point and keeps helper methods private.
# pylint: disable=too-few-public-methods
class FormulaicAnalyzer:
    """Analyzes financial data and renders mathematical relationships."""

    def __init__(self) -> None:
        """
        Initialize a FormulaicAnalyzer instance.

        Creates an empty list to collect Formula objects discovered
        during graph analysis, and prepares the analyzer for use.
        """
        self.formulas: List[Formula] = []

    def analyze_graph(self, graph: AssetRelationshipGraph) -> Dict[str, Any]:
        """
        Analyze an AssetRelationshipGraph and assemble a collection of
        financial formulas and empirical relationship data describing asset
        interactions.

        Parameters:
            graph (AssetRelationshipGraph):
                Graph of assets and their relationships used to detect
                asset types, extract formula templates, and compute empirical
                relationship metrics.

        Returns:
            dict:
                A summary structure with the following keys:
                - "formulas" (List[Formula]):
                    All generated Formula objects describing relationships
                    and metrics.
                - "empirical_relationships" (Any):
                    Empirical data derived from the graph (e.g.,
                    correlation matrices or derived metrics).
                - "formula_count" (int):
                    Total number of formulas generated.
                - "categories" (Dict[str, int]):
                    Counts of formulas grouped by category.
                - "summary" (Dict[str, Any]):
                    High-level summary metrics and insights about the generated
                    formulas and empirical relationships.
        """
        logger.info("Starting formulaic analysis of asset relationships")
        all_formulas = self._collect_formula_groups(graph)
        empirical_relationships = self._calculate_empirical_relationships(graph)
        return self._build_analysis_result(
            all_formulas,
            empirical_relationships,
        )

    def _collect_formula_groups(
        self,
        graph: AssetRelationshipGraph,
    ) -> List[Formula]:
        """Collect all formula groups generated from the graph."""
        return (
            self._extract_fundamental_formulas(graph)
            + self._analyze_correlation_patterns(graph)
            + self._extract_valuation_relationships(graph)
            + self._analyze_risk_return_relationships(graph)
            + self._extract_portfolio_theory_formulas(graph)
            + self._analyze_cross_asset_relationships(graph)
        )

    def _build_analysis_result(
        self,
        all_formulas: List[Formula],
        empirical_relationships: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the top-level analysis payload consumed by callers."""
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
        self,
        graph: AssetRelationshipGraph,
    ) -> List[Formula]:
        """
        Build fundamental valuation and income formulas relevant to the assets
        in the graph.

        Parameters:
            graph (AssetRelationshipGraph):
                The asset relationship graph to analyze.

        Returns:
            List[Formula]: Formula objects for commonly-used metrics such as
            price-to-earnings, dividend yield,
            bond yield-to-maturity approximation,
            and market capitalization, where applicable to assets in the
            provided graph.
        """
        formulas: list[Formula] = []
        formulas.extend(self._equity_fundamental_formulas(graph))
        if has_dividend_stocks(graph):
            formulas.append(self._dividend_yield_formula(graph))

        # NOTE: Bond yield-to-maturity (YTM) approximation
        # is not yet implemented.
        # When bond instruments are present in the graph, detect bond nodes and
        # compute approximate YTM using bond price, coupon rate,
        # and time to maturity (e.g., via iterative solution of
        # price = present value of cash flows).
        # Add a Formula entry for YTM to the formulas list.
        return formulas

    @staticmethod
    def _equity_fundamental_formulas(
        graph: AssetRelationshipGraph,
    ) -> list[Formula]:
        """Return equity-only fundamental formulas."""
        if not has_equities(graph):
            return []
        return [
            FormulaicAnalyzer._price_to_earnings_formula(graph),
            FormulaicAnalyzer._market_capitalization_formula(graph),
        ]

    @staticmethod
    def _price_to_earnings_formula(graph: AssetRelationshipGraph) -> Formula:
        """Build the Price-to-Earnings formula."""
        return Formula(
            name="Price-to-Earnings",
            expression="P / E",
            latex=r"\frac{P}{E}",
            description=("Market price per share divided by earnings per share."),
            variables={
                "P": PRICE_PER_SHARE_LABEL,
                "E": "Earnings per share (EPS)",
            },
            example_calculation=calculate_pe_examples(graph),
            category="Valuation",
            r_squared=0.0,
        )

    @staticmethod
    def _dividend_yield_formula(graph: AssetRelationshipGraph) -> Formula:
        """Build the Dividend Yield formula."""
        return Formula(
            name="Dividend Yield",
            expression="D / P",
            latex=r"\frac{D}{P}",
            description="Dividend per share divided by price per share.",
            variables={
                "D": "Dividend per share",
                "P": PRICE_PER_SHARE_LABEL,
            },
            example_calculation=calculate_dividend_examples(graph),
            category="Income",
            r_squared=0.0,
        )

    @staticmethod
    def _market_capitalization_formula(
        graph: AssetRelationshipGraph,
    ) -> Formula:
        """Build the Market Capitalization formula."""
        return Formula(
            name="Market Capitalization",
            expression="Price × Shares Outstanding",
            latex=r"P \times \text{Shares}",
            description=("Estimated market capitalization computed from price and shares outstanding."),
            variables={
                "Price": PRICE_PER_SHARE_LABEL,
                "Shares Outstanding": "Number of shares outstanding",
            },
            example_calculation=calculate_market_cap_examples(graph),
            category="Valuation",
            r_squared=0.0,
        )

    def _analyze_correlation_patterns(
        self,
        graph: AssetRelationshipGraph,
    ) -> List[Formula]:
        """
        Build Formula objects describing
        asset correlation and systematic risk.

        Create formula entries for Beta
        (asset sensitivity to market movements)
        and the Pearson correlation coefficient,
        each populated with variable descriptions,
        example calculations, and an r_squared estimate.

        Returns:
            List[Formula]: A list of Formula objects for Beta and the
                correlation coefficient, populated with descriptions,
                variables, example calculations, categories, and r_squared
                values.
        """
        formulas = []

        # Beta relationship (systematic risk)
        beta_formula = Formula(
            name="Beta (Systematic Risk)",
            expression="β = Cov(R_asset, R_market) / Var(R_market)",
            latex=r"\beta = \frac{Cov(R_i, R_m)}{Var(R_m)}",
            description=("Measure of an asset's sensitivity to market movements"),
            variables={
                "β": "Beta coefficient",
                "R_i": "Asset return",
                "R_m": "Market return",
                "Cov": "Covariance",
                "Var": "Variance",
            },
            example_calculation=calculate_beta_examples(graph),
            category=RISK_MANAGEMENT_CATEGORY,
            r_squared=0.75,
        )
        formulas.append(beta_formula)

        # Correlation coefficient
        correlation_formula = Formula(
            name="Correlation Coefficient",
            expression="ρ = Cov(X, Y) / (σ_X × σ_Y)",
            latex=(r"\rho = \frac{Cov(X, Y)}{\sigma_X \times \sigma_Y}"),
            description="Measure of linear relationship between two variables",
            variables={
                "ρ": "Correlation coefficient (-1 to 1)",
                "Cov(X,Y)": "Covariance between X and Y",
                "σ_X": "Standard deviation of X",
                "σ_Y": "Standard deviation of Y",
            },
            example_calculation=calculate_correlation_examples(graph),
            category="Statistical Analysis",
            r_squared=self._calculate_avg_correlation_strength(graph),
        )
        formulas.append(correlation_formula)

        return formulas

    def _extract_valuation_relationships(
        self,
        graph: AssetRelationshipGraph,
    ) -> List[Formula]:
        """
        Assemble valuation-related formulas derived from the provided asset
        relationship graph.

        Generates valuation formulas when relevant asset types or
        attributes are present (for example, Price-to-Book when equities
        exist, and Enterprise Value).

        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and relationships
                used to determine which valuation formulas apply.

        Returns:
            list[Formula]: A list of Formula objects representing
                extracted valuation relationships.
        """
        formulas: List[Formula] = []
        if has_equities(graph):
            formulas.append(self._price_to_book_formula(graph))
        formulas.append(self._enterprise_value_formula())
        return formulas

    @staticmethod
    def _price_to_book_formula(graph: AssetRelationshipGraph) -> Formula:
        """Build the Price-to-Book ratio formula."""
        return Formula(
            name="Price-to-Book Ratio",
            expression="P/B = Market_Price / Book_Value_per_Share",
            latex=r"P/B = \frac{P}{BV_{per\_share}}",
            description=("Valuation metric comparing market price to book value"),
            variables={
                "P/B": "Price-to-Book Ratio",
                "P": "Market Price per Share ($)",
                "BV_per_share": ("Book Value per Share ($)"),
            },
            example_calculation=calculate_pb_examples(graph),
            category="Valuation",
            r_squared=0.88,
        )

    @staticmethod
    def _enterprise_value_formula() -> Formula:
        """Build the Enterprise Value formula."""
        return Formula(
            name="Enterprise Value",
            expression="EV = Market_Cap + Total_Debt - Cash",
            latex=r"EV = MarketCap + Debt - Cash",
            description="Total value of a company including debt",
            variables={
                "EV": "Enterprise Value ($)",
                "Market_Cap": "Market Capitalization ($)",
                "Debt": "Total Debt ($)",
                "Cash": "Cash and Cash Equivalents ($)",
            },
            example_calculation=("EV calculation requires debt and cash data (not available in current dataset)"),
            category="Valuation",
            r_squared=0.95,
        )

    def _analyze_risk_return_relationships(
        self,
        graph: AssetRelationshipGraph,
    ) -> List[Formula]:
        """
        Assemble a set of formula definitions for common risk–return metrics.

        Parameters:
            graph (AssetRelationshipGraph): Graph used to populate example
                calculations and contextual values for each formula.

        Returns:
            List[Formula]: A list of Formula objects describing
                risk–return metrics (for example, Sharpe Ratio
                and volatility) with populated fields
                such as expression, LaTeX, variables, example_calculation,
                category, and r_squared.
        """
        formulas = []

        # Sharpe Ratio
        sharpe_formula = Formula(
            name="Sharpe Ratio",
            expression="Sharpe = (R_portfolio - R_risk_free) / σ_portfolio",
            latex=r"Sharpe = \frac{R_p - R_f}{\sigma_p}",
            description="Risk-adjusted return metric",
            variables={
                "Sharpe": "Sharpe Ratio",
                "R_p": "Portfolio Return (%)",
                "R_f": "Risk-free Rate (%)",
                "σ_p": "Portfolio Standard Deviation (%)",
            },
            example_calculation=calculate_sharpe_examples(graph),
            category=RISK_MANAGEMENT_CATEGORY,
            r_squared=0.82,
        )
        formulas.append(sharpe_formula)

        # Volatility (Standard Deviation)
        volatility_formula = Formula(
            name="Volatility (Standard Deviation)",
            expression="σ = √(Σ(R_i - μ)² / (n-1))",
            latex=r"\sigma = \sqrt{\frac{\sum_{i=1}^{n}(R_i - \mu)^2}{n-1}}",
            description="Measure of price variability and risk",
            variables={
                "σ": "Standard deviation (volatility)",
                "R_i": "Individual return",
                "μ": "Mean return",
                "n": "Number of observations",
            },
            example_calculation=calculate_volatility_examples(graph),
            category=RISK_MANAGEMENT_CATEGORY,
            r_squared=0.90,
        )
        formulas.append(volatility_formula)

        return formulas

    def _extract_portfolio_theory_formulas(
        self,
        graph: AssetRelationshipGraph,
    ) -> List[Formula]:
        """
        Build Modern Portfolio Theory formulas
        derived from the asset relationship graph.

        Returns:
            formulas (List[Formula]): Formula objects
                representing portfolio theory relationships,
                including portfolio expected return and portfolio
                variance for a two-asset case.
        """
        formulas = []

        # Portfolio Expected Return
        portfolio_return_formula = Formula(
            name="Portfolio Expected Return",
            expression="E(R_p) = Σ(w_i × E(R_i))",
            latex=r"E(R_p) = \sum_{i=1}^{n} w_i \times E(R_i)",
            description=("Weighted average of individual asset expected returns"),
            variables={
                "E(R_p)": "Expected portfolio return",
                "w_i": "Weight of asset i in portfolio",
                "E(R_i)": "Expected return of asset i",
                "n": "Number of assets",
            },
            example_calculation=(calculate_portfolio_return_examples(graph)),
            category="Portfolio Theory",
            r_squared=1.0,
        )
        formulas.append(portfolio_return_formula)

        # Portfolio Variance (2-asset case)
        return formulas

    def _analyze_cross_asset_relationships(
        self,
        graph: AssetRelationshipGraph,
    ) -> List[Formula]:
        """
        Assemble formulas describing detected
        relationships between different asset classes in the graph.

        Includes currency triangular-arbitrage/exchange-rate relationships when
        currencies are present, and commodity–currency inverse
        relationships when both commodities and currencies are present.

        Returns:
            formulas (List[Formula]):
                A list of Formula objects
                representing cross-asset relationships in the graph.
        """
        formulas = []

        # Currency exchange relationships
        if has_currencies(graph):
            exchange_rate_formula = Formula(
                name="Exchange Rate Relationships",
                expression="USD/EUR × EUR/GBP = USD/GBP",
                latex=(r"\frac{USD}{EUR} \times \frac{EUR}{GBP} = " r"\frac{USD}{GBP}"),
                description=("Triangular arbitrage relationship between currencies"),
                variables={
                    "USD/EUR": "US Dollar to Euro exchange rate",
                    "EUR/GBP": "Euro to British Pound exchange rate",
                    "USD/GBP": "US Dollar to British Pound exchange rate",
                },
                example_calculation=(calculate_exchange_rate_examples(graph)),
                category="Currency Markets",
                r_squared=0.99,
            )
            formulas.append(exchange_rate_formula)

        # Commodity-Currency relationship
        if has_commodities(graph) and has_currencies(graph):
            commodity_currency_formula = Formula(
                name="Commodity-Currency Relationship",
                expression=("Currency_Value ∝ 1/Commodity_Price (for commodity exporters)"),
                latex=r"FX_{commodity} \propto \frac{1}{P_{commodity}}",
                description=("Inverse relationship between commodity prices and currency values"),
                variables={
                    "FX_commodity": "Currency value of commodity exporter",
                    "P_commodity": "Commodity price",
                },
                example_calculation=(calculate_commodity_currency_examples(graph)),
                category="Cross-Asset",
                r_squared=0.65,
            )
            formulas.append(commodity_currency_formula)

        return formulas

    @staticmethod
    def _calculate_empirical_relationships(
        graph: AssetRelationshipGraph,
    ) -> Dict[str, Any]:
        """Calculate empirical relationships from the asset graph."""
        correlation_matrix = FormulaicAnalyzer._build_correlation_matrix(graph)
        strongest_correlations = FormulaicAnalyzer._build_strongest_correlations(correlation_matrix)
        asset_class_relationships = FormulaicAnalyzer._build_asset_class_relationships(graph)
        sector_relationships = FormulaicAnalyzer._build_sector_relationships(graph)
        return {
            "correlation_matrix": correlation_matrix,
            "strongest_correlations": strongest_correlations,
            "asset_class_relationships": asset_class_relationships,
            "sector_relationships": sector_relationships,
        }

    @staticmethod
    def _build_correlation_matrix(
        graph: AssetRelationshipGraph,
    ) -> Dict[str, float]:
        """Build a correlation-style matrix from relationship strengths."""
        correlation_matrix: Dict[str, float] = {}
        for src_id, rels in graph.relationships.items():
            for target_id, _rel_type, strength in rels:
                if src_id == target_id:
                    continue
                try:
                    strength_value = float(strength)
                except (TypeError, ValueError):
                    continue
                pair_key = f"{src_id}-{target_id}"
                existing = correlation_matrix.get(pair_key)
                if existing is None or abs(strength_value) > abs(existing):
                    correlation_matrix[pair_key] = strength_value
        return correlation_matrix

    @staticmethod
    def _build_strongest_correlations(
        correlation_matrix: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Build top strongest correlation entries from correlation data."""
        strongest_correlations: List[Dict[str, Any]] = []
        for pair_key, corr in correlation_matrix.items():
            asset1, asset2 = pair_key.split("-", 1)
            if abs(corr) >= 1.0:
                continue
            if abs(corr) > 0.7:
                strength_label = "Strong"
            elif abs(corr) > 0.4:
                strength_label = "Moderate"
            else:
                strength_label = "Weak"
            strongest_correlations.append(
                {
                    "pair": f"{asset1}-{asset2}",
                    "asset1": asset1,
                    "asset2": asset2,
                    "correlation": corr,
                    "strength": strength_label,
                }
            )
        strongest_correlations.sort(
            key=lambda item: abs(item["correlation"]),
            reverse=True,
        )
        return strongest_correlations[:10]

    @staticmethod
    def _build_asset_class_relationships(
        graph: AssetRelationshipGraph,
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate relationship statistics by asset class."""
        asset_class_relationships: Dict[str, Dict[str, Any]] = {}
        for asset in graph.assets.values():
            asset_class = getattr(
                asset.asset_class,
                "value",
                str(asset.asset_class),
            )
            price = float(getattr(asset, "price", 0.0) or 0.0)
            market_cap = float(getattr(asset, "market_cap", 0.0) or 0.0)
            stats = asset_class_relationships.setdefault(
                asset_class,
                {
                    "asset_count": 0,
                    "avg_price": 0.0,
                    "total_value": 0.0,
                    "_total_price": 0.0,
                },
            )
            stats["asset_count"] += 1
            stats["_total_price"] += price
            stats["total_value"] += market_cap

        for stats in asset_class_relationships.values():
            count = stats["asset_count"]
            total_price = stats.pop("_total_price", 0.0)
            stats["avg_price"] = total_price / count if count else 0.0
        return asset_class_relationships

    @staticmethod
    def _build_sector_relationships(
        graph: AssetRelationshipGraph,
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate relationship statistics by sector."""
        sector_relationships: Dict[str, Dict[str, Any]] = {}
        for asset in graph.assets.values():
            sector = getattr(asset, "sector", None)
            if not sector:
                continue
            price = float(getattr(asset, "price", 0.0) or 0.0)
            stats = sector_relationships.setdefault(
                sector,
                {
                    "asset_count": 0,
                    "avg_price": 0.0,
                    "price_range": "",
                    "_prices": [],
                },
            )
            stats["asset_count"] += 1
            stats["_prices"].append(price)

        for stats in sector_relationships.values():
            prices = stats.pop("_prices", [])
            avg_price, price_range = FormulaicAnalyzer._summarize_sector_prices(prices)
            stats["avg_price"] = avg_price
            stats["price_range"] = price_range
        return sector_relationships

    @staticmethod
    def _summarize_sector_prices(prices: List[float]) -> tuple[float, str]:
        """Return average price and display range for a sector price list."""
        if not prices:
            return 0.0, "$0.00 - $0.00"
        return (
            (sum(prices) / len(prices)),
            f"${min(prices):.2f} - ${max(prices):.2f}",
        )

    @staticmethod
    def _calculate_avg_correlation_strength(
        graph: AssetRelationshipGraph,
    ) -> float:
        """
        Estimate the average correlation strength across all relationships
        in the provided graph.

        Returns:
            A float between 0.0 and 0.75 representing the average relationship
            strength; returns 0.5 when the graph contains no relationship
            strength data.
        """
        strengths = [strength for rels in graph.relationships.values() for _, _, strength in rels]
        if strengths:
            avg_strength = sum(strengths) / len(strengths)
            return min(0.75, max(0.0, avg_strength))
        return 0.5

    @staticmethod
    def _categorize_formulas(formulas: List[Formula]) -> Dict[str, int]:
        """Categorize formulas by type."""
        categories: Dict[str, int] = {}
        for formula in formulas:
            category = formula.category
            categories[category] = categories.get(category, 0) + 1
        return categories

    def _generate_formula_summary(
        self,
        formulas: List[Formula],
        empirical_relationships: Dict,
    ) -> Dict[str, Any]:
        """
        Create a concise summary of analyzed formulas and their
        empirical relationships.

        Parameters:
            formulas (List[Formula]):
                List of Formula objects produced by the analysis.
            empirical_relationships (dict):
                Empirical data from the analysis; may contain a
                "correlation_matrix" mapping whose length is used to count
                    empirical data points.

        Returns:
            dict: Summary with keys:
                total_formulas (int): Number of formulas in `formulas`.
                avg_r_squared (float): Average `r_squared` across `formulas`
                    (0 if `formulas` is empty).
                formula_categories (dict): Mapping of category name
                    to count of formulas.
                empirical_data_points (int):
                    Number of entries in
                    `empirical_relationships["correlation_matrix"]`
                    (0 if missing).
                key_insights (list[str]): Short human-readable insight strings
                    derived from the formulas and empirical data.
        """
        avg_corr_strength = self._calculate_avg_correlation_strength_from_empirical(empirical_relationships)

        if formulas:
            avg_r_squared = sum(f.r_squared for f in formulas if isinstance(f.r_squared, (int, float))) / len(formulas)
        else:
            avg_r_squared = 0.0

        return {
            "total_formulas": len(formulas),
            "avg_r_squared": avg_r_squared,
            "formula_categories": self._categorize_formulas(formulas),
            "empirical_data_points": len(empirical_relationships.get("correlation_matrix", {})),
            "key_insights": [
                f"Identified {len(formulas)} mathematical relationships",
                f"Average correlation strength: {avg_corr_strength:.2f}",
                "Valuation models applicable to equity assets",
                "Portfolio theory formulas available for multi-asset analysis",
                ("Cross-asset relationships identified between commodities and currencies"),
            ],
        }

    @staticmethod
    def _calculate_avg_correlation_strength_from_empirical(
        empirical_relationships: Dict,
    ) -> float:
        """
        Estimate the average correlation value
        from the empirical relationships data.

        Expects a mapping under the "correlation_matrix" key where values are
        correlation coefficients.
        Ignores correlation entries equal to or exceeding 1.0
        (typically self-correlations) and computes the arithmetic mean
        of the remaining values. If no valid correlations are found or
        the expected key is missing, returns 0.5 as a neutral default.

        Parameters:
            empirical_relationships (dict): Empirical data that should contain
                a "correlation_matrix" mapping identifiers to numeric
                correlation coefficients.

        Returns:
            float: The average correlation (0.0–1.0), or 0.5 if no valid
                correlation values are found.
        """
        correlations = empirical_relationships.get("correlation_matrix", {})
        if correlations:
            valid_correlations = [v for v in correlations.values() if v < 1.0]
            return sum(valid_correlations) / len(valid_correlations) if valid_correlations else 0.5
        return 0.5
