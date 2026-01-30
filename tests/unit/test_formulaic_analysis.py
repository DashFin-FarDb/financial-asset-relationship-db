"""
Comprehensive unit tests for src/analysis/formulaic_analysis.py.

Tests cover:
- FormulaicAnalyzer initialization
- Formula data structure
- Graph analysis methods
- Formula extraction for different asset types
- Correlation and valuation formulas
- Risk-return calculations
- Portfolio theory formulas
- Cross-asset relationships
- Edge cases and boundary conditions
"""

import pytest

from src.analysis.formulaic_analysis import Formula, FormulaicAnalyzer
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


class TestFormula:
    """Test the Formula dataclass."""

    @staticmethod
    def test_formula_creation():
        """Test creating a Formula instance with all fields."""
        formula = Formula(
            name="Test Formula",
            formula="A = B + C",
            latex=r"A = B + C",
            description="A test formula",
            variables={"A": "Result", "B": "Input 1", "C": "Input 2"},
            example_calculation="A = 1 + 2 = 3",
            category="Test",
            r_squared=0.95,
        )

        assert formula.name == "Test Formula"
        assert formula.formula == "A = B + C"
        assert formula.latex == r"A = B + C"
        assert formula.description == "A test formula"
        assert formula.variables == {"A": "Result", "B": "Input 1", "C": "Input 2"}
        assert formula.example_calculation == "A = 1 + 2 = 3"
        assert formula.category == "Test"
        assert formula.r_squared == 0.95

    @staticmethod
    def test_formula_default_r_squared():
        """Test that r_squared defaults to 0.0."""
        formula = Formula(
            name="Test",
            formula="A = B",
            latex=r"A = B",
            description="Test",
            variables={"A": "A", "B": "B"},
            example_calculation="Test",
            category="Test",
        )
        assert formula.r_squared == 0.0


class TestFormulaicAnalyzerInitialization:
    """Test FormulaicAnalyzer initialization."""

    @staticmethod
    def test_analyzer_init():
        """Test that FormulaicAnalyzer initializes with empty formulas list."""
        analyzer = FormulaicAnalyzer()
        assert analyzer.formulas == []
        assert isinstance(analyzer.formulas, list)


class TestAnalyzeGraph:
    """Test the main analyze_graph method."""

    @staticmethod
    def test_analyze_empty_graph():
        """Test analyzing an empty graph."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        result = analyzer.analyze_graph(graph)

        assert "formulas" in result
        assert "empirical_relationships" in result
        assert "formula_count" in result
        assert "categories" in result
        assert "summary" in result
        assert isinstance(result["formulas"], list)
        assert isinstance(result["empirical_relationships"], dict)
        assert result["formula_count"] == len(result["formulas"])

    @staticmethod
    def test_analyze_graph_with_equities():
        """Test analyzing a graph with equity assets."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
            pe_ratio=25.0,
            dividend_yield=0.005,
        )
        graph.add_asset(equity)

        result = analyzer.analyze_graph(graph)

        assert result["formula_count"] > 0
        formulas = result["formulas"]
        formula_names = [f.name for f in formulas]

        # Should include equity-related formulas
        assert any("Price-to-Earnings" in name for name in formula_names)
        assert any("Market Capitalization" in name for name in formula_names)

    @staticmethod
    def test_analyze_graph_with_bonds():
        """Test analyzing a graph with bond assets."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        bond = Bond(
            id="BOND1",
            symbol="BOND1",
            name="Test Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Government",
            price=100.0,
            yield_to_maturity=0.03,
        )
        graph.add_asset(bond)

        result = analyzer.analyze_graph(graph)

        formulas = result["formulas"]
        formula_names = [f.name for f in formulas]

        # Should include bond-related formulas
        assert any("Yield-to-Maturity" in name for name in formula_names)

    @staticmethod
    def test_analyze_graph_with_commodities():
        """Test analyzing a graph with commodity assets."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        commodity = Commodity(
            id="GOLD",
            symbol="GC",
            name="Gold",
            asset_class=AssetClass.COMMODITY,
            sector="Precious Metals",
            price=2000.0,
        )
        graph.add_asset(commodity)

        result = analyzer.analyze_graph(graph)

        assert result["formula_count"] > 0

    @staticmethod
    def test_analyze_graph_with_currencies():
        """Test analyzing a graph with currency assets."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        currency = Currency(
            id="EUR",
            symbol="EUR",
            name="Euro",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.1,
            exchange_rate=1.1,
        )
        graph.add_asset(currency)

        result = analyzer.analyze_graph(graph)

        formulas = result["formulas"]
        formula_names = [f.name for f in formulas]

        # Should include currency-related formulas
        assert any("Exchange Rate" in name for name in formula_names)

    @staticmethod
    def test_analyze_graph_formula_count_matches():
        """Test that formula_count matches the length of formulas list."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)

        result = analyzer.analyze_graph(graph)

        assert result["formula_count"] == len(result["formulas"])


