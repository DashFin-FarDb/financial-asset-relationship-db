"""Unit tests for formulaic visualizations."""

from unittest.mock import Mock

import plotly.graph_objects as go
import pytest

from src.visualizations.formulaic_visuals import FormulaicVisualizer


@pytest.fixture
def visualizer() -> FormulaicVisualizer:
    """Provide a FormulaicVisualizer instance for testing."""
    return FormulaicVisualizer()


@pytest.mark.unit
def test_aggregate_category_stats_happy_path(visualizer: FormulaicVisualizer) -> None:
    """Test aggregation with valid formulas."""
    formulas = [
        Mock(category="Valuation", r_squared=0.8),
        Mock(category="Valuation", r_squared=0.6),
        Mock(category="Income", r_squared=0.9),
    ]

    stats = visualizer._aggregate_category_stats(formulas)

    assert len(stats) == 2
    assert "Valuation" in stats
    assert "Income" in stats

    assert stats["Valuation"]["count"] == 2.0
    assert stats["Valuation"]["total_r2"] == pytest.approx(1.4)
    assert stats["Valuation"]["avg_r2"] == pytest.approx(0.7)

    assert stats["Income"]["count"] == 1.0
    assert stats["Income"]["total_r2"] == 0.9
    assert stats["Income"]["avg_r2"] == 0.9


@pytest.mark.unit
def test_aggregate_category_stats_empty_formulas(visualizer: FormulaicVisualizer) -> None:
    """Test aggregation safely handles empty or None inputs."""
    assert visualizer._aggregate_category_stats([]) == {}
    assert visualizer._aggregate_category_stats(None) == {}


@pytest.mark.unit
def test_aggregate_category_stats_missing_attributes(visualizer: FormulaicVisualizer) -> None:
    """Test aggregation handles objects completely missing category/r_squared."""
    # Create a mock with NO attributes specified
    formulas = [Mock(spec=[])]

    stats = visualizer._aggregate_category_stats(formulas)

    assert len(stats) == 1
    assert "Unknown" in stats
    assert stats["Unknown"]["count"] == 1.0
    assert stats["Unknown"]["total_r2"] == 0.0
    assert stats["Unknown"]["avg_r2"] == 0.0


@pytest.mark.unit
def test_aggregate_category_stats_none_attributes(visualizer: FormulaicVisualizer) -> None:
    """Test aggregation handles objects where category or r_squared is explicitly None."""
    formulas = [Mock(category=None, r_squared=None)]
    stats = visualizer._aggregate_category_stats(formulas)

    assert "Unknown" in stats
    assert stats["Unknown"]["total_r2"] == 0.0


@pytest.mark.unit
def test_aggregate_category_stats_empty_category_string(visualizer: FormulaicVisualizer) -> None:
    """Test empty string categories default to 'Unknown'."""
    formulas = [Mock(category="", r_squared=0.5)]
    stats = visualizer._aggregate_category_stats(formulas)

    assert "Unknown" in stats
    assert stats["Unknown"]["total_r2"] == 0.5


@pytest.mark.unit
def test_apply_dashboard_layout_mutates_figure_correctly(visualizer: FormulaicVisualizer) -> None:
    """Test that dashboard layout properties are correctly applied without adding traces."""
    fig = go.Figure()

    visualizer._apply_dashboard_layout(fig)

    assert fig.layout.title.text == "📊 Financial Formulaic Analysis Dashboard"
    assert fig.layout.height == 1000
    assert fig.layout.showlegend is False
    assert fig.layout.plot_bgcolor == "white"
    assert fig.layout.paper_bgcolor == "#F8F9FA"
    assert len(fig.data) == 0  # Asserts data separation of concerns


@pytest.mark.unit
def test_apply_metric_comparison_layout_mutates_figure_correctly(visualizer: FormulaicVisualizer) -> None:
    """Test that metric comparison layout properties are applied correctly."""
    fig = go.Figure()

    visualizer._apply_metric_comparison_layout(fig)

    assert fig.layout.title.text == "Formula Categories: Reliability vs Count"
    assert fig.layout.xaxis.title.text == "Formula Category"
    assert fig.layout.yaxis.title.text == "Value"
    assert fig.layout.barmode == "group"
    assert fig.layout.plot_bgcolor == "white"
    assert len(fig.data) == 0


@pytest.mark.unit
def test_format_name(visualizer: FormulaicVisualizer) -> None:
    """Test string truncation and fallback for formula names."""
    assert visualizer._format_name("Short Name") == "Short Name"
    assert (
        visualizer._format_name("This is a very long name that exceeds thirty characters")
        == "This is a very long name th..."
    )
    assert visualizer._format_name(None) == "N/A"
    assert visualizer._format_name("") == "N/A"


@pytest.mark.unit
def test_format_r_squared(visualizer: FormulaicVisualizer) -> None:
    """Test decimal formatting and safe fallbacks for R-squared values."""
    assert visualizer._format_r_squared(0.98765) == "0.9877"
    assert visualizer._format_r_squared(1) == "1.0000"
    assert visualizer._format_r_squared(0) == "0.0000"
    assert visualizer._format_r_squared(None) == "N/A"
    assert visualizer._format_r_squared("invalid") == "N/A"


@pytest.mark.unit
def test_get_sorted_formulas(visualizer: FormulaicVisualizer) -> None:
    """Test formula sorting handles missing r_squared attributes safely."""
    f1 = Mock(r_squared=0.5)
    f2 = Mock(r_squared=0.9)
    f3 = Mock(r_squared=0.1)
    f_missing = Mock(spec=[])  # Completely missing r_squared attribute

    formulas = [f1, f2, f_missing, f3]
    sorted_f = visualizer._get_sorted_formulas(formulas)

    assert sorted_f == [f2, f1, f3, f_missing]


@pytest.mark.unit
def test_parse_correlation_item(visualizer: FormulaicVisualizer) -> None:
    """Test parsing of correlation items from various data structures."""
    # Dictionary format
    assert visualizer._parse_correlation_item({"asset1": "A", "asset2": "B", "correlation": 0.8}) == ("A", "B", 0.8)
    assert visualizer._parse_correlation_item({"asset1": "A"}) == ("A", "", 0.0)

    # List/Tuple format
    assert visualizer._parse_correlation_item(["A", "B", 0.8]) == ("A", "B", 0.8)
    assert visualizer._parse_correlation_item(("A", "B")) == ("A", "B", 0.0)

    # Invalid format
    assert visualizer._parse_correlation_item("invalid string format") == ("", "", 0.0)
    assert visualizer._parse_correlation_item(None) == ("", "", 0.0)
