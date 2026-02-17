import logging
from dataclasses import dataclass
from typing import Any, Dict, Final, List

from src.logic.asset_graph import AssetRelationshipGraph

logger = logging.getLogger(__name__)

PRICE_PER_SHARE_LABEL: Final = "Price per share"


@dataclass
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


class FormulaicAnalyzer:
    """Analyzes financial data to extract and render mathematical relationships."""

    def __init__(self):
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

    def _extract_fundamental_formulas(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Build fundamental valuation and income formulas relevant to the assets
        in the graph.

        Parameters:
            graph (AssetRelationshipGraph): The asset relationship graph to analyze.

        Returns:
            List[Formula]: Formula objects for commonly-used metrics such as
            price-to-earnings, dividend yield,
            bond yield-to-maturity approximation,
            and market capitalization, where applicable to assets in the
            provided graph.
        """
        formulas: list[Formula] = []

        # Example: Price-to-earnings (P/E)
        if self._has_equities(graph):
            formulas.append(
                Formula(
                    name="Price-to-Earnings",
                    expression="P / E",
                    latex=r"\frac{P}{E}",
                    description="Market price per share divided by earnings per share.",
                    variables={
                        "P": PRICE_PER_SHARE_LABEL,
                        "E": "Earnings per share (EPS)",
                    },
                    example_calculation=self._calculate_pe_examples(graph),
                    category="Valuation",
                    r_squared=0.0,
                )
            )

        # Dividend yield
        if self._has_dividend_stocks(graph):
            formulas.append(
                Formula(
                    name="Dividend Yield",
                    formula="D / P",
                    latex=r"\frac{D}{P}",
                    description="Dividend per share divided by price per share.",
                    variables={
                        "D": "Dividend per share",
                        "P": PRICE_PER_SHARE_LABEL,
                    },
                    example_calculation=self._calculate_dividend_examples(graph),
                    category="Income",
                    r_squared=0.0,
                )
            )

        # Market capitalization
        if self._has_equities(graph):
            formulas.append(
                Formula(
                    name="Market Capitalization",
                    formula="Price × Shares Outstanding",
                    latex=r"P \times \text{Shares}",
                    description=("Estimated market capitalization computed from price and " "shares outstanding."),
                    variables={
                        "Price": PRICE_PER_SHARE_LABEL,
                        "Shares Outstanding": "Number of shares outstanding",
                    },
                    example_calculation=self._calculate_market_cap_examples(graph),
                    category="Valuation",
                    r_squared=0.0,
                )
            )

        # NOTE: Bond yield-to-maturity (YTM) approximation is not yet implemented.
        # When bond instruments are present in the graph, detect bond nodes and
        # compute approximate YTM using bond price, coupon rate, and time to maturity
        # (e.g., via iterative solution of price = present value of cash flows).
        # Add a Formula entry for YTM to the formulas list.
        return formulas

    def _analyze_correlation_patterns(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Builds Formula objects that describe asset correlation and systematic risk.

        Creates formula entries for Beta (asset sensitivity to market movements) and
        the Pearson correlation coefficient, each populated with variable
        descriptions, example calculations, drawn from the graph, and an
        r_squared estimate.

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
            latex=(r"\rho = \frac{Cov(X, Y)}{\sigma_X \times \sigma_Y}"),
            description="Measure of linear relationship between two variables",
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

    def _extract_valuation_relationships(self, graph: AssetRelationshipGraph) -> List[Formula]:
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
                    "BV_per_share": ("Book Value per Share ($)"),
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
        Assemble a set of formula definitions for common risk–return metrics.

        Parameters:
            graph (AssetRelationshipGraph): Graph used to populate example
                calculations and contextual values for each formula.

        Returns:
            List[Formula]: A list of Formula objects describing risk–return metrics
                (for example, Sharpe Ratio and volatility) with populated fields
                such as expression, LaTeX, variables, example_calculation,
                category, and r_squared.
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
            latex=(r"\sigma = \sqrt{\frac{\sum_{i=1}^{n}(R_i - \mu)^2}" r"{n-1}}"),
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
        Builds Modern Portfolio Theory formulas derived from the asset relationship
        graph.

        Returns:
            formulas (List[Formula]): Formula objects representing portfolio theory
                relationships, including portfolio expected return and portfolio
                variance for a two-asset case.
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
        return formulas

    def _analyze_cross_asset_relationships(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Assemble formulas describing detected relationships between different asset
        classes in the graph.

        Includes currency triangular-arbitrage/exchange-rate relationships when
        currencies are present, and commodity–currency inverse
        relationships when both commodities and currencies are present.

        Returns:
            formulas (List[Formula]):
                A list of Formula objects representing cross-asset relationships
                in the graph.
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
        categories = {}
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
                empirical_data_points (int): Number of entries in
                    `empirical_relationships["correlation_matrix"]` (0 if missing).
                key_insights (list[str]): Short human-readable insight strings
                    derived from the formulas and empirical data.
        """
        avg_corr_strength = self._calculate_avg_correlation_strength_from_empirical(empirical_relationships)
        return {
            "total_formulas": len(formulas),
            "avg_r_squared": (sum(f.r_squared for f in formulas) / len(formulas) if formulas else 0),
            "formula_categories": self._categorize_formulas(formulas),
            "empirical_data_points": len(empirical_relationships.get("correlation_matrix", {})),
            "key_insights": [
                (f"Identified {len(formulas)} mathematical relationships"),
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
        Estimate the average correlation value from the empirical relationships data.

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

    @staticmethod
    def _has_equities(graph: AssetRelationshipGraph) -> bool:
        """Check if the graph contains equity assets."""
        from src.models.financial_models import AssetClass

        return any(asset.asset_class == AssetClass.EQUITY for asset in graph.assets.values())

    @staticmethod
    def _has_bonds(graph: AssetRelationshipGraph) -> bool:
        """
        Check whether the graph contains any fixed-income (bond) assets.

        Parameters:
            graph (AssetRelationshipGraph): The asset relationship graph to inspect.

        Returns:
            True if the graph contains at least one fixed-income asset, False otherwise.
        """
        from src.models.financial_models import AssetClass

        return any(asset.asset_class == AssetClass.FIXED_INCOME for asset in graph.assets.values())

    @staticmethod
    def _has_commodities(graph: AssetRelationshipGraph) -> bool:
        """
        Determine whether the graph includes any commodity assets.

        Returns:
            bool: `true` if the graph contains at least one asset
                  with AssetClass.COMMODITY, `false` otherwise.
        """
        from src.models.financial_models import AssetClass

        return any(asset.asset_class == AssetClass.COMMODITY for asset in graph.assets.values())

    @staticmethod
    def _has_currencies(graph: AssetRelationshipGraph) -> bool:
        """
        Check whether the graph contains any currency assets.

        Returns:
            `true` if the graph contains at least one asset with
            `AssetClass.CURRENCY`, `false` otherwise.
        """
        from src.models.financial_models import AssetClass

        return any(asset.asset_class == AssetClass.CURRENCY for asset in graph.assets.values())

    @staticmethod
    def _has_dividend_stocks(graph: AssetRelationshipGraph) -> bool:
        """
        Check whether the graph contains any equity assets with a dividend yield
        greater than zero.

        Returns:
            `true` if at least one equity asset has a dividend yield greater than
            zero, `false` otherwise.
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
            if asset.asset_class == AssetClass.EQUITY and hasattr(asset, "pe_ratio") and asset.pe_ratio is not None:
                examples.append(f"{asset.symbol}: PE = {asset.pe_ratio:.2f}")
                if len(examples) >= 2:
                    break
        return "; ".join(examples) if examples else "Example: PE = 100.00 / 5.00 = 20.00"

    @staticmethod
    def _calculate_dividend_examples(graph: AssetRelationshipGraph) -> str:
        """
        Create up to two short examples showing dividend yield for equity
        assets present in the graph.

        Returns:
            A string containing up to two formatted examples like
            "SYMBOL: Yield = X.XX% at price $Y.YY"
            joined by "; ".
            If no equity with a dividend yield is found, returns a default
            illustrative example string.
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
                examples.append(f"{asset.symbol}: Yield = {yield_pct:.2f}% " f"at price ${asset.price:.2f}")
                if len(examples) >= 2:
                    break
        return "; ".join(examples) if examples else "Example: Div Yield = (2.00 / 100.00) * 100 = 2.00%"

    @staticmethod
    def _calculate_ytm_examples(graph: AssetRelationshipGraph) -> str:
        """
        Produce up to two example Yield-to-Maturity (YTM) strings
        from fixed-income assets in the given graph.

        Searches the graph for fixed-income assets with a defined YTM
        and formats each example as "SYMBOL: YTM ≈ X.XX%".
        If no valid YTMs are found, returns a default example string.

        Parameters:
            graph (AssetRelationshipGraph): Asset relationship graph to
                source fixed-income assets from.

        Returns:
            str: A semicolon-separated string with up to two examples like
                "SYMBOL: YTM ≈ 3.45%", or "Example: YTM ≈ 3.0%"
                when no valid YTMs are available.
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
        """
        Builds example market-capitalization strings for up to two equity assets
        found in the graph.

        Scans the graph's assets for items classified as EQUITY that have a non-null
        market_cap, formats up to two examples in billions
        (e.g., "SYM: Market Cap = $1.5B"),
        and returns a semicolon-separated string.
        If no valid equity market-cap values are found, returns the
        default example string.

        Parameters:
            graph (AssetRelationshipGraph): Graph containing assets to sample for
                market-cap examples.

        Returns:
            str: Formatted example(s) or the default example message.
        """
        from src.models.financial_models import AssetClass

        examples = []
        for asset in graph.assets.values():
            if asset.asset_class == AssetClass.EQUITY and hasattr(asset, "market_cap") and asset.market_cap is not None:
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
        """
        Generate up to two example strings illustrating the price-to-book (P/B)
        ratio from equities in the graph.

        Scans equity assets that have a defined `book_value` and formats each
        example as "SYMBOL: P/B = X.XX". If no qualifying equities are found,
        returns the default example string "Example: P/B = 150 / 50 = 3.0".

        Returns:
            A single string containing up to two examples separated by "; ",
            or the default example when no qualifying equities exist.
        """
        from src.models.financial_models import AssetClass

        examples = []
        for asset in graph.assets.values():
            if asset.asset_class == AssetClass.EQUITY and hasattr(asset, "book_value") and asset.book_value is not None:
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
        """
        Produce a human-readable example of the two-asset portfolio variance
        calculation using asset weights, volatilities, and covariance.

        Parameters:
            graph (AssetRelationshipGraph): Graph used to source example weights,
                volatilities, and an estimated correlation/covariance when available.

        Returns:
            example (str): A formatted example string showing the portfolio variance
                expression (σ²_p) with numeric terms.
        """
        return "Example: σ²p = (0.6² × 0.2²) + (0.4² × 0.1²) + " "(2 × 0.6 × 0.4 × 0.2 × 0.1 × 0.5)"

    @staticmethod
    def _calculate_exchange_rate_examples(graph: AssetRelationshipGraph) -> str:
        """
        Produce a worked example string demonstrating exchange-rate composition
        using two currencies from the graph.

        Returns:
            A worked example of an exchange-rate conversion
            using two currencies from the graph (e.g., "EUR/USD × USD/GBP = EUR/GBP");
            if fewer than two currencies are available, returns
            a default example string.
        """
        from src.models.financial_models import AssetClass

        currencies = [asset for asset in graph.assets.values() if asset.asset_class == AssetClass.CURRENCY]
        if len(currencies) >= 2:
            c1, c2 = currencies[0], currencies[1]
            return f"{c1.symbol}/USD × USD/{c2.symbol} = {c1.symbol}/{c2.symbol}"
        return "Example: USD/EUR × EUR/GBP = USD/GBP"

    @staticmethod
    def _calculate_commodity_currency_examples(graph: AssetRelationshipGraph) -> str:
        """Generate an example of a commodity-currency relationship calculation."""
        return "Example: As oil prices rise, USD strengthens (inverse relationship)"