class TestExtractFundamentalFormulas:
    """Test _extract_fundamental_formulas method."""

    @staticmethod
    def test_extract_with_no_assets():
        """Test extracting formulas from empty graph."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._extract_fundamental_formulas(graph)

        # Should return correlation and risk formulas even without assets
        assert isinstance(formulas, list)

    @staticmethod
    def test_extract_with_equity():
        """Test extracting formulas with equity assets."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
        )
        graph.add_asset(equity)

        formulas = analyzer._extract_fundamental_formulas(graph)

        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Price-to-Earnings Ratio" in formula_names
        assert "Market Capitalization" in formula_names

    @staticmethod
    def test_extract_with_dividend_stock():
        """Test extracting dividend yield formula."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        dividend_stock = Equity(
            id="DIV",
            symbol="DIV",
            name="Dividend Stock",
            asset_class=AssetClass.EQUITY,
            sector="Utilities",
            price=100.0,
            dividend_yield=0.04,
        )
        graph.add_asset(dividend_stock)

        formulas = analyzer._extract_fundamental_formulas(graph)

        formula_names = [f.name for f in formulas]
        assert "Dividend Yield" in formula_names

    @staticmethod
    def test_extract_with_bond():
        """Test extracting bond formulas."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        bond = Bond(
            id="BOND",
            symbol="BOND",
            name="Test Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Government",
            price=100.0,
        )
        graph.add_asset(bond)

        formulas = analyzer._extract_fundamental_formulas(graph)

        formula_names = [f.name for f in formulas]
        assert any("Yield-to-Maturity" in name for name in formula_names)

    @staticmethod
    def test_formula_has_required_fields():
        """Test that extracted formulas have all required fields."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)

        formulas = analyzer._extract_fundamental_formulas(graph)

        for formula in formulas:
            assert formula.name
            assert formula.formula
            assert formula.latex
            assert formula.description
            assert isinstance(formula.variables, dict)
            assert formula.example_calculation is not None
            assert formula.category
            assert isinstance(formula.r_squared, float)


class TestAnalyzeCorrelationPatterns:
    """Test _analyze_correlation_patterns method."""

    @staticmethod
    def test_correlation_patterns_basic():
        """Test basic correlation pattern analysis."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._analyze_correlation_patterns(graph)

        assert isinstance(formulas, list)
        assert len(formulas) > 0

        formula_names = [f.name for f in formulas]
        assert "Beta (Systematic Risk)" in formula_names
        assert "Correlation Coefficient" in formula_names

    @staticmethod
    def test_beta_formula_properties():
        """Test beta formula has correct properties."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._analyze_correlation_patterns(graph)

        beta_formula = next((f for f in formulas if "Beta" in f.name), None)
        assert beta_formula is not None
        assert beta_formula.category == "Risk Management"
        assert "β" in beta_formula.variables
        assert beta_formula.r_squared > 0

    @staticmethod
    def test_correlation_formula_properties():
        """Test correlation coefficient formula properties."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._analyze_correlation_patterns(graph)

        corr_formula = next((f for f in formulas if "Correlation" in f.name), None)
        assert corr_formula is not None
        assert corr_formula.category == "Statistical Analysis"
        assert "ρ" in corr_formula.variables


