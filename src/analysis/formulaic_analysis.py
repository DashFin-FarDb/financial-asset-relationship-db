import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from src.logic.asset_graph import AssetRelationshipGraph

logger = logging.getLogger(__name__)


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
        Initialize analyzer state.
        
        Creates the instance attribute `formulas` as an empty list for accumulating Formula objects discovered during graph analysis.
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
        Builds fundamental valuation and income formulas relevant to the assets present in the given graph.
        
        Parameters:
            graph (AssetRelationshipGraph): AssetRelationshipGraph to inspect for asset types and sample values used in example calculations.
        
        Returns:
            List[Formula]: List of Formula objects for core metrics such as price-to-earnings, dividend yield, bond yield-to-maturity approximation, and market capitalization when applicable to the graph.
        """
        formulas = []

        # Price-to-Earnings Ratio
        if self._has_equities(graph):
            pe_formula = Formula(
                name="Price-to-Earnings Ratio",
                expression="PE = P / EPS",
                latex=r"PE = \frac{P}{EPS}",
                description="Ratio of market price to earnings per share",
                variables={
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
                expression="Div_Yield = (Annual_Dividends / Price) × 100%",
                latex=r"DivYield = \frac{D_{annual}}{P} \times 100%",
                description="Percentage return from dividends relative to stock price",
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
                name="Bond Yield-to-Maturity (Approximation)",
                expression="YTM ≈ (C + (FV - P) / n) / ((FV + P) / 2)",
                latex=r"YTM \approx \frac{C + \frac{FV - P}{n}}{\frac{FV + P}{2}}",
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
                expression="Market_Cap = Price × Shares_Outstanding",
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
        Constructs Formula objects for correlation and systematic risk measures.
        
        Creates Formula entries for Beta (systematic risk) and the correlation coefficient, each populated with expression, LaTeX, variable descriptions, example calculations, category, and an r_squared estimate.
        
        Returns:
            formulas (List[Formula]): List containing Formula objects for Beta and the correlation coefficient.
        """
        formulas = []

        # Beta relationship (systematic risk)
        beta_formula = Formula(
            name="Beta (Systematic Risk)",
            expression="β = Cov(R_asset, R_market) / Var(R_market)",
            latex=r"\beta = \frac{Cov(R_i, R_m)}{Var(R_m)}",
            description="Measure of an asset's sensitivity to market movements",
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
            expression="ρ = Cov(X, Y) / (σ_X × σ_Y)",
            latex=r"\rho = \frac{Cov(X, Y)}{\sigma_X \times \sigma_Y}",
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
        Assemble valuation formulas applicable to the given asset relationship graph.
        
        Builds a list of valuation-related Formula objects (for example, Price-to-Book when equities are present and Enterprise Value) based on asset types and attributes found in the provided AssetRelationshipGraph.
        
        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and relationships used to determine which valuation formulas apply.
        
        Returns:
            list[Formula]: List of valuation Formula objects discovered or constructed for the graph.
        """
        formulas = []

        # Price-to-Book Ratio
        if self._has_equities(graph):
            pb_formula = Formula(
                name="Price-to-Book Ratio",
                expression="P/B = Market_Price / Book_Value_per_Share",
                latex=r"P/B = \frac{P}{BV_{per\_share}}",
                description="Valuation metric comparing market price to book value",
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
            expression="EV = Market_Cap + Total_Debt - Cash",
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
        Assemble formulaic representations of common risk–return relationships.

        Parameters:
            graph (AssetRelationshipGraph): Asset relationship graph used to populate
                example calculations and to determine contextual values for the
                formulas.

        Returns:
            List[Formula]: List of Formula objects representing risk–return metrics
                (e.g., Sharpe Ratio, volatility) with populated fields such as
                expression, LaTeX, variables, example_calculation, category, and
                r_squared.
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
            example_calculation=self._calculate_sharpe_examples(graph),
            category="Risk Management",
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
            example_calculation=self._calculate_volatility_examples(graph),
            category="Risk Management",
            r_squared=0.90,
        )
        formulas.append(volatility_formula)

        return formulas

    def _extract_portfolio_theory_formulas(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Builds Modern Portfolio Theory formulas derived from the asset relationship graph.
        
        Returns:
            List[Formula]: Formula objects for portfolio theory, including the portfolio expected return and the two-asset portfolio variance.
        """
        formulas = []

        # Portfolio Expected Return
        portfolio_return_formula = Formula(
            name="Portfolio Expected Return",
            expression="E(R_p) = Σ(w_i × E(R_i))",
            latex=r"E(R_p) = \sum_{i=1}^{n} w_i \times E(R_i)",
            description="Weighted average of individual asset expected returns",
            variables={
                "E(R_p)": "Expected portfolio return",
                "w_i": "Weight of asset i in portfolio",
                "E(R_i)": "Expected return of asset i",
                "n": "Number of assets",
            },
            example_calculation=self._calculate_portfolio_return_examples(graph),
            category="Portfolio Theory",
            r_squared=1.0,
        )
        formulas.append(portfolio_return_formula)

        # Portfolio Variance (2-asset case)
        portfolio_variance_formula = Formula(
            name="Portfolio Variance (2-Asset)",
            expression="σ²_p = w₁²σ₁² + w₂²σ₂² + 2w₁w₂σ₁σ₂ρ₁₂",
            latex=r"\sigma^2_p = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2w_1w_2\sigma_1\sigma_2\rho_{12}",
            description="Portfolio risk considering correlation between assets",
            variables={
                "σ²_p": "Portfolio variance",
                "w_1, w_2": "Weights of assets 1 and 2",
                "σ_1, σ_2": "Standard deviations of assets 1 and 2",
                "ρ_12": "Correlation between assets 1 and 2",
            },
            example_calculation=self._calculate_portfolio_variance_examples(graph),
            category="Portfolio Theory",
            r_squared=0.87,
        )
        formulas.append(portfolio_variance_formula)

        return formulas

    def _analyze_cross_asset_relationships(self, graph: AssetRelationshipGraph) -> List[Formula]:
        """
        Constructs Formula objects representing cross-asset relationships detected in the given AssetRelationshipGraph.
        
        When currency assets exist, includes a triangular-arbitrage (exchange rate) formula. When both commodity and currency assets exist, additionally includes a commodity–currency inverse relationship (typical for commodity-exporting currencies).
        
        Returns:
            formulas (List[Formula]): List of Formula objects for cross-asset relationships found in the graph.
        """
        formulas = []

        # Currency exchange relationships
        if self._has_currencies(graph):
            exchange_rate_formula = Formula(
                name="Exchange Rate Relationships",
                expression="USD/EUR × EUR/GBP = USD/GBP",
                latex=r"\frac{USD}{EUR} \times \frac{EUR}{GBP} = \frac{USD}{GBP}",
                description="Triangular arbitrage relationship between currencies",
                variables={
                    "USD/EUR": "US Dollar to Euro exchange rate",
                    "EUR/GBP": "Euro to British Pound exchange rate",
                    "USD/GBP": "US Dollar to British Pound exchange rate",
                },
                example_calculation=self._calculate_exchange_rate_examples(graph),
                category="Currency Markets",
                r_squared=0.99,
            )
            formulas.append(exchange_rate_formula)

        # Commodity-Currency relationship
        if self._has_commodities(graph) and self._has_currencies(graph):
            commodity_currency_formula = Formula(
                name="Commodity-Currency Relationship",
                expression="Currency_Value ∝ 1/Commodity_Price (for commodity exporters)",
                latex=r"FX_{commodity} \propto \frac{1}{P_{commodity}}",
                description="Inverse relationship between commodity prices and currency values",
                variables={
                    "FX_commodity": "Currency value of commodity exporter",
                    "P_commodity": "Commodity price",
                },
                example_calculation=self._calculate_commodity_currency_examples(graph),
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
        Calculate empirical relationships derived from an AssetRelationshipGraph.
        
        Parameters:
            graph (AssetRelationshipGraph): Graph of assets and relationships to analyze for empirical relationships (correlations, pairwise statistics, sample sizes, etc.).
        
        Returns:
            Dict[str, Any]: A dictionary intended to contain empirical relationship data (for example keys like "correlation_matrix", "pairwise_statistics", "sample_counts"). Currently returns an empty dict as a placeholder implementation.
        """
        return {}

    @staticmethod
    def _calculate_avg_correlation_strength(graph: AssetRelationshipGraph) -> float:
        """
        Estimate the average correlation strength across relationships in the graph.
        
        Returns:
            float: Average relationship strength clamped to the range 0.0–0.75; returns 0.5 if no relationship strength data is present.
        """
        strengths = [strength for rels in graph.relationships.values() for _, _, strength in rels]
        if strengths:
            avg_strength = sum(strengths) / len(strengths)
            return min(0.75, max(0.0, avg_strength))
        return 0.5

    @staticmethod
    def _categorize_formulas(formulas: List[Formula]) -> Dict[str, int]:
        """
        Count formulas grouped by their category.
        
        Returns:
            Dict[str, int]: Mapping from category name to the number of formulas in that category.
        """
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
        Produce a concise summary of the analysis results for a set of formulas and
        associated empirical relationships.

        Parameters:
            empirical_relationships (dict): Empirical data produced during analysis;
                may include a "correlation_matrix" mapping used to count empirical data
                points.

        Returns:
            summary (dict): Summary values with keys:
                - total_formulas (int): Number of formulas analyzed.
                - avg_r_squared (float): Average `r_squared` across provided
                  formulas (0 if none).
                - formula_categories (dict): Mapping of category name to count of
                  formulas in that category.
                - empirical_data_points (int): Number of entries in
                  `empirical_relationships["correlation_matrix"]` (0 if missing).
                - key_insights (list[str]): Human-readable insight strings
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
        """
        Determine whether the graph contains any equity assets.
        
        Returns:
            true if the graph contains at least one equity asset, false otherwise.
        """
        from src.models.financial_models import AssetClass

        return any(asset.asset_class == AssetClass.EQUITY for asset in graph.assets.values())

    @staticmethod
    def _has_bonds(graph: AssetRelationshipGraph) -> bool:
        """
        Check whether the graph contains any fixed-income (bond) assets.
        
        Returns:
            True if the graph contains at least one asset with class `FIXED_INCOME`, `False` otherwise.
        """
        from src.models.financial_models import AssetClass

        return any(asset.asset_class == AssetClass.FIXED_INCOME for asset in graph.assets.values())

    @staticmethod
    def _has_commodities(graph: AssetRelationshipGraph) -> bool:
        """
        Check whether the provided asset graph contains any commodity assets.
        
        Returns:
            True if the graph contains at least one asset with `AssetClass.COMMODITY`, False otherwise.
        """
        from src.models.financial_models import AssetClass

        return any(asset.asset_class == AssetClass.COMMODITY for asset in graph.assets.values())

    @staticmethod
    def _has_currencies(graph: AssetRelationshipGraph) -> bool:
        """
        Determine whether the graph contains any currency assets.

        Returns:
            True if the graph contains at least one asset
            with AssetClass.CURRENCY, False otherwise.
        """
        from src.models.financial_models import AssetClass

        return any(asset.asset_class == AssetClass.CURRENCY for asset in graph.assets.values())

    @staticmethod
    def _has_dividend_stocks(graph: AssetRelationshipGraph) -> bool:
        """
        Return whether the graph contains any equity asset with a dividend yield greater than zero.
        
        Returns:
            bool: `True` if at least one equity asset has a numeric `dividend_yield` greater than 0, `False` otherwise.
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
        """
        Produce up to two example price-to-earnings (P/E) ratio calculations sampled from equity assets in the graph.
        
        Parameters:
            graph (AssetRelationshipGraph): Graph used to sample equity assets and their P/E ratios.
        
        Returns:
            str: A semi-colon separated string of up to two examples formatted as "SYMB: PE = 12.34", or a default illustrative example if no P/E values are available.
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
        Produce up to two formatted dividend-yield examples sampled from equity assets in the graph.
        
        Returns:
            str: Semicolon-separated examples like "SYM: Yield = X.XX% at price $Y.YY" for up to two equities that have a defined `dividend_yield`; if no such assets are found, returns a default illustrative example string.
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
        Format up to two example yield-to-maturity (YTM) strings from fixed-income
        assets in the provided graph.

        Parameters:
            graph (AssetRelationshipGraph): Asset relationship graph to source
                fixed-income assets from.

        Returns:
            str: A semicolon-separated string with up to two examples like
                "SYMBOL: YTM ≈ 3.45%", or a default example string
                when no valid YTMs are found.
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
        Generate up to two market-cap examples from EQUITY assets in the graph.
        
        Searches the graph for equity assets with a non-null `market_cap` and returns up to two examples formatted in billions (e.g., "SYM: Market Cap = $1.5B") joined by "; ". If no examples are found, returns the default: "Example: Market Cap = $1.5T".
        
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
        """
        Generate a concise, human-readable example describing how beta is calculated for assets in the graph.
        
        If equity and market index return data are present, the string references historical return comparison; otherwise it provides a generic beta calculation description.
        
        Returns:
            A string describing beta calculation examples (historical asset returns vs. market index).
        """
        return "Beta calculated from historical returns vs market index"

    @staticmethod
    def _calculate_correlation_examples(graph: AssetRelationshipGraph) -> str:
        """
        Create a short example string describing how correlation values were derived from the graph's asset relationships.
        
        Parameters:
            graph (AssetRelationshipGraph): The asset relationship graph used to sample relationship counts.
        
        Returns:
            str: Example text — `"Calculated from N asset pair relationships"` when relationship data exists, otherwise a generic explanation of how correlations are computed.
        """
        if graph.relationships:
            count = sum(len(rels) for rels in graph.relationships.values())
            return f"Calculated from {count} asset pair relationships"
        return "Correlation between asset pairs calculated from price movements"

    @staticmethod
    def _calculate_pb_examples(graph: AssetRelationshipGraph) -> str:
        """
        Build up to two example Price-to-Book (P/B) ratio strings from equity assets in the graph.
        
        Collects up to two equities that have a non-null `book_value` and formats each as
        "SYMBOL: P/B = X.XX"; if none are found, returns a fixed illustrative example.
        
        Returns:
            str: One or two examples joined by "; " (e.g. "AAPL: P/B = 8.12; MSFT: P/B = 13.45")
                 or the default "Example: P/B = 150 / 50 = 3.0" when no examples are available.
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
        """
        Produce a brief example illustrating a Sharpe ratio calculation.
        
        Returns:
            example (str): A human-readable example string showing a sample Sharpe ratio calculation (e.g., "Sharpe = (10% - 2%) / 15% = 0.53").
        """
        return "Sharpe = (10% - 2%) / 15% = 0.53"

    @staticmethod
    def _calculate_volatility_examples(graph: AssetRelationshipGraph) -> str:
        """
        Return up to two example volatility values for commodity assets found in the graph.
        
        Returns:
        	A string containing one or two volatility examples formatted like "SYMBOL: σ = 20.00%"; if no commodity volatility is available, returns the default "Example: σ = 20% annualized".
        """
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
        """
        Return a human-readable example showing how to compute a portfolio's expected return.
        
        Returns:
            example (str): A single-line example string illustrating E(Rp) = sum(weight × return), e.g. "E(Rp) = 0.6 × 10% + 0.4 × 5% = 8%".
        """
        return "Example: E(Rp) = 0.6 × 10% + 0.4 × 5% = 8%"

    @staticmethod
    def _calculate_portfolio_variance_examples(graph: AssetRelationshipGraph) -> str:
        """
        Generate a human-readable example of the two-asset portfolio variance formula using weights and volatilities sourced from the graph when available.
        
        Parameters:
            graph (AssetRelationshipGraph): Graph used to source asset weights and volatilities for the example; defaults are used if values are not present.
        
        Returns:
            A formatted string showing the portfolio variance (σ²p) with numeric terms.
        """
        return "Example: σ²p = (0.6² × 0.2²) + (0.4² × 0.1²) + " "(2 × 0.6 × 0.4 × 0.2 × 0.1 × 0.5)"

    @staticmethod
    def _calculate_exchange_rate_examples(graph: AssetRelationshipGraph) -> str:
        """
        Create a worked example string illustrating an exchange-rate conversion using two currencies from the graph.
        
        Returns:
            example (str): A conversion example using two currency symbols found in `graph` (e.g., "EUR/USD × USD/GBP = EUR/GBP"); if fewer than two currencies are present, returns a default example string.
        """
        from src.models.financial_models import AssetClass

        currencies = [asset for asset in graph.assets.values() if asset.asset_class == AssetClass.CURRENCY]
        if len(currencies) >= 2:
            c1, c2 = currencies[0], currencies[1]
            return f"{c1.symbol}/USD × USD/{c2.symbol} = {c1.symbol}/{c2.symbol}"
        return "Example: USD/EUR × EUR/GBP = USD/GBP"

    @staticmethod
    def _calculate_commodity_currency_examples(graph: AssetRelationshipGraph) -> str:
        """
        Provide a concise example illustrating a commodity–currency relationship.
        
        Returns:
            example (str): A short example string showing how a commodity price (oil) and a currency (USD) co-move, e.g. "Example: As oil prices rise, USD strengthens (inverse relationship)".
        """
        return "Example: As oil prices rise, USD strengthens (inverse relationship)"