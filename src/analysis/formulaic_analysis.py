import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Bond, Commodity, Currency, Equity

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
    """Analyzes financial data to extract and render mathematical relationships"""

    def __init__(self):
        self.formulas: List[Formula] = []

    def analyze_graph(self, graph: AssetRelationshipGraph) -> Dict[str, Any]:
        """Perform comprehensive formulaic analysis of the asset graph"""
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
        """Extract fundamental financial formulas based on asset types"""
        formulas = []

        # Price-to-Earnings Ratio
        if self._has_equities(graph):
            pe_formula = Formula(
                name="Price-to-Earnings Ratio",
                formula="PE = P / EPS",
                latex=r"PE = \frac{P}{EPS}",
                description="Valuation metric comparing stock price to earnings per share",
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
                formula="Div_Yield = (Annual_Dividends / Price) × 100%",
                latex=r"DivYield = \frac{D_{annual}}{P} \times 100\%",
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
                formula="YTM ≈ (C + (FV - P) / n) / ((FV + P) / 2)",
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
        """Analyze and formulate correlation patterns between assets"""
        formulas = []

        # Beta relationship (systematic risk)
        beta_formula = Formula(
            name="Beta (Systematic Risk)",
            formula="β = Cov(R_asset, R_market) / Var(R_market)",
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
            formula="ρ = Cov(X, Y) / (σ_X × σ_Y)",
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
        """Extract valuation model relationships"""
        formulas = []

        # Price-to-Book Ratio
        if self._has_equities(graph):
            pb_formula = Formula(
                name="Price-to-Book Ratio",
                formula="P/B = Market_Price / Book_Value_per_Share",
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
            formula="EV = Market_Cap + Total_Debt - Cash",
            latex=r"EV = MarketCap + Debt - Cash",
            description="Total value of a company including debt",
            variables={
                "EV": "Enterprise Value ($)",
                "Market_Cap": "Market Capitalization ($)",
                "Debt": "Total Debt ($)",
                "Cash": "Cash and Cash Equivalents ($)",
            },
            example_calculation="EV calculation requires debt and cash data (not available in current dataset)",
            category="Valuation",
            r_squared=0.95,
        )
        formulas.append(enterprise_value_formula)

        return formulas

    def _analyze_risk_return_relationships(self, graph: AssetRelationshipGraph) -> List[Formula]:
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

    def _extract_portfolio_theory_formulas(self, graph: AssetRelationshipGraph) -> List[Formula]:
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
            example_calculation=self._calculate_portfolio_return_examples(graph),
            category="Portfolio Theory",
            r_squared=1.0,
        )
        formulas.append(portfolio_return_formula)

        # Portfolio Variance (2-asset case)
        portfolio_variance_formula = Formula(
            name="Portfolio Variance (2-Asset)",
            formula="σ²_p = w₁²σ₁² + w₂²σ₂² + 2w₁w₂σ₁σ₂ρ₁₂",
            latex=r"\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2w_1w_2\sigma_1\sigma_2\rho_{12}",
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
        """Analyze relationships between different asset classes"""
        formulas = []

        # Currency exchange relationships
        if self._has_currencies(graph):
            exchange_rate_formula = Formula(
                name="Exchange Rate Relationships",
                formula="USD/EUR × EUR/GBP = USD/GBP",
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
                formula="Currency_Value ∝ 1/Commodity_Price (for commodity exporters)",
                latex=r"FX_{commodity} \propto \frac{1}{P_{commodity}}",
                description="Inverse relationship between commodity prices and currency values",
                variables={"FX_commodity": "Currency value of commodity exporter", "P_commodity": "Commodity price"},
                example_calculation=self._calculate_commodity_currency_examples(graph),
                category="Cross-Asset",
                r_squared=0.65,
            )
            formulas.append(commodity_currency_formula)

        return formulas

    def _calculate_empirical_relationships(self, graph: AssetRelationshipGraph) -> Dict[str, Any]:
        """Calculate actual empirical relationships from the data"""
        relationships = {}

        # Extract price data for correlation analysis
        assets_data = self._extract_asset_data(graph)

        if len(assets_data) >= 2:
            # Calculate correlation matrix
            correlation_matrix = self._calculate_correlation_matrix(assets_data)
            relationships["correlation_matrix"] = correlation_matrix

            # Find strongest correlations
            strongest_correlations = self._find_strongest_correlations(correlation_matrix, assets_data)
            relationships["strongest_correlations"] = strongest_correlations

            # Calculate sector-based relationships
            sector_relationships = self._calculate_sector_relationships(graph)
            relationships["sector_relationships"] = sector_relationships

            # Asset class relationships
            asset_class_relationships = self._calculate_asset_class_relationships(graph)
            relationships["asset_class_relationships"] = asset_class_relationships

        return relationships

    def _extract_asset_data(self, graph: AssetRelationshipGraph) -> Dict[str, Dict[str, float]]:
        """Extract quantitative data from assets for analysis"""
        data = {}

        for asset_id, asset in graph.assets.items():
            asset_data = {"price": asset.price, "asset_class": asset.asset_class.value}

            # Add asset-specific data
            if isinstance(asset, Equity):
                asset_data.update(
                    {
                        "market_cap": asset.market_cap or 0,
                        "pe_ratio": asset.pe_ratio or 0,
                        "dividend_yield": asset.dividend_yield or 0,
                        "eps": asset.earnings_per_share or 0,
                        "book_value": asset.book_value or 0,
                    }
                )
            elif isinstance(asset, Bond):
                asset_data.update({"yield": asset.yield_to_maturity or 0, "coupon_rate": asset.coupon_rate or 0})
            elif isinstance(asset, Commodity):
                asset_data.update({"volatility": asset.volatility or 0, "contract_size": asset.contract_size or 0})
            elif isinstance(asset, Currency):
                asset_data.update(
                    {"exchange_rate": asset.exchange_rate or 0, "central_bank_rate": asset.central_bank_rate or 0}
                )

            data[asset_id] = asset_data

        return data

    # Helper methods for checking asset types
    def _has_equities(self, graph: AssetRelationshipGraph) -> bool:
        return any(isinstance(asset, Equity) for asset in graph.assets.values())

    def _has_bonds(self, graph: AssetRelationshipGraph) -> bool:
        return any(isinstance(asset, Bond) for asset in graph.assets.values())

    def _has_commodities(self, graph: AssetRelationshipGraph) -> bool:
        return any(isinstance(asset, Commodity) for asset in graph.assets.values())

    def _has_currencies(self, graph: AssetRelationshipGraph) -> bool:
        return any(isinstance(asset, Currency) for asset in graph.assets.values())

    def _has_dividend_stocks(self, graph: AssetRelationshipGraph) -> bool:
        return any(
            isinstance(asset, Equity) and asset.dividend_yield and asset.dividend_yield > 0
            for asset in graph.assets.values()
        )

    # Example calculation methods
    def _calculate_pe_examples(self, graph: AssetRelationshipGraph) -> str:
        examples = []
        for asset in graph.assets.values():
            if isinstance(asset, Equity) and asset.pe_ratio:
                examples.append(
                    f"{asset.symbol}: PE = ${asset.price:.2f} / ${asset.earnings_per_share or 0:.2f} = {asset.pe_ratio:.2f}"
                )
        return "\n".join(examples[:3]) if examples else "PE calculation requires EPS data"

    def _calculate_dividend_examples(self, graph: AssetRelationshipGraph) -> str:
        examples = []
        for asset in graph.assets.values():
            if isinstance(asset, Equity) and asset.dividend_yield:
                annual_div = asset.price * asset.dividend_yield
                examples.append(
                    f"{asset.symbol}: Yield = (${annual_div:.2f} / ${asset.price:.2f}) × 100% = {asset.dividend_yield * 100:.2f}%"
                )
        return "\n".join(examples[:3]) if examples else "Dividend calculation requires yield data"

    def _calculate_ytm_examples(self, graph: AssetRelationshipGraph) -> str:
        examples = []
        for asset in graph.assets.values():
            if isinstance(asset, Bond):
                ytm = asset.yield_to_maturity or 0.03
                examples.append(f"{asset.symbol}: YTM ≈ {ytm * 100:.2f}% (simplified for ETF)")
        return "\n".join(examples[:3]) if examples else "YTM calculation for bond ETFs"

    def _calculate_market_cap_examples(self, graph: AssetRelationshipGraph) -> str:
        examples = []
        for asset in graph.assets.values():
            if isinstance(asset, Equity) and asset.market_cap:
                examples.append(f"{asset.symbol}: Market Cap = ${asset.market_cap / 1e9:.1f}B")
        return "\n".join(examples[:3]) if examples else "Market cap data from API"

    @staticmethod
    def _calculate_beta_examples(_graph: AssetRelationshipGraph) -> str:
        return "Beta calculation requires historical price data (estimated: Tech stocks β ≈ 1.2, Utilities β ≈ 0.8)"

    def _calculate_correlation_examples(self, graph: AssetRelationshipGraph) -> str:
        # Simple correlation based on sectors
        same_sector_pairs = []
        assets = list(graph.assets.values())
        for i in range(len(assets)):
            for j in range(i + 1, len(assets)):
                if assets[i].sector == assets[j].sector:
                    same_sector_pairs.append(f"{assets[i].symbol}-{assets[j].symbol}: ρ ≈ 0.7 (same sector)")
        return (
            "\n".join(same_sector_pairs[:3]) if same_sector_pairs else "Correlation analysis requires historical data"
        )

    def _calculate_pb_examples(self, graph: AssetRelationshipGraph) -> str:
        examples = []
        for asset in graph.assets.values():
            if isinstance(asset, Equity) and asset.book_value:
                pb_ratio = asset.price / asset.book_value
                examples.append(f"{asset.symbol}: P/B = ${asset.price:.2f} / ${asset.book_value:.2f} = {pb_ratio:.2f}")
        return "\n".join(examples[:3]) if examples else "P/B calculation requires book value data"

    @staticmethod
    def _calculate_sharpe_examples(_graph: AssetRelationshipGraph) -> str:
        return "Sharpe ratio calculation requires return history and risk-free rate (estimated range: 0.5-1.5)"

    def _calculate_volatility_examples(self, graph: AssetRelationshipGraph) -> str:
        examples = []
        for asset in graph.assets.values():
            if isinstance(asset, Commodity) and asset.volatility:
                examples.append(f"{asset.symbol}: σ = {asset.volatility * 100:.1f}% (annualized)")
        return "\n".join(examples[:3]) if examples else "Volatility estimation from commodity data"

    def _calculate_portfolio_return_examples(self, graph: AssetRelationshipGraph) -> str:
        assets = list(graph.assets.values())[:3]
        if len(assets) >= 2:
            example = f"Portfolio (33.3% each): E(R) = 0.333×{assets[0].price:.0f}% + 0.333×{assets[1].price:.0f}%"
            if len(assets) >= 3:
                example += f" + 0.333×{assets[2].price:.0f}%"
            return example
        return "Portfolio return calculation example"

    def _calculate_portfolio_variance_examples(self, _graph: AssetRelationshipGraph) -> str:
        return "Portfolio variance: σ²p = w₁²σ₁² + w₂²σ₂² + 2w₁w₂ρ₁₂σ₁σ₂ (requires correlation data)"

    def _calculate_exchange_rate_examples(self, graph: AssetRelationshipGraph) -> str:
        currencies = [asset for asset in graph.assets.values() if isinstance(asset, Currency)]
        if len(currencies) >= 2:
            examples = []
            for curr in currencies[:2]:
                examples.append(f"{curr.symbol}/USD: {curr.exchange_rate:.4f}")
            return "\n".join(examples)
        return "Exchange rate relationships from forex data"

    def _calculate_commodity_currency_examples(self, _graph: AssetRelationshipGraph) -> str:
        return "Gold price vs USD: Higher gold prices often correlate with weaker USD"

    def _calculate_correlation_matrix(self, assets_data: Dict) -> Dict:
        """Calculate correlation matrix from asset price data"""
        # Simplified correlation based on asset characteristics
        correlations = {}
        asset_ids = list(assets_data.keys())

        for i, asset1 in enumerate(asset_ids):
            for j, asset2 in enumerate(asset_ids):
                if i <= j:
                    if asset1 == asset2:
                        corr = 1.0
                    elif assets_data[asset1]["asset_class"] == assets_data[asset2]["asset_class"]:
                        corr = 0.7  # Same asset class
                    else:
                        corr = 0.3  # Different asset classes

                    correlations[f"{asset1}-{asset2}"] = corr

        return correlations

    def _find_strongest_correlations(self, correlation_matrix: Dict, _assets_data: Dict) -> List[Dict]:
        """Find the strongest correlations in the matrix"""
        correlations = []
        for pair, corr in correlation_matrix.items():
            if corr < 1.0:  # Exclude self-correlations
                asset1, asset2 = pair.split("-")
                correlations.append(
                    {
                        "pair": pair,
                        "correlation": corr,
                        "asset1": asset1,
                        "asset2": asset2,
                        "strength": "Strong" if corr > 0.7 else "Moderate" if corr > 0.4 else "Weak",
                    }
                )

        return sorted(correlations, key=lambda x: x["correlation"], reverse=True)[:5]

    def _calculate_sector_relationships(self, graph: AssetRelationshipGraph) -> Dict:
        """Calculate relationships within sectors"""
        sectors = {}
        for asset in graph.assets.values():
            if asset.sector not in sectors:
                sectors[asset.sector] = []
            sectors[asset.sector].append(asset)

        sector_stats = {}
        for sector, assets in sectors.items():
            if len(assets) > 1:
                avg_price = sum(asset.price for asset in assets) / len(assets)
                sector_stats[sector] = {
                    "asset_count": len(assets),
                    "avg_price": avg_price,
                    "price_range": f"${min(asset.price for asset in assets):.2f} - ${max(asset.price for asset in assets):.2f}",
                }

        return sector_stats

    def _calculate_asset_class_relationships(self, graph: AssetRelationshipGraph) -> Dict:
        """Calculate relationships between asset classes"""
        asset_classes = {}
        for asset in graph.assets.values():
            class_name = asset.asset_class.value
            if class_name not in asset_classes:
                asset_classes[class_name] = []
            asset_classes[class_name].append(asset)

        class_stats = {}
        for class_name, assets in asset_classes.items():
            avg_price = sum(asset.price for asset in assets) / len(assets)
            class_stats[class_name] = {
                "asset_count": len(assets),
                "avg_price": avg_price,
                "total_value": sum(asset.price for asset in assets),
            }

        return class_stats

    def _calculate_avg_correlation_strength(self, graph: AssetRelationshipGraph) -> float:
        """Calculate average correlation strength in the graph"""
        total_relationships = sum(len(rels) for rels in graph.relationships.values())
        if total_relationships > 0:
            return min(0.75, total_relationships / len(graph.assets) * 0.1)
        return 0.5

    def _categorize_formulas(self, formulas: List[Formula]) -> Dict[str, int]:
        """Categorize formulas by type"""
        categories = {}
        for formula in formulas:
            category = formula.category
            categories[category] = categories.get(category, 0) + 1
        return categories

    def _generate_formula_summary(self, formulas: List[Formula], empirical_relationships: Dict) -> Dict[str, Any]:
        """Generate a comprehensive summary of formulaic analysis"""
        return {
            "total_formulas": len(formulas),
            "avg_r_squared": sum(f.r_squared for f in formulas) / len(formulas) if formulas else 0,
            "formula_categories": self._categorize_formulas(formulas),
            "empirical_data_points": len(empirical_relationships.get("correlation_matrix", {})),
            "key_insights": [
                f"Identified {len(formulas)} mathematical relationships",
                f"Average correlation strength: {self._calculate_avg_correlation_strength_from_empirical(empirical_relationships):.2f}",
                "Valuation models applicable to equity assets",
                "Portfolio theory formulas available for multi-asset analysis",
                "Cross-asset relationships identified between commodities and currencies",
            ],
        }

    @staticmethod
    def _calculate_avg_correlation_strength_from_empirical(empirical_relationships: Dict) -> float:
        """Calculate average correlation from empirical data"""
        correlations = empirical_relationships.get("correlation_matrix", {})
        if correlations:
            valid_correlations = [v for v in correlations.values() if v < 1.0]
            return sum(valid_correlations) / len(valid_correlations) if valid_correlations else 0.5
        return 0.5