class TestExtractValuationRelationships:
    """Test _extract_valuation_relationships method."""

    @staticmethod
    def test_valuation_with_equities():
        """Test valuation formulas with equity assets."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)

        formulas = analyzer._extract_valuation_relationships(graph)

        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Price-to-Book Ratio" in formula_names
        assert "Enterprise Value" in formula_names

    @staticmethod
    def test_valuation_without_equities():
        """Test valuation formulas without equity assets."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        bond = Bond(
            id="BOND",
            symbol="BOND",
            name="Test Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Government",
            price=100.0,
        )
        graph.add_asset(bond)

        formulas = analyzer._extract_valuation_relationships(graph)

        # Should still include Enterprise Value formula
        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Enterprise Value" in formula_names

    @staticmethod
    def test_pb_ratio_formula_category():
        """Test P/B ratio formula is in Valuation category."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)

        formulas = analyzer._extract_valuation_relationships(graph)

        pb_formula = next((f for f in formulas if "Price-to-Book" in f.name), None)
        assert pb_formula is not None
        assert pb_formula.category == "Valuation"


class TestAnalyzeRiskReturnRelationships:
    """Test _analyze_risk_return_relationships method."""

    @staticmethod
    def test_risk_return_formulas_exist():
        """Test that risk-return formulas are generated."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._analyze_risk_return_relationships(graph)

        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Sharpe Ratio" in formula_names
        assert any("Volatility" in name for name in formula_names)

    @staticmethod
    def test_sharpe_ratio_formula():
        """Test Sharpe Ratio formula properties."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._analyze_risk_return_relationships(graph)

        sharpe_formula = next((f for f in formulas if "Sharpe" in f.name), None)
        assert sharpe_formula is not None
        assert sharpe_formula.category == "Risk Management"
        assert "Sharpe" in sharpe_formula.variables

    @staticmethod
    def test_volatility_formula():
        """Test volatility formula properties."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._analyze_risk_return_relationships(graph)

        vol_formula = next((f for f in formulas if "Volatility" in f.name), None)
        assert vol_formula is not None
        assert vol_formula.category == "Risk Management"
        assert "σ" in vol_formula.variables


class TestExtractPortfolioTheoryFormulas:
    """Test _extract_portfolio_theory_formulas method."""

    def test_portfolio_formulas_exist(self):
        """Test that portfolio theory formulas are generated."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._extract_portfolio_theory_formulas(graph)

        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert any("Portfolio Expected Return" in name for name in formula_names)
        assert any("Portfolio Variance" in name for name in formula_names)

    def test_portfolio_return_formula(self):
        """Test portfolio expected return formula."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._extract_portfolio_theory_formulas(graph)

        ret_formula = next((f for f in formulas if "Expected Return" in f.name), None)
        assert ret_formula is not None
        assert ret_formula.category == "Portfolio Theory"
        assert "E(R_p)" in ret_formula.variables

    def test_portfolio_variance_formula(self):
        """Test portfolio variance formula."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        formulas = analyzer._extract_portfolio_theory_formulas(graph)

        var_formula = next((f for f in formulas if "Variance" in f.name), None)
        assert var_formula is not None
        assert var_formula.category == "Portfolio Theory"


class TestAnalyzeCrossAssetRelationships:
    """Test _analyze_cross_asset_relationships method."""

    def test_cross_asset_without_currencies(self):
        """Test cross-asset analysis without currencies."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)

        formulas = analyzer._analyze_cross_asset_relationships(graph)

        # Should return empty list or no currency formulas
        assert isinstance(formulas, list)

    def test_cross_asset_with_currencies(self):
        """Test cross-asset analysis with currencies."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        currency1 = Currency(
            id="EUR",
            symbol="EUR",
            name="Euro",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.1,
        )
        currency2 = Currency(
            id="GBP",
            symbol="GBP",
            name="British Pound",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.3,
        )
        graph.add_asset(currency1)
        graph.add_asset(currency2)

        formulas = analyzer._analyze_cross_asset_relationships(graph)

        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert any("Exchange Rate" in name for name in formula_names)

    def test_cross_asset_with_commodities_and_currencies(self):
        """Test cross-asset analysis with both commodities and currencies."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        commodity = Commodity(
            id="GOLD",
            symbol="GC",
            name="Gold",
            asset_class=AssetClass.COMMODITY,
            sector="Precious Metals",
            price=2000.0,
        )
        currency = Currency(
            id="USD",
            symbol="USD",
            name="US Dollar",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.0,
        )
        graph.add_asset(commodity)
        graph.add_asset(currency)

        formulas = analyzer._analyze_cross_asset_relationships(graph)

        formula_names = [f.name for f in formulas]
        # Should include commodity-currency relationship formula
        assert any("Commodity-Currency" in name for name in formula_names)


