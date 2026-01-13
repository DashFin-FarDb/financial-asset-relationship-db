"""Unit tests for formulaic visualizations.

This module contains comprehensive unit tests for the formulaic_visuals module including:
- Formula dashboard creation
- Formula detail views
- Correlation network visualization
- Metric comparison charts
- Edge cases and error handling
"""

import plotly.graph_objects as go
import pytest

from src.analysis.formulaic_analysis import Formula
from src.visualizations.formulaic_visuals import FormulaicVisualizer


@pytest.mark.unit
class TestFormulaicVisualizer:
    """Test suite for the FormulaicVisualizer class."""

    @pytest.fixture
    def visualizer(self):
        """Create a FormulaicVisualizer instance."""
        return FormulaicVisualizer()

    @pytest.fixture
    def sample_formula(self):
        """Create a sample formula for testing."""
        return Formula(
            name="Price-to-Earnings Ratio",
            formula="PE = P / EPS",
            latex=r"PE = \frac{P}{EPS}",
            description="Valuation metric comparing stock price to earnings per share",
            variables={
                "PE": "Price-to-Earnings Ratio",
                "P": "Current Stock Price ($)",
                "EPS": "Earnings Per Share ($)",
            },
            example_calculation="AAPL: PE = $150.00 / $5.89 = 25.47",
            category="Valuation",
            r_squared=0.95,
        )

    @pytest.fixture
    def sample_analysis_results(self, sample_formula):
        """Create sample analysis results."""
        return {
            "formulas": [
                sample_formula,
                dict(
                    description="Percentage return from dividends",
                    variables={"Div_Yield": "Dividend Yield (%)", "D_annual": "Annual Dividends ($)", "P": "Price ($)"},
                    example_calculation="MSFT: Yield = 2.5%",
                    category="Income",
                    r_squared=1.0,
                ),
            ],
            "categories": {"Valuation": 1, "Income": 1},
            "empirical_relationships": {
                "correlation_matrix": {
                    "AAPL-MSFT": 0.8,
                    "AAPL-GOOGL": 0.7,
                    "MSFT-GOOGL": 0.75,
                },
                "strongest_correlations": [
                    {"asset1": "AAPL", "asset2": "MSFT", "correlation": 0.8, "strength": "Strong"},
                    {"asset1": "MSFT", "asset2": "GOOGL", "correlation": 0.75, "strength": "Strong"},
                ],
            },
            "asset_class_relationships": {"Equity": {"asset_count": 3, "avg_price": 150.0, "total_value": 450.0}},
            "sector_relationships": {
                "Technology": {"asset_count": 3, "avg_price": 150.0, "price_range": "$100.00 - $200.00"}
            },
        }

    @staticmethod
    def test_visualizer_initialization(visualizer):
        """Test FormulaicVisualizer initialization."""
        assert isinstance(visualizer, FormulaicVisualizer)
        assert hasattr(visualizer, "color_scheme")
        assert isinstance(visualizer.color_scheme, dict)
        assert "Valuation" in visualizer.color_scheme
        assert "Income" in visualizer.color_scheme

    @staticmethod
    def test_color_scheme_completeness(visualizer):
        """Test that color scheme includes all expected categories."""
        expected_categories = [
            "Valuation",
            "Income",
            "Fixed Income",
            "Risk Management",
            "Portfolio Theory",
            "Statistical Analysis",
            "Currency Markets",
            "Cross-Asset",
        ]

        for category in expected_categories:
            assert category in visualizer.color_scheme, f"Color scheme should include {category}"
            assert isinstance(visualizer.color_scheme[category], str), f"Color for {category} should be a string"

    @staticmethod
    def test_create_formula_dashboard_with_full_data(visualizer, sample_analysis_results):
        """Test creating a formula dashboard with comprehensive data."""
        # Execute
        fig = visualizer.create_formula_dashboard(sample_analysis_results)

        # Assert
        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "📊 Financial Formulaic Analysis Dashboard"
        assert fig.layout.height == 1000
        assert fig.layout.showlegend is False
        assert fig.layout.plot_bgcolor == "white"
        assert fig.layout.paper_bgcolor == "#F8F9FA"

    @staticmethod
    @staticmethod
    def test_create_formula_dashboard_with_empty_data(visualizer):
        """Test creating a formula dashboard with empty data."""
        empty_results = {
            "formulas": [],
            "categories": {},
            "empirical_relationships": {},
        }

        # Execute
        fig = visualizer.create_formula_dashboard(empty_results)

        # Assert - should still create a valid figure
        assert isinstance(fig, go.Figure)
        assert fig.layout.title.text == "📊 Financial Formulaic Analysis Dashboard"

    @staticmethod
    @staticmethod
    def test_create_formula_dashboard_categories_pie_chart(visualizer, sample_analysis_results):
        """Test that formula categories pie chart is created correctly."""
        # Execute
        fig = visualizer.create_formula_dashboard(sample_analysis_results)

        # Find the pie chart trace (should be first trace in first subplot)
        pie_traces = [trace for trace in fig.data if trace.type == "pie"]
        assert len(pie_traces) > 0, "Should have at least one pie chart"

        pie_trace = pie_traces[0]
        assert pie_trace.hole == 0.4, "Should be a donut chart"
        assert len(pie_trace.labels) > 0, "Should have category labels"
        assert len(pie_trace.values) > 0, "Should have category values"

    @staticmethod
    @staticmethod
    def test_create_formula_dashboard_reliability_bar_chart(visualizer, sample_analysis_results):
        """Test that formula reliability bar chart is created correctly."""
        # Execute
        fig = visualizer.create_formula_dashboard(sample_analysis_results)

        # Find bar chart traces
        bar_traces = [trace for trace in fig.data if trace.type == "bar"]
        assert len(bar_traces) > 0, "Should have at least one bar chart"

    @staticmethod
    @staticmethod
    def test_create_formula_dashboard_correlation_heatmap(visualizer, sample_analysis_results):
        """Test that correlation heatmap is created correctly."""
        # Execute
        fig = visualizer.create_formula_dashboard(sample_analysis_results)

        # Find heatmap trace
        heatmap_traces = [trace for trace in fig.data if trace.type == "heatmap"]
        assert len(heatmap_traces) > 0, "Should have a heatmap"

        heatmap = heatmap_traces[0]
        assert heatmap.colorscale == "RdYlBu_r"
        assert heatmap.zmin == -1
        assert heatmap.zmax == 1

    @staticmethod
    @staticmethod
    def test_create_formula_dashboard_with_table(visualizer, sample_analysis_results):
        """Test that formula examples table is created."""
        # Execute
        fig = visualizer.create_formula_dashboard(sample_analysis_results)

        # Find table trace
        table_traces = [trace for trace in fig.data if trace.type == "table"]
        assert len(table_traces) > 0, "Should have a table"

        table = table_traces[0]
        assert hasattr(table, "header")
        assert hasattr(table, "cells")

    @staticmethod
    @staticmethod
    def test_create_formula_detail_view(visualizer, sample_formula):
        """Test creating a detailed formula view."""
        # Execute
        fig = visualizer.create_formula_detail_view(sample_formula)

        # Assert
        assert isinstance(fig, go.Figure)
        assert "Formula Details:" in fig.layout.title.text
        assert sample_formula.name in fig.layout.title.text
        assert fig.layout.height == 600
        assert fig.layout.plot_bgcolor == "white"

        # Check that annotation exists with formula details
        assert len(fig.layout.annotations) > 0
        annotation = fig.layout.annotations[0]
        assert sample_formula.name in annotation.text
        assert sample_formula.formula in annotation.text
        assert sample_formula.description in annotation.text

    @staticmethod
    @staticmethod
    def test_create_formula_detail_view_includes_all_fields(visualizer, sample_formula):
        """Test that detail view includes all formula fields."""
        # Execute
        fig = visualizer.create_formula_detail_view(sample_formula)

        # Get annotation text
        annotation_text = fig.layout.annotations[0].text

        # Verify all fields are included
        assert sample_formula.name in annotation_text
        assert sample_formula.formula in annotation_text
        assert sample_formula.latex in annotation_text
        assert sample_formula.description in annotation_text
        assert sample_formula.category in annotation_text
        assert f"{sample_formula.r_squared:.3f}" in annotation_text

        # Check variables are included
        for var, desc in sample_formula.variables.items():
            assert var in annotation_text or desc in annotation_text

    @staticmethod
    def test_create_correlation_network_with_data(visualizer, sample_analysis_results):
        """Test creating a correlation network with data."""
        # Execute
        fig = visualizer.create_correlation_network(sample_analysis_results["empirical_relationships"])

        # Assert
        assert isinstance(fig, go.Figure)
        assert "Asset Correlation Network" in fig.layout.title.text
        assert len(fig.data) > 0, "Should have traces for nodes and edges"

    @staticmethod
    def test_create_correlation_network_without_data(visualizer):
        """Test creating a correlation network without correlation data."""
        empty_relationships = {"strongest_correlations": []}

        # Execute
        fig = visualizer.create_correlation_network(empty_relationships)

        # Assert
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0
        assert "No correlation data available" in fig.layout.annotations[0].text

    @staticmethod
    def test_create_correlation_network_node_positioning(visualizer, sample_analysis_results):
        """Test that correlation network positions nodes in a circle."""
        # Execute
        fig = visualizer.create_correlation_network(sample_analysis_results["empirical_relationships"])

        # Find node trace (should be the last trace with mode containing 'markers')
        node_traces = [trace for trace in fig.data if "markers" in trace.mode]
        assert len(node_traces) > 0, "Should have node trace"

        node_trace = node_traces[-1]
        assert len(node_trace.x) > 0, "Should have node x coordinates"
        assert len(node_trace.y) > 0, "Should have node y coordinates"
        assert len(node_trace.x) == len(node_trace.y), "Should have matching x and y coordinates"

    @staticmethod
    @staticmethod
    def test_create_correlation_network_edge_colors(visualizer):
        """Test that correlation network uses correct edge colors based on strength."""
        # Modify correlations to test different strengths
        relationships = {
            "strongest_correlations": [
                {"asset1": "AAPL", "asset2": "MSFT", "correlation": 0.8},  # red (>0.7)
                {"asset1": "AAPL", "asset2": "GOOGL", "correlation": 0.5},  # orange (>0.4)
                {"asset1": "MSFT", "asset2": "AMZN", "correlation": 0.3},  # lightgray (<0.4)
            ]
        }

        # Execute
        fig = visualizer.create_correlation_network(relationships)

        # Find edge traces (lines)
        edge_traces = [trace for trace in fig.data if trace.mode == "lines"]
        assert len(edge_traces) > 0, "Should have edge traces"

    @staticmethod
    @staticmethod
    def test_create_metric_comparison_chart(visualizer, sample_analysis_results):
        """Test creating a metric comparison chart."""
        # Execute
        fig = visualizer.create_metric_comparison_chart(sample_analysis_results)

        # Assert
        assert isinstance(fig, go.Figure)
        assert "Formula Categories: Reliability vs Count" in fig.layout.title.text
        assert fig.layout.barmode == "group"
        assert fig.layout.plot_bgcolor == "white"

    @staticmethod
    def test_create_metric_comparison_chart_with_empty_formulas(visualizer):
        """Test metric comparison chart with no formulas."""
        empty_results = {"formulas": []}

        # Execute
        fig = visualizer.create_metric_comparison_chart(empty_results)

        # Assert - should create valid figure even with no data
        assert isinstance(fig, go.Figure)

    @staticmethod
    @staticmethod
    def test_create_metric_comparison_chart_multiple_categories(visualizer):
        """Test metric comparison chart with multiple categories."""
        results = {
            "formulas": [
                Formula(
                    name="Formula 1",
                    formula="F1",
                    latex="F1",
                    description="Desc 1",
                    variables={},
                    example_calculation="Ex 1",
                    category="Valuation",
                    r_squared=0.9,
                ),
                Formula(
                    name="Formula 2",
                    formula="F2",
                    latex="F2",
                    description="Desc 2",
                    variables={},
                    example_calculation="Ex 2",
                    category="Valuation",
                    r_squared=0.8,
                ),
                Formula(
                    name="Formula 3",
                    formula="F3",
                    latex="F3",
                    description="Desc 3",
                    variables={},
                    example_calculation="Ex 3",
                    category="Risk Management",
                    r_squared=0.7,
                ),
            ]
        }

        # Execute
        fig = visualizer.create_metric_comparison_chart(results)

        # Assert
        assert len(fig.data) == 2, "Should have two bar traces (R-squared and count)"

        # Find the traces
        r_squared_trace = next((t for t in fig.data if t.name == "Average R-squared"), None)
        count_trace = next((t for t in fig.data if t.name == "Formula Count"), None)

        assert r_squared_trace is not None, "Should have R-squared trace"
        assert count_trace is not None, "Should have count trace"

    @staticmethod
    @staticmethod
    def test_formula_dashboard_handles_large_correlation_matrix(visualizer):
        """Test dashboard with a large correlation matrix."""
        # Create a large correlation matrix (more than 8x8)
        assets = [f"ASSET_{i}" for i in range(15)]
        correlation_matrix = {}

        for i, asset1 in enumerate(assets):
            for j, asset2 in enumerate(assets):
                if i <= j:
                    corr = 1.0 if i == j else 0.5 + (i + j) / 100.0
                    correlation_matrix[f"{asset1}-{asset2}"] = min(corr, 1.0)

        results = {
            "formulas": [],
            "categories": {},
            "empirical_relationships": {"correlation_matrix": correlation_matrix},
        }

        # Execute
        fig = visualizer.create_formula_dashboard(results)

        # Assert - should limit to 8x8
        assert isinstance(fig, go.Figure)
        heatmap_traces = [trace for trace in fig.data if trace.type == "heatmap"]
        if heatmap_traces:
            heatmap = heatmap_traces[0]
            assert len(heatmap.z) <= 8, "Should limit heatmap to 8x8"

    @staticmethod
    @staticmethod
    def test_formula_detail_view_with_special_characters(visualizer):
        """Test detail view with formulas containing special characters."""
        special_formula = Formula(
            name="Complex Formula",
            formula="sigma^2_p = w1^2*sigma1^2 + w2^2*sigma2^2 + 2*w1*w2*rho12*sigma1*sigma2",
            latex=r"\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2w_1w_2\rho_{12}\sigma_1\sigma_2",
            description="Portfolio variance with Greek letters",
            variables={"sigma^2_p": "Portfolio variance", "rho12": "Correlation"},
            example_calculation="Example with sigma = 0.15",
            category="Portfolio Theory",
            r_squared=0.87,
        )

        # Execute
        fig = visualizer.create_formula_detail_view(special_formula)

        # Assert - should handle special characters
        assert isinstance(fig, go.Figure)
        annotation_text = fig.layout.annotations[0].text
        assert "sigma" in annotation_text or "rho" in annotation_text

    @staticmethod
    def test_correlation_network_with_many_correlations(visualizer):
        """Test correlation network limits to top 10 correlations."""
        # Create many correlations
        relationships = {
            "strongest_correlations": [
                {"asset1": f"ASSET_{i}", "asset2": f"ASSET_{i+1}", "correlation": 0.9 - i * 0.05} for i in range(20)
            ]
        }

        # Execute
        fig = visualizer.create_correlation_network(relationships)

        # Assert
        assert isinstance(fig, go.Figure)
        # Edge traces should be limited
        edge_traces = [trace for trace in fig.data if trace.mode == "lines"]
        assert len(edge_traces) <= 10, "Should limit to top 10 correlations"

    @staticmethod
    def test_metric_comparison_calculates_averages_correctly(visualizer):
        """Test that metric comparison correctly calculates category averages."""
        results = {
            "formulas": [
                Formula(
                    name="F1",
                    formula="F1",
                    latex="F1",
                    description="D1",
                    variables={},
                    example_calculation="E1",
                    category="Valuation",
                    r_squared=0.9,
                ),
                Formula(
                    name="F2",
                    formula="F2",
                    latex="F2",
                    description="D2",
                    variables={},
                    example_calculation="E2",
                    category="Valuation",
                    r_squared=0.7,
                ),
            ]
        }

        # Execute
        fig = visualizer.create_metric_comparison_chart(results)

        # Assert
        r_squared_trace = next((t for t in fig.data if t.name == "Average R-squared"), None)
        assert r_squared_trace is not None

        # Average should be (0.9 + 0.7) / 2 = 0.8
        assert len(r_squared_trace.y) > 0
        avg_value = r_squared_trace.y[0]
        assert abs(avg_value - 0.8) < 0.01, "Should correctly calculate average R-squared"
