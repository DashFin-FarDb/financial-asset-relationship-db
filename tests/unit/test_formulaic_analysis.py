"""Unit tests for formulaic analysis.

This module contains comprehensive unit tests for the formulaic_analysis module including:
- Formula extraction and analysis
- Empirical relationship calculations
- Asset type detection
- Correlation analysis
- Formula categorization
- Edge cases and error handling
"""

import pytest

from src.analysis.formulaic_analysis import Formula, FormulaicdAnalyzer
from src.models.financial_models import AssetClass, Equity


@pytest.mark.unit
class TestFormula:
    """Test suite for the Formula dataclass."""

    def test_formula_creation(self):
        """Test creating a Formula instance."""
        formula = Formula(
            name="Test Formula",
            formula="A = B + C",
            latex=r"A = B + C",
            description="A test formula",
            variables={"A": "Result", "B": "Input 1", "C": "Input 2"},
            example_calculation="A = 5 + 3 = 8",
            category="Test",
            r_squared=0.95,
        )

        assert formula.name == "Test Formula"
        assert formula.formula == "A = B + C"
        assert formula.latex == r"A = B + C"
        assert formula.description == "A test formula"
        assert formula.category == "Test"
        assert formula.r_squared == 0.95
        assert len(formula.variables) == 3

    def test_formula_default_r_squared(self):
        """Test that r_squared defaults to 0.0."""
        formula = Formula(
            name="Test",
            formula="F",
            latex="F",
            description="Desc",
            variables={},
            example_calculation="Ex",
            category="Cat",
        )

        assert formula.r_squared == 0.0