class TestHelperMethods:
    """Test helper and utility methods."""

    @staticmethod
    def test_calculate_empirical_relationships():
        """Test _calculate_empirical_relationships returns empty dict."""
        graph = AssetRelationshipGraph()
        result = FormulaicAnalyzer._calculate_empirical_relationships(graph)

        assert isinstance(result, dict)
        assert len(result) == 0

    @staticmethod
    def test_calculate_avg_correlation_strength():
        """Test _calculate_avg_correlation_strength calculation."""
        graph = AssetRelationshipGraph()

        # Empty graph
        strength = FormulaicAnalyzer._calculate_avg_correlation_strength(graph)
        assert isinstance(strength, float)
        assert 0 <= strength <= 1

    @staticmethod
    def test_calculate_avg_correlation_strength_with_relationships():
        """Test correlation strength with relationships."""
        graph = AssetRelationshipGraph()

        equity1 = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
        )
        equity2 = Equity(
            id="MSFT",
            symbol="MSFT",
            name="Microsoft",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=300.0,
        )
        graph.add_asset(equity1)
        graph.add_asset(equity2)
        graph.build_relationships()

        strength = FormulaicAnalyzer._calculate_avg_correlation_strength(graph)
        assert isinstance(strength, float)

    @staticmethod
    def test_categorize_formulas():
        """Test _categorize_formulas method."""
        analyzer = FormulaicAnalyzer()

        formulas = [
            Formula(
                name="Test1",
                formula="A=B",
                latex="A=B",
                description="Test",
                variables={},
                example_calculation="",
                category="Valuation",
            ),
            Formula(
                name="Test2",
                formula="C=D",
                latex="C=D",
                description="Test",
                variables={},
                example_calculation="",
                category="Valuation",
            ),
            Formula(
                name="Test3",
                formula="E=F",
                latex="E=F",
                description="Test",
                variables={},
                example_calculation="",
                category="Risk Management",
            ),
        ]

        categories = analyzer._categorize_formulas(formulas)

        assert categories["Valuation"] == 2
        assert categories["Risk Management"] == 1

    @staticmethod
    def test_generate_formula_summary():
        """Test _generate_formula_summary method."""
        analyzer = FormulaicAnalyzer()

        formulas = [
            Formula(
                name="Test",
                formula="A=B",
                latex="A=B",
                description="Test",
                variables={},
                example_calculation="",
                category="Valuation",
                r_squared=0.9,
            ),
        ]
        empirical = {}

        summary = analyzer._generate_formula_summary(formulas, empirical)

        assert "total_formulas" in summary
        assert "avg_r_squared" in summary
        assert "formula_categories" in summary
        assert "empirical_data_points" in summary
        assert "key_insights" in summary
        assert summary["total_formulas"] == 1
        assert summary["avg_r_squared"] == 0.9

    @staticmethod
    def test_generate_formula_summary_empty():
        """Test summary generation with no formulas."""
        analyzer = FormulaicAnalyzer()

        summary = analyzer._generate_formula_summary([], {})

        assert summary["total_formulas"] == 0
        assert summary["avg_r_squared"] == 0

    @staticmethod
    def test_calculate_avg_correlation_strength_from_empirical():
        """Test _calculate_avg_correlation_strength_from_empirical."""
        # Empty empirical data
        result = FormulaicAnalyzer._calculate_avg_correlation_strength_from_empirical({})
        assert result == 0.5

        # With correlation matrix
        empirical = {"correlation_matrix": {"pair1": 0.8, "pair2": 0.6}}
        result = FormulaicAnalyzer._calculate_avg_correlation_strength_from_empirical(empirical)
        assert 0 <= result <= 1

        # With perfect correlation (should filter out)
        empirical = {"correlation_matrix": {"pair1": 1.0, "pair2": 0.8}}
        result = FormulaicAnalyzer._calculate_avg_correlation_strength_from_empirical(empirical)
        assert 0 <= result <= 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_analyze_graph_with_all_asset_types(self):
        """Test analyzing a graph with all asset types."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        # Add all types
        equity = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
            dividend_yield=0.005,
        )
        bond = Bond(
            id="BOND",
            symbol="BOND",
            name="Test Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Government",
            price=100.0,
        )
        commodity = Commodity(
            id="GOLD",
            symbol="GC",
            name="Gold",
            asset_class=AssetClass.COMMODITY,
            sector="Precious Metals",
            price=2000.0,
        )
        currency = Currency(
            id="EUR",
            symbol="EUR",
            name="Euro",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.1,
        )

        graph.add_asset(equity)
        graph.add_asset(bond)
        graph.add_asset(commodity)
        graph.add_asset(currency)

        result = analyzer.analyze_graph(graph)

        # Should have formulas from all categories
        assert result["formula_count"] > 5
        categories = result["categories"]
        assert len(categories) > 0

    def test_analyze_graph_with_relationships(self):
        """Test analyzing a graph with relationships."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity1 = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
        )
        equity2 = Equity(
            id="MSFT",
            symbol="MSFT",
            name="Microsoft",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=300.0,
        )

        graph.add_asset(equity1)
        graph.add_asset(equity2)
        graph.build_relationships()

        result = analyzer.analyze_graph(graph)

        # Should handle relationships when calculating correlations
        assert result["formula_count"] > 0

    def test_analyze_graph_with_regulatory_events(self):
        """Test analyzing a graph with regulatory events."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
        )
        graph.add_asset(equity)

        event = RegulatoryEvent(
            id="EVENT1",
            asset_id="AAPL",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-01",
            description="Q4 Earnings",
            impact_score=0.8,
        )
        graph.add_regulatory_event(event)

        result = analyzer.analyze_graph(graph)

        assert result["formula_count"] > 0

    def test_multiple_same_sector_assets(self):
        """Test with multiple assets in the same sector."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        for i in range(5):
            equity = Equity(
                id=f"TECH{i}",
                symbol=f"TECH{i}",
                name=f"Tech Company {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + i * 10,
            )
            graph.add_asset(equity)

        result = analyzer.analyze_graph(graph)

        # Should still generate formulas correctly
        assert result["formula_count"] > 0
        assert result["summary"]["total_formulas"] == result["formula_count"]


