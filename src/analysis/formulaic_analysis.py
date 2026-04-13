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
        Produce a collection of financial formulas and empirical relationship data derived from an AssetRelationshipGraph.

        Orchestrates collection of formula groups and computation of empirical relationship metrics, then assembles the final analysis payload.

        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and their relationships used to detect asset types, select applicable formula templates, and compute empirical metrics.

        Returns:
            result (dict): Analysis payload with keys:
                - "formulas" (List[Formula]): Generated Formula objects describing relationships and metrics.
                - "empirical_relationships" (Dict[str, Any]): Empirical data derived from the graph (e.g., correlation matrix, strongest correlations, asset-class and sector relationships).
                - "formula_count" (int): Total number of formulas generated.
                - "categories" (Dict[str, int]): Counts of formulas grouped by category.
                - "summary" (Dict[str, Any]): High-level summary metrics and insights about the generated formulas and empirical relationships.
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
        """
        Collects and concatenates all formula groups derived from the provided asset relationship graph.
        
        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and their relationships used to derive formulas.
        
        Returns:
            List[Formula]: A flat list of Formula objects assembled from fundamental, correlation, valuation,
            risk/return, portfolio theory, and cross-asset analysis routines.
        """
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
        """
        Builds the top-level analysis payload containing discovered formulas, empirical relationships, and computed metadata.

        Parameters:
            all_formulas (List[Formula]): Discovered Formula objects to include in the payload.
            empirical_relationships (Dict[str, Any]): Empirical data derived from the graph (e.g., correlation matrix, strongest correlations, asset/sector summaries).

        Returns:
            analysis_result (Dict[str, Any]): Mapping with keys:
                - "formulas": list of provided Formula objects,
                - "empirical_relationships": the provided empirical relationships dict,
                - "formula_count": total number of formulas,
                - "categories": mapping of category name to formula count,
                - "summary": summary metrics and insights computed from the formulas and empirical data.
        """
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
        Builds fundamental valuation and income formulas relevant to the assets in the provided graph.

        Parameters:
            graph (AssetRelationshipGraph): Asset relationship graph used to determine which fundamental formulas are applicable.

        Returns:
            List[Formula]: A list of Formula objects for applicable fundamentals (for example: equity fundamentals and dividend yield when dividend-paying stocks are present).
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
        """
        Return fundamental equity formulas when the graph contains equities.
        
        Returns:
            list[Formula]: Price-to-Earnings and Market Capitalization formulas when the graph contains equities, otherwise an empty list.
        """
        if not has_equities(graph):
            return []
        return [
            FormulaicAnalyzer._price_to_earnings_formula(graph),
            FormulaicAnalyzer._market_capitalization_formula(graph),
        ]

    @staticmethod
    def _price_to_earnings_formula(graph: AssetRelationshipGraph) -> Formula:
        """
        Constructs a Formula describing the Price-to-Earnings (P/E) ratio.
        
        Parameters:
            graph (AssetRelationshipGraph): Graph used to derive the example_calculation for the formula.
        
        Returns:
            Formula: A Formula with name "Price-to-Earnings", expression "P / E", LaTeX r"\frac{P}{E}", variables mapping `"P"` to the price-per-share label and `"E"` to "Earnings per share (EPS)", category "Valuation", example_calculation produced from `graph`, and `r_squared` set to 0.0.
        """
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
        """
        Create a Formula representing dividend yield (dividend per share divided by price per share).
        
        Parameters:
            graph (AssetRelationshipGraph): Graph used to derive example calculations for dividend yield.
        
        Returns:
            Formula: A Formula with name "Dividend Yield", expression "D / P", LaTeX "\\frac{D}{P}", variable descriptions for `D` and `P`, an example_calculation derived from the provided graph, category "Income", and r_squared set to 0.0.
        """
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
        """
        Constructs a Formula representing market capitalization (Price × Shares Outstanding).
        
        Parameters:
            graph (AssetRelationshipGraph): Graph used to derive the formula's example_calculation and contextual metadata.
        
        Returns:
            Formula: A Formula for market capitalization whose example_calculation is generated from the provided graph, with category "Valuation" and r_squared set to 0.0.
        """
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
        Collects standard formulas describing asset beta (systematic risk) and the Pearson correlation coefficient.
        
        Each Formula includes variable descriptions, an example calculation derived from the provided graph, a category label, and an r_squared estimate indicating expected explanatory strength.
        
        Returns:
            List[Formula]: Two Formula objects: `Beta (Systematic Risk)` and `Correlation Coefficient`.
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
        Collect valuation formulas applicable to the provided asset relationship graph.
        
        Includes price-to-book when equities are present and always includes an enterprise value formula.
        
        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and relationships used to determine applicable valuation formulas.
        
        Returns:
            List[Formula]: Valuation Formula objects relevant to the graph (e.g., Price-to-Book, Enterprise Value).
        """
        formulas: List[Formula] = []
        if has_equities(graph):
            formulas.append(self._price_to_book_formula(graph))
        formulas.append(self._enterprise_value_formula())
        return formulas

    @staticmethod
    def _price_to_book_formula(graph: AssetRelationshipGraph) -> Formula:
        """
        Create a Formula object representing the Price-to-Book (P/B) ratio.
        
        Parameters:
            graph (AssetRelationshipGraph): Graph used to generate the example calculation for the formula.
        
        Returns:
            Formula: A Formula describing the Price-to-Book ratio with its expression, variables, example calculation populated from `graph`, category "Valuation", and an expected r_squared of 0.88.
        """
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
        """
        Constructs a Formula describing Enterprise Value (EV = Market_Cap + Total_Debt - Cash).
        
        Returns:
            Formula: A Formula populated with metadata for Enterprise Value, including the expression and LaTeX, variable descriptions for EV, Market_Cap, Debt, and Cash, an example_calculation noting debt/cash data is unavailable in the current dataset, category "Valuation", and r_squared set to 0.95.
        """
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
        Assemble formula definitions for common risk–return metrics.

        Parameters:
            graph (AssetRelationshipGraph): Graph used to populate example calculations and contextual values for each formula.

        Returns:
            List[Formula]: A list of Formula objects (e.g., Sharpe Ratio and volatility) with expression, LaTeX, variables, example_calculation, category, and r_squared populated.
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
        Constructs portfolio-theory formulas applicable to the given asset relationship graph.

        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and relationships used to derive example calculations and populate formula metadata.

        Returns:
            List[Formula]: Formula objects representing portfolio-theory relationships, currently including the Portfolio Expected Return formula.
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
        Identify and construct formulas representing detected cross-asset relationships in the asset graph.

        Includes currency exchange (triangular arbitrage) relationships when currencies are present and commodity–currency inverse relationships when both commodities and currencies are present.

        Returns:
            List[Formula]: Formula objects representing detected cross-asset relationships; an empty list if none are found.
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
        """
        Generate empirical relationship data derived from an AssetRelationshipGraph.

        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and relationships used to compute empirical statistics.

        Returns:
            dict: Payload containing empirical data with keys:
                - correlation_matrix (Dict[str, float]): Pairwise relationship strengths keyed by "srcId-targetId".
                - strongest_correlations (List[Dict[str, Any]]): Top correlations with metadata (pair, asset1, asset2, correlation, strength).
                - asset_class_relationships (Dict[str, Dict[str, Any]]): Aggregated statistics per asset class (asset_count, avg_price, total_value).
                - sector_relationships (Dict[str, Dict[str, Any]]): Aggregated statistics per sector (asset_count, avg_price, price_range).
        """
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
        """
        Construct a mapping of asset-pair keys to the strongest numeric relationship strength observed between them.

        Parameters:
            graph (AssetRelationshipGraph): Graph whose relationships are iterated to extract numeric strength values. Each relationship entry is expected to contain (target_id, type, strength).

        Returns:
            Dict[str, float]: Mapping where each key is a canonical "assetA-assetB"
            pair (lexicographically sorted) and the value is the largest-magnitude
            numeric strength seen for that pair. Entries with non-numeric strengths
            are skipped; self-relations are not included.
        """
        correlation_matrix: Dict[str, float] = {}
        for src_id, rels in graph.relationships.items():
            for target_id, _rel_type, strength in rels:
                if src_id == target_id:
                    continue
                try:
                    strength_value = float(strength)
                except (TypeError, ValueError):
                    continue
                pair_key = "-".join(sorted((src_id, target_id)))
                existing = correlation_matrix.get(pair_key)
                if existing is None or abs(strength_value) > abs(existing):
                    correlation_matrix[pair_key] = strength_value
        return correlation_matrix

    @staticmethod
    def _build_strongest_correlations(
        correlation_matrix: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        Compile the top correlation pairs by absolute strength from a correlation matrix.

        Parameters:
            correlation_matrix (Dict[str, float]): Mapping with keys of the form "assetA-assetB" and numeric correlation values.

        Returns:
            List[Dict[str, Any]]: Up to 10 correlation entries sorted by descending absolute correlation. Each entry contains:
                - "pair": string "assetA-assetB"
                - "asset1": first asset id
                - "asset2": second asset id
                - "correlation": numeric correlation value
                - "strength": one of "Strong" (>0.7), "Moderate" (>0.4), or "Weak" (otherwise)

        Notes:
            Correlations with absolute value > 1.0 are excluded as invalid.
        """
        strongest_correlations: List[Dict[str, Any]] = []
        for pair_key, corr in correlation_matrix.items():
            asset1, asset2 = pair_key.split("-", 1)
            if abs(corr) > 1.0:
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
        """
        Summarizes asset counts, average price, and total market value grouped by asset class.

        This function iterates the assets in the provided graph and produces per-asset-class
        statistics. Missing or non-numeric price and market_cap values are treated as 0.0.

        Parameters:
            graph (AssetRelationshipGraph): Graph containing assets to aggregate.

        Returns:
            Dict[str, Dict[str, Any]]: Mapping from asset class name to a stats dictionary with keys:
                - "asset_count" (int): Number of assets in the class.
                - "avg_price" (float): Average asset price for the class (0.0 if none).
                - "total_value" (float): Sum of market_cap values for the class.
        """
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
        """
        Build per-sector statistics for assets in the provided graph.

        Produces a mapping from sector name to a dictionary containing:
        - asset_count: number of assets assigned to the sector.
        - avg_price: average price of assets in the sector as a float.
        - price_range: formatted string representing the sector's price range (min to max, e.g. "$1.00 - $5.00").

        Assets that do not have a sector are ignored.
        """
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
        """
        Compute the average price and a human-readable price range for a sector.

        Parameters:
            prices (List[float]): List of asset prices in USD for the sector.

        Returns:
            tuple[float, str]: A tuple where the first element is the average price (0.0 if list is empty)
            and the second element is a formatted price range string like "$min - $max" (or "$0.00 - $0.00" if empty).
        """
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
        """
        Group formulas by category and count how many formulas belong to each category.

        Parameters:
            formulas (List[Formula]): Sequence of Formula objects to categorize.

        Returns:
            category_counts (Dict[str, int]): Mapping from category name to the number of formulas in that category.
        """
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
                *(
                    ["Cross-asset relationships identified between commodities and currencies"]
                    if any(formula.name == "Commodity-Currency Relationship" for formula in formulas)
                    else []
                ),
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