@pytest.mark.unit
class TestFormulaicdAnalyzer:
    """Test suite for the FormulaicdAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a FormulaicdAnalyzer instance."""
        return FormulaicdAnalyzer()

    def test_analyzer_initialization(self, analyzer):
        """Test FormulaicdAnalyzer initialization."""
        assert isinstance(analyzer, FormulaicdAnalyzer)
        assert hasattr(analyzer, "formulas")
        assert isinstance(analyzer.formulas, list)
        assert len(analyzer.formulas) == 0

    def test_analyze_graph_with_populated_graph(self, analyzer, populated_graph):
        """Test analyzing a populated graph."""
        # Execute
        results = analyzer.analyze_graph(populated_graph)

        # Assert
        assert isinstance(results, dict)
        assert "formulas" in results
        assert "empirical_relationships" in results
        assert "formula_count" in results
        assert "categories" in results
        assert "summary" in results

        # Verify formulas were extracted
        assert len(results["formulas"]) > 0
        assert results["formula_count"] == len(results["formulas"])

    def test_analyze_graph_with_empty_graph(self, analyzer, empty_graph):
        """Test analyzing an empty graph."""
        # Execute
        results = analyzer.analyze_graph(empty_graph)

        # Assert - should still return valid structure
        assert isinstance(results, dict)
        assert "formulas" in results
        assert "empirical_relationships" in results
        assert isinstance(results["formulas"], list)

    def test_has_equities_detection(self, analyzer, empty_graph, sample_equity):
        """Test detection of equity assets."""
        # Empty graph should have no equities
        assert not analyzer._has_equities(empty_graph)

        # Add equity
        empty_graph.add_asset(sample_equity)
        assert analyzer._has_equities(empty_graph)

    def test_has_bonds_detection(self, analyzer, empty_graph, sample_bond):
        """Test detection of bond assets."""
        # Empty graph should have no bonds
        assert not analyzer._has_bonds(empty_graph)

        # Add bond
        empty_graph.add_asset(sample_bond)
        assert analyzer._has_bonds(empty_graph)

    def test_has_commodities_detection(self, analyzer, empty_graph, sample_commodity):
        """Test detection of commodity assets."""
        # Empty graph should have no commodities
        assert not analyzer._has_commodities(empty_graph)

        # Add commodity
        empty_graph.add_asset(sample_commodity)
        assert analyzer._has_commodities(empty_graph)

    def test_has_currencies_detection(self, analyzer, empty_graph, sample_currency):
        """Test detection of currency assets."""
        # Empty graph should have no currencies
        assert not analyzer._has_currencies(empty_graph)

        # Add currency
        empty_graph.add_asset(sample_currency)
        assert analyzer._has_currencies(empty_graph)

    def test_has_dividend_stocks_detection(self, analyzer, empty_graph, dividend_stock):
        """Test detection of dividend-paying stocks."""
        # Empty graph should have no dividend stocks
        assert not analyzer._has_dividend_stocks(empty_graph)

        # Add equity with dividend
        empty_graph.add_asset(dividend_stock)
        assert analyzer._has_dividend_stocks(empty_graph)

        # Add equity without dividend
        no_div_stock = Equity(
            id="NO_DIV",
            symbol="NODIV",
            name="No Dividend Stock",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=200.0,
            market_cap=2e10,
            pe_ratio=30.0,
            dividend_yield=0.0,
            earnings_per_share=6.67,
        )
        empty_graph.add_asset(no_div_stock)
        # Should still be true because we have one dividend stock
        assert analyzer._has_dividend_stocks(empty_graph)

    def test_extract_fundamental_formulas_with_equities(self, analyzer, empty_graph, sample_equity):
        """Test extraction of fundamental formulas with equity assets."""
        empty_graph.add_asset(sample_equity)

        # Execute
        formulas = analyzer._extract_fundamental_formulas(empty_graph)

        # Assert
        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Price-to-Earnings Ratio" in formula_names
        assert "Market Capitalization" in formula_names

    def test_extract_fundamental_formulas_with_bonds(self, analyzer, empty_graph, sample_bond):
        """Test extraction of fundamental formulas with bond assets."""
        empty_graph.add_asset(sample_bond)

        # Execute
        formulas = analyzer._extract_fundamental_formulas(empty_graph)

        # Assert
        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Bond Yield-to-Maturity (Approximation)" in formula_names

    def test_extract_fundamental_formulas_with_dividend_stocks(self, analyzer, empty_graph, dividend_stock):
        """Test extraction of dividend yield formula."""
        empty_graph.add_asset(dividend_stock)

        # Execute
        formulas = analyzer._extract_fundamental_formulas(empty_graph)

        # Assert
        formula_names = [f.name for f in formulas]
        assert "Dividend Yield" in formula_names

    def test_analyze_correlation_patterns(self, analyzer, populated_graph):
        """Test correlation pattern analysis."""
        # Execute
        formulas = analyzer._analyze_correlation_patterns(populated_graph)

        # Assert
        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Beta (Systematic Risk)" in formula_names
        assert "Correlation Coefficient" in formula_names

    def test_extract_valuation_relationships(self, analyzer, populated_graph):
        """Test valuation relationship extraction."""
        # Execute
        formulas = analyzer._extract_valuation_relationships(populated_graph)

        # Assert
        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Price-to-Book Ratio" in formula_names
        assert "Enterprise Value" in formula_names

    def test_analyze_risk_return_relationships(self, analyzer, populated_graph):
        """Test risk-return relationship analysis."""
        # Execute
        formulas = analyzer._analyze_risk_return_relationships(populated_graph)

        # Assert
        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Sharpe Ratio" in formula_names
        assert "Volatility (Standard Deviation)" in formula_names

    def test_extract_portfolio_theory_formulas(self, analyzer, populated_graph):
        """Test portfolio theory formula extraction."""
        # Execute
        formulas = analyzer._extract_portfolio_theory_formulas(populated_graph)

        # Assert
        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Portfolio Expected Return" in formula_names
        assert "Portfolio Variance (2-Asset)" in formula_names

    def test_analyze_cross_asset_relationships_with_currencies(self, analyzer, empty_graph, sample_currency):
        """Test cross-asset relationship analysis with currencies."""
        empty_graph.add_asset(sample_currency)

        # Execute
        formulas = analyzer._analyze_cross_asset_relationships(empty_graph)

        # Assert
        assert len(formulas) > 0
        formula_names = [f.name for f in formulas]
        assert "Exchange Rate Relationships" in formula_names

    def test_analyze_cross_asset_relationships_with_commodities_and_currencies(
        self, analyzer, empty_graph, sample_commodity, sample_currency
    ):
        """Test cross-asset relationships with commodities and currencies."""
        empty_graph.add_asset(sample_commodity)
        empty_graph.add_asset(sample_currency)

        # Execute
        formulas = analyzer._analyze_cross_asset_relationships(empty_graph)

        # Assert
        formula_names = [f.name for f in formulas]
        assert "Commodity-Currency Relationship" in formula_names

    def test_calculate_empirical_relationships_with_multiple_assets(self, analyzer, populated_graph):
        """Test calculation of empirical relationships."""
        # Execute
        relationships = analyzer._calculate_empirical_relationships(populated_graph)

        # Assert
        assert isinstance(relationships, dict)
        assert "correlation_matrix" in relationships
        assert "strongest_correlations" in relationships
        assert "sector_relationships" in relationships
        assert "asset_class_relationships" in relationships

    def test_calculate_empirical_relationships_with_single_asset(self, analyzer, empty_graph, sample_equity):
        """Test empirical relationships with only one asset."""
        empty_graph.add_asset(sample_equity)

        # Execute
        relationships = analyzer._calculate_empirical_relationships(empty_graph)

        # Assert - should handle single asset gracefully
        assert isinstance(relationships, dict)

    def test_extract_asset_data(self, analyzer, populated_graph):
        """Test extracting quantitative data from assets."""
        # Execute
        data = analyzer._extract_asset_data(populated_graph)

        # Assert
        assert isinstance(data, dict)
        assert len(data) == len(populated_graph.assets)

        # Check that each asset has required fields
        for _asset_id, asset_data in data.items():
            assert "price" in asset_data
            assert "asset_class" in asset_data

    def test_extract_asset_data_equity_specific_fields(self, analyzer, empty_graph, sample_equity):
        """Test that equity-specific fields are extracted."""
        empty_graph.add_asset(sample_equity)

        # Execute
        data = analyzer._extract_asset_data(empty_graph)

        # Assert
        equity_data = data["TEST_AAPL"]
        assert "market_cap" in equity_data
        assert "pe_ratio" in equity_data
        assert "dividend_yield" in equity_data
        assert "eps" in equity_data

    def test_extract_asset_data_bond_specific_fields(self, analyzer, empty_graph, sample_bond):
        """Test that bond-specific fields are extracted."""
        empty_graph.add_asset(sample_bond)

        # Execute
        data = analyzer._extract_asset_data(empty_graph)

        # Assert
        bond_data = data["TEST_BOND"]
        assert "yield" in bond_data
        assert "coupon_rate" in bond_data

    def test_extract_asset_data_commodity_specific_fields(self, analyzer, empty_graph, sample_commodity):
        """Test that commodity-specific fields are extracted."""
        empty_graph.add_asset(sample_commodity)

        # Execute
        data = analyzer._extract_asset_data(empty_graph)

        # Assert
        commodity_data = data["TEST_GOLD"]
        assert "volatility" in commodity_data
        assert "contract_size" in commodity_data

    def test_extract_asset_data_currency_specific_fields(self, analyzer, empty_graph, sample_currency):
        """Test that currency-specific fields are extracted."""
        empty_graph.add_asset(sample_currency)

        # Execute
        data = analyzer._extract_asset_data(empty_graph)

        # Assert
        currency_data = data["TEST_EUR"]
        assert "exchange_rate" in currency_data
        assert "central_bank_rate" in currency_data

    def test_calculate_correlation_matrix(self, analyzer, populated_graph):
        """Test correlation matrix calculation."""
        assets_data = analyzer._extract_asset_data(populated_graph)

        # Execute
        correlation_matrix = analyzer._calculate_correlation_matrix(assets_data)

        # Assert
        assert isinstance(correlation_matrix, dict)
        assert len(correlation_matrix) > 0

        # Check that all correlations are between -1 and 1
        for pair, corr in correlation_matrix.items():
            assert -1.0 <= corr <= 1.0, f"Correlation for {pair} should be between -1 and 1"

    def test_calculate_correlation_matrix_self_correlation(self, analyzer, empty_graph, sample_equity):
        """Test that self-correlations are 1.0."""
        empty_graph.add_asset(sample_equity)
        assets_data = analyzer._extract_asset_data(empty_graph)

        # Execute
        correlation_matrix = analyzer._calculate_correlation_matrix(assets_data)

        # Assert
        assert "TEST_AAPL-TEST_AAPL" in correlation_matrix
        assert correlation_matrix["TEST_AAPL-TEST_AAPL"] == 1.0

    def test_find_strongest_correlations(self, analyzer):
        """Test finding strongest correlations."""
        correlation_matrix = {
            "A-B": 0.9,
            "A-C": 0.5,
            "B-C": 0.7,
            "A-D": 0.3,
            "B-D": 0.8,
            "C-D": 0.4,
        }
        assets_data = {}  # Not used in this method

        # Execute
        strongest = analyzer._find_strongest_correlations(correlation_matrix, assets_data)

        # Assert
        assert len(strongest) <= 5, "Should return at most 5 correlations"
        assert all(c["correlation"] < 1.0 for c in strongest), "Should exclude self-correlations"

        # Check that results are sorted by correlation strength
        correlations = [c["correlation"] for c in strongest]
        assert correlations == sorted(correlations, reverse=True)

    def test_calculate_sector_relationships(self, analyzer, populated_graph):
        """Test calculation of sector-based relationships."""
        # Execute
        sector_stats = analyzer._calculate_sector_relationships(populated_graph)

        # Assert
        assert isinstance(sector_stats, dict)

        for _sector, stats in sector_stats.items():
            assert "asset_count" in stats
            assert "avg_price" in stats
            assert "price_range" in stats
            assert stats["asset_count"] >= 2, "Sector stats should only include sectors with 2+ assets"

    def test_calculate_asset_class_relationships(self, analyzer, populated_graph):
        """Test calculation of asset class relationships."""
        # Execute
        class_stats = analyzer._calculate_asset_class_relationships(populated_graph)

        # Assert
        assert isinstance(class_stats, dict)

        for _class_name, stats in class_stats.items():
            assert "asset_count" in stats
            assert "avg_price" in stats
            assert "total_value" in stats
            assert stats["asset_count"] > 0
            assert stats["avg_price"] > 0
            assert stats["total_value"] > 0

    def test_calculate_avg_correlation_strength(self, analyzer, populated_graph):
        """Test calculation of average correlation strength."""
        # Execute
        strength = analyzer._calculate_avg_correlation_strength(populated_graph)

        # Assert
        assert isinstance(strength, float)
        assert 0.0 <= strength <= 1.0, "Correlation strength should be between 0 and 1"

    def test_categorize_formulas(self, analyzer):
        """Test formula categorization."""
        formulas = [
            Formula("F1", "f1", "f1", "desc1", {}, "ex1", "Valuation", 0.9),
            Formula("F2", "f2", "f2", "desc2", {}, "ex2", "Valuation", 0.8),
            Formula("F3", "f3", "f3", "desc3", {}, "ex3", "Income", 1.0),
        ]

        # Execute
        categories = analyzer._categorize_formulas(formulas)

        # Assert
        assert categories["Valuation"] == 2
        assert categories["Income"] == 1

    def test_generate_formula_summary(self, analyzer):
        """Test generation of formula summary."""
        formulas = [
            Formula("F1", "f1", "f1", "desc1", {}, "ex1", "Valuation", 0.9),
            Formula("F2", "f2", "f2", "desc2", {}, "ex2", "Income", 0.8),
        ]
        empirical_relationships = {"correlation_matrix": {"A-B": 0.7, "A-C": 0.5}}

        # Execute
        summary = analyzer._generate_formula_summary(formulas, empirical_relationships)

        # Assert
        assert "total_formulas" in summary
        assert summary["total_formulas"] == 2
        assert "avg_r_squared" in summary
        assert abs(summary["avg_r_squared"] - 0.85) < 0.01
        assert "formula_categories" in summary
        assert "empirical_data_points" in summary
        assert "key_insights" in summary
        assert isinstance(summary["key_insights"], list)