class TestRegressionCases:
    """Regression tests for previously identified issues."""

    def test_formula_latex_escaping(self):
        """Test that LaTeX formulas are properly formatted."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)

        result = analyzer.analyze_graph(graph)

        # Check that latex fields are present and contain backslashes
        for formula in result["formulas"]:
            assert formula.latex
            # LaTeX formulas should typically contain backslashes
            if "frac" in formula.latex or "times" in formula.latex:
                assert "\\" in formula.latex

    def test_r_squared_bounds(self):
        """Test that all r_squared values are within valid bounds."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)

        result = analyzer.analyze_graph(graph)

        for formula in result["formulas"]:
            assert 0 <= formula.r_squared <= 1, f"r_squared out of bounds for {formula.name}: {formula.r_squared}"

    def test_summary_consistency(self):
        """Test that summary statistics are consistent with formulas."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)

        result = analyzer.analyze_graph(graph)

        # Verify summary consistency
        assert result["summary"]["total_formulas"] == len(result["formulas"])

        # Verify category counts match
        manual_category_count = sum(result["categories"].values())
        assert manual_category_count == len(result["formulas"])


class TestNegativeCases:
    """Test negative scenarios and error conditions."""

    @staticmethod
    def test_analyze_graph_with_zero_price_asset():
        """Test handling asset with zero price."""
        # Try to create asset with zero price - should be rejected by validation
        with pytest.raises(ValueError):
            equity = Equity(
                id="ZERO",
                symbol="ZERO",
                name="Zero Price",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=0.0,
            )

    @staticmethod
    def test_analyze_graph_with_negative_price():
        """Test handling asset with negative price."""
        # Should be rejected by Asset validation
        with pytest.raises(ValueError):
            Equity(
                id="NEG",
                symbol="NEG",
                name="Negative Price",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=-100.0,
            )


class TestBoundaryConditions:
    """Test boundary conditions and extreme values."""

    def test_very_high_pe_ratio(self):
        """Test formula extraction with very high P/E ratio."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="HIGH_PE",
            symbol="HPE",
            name="High PE",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=1000.0,
            pe_ratio=1000.0,
        )
        graph.add_asset(equity)

        result = analyzer.analyze_graph(graph)
        assert result["formula_count"] > 0

    def test_very_low_prices(self):
        """Test with very low asset prices."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        equity = Equity(
            id="PENNY",
            symbol="PENNY",
            name="Penny Stock",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=0.01,
        )
        graph.add_asset(equity)

        result = analyzer.analyze_graph(graph)
        assert result["formula_count"] > 0

    def test_large_number_of_assets(self):
        """Test analyzer with large number of assets."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        # Add 50 assets
        for i in range(50):
            equity = Equity(
                id=f"ASSET{i}",
                symbol=f"A{i}",
                name=f"Asset {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + i,
            )
            graph.add_asset(equity)

        result = analyzer.analyze_graph(graph)
        assert result["formula_count"] > 0
        assert "summary" in result

    def test_correlation_strength_bounds(self):
        """Test correlation strength calculation stays within bounds."""
        graph = AssetRelationshipGraph()

        # Add many assets and relationships
        for i in range(10):
            equity = Equity(
                id=f"CORR{i}",
                symbol=f"C{i}",
                name=f"Corr {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0,
            )
            graph.add_asset(equity)

        graph.build_relationships()

        strength = FormulaicAnalyzer._calculate_avg_correlation_strength(graph)
        assert 0 <= strength <= 1.0


class TestIntegrationScenarios:
    """Test integrated scenarios with multiple components."""

    def test_diversified_portfolio_analysis(self):
        """Test analysis of a diversified portfolio."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        # Add diverse assets
        equity = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
            dividend_yield=0.005,
        )
        bond = Bond(
            id="BOND",
            symbol="BOND",
            name="Gov Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Government",
            price=1000.0,
            yield_to_maturity=0.03,
        )
        commodity = Commodity(
            symbol="GC",
            name="Gold",
            asset_class=AssetClass.COMMODITY,
            sector="Precious Metals",
            price=2000.0,
        )
        currency = Currency(
            id="EUR",
            symbol="EUR",
            name="Euro",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.1,
        )

        for asset in [equity, bond, commodity, currency]:
            graph.add_asset(asset)

        graph.build_relationships()

        result = analyzer.analyze_graph(graph)

        # Should have formulas from all categories
        assert result["formula_count"] > 10
        categories = result["categories"]
        assert "Valuation" in categories
        assert "Risk Management" in categories
        assert "Portfolio Theory" in categories

    @staticmethod
    def test_sector_correlation_analysis():
        """Test correlation analysis for same-sector assets."""
        analyzer = FormulaicAnalyzer()
        graph = AssetRelationshipGraph()

        # Add multiple tech stocks
        for i, (symbol, name) in enumerate([("AAPL", "Apple"), ("MSFT", "Microsoft"), ("GOOGL", "Google")]):
            equity = Equity(
                id=symbol,
                symbol=symbol,
                name=name,
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + i * 50,
            )
            graph.add_asset(equity)

        graph.build_relationships()

        result = analyzer.analyze_graph(graph)

        # Should identify correlations
        formulas = result["formulas"]
        correlation_formulas = [f for f in formulas if "Correlation" in f.name or "Beta" in f.name]
        assert len(correlation_formulas) > 0