@pytest.mark.unit
class TestExampleCalculationMethods:
    """Test suite for example calculation methods."""

    @pytest.fixture
    def analyzer(self):
        """Create a FormulaicdAnalyzer instance."""
        return FormulaicdAnalyzer()

    def test_calculate_pe_examples(self, analyzer, empty_graph, sample_equity):
        """Test PE ratio example calculations."""
        empty_graph.add_asset(sample_equity)

        # Execute
        examples = analyzer._calculate_pe_examples(empty_graph)

        # Assert
        assert isinstance(examples, str)
        assert len(examples) > 0
        assert "PE" in examples or "calculation requires EPS data" in examples

    def test_calculate_dividend_examples(self, analyzer, empty_graph, dividend_stock):
        """Test dividend yield example calculations."""
        empty_graph.add_asset(dividend_stock)

        # Execute
        examples = analyzer._calculate_dividend_examples(empty_graph)

        # Assert
        assert isinstance(examples, str)
        assert "Yield" in examples or "calculation requires yield data" in examples

    def test_calculate_ytm_examples(self, analyzer, empty_graph, sample_bond):
        """Test YTM example calculations."""
        empty_graph.add_asset(sample_bond)

        # Execute
        examples = analyzer._calculate_ytm_examples(empty_graph)

        # Assert
        assert isinstance(examples, str)
        assert "YTM" in examples or "bond ETFs" in examples.lower()

    def test_calculate_market_cap_examples(self, analyzer, empty_graph, sample_equity):
        """Test market cap example calculations."""
        empty_graph.add_asset(sample_equity)

        # Execute
        examples = analyzer._calculate_market_cap_examples(empty_graph)

        # Assert
        assert isinstance(examples, str)
        assert "Market Cap" in examples or "market cap data" in examples.lower()

    def test_calculate_beta_examples(self, analyzer, populated_graph):
        """Test beta example calculations."""
        # Execute
        examples = analyzer._calculate_beta_examples(populated_graph)

        # Assert
        assert isinstance(examples, str)
        assert "Beta" in examples or "historical price data" in examples

    def test_calculate_correlation_examples(self, analyzer, populated_graph):
        """Test correlation example calculations."""
        # Execute
        examples = analyzer._calculate_correlation_examples(populated_graph)

        # Assert
        assert isinstance(examples, str)

    def test_calculate_pb_examples(self, analyzer, empty_graph):
        """Test P/B ratio example calculations."""
        equity_with_book_value = Equity(
            id="PB_STOCK",
            symbol="PBS",
            name="PB Stock",
            asset_class=AssetClass.EQUITY,
            sector="Finance",
            price=100.0,
            market_cap=1e10,
            pe_ratio=15.0,
            dividend_yield=0.02,
            earnings_per_share=6.67,
            book_value=80.0,
        )
        empty_graph.add_asset(equity_with_book_value)

        # Execute
        examples = analyzer._calculate_pb_examples(empty_graph)

        # Assert
        assert isinstance(examples, str)
        assert "P/B" in examples or "book value" in examples.lower()

    def test_calculate_sharpe_examples(self, analyzer, populated_graph):
        """Test Sharpe ratio example calculations."""
        # Execute
        examples = analyzer._calculate_sharpe_examples(populated_graph)

        # Assert
        assert isinstance(examples, str)
        assert "Sharpe" in examples or "return history" in examples

    def test_calculate_volatility_examples(self, analyzer, empty_graph, sample_commodity):
        """Test volatility example calculations."""
        empty_graph.add_asset(sample_commodity)

        # Execute
        examples = analyzer._calculate_volatility_examples(empty_graph)

        # Assert
        assert isinstance(examples, str)

    def test_calculate_portfolio_return_examples(self, analyzer, populated_graph):
        """Test portfolio return example calculations."""
        # Execute
        examples = analyzer._calculate_portfolio_return_examples(populated_graph)

        # Assert
        assert isinstance(examples, str)
        assert "Portfolio" in examples

    def test_calculate_portfolio_variance_examples(self, analyzer, populated_graph):
        """Test portfolio variance example calculations."""
        # Execute
        examples = analyzer._calculate_portfolio_variance_examples(populated_graph)

        # Assert
        assert isinstance(examples, str)
        assert "variance" in examples.lower()

    def test_calculate_exchange_rate_examples(self, analyzer, empty_graph, sample_currency):
        """Test exchange rate example calculations."""
        empty_graph.add_asset(sample_currency)

        # Execute
        examples = analyzer._calculate_exchange_rate_examples(empty_graph)

        # Assert
        assert isinstance(examples, str)

    def test_calculate_commodity_currency_examples(self, analyzer, populated_graph):
        """Test commodity-currency example calculations."""
        # Execute
        examples = analyzer._calculate_commodity_currency_examples(populated_graph)

        # Assert
        assert isinstance(examples, str)
        assert "Gold" in examples or "commodity" in examples.lower()


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def analyzer(self):
        """Create a FormulaicdAnalyzer instance."""
        return FormulaicdAnalyzer()

    def test_analyze_graph_with_many_assets(self, analyzer, empty_graph):
        """Test analyzing a graph with many assets."""
        # Add 20 different assets
        for i in range(20):
            equity = Equity(
                id=f"STOCK_{i}",
                symbol=f"STK{i}",
                name=f"Stock {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology" if i % 2 == 0 else "Finance",
                price=100.0 + i * 10,
                market_cap=1e10 * (i + 1),
                pe_ratio=20.0 + i,
                dividend_yield=0.02,
                earnings_per_share=5.0,
            )
            empty_graph.add_asset(equity)

        # Execute
        results = analyzer.analyze_graph(empty_graph)

        # Assert
        assert len(results["formulas"]) > 0
        assert results["formula_count"] > 0

    def test_extract_asset_data_with_none_values(self, analyzer, empty_graph):
        """Test extracting asset data when some fields are None."""
        equity_with_nones = Equity(
            id="NONE_STOCK",
            symbol="NONE",
            name="Stock with Nones",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
            market_cap=None,
            pe_ratio=None,
            dividend_yield=None,
            earnings_per_share=None,
        )
        empty_graph.add_asset(equity_with_nones)

        # Execute
        data = analyzer._extract_asset_data(empty_graph)

        # Assert - should handle None values gracefully
        assert "NONE_STOCK" in data
        equity_data = data["NONE_STOCK"]
        assert "market_cap" in equity_data
        assert equity_data["market_cap"] == 0  # Should default to 0

    def test_correlation_matrix_with_empty_asset_data(self, analyzer):
        """Test correlation matrix with empty asset data."""
        # Execute
        correlation_matrix = analyzer._calculate_correlation_matrix({})

        # Assert
        assert isinstance(correlation_matrix, dict)
        assert len(correlation_matrix) == 0

    def test_find_strongest_correlations_with_no_correlations(self, analyzer):
        """Test finding strongest correlations when matrix only has self-correlations."""
        correlation_matrix = {"A-A": 1.0, "B-B": 1.0}

        # Execute
        strongest = analyzer._find_strongest_correlations(correlation_matrix, {})

        # Assert
        assert len(strongest) == 0, "Should return empty list when no cross-correlations exist"

    def test_sector_relationships_with_single_asset_sectors(self, analyzer, populated_graph):
        """Test that sectors with only one asset are excluded."""
        # Add a unique sector with one asset
        unique_equity = Equity(
            id="UNIQUE",
            symbol="UNQ",
            name="Unique Sector Stock",
            asset_class=AssetClass.EQUITY,
            sector="Aerospace",
            price=200.0,
            market_cap=5e10,
            pe_ratio=18.0,
            dividend_yield=0.01,
            earnings_per_share=11.11,
        )
        populated_graph.add_asset(unique_equity)

        # Execute
        sector_stats = analyzer._calculate_sector_relationships(populated_graph)

        # Assert
        assert "Aerospace" not in sector_stats, "Sectors with only one asset should be excluded"

    def test_calculate_avg_correlation_strength_with_no_relationships(self, analyzer, empty_graph):
        """Test average correlation strength with no relationships."""
        # Execute
        strength = analyzer._calculate_avg_correlation_strength(empty_graph)

        # Assert
        assert strength == 0.5, "Should return 0.5 when no relationships exist"

    def test_generate_formula_summary_with_empty_formulas(self, analyzer):
        """Test generating summary with no formulas."""
        # Execute
        summary = analyzer._generate_formula_summary([], {})

        # Assert
        assert summary["total_formulas"] == 0
        assert summary["avg_r_squared"] == 0

    def test_analyze_graph_preserves_original_formulas_list(self, analyzer, populated_graph):
        """Test that analyzing a graph doesn't modify the analyzer's formulas list."""
        initial_length = len(analyzer.formulas)

        # Execute
        analyzer.analyze_graph(populated_graph)

        # Assert
        assert len(analyzer.formulas) == initial_length, "Should not modify analyzer's formulas list"
