"""Unit tests for metric visualizations.

This module contains comprehensive unit tests for the metric_visuals module including:
- Visualization generation from graph metrics
- Asset class distribution charts
- Relationship type distribution charts
- Regulatory events timeline visualization
- Edge cases and error handling
"""

from datetime import datetime
from unittest.mock import MagicMock

import plotly.graph_objects as go
import pytest

from src.visualizations.metric_visuals import visualize_metrics


@pytest.mark.unit
class TestVisualizeMetrics:
    """Test suite for the visualize_metrics function."""

    def test_visualize_metrics_with_populated_graph(self, populated_graph):
        """Test metric visualization with a populated graph."""
        # Execute
        fig1, fig2, fig3 = visualize_metrics(populated_graph)

        # Assert all figures are created
        assert isinstance(fig1, go.Figure), "First figure should be a plotly Figure"
        assert isinstance(fig2, go.Figure), "Second figure should be a plotly Figure"
        assert isinstance(fig3, go.Figure), "Third figure should be a plotly Figure"

        # Verify figure 1 (Asset Class Distribution)
        assert fig1.layout.title.text == "Asset Class Distribution"
        assert fig1.layout.xaxis.title.text == "Asset Class"
        assert fig1.layout.yaxis.title.text == "Count"
        assert len(fig1.data) > 0, "Figure should have at least one trace"
        assert fig1.data[0].type == "bar", "Should be a bar chart"

        # Verify figure 2 (Relationship Distribution)
        assert fig2.layout.title.text == "Relationship Types Distribution"
        assert fig2.layout.xaxis.title.text == "Relationship Type"
        assert fig2.layout.yaxis.title.text == "Count"
        assert fig2.layout.xaxis.tickangle == -45
        assert len(fig2.data) > 0, "Figure should have at least one trace"

        # Verify figure 3 (Regulatory Events)
        assert fig3.layout.title.text == "Regulatory Events Timeline"
        assert fig3.layout.xaxis.title.text == "Date"
        assert fig3.layout.yaxis.title.text == "Impact Score"

    def test_visualize_metrics_with_empty_graph(self, empty_graph):
        """Test metric visualization with an empty graph."""
        # Execute
        fig1, fig2, fig3 = visualize_metrics(empty_graph)

        # Assert figures are created even with empty data
        assert isinstance(fig1, go.Figure)
        assert isinstance(fig2, go.Figure)
        assert isinstance(fig3, go.Figure)

        # Verify figures have basic structure
        assert fig1.layout.title.text == "Asset Class Distribution"
        assert fig2.layout.title.text == "Relationship Types Distribution"
        assert fig3.layout.title.text == "Regulatory Events Timeline"

    def test_asset_class_distribution_colors(self, populated_graph):
        """Test that asset class distribution uses consistent colors."""
        # Execute
        fig1, _, _ = visualize_metrics(populated_graph)

        # Verify colors are applied
        bar_trace = fig1.data[0]
        assert hasattr(bar_trace, "marker"), "Bar trace should have marker"
        assert hasattr(bar_trace.marker, "color"), "Marker should have color"

        # Check color consistency with base colors
        base_colors = ["blue", "green", "orange", "red", "purple"]
        colors = bar_trace.marker.color
        if isinstance(colors, list):
            for color in colors:
                assert color in base_colors, f"Color {color} should be from base colors"

    def test_relationship_distribution_data(self, populated_graph):
        """Test that relationship distribution contains correct data."""
        # Add some relationships
        populated_graph.add_relationship("TEST_AAPL", "TEST_BOND", "corporate_bond_to_equity", 0.8)
        populated_graph.add_relationship("TEST_GOLD", "TEST_EUR", "commodity_currency", 0.6)

        # Execute
        _, fig2, _ = visualize_metrics(populated_graph)

        # Verify data
        bar_trace = fig2.data[0]
        assert len(bar_trace.x) > 0, "Should have relationship types"
        assert len(bar_trace.y) > 0, "Should have counts"
        assert all(count >= 0 for count in bar_trace.y), "Counts should be non-negative"

    def test_regulatory_events_timeline_sorting(self, populated_graph):
        """Test that regulatory events are sorted by date."""
        from src.models.financial_models import RegulatoryActivity, RegulatoryEvent

        # Add multiple events with different dates
        event1 = RegulatoryEvent(
            id="EVENT_001",
            asset_id="TEST_AAPL",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-15",
            description="Q4 2023 Earnings",
            impact_score=0.8,
            related_assets=[],
        )
        event2 = RegulatoryEvent(
            id="EVENT_002",
            asset_id="TEST_BOND",
            event_type=RegulatoryActivity.REGULATORY_FILING,
            date="2024-02-20",
            description="Annual Filing",
            impact_score=-0.3,
            related_assets=[],
        )
        event3 = RegulatoryEvent(
            id="EVENT_003",
            asset_id="TEST_GOLD",
            event_type=RegulatoryActivity.COMPLIANCE_UPDATE,
            date="2024-01-10",
            description="Compliance Update",
            impact_score=0.5,
            related_assets=[],
        )

        populated_graph.add_regulatory_event(event1)
        populated_graph.add_regulatory_event(event2)
        populated_graph.add_regulatory_event(event3)

        # Execute
        _, _, fig3 = visualize_metrics(populated_graph)

        # Verify events are sorted by date
        bar_trace = fig3.data[0]
        dates = bar_trace.x

        # Convert to datetime for comparison
        datetime_dates = [datetime.fromisoformat(d) if isinstance(d, str) else d for d in dates]
        sorted_dates = sorted(datetime_dates)

        assert datetime_dates == sorted_dates, "Events should be sorted by date"

    def test_regulatory_events_impact_colors(self, populated_graph):
        """Test that regulatory events use correct colors based on impact."""
        from src.models.financial_models import RegulatoryActivity, RegulatoryEvent

        # Add events with positive and negative impacts
        positive_event = RegulatoryEvent(
            id="POS_EVENT",
            asset_id="TEST_AAPL",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-15",
            description="Positive Event",
            impact_score=0.8,
            related_assets=[],
        )
        negative_event = RegulatoryEvent(
            id="NEG_EVENT",
            asset_id="TEST_BOND",
            event_type=RegulatoryActivity.LEGAL_PROCEEDING,
            date="2024-01-20",
            description="Negative Event",
            impact_score=-0.5,
            related_assets=[],
        )

        populated_graph.add_regulatory_event(positive_event)
        populated_graph.add_regulatory_event(negative_event)

        # Execute
        _, _, fig3 = visualize_metrics(populated_graph)

        # Verify colors
        bar_trace = fig3.data[0]
        colors = bar_trace.marker.color

        assert isinstance(colors, list), "Colors should be a list"
        assert "green" in colors, "Should have green for positive impact"
        assert "red" in colors, "Should have red for negative impact"

    def test_visualize_metrics_with_single_asset(self, empty_graph, sample_equity):
        """Test visualization with only one asset."""
        empty_graph.add_asset(sample_equity)

        # Execute
        fig1, fig2, fig3 = visualize_metrics(empty_graph)

        # Verify figures are created
        assert isinstance(fig1, go.Figure)
        assert isinstance(fig2, go.Figure)
        assert isinstance(fig3, go.Figure)

        # Verify asset class chart has one bar
        assert len(fig1.data) > 0
        bar_trace = fig1.data[0]
        assert len(bar_trace.x) >= 1, "Should have at least one asset class"

    def test_visualize_metrics_preserves_graph_state(self, populated_graph):
        """Test that visualization doesn't modify the graph."""
        initial_asset_count = len(populated_graph.assets)
        initial_relationship_count = sum(len(rels) for rels in populated_graph.relationships.values())

        # Execute
        visualize_metrics(populated_graph)

        # Verify graph state unchanged
        assert len(populated_graph.assets) == initial_asset_count
        assert sum(len(rels) for rels in populated_graph.relationships.values()) == initial_relationship_count

    def test_multiple_asset_classes_distribution(self, populated_graph):
        """Test asset class distribution with multiple classes."""
        # The populated_graph already has multiple asset classes

        # Execute
        fig1, _, _ = visualize_metrics(populated_graph)

        # Verify multiple classes are represented
        bar_trace = fig1.data[0]
        num_classes = len(bar_trace.x)

        assert num_classes >= 2, "Should have at least 2 asset classes in populated graph"
        assert len(bar_trace.y) == num_classes, "Should have count for each class"

    def test_regulatory_events_with_zero_impact(self, empty_graph, sample_equity):
        """Test regulatory events with zero impact score."""
        from src.models.financial_models import RegulatoryActivity, RegulatoryEvent

        empty_graph.add_asset(sample_equity)

        zero_event = RegulatoryEvent(
            id="ZERO_EVENT",
            asset_id="TEST_AAPL",
            event_type=RegulatoryActivity.REGULATORY_FILING,
            date="2024-01-15",
            description="Neutral Event",
            impact_score=0.0,
            related_assets=[],
        )

        empty_graph.add_regulatory_event(zero_event)

        # Execute
        _, _, fig3 = visualize_metrics(empty_graph)

        # Verify zero impact is handled correctly
        bar_trace = fig3.data[0]
        assert len(bar_trace.y) > 0, "Should have impact scores"
        assert 0.0 in bar_trace.y or any(abs(score) < 0.01 for score in bar_trace.y), "Should include zero impact"

    def test_figure_return_types(self, empty_graph):
        """Test that all three figures are returned in correct order."""
        # Execute
        result = visualize_metrics(empty_graph)

        # Verify return type
        assert isinstance(result, tuple), "Should return a tuple"
        assert len(result) == 3, "Should return exactly 3 figures"

        fig1, fig2, fig3 = result

        # Verify each is a Figure object
        assert isinstance(fig1, go.Figure)
        assert isinstance(fig2, go.Figure)
        assert isinstance(fig3, go.Figure)

    def test_bar_chart_properties(self, populated_graph):
        """Test that bar charts have correct properties."""
        # Execute
        fig1, fig2, fig3 = visualize_metrics(populated_graph)

        # Verify bar chart properties for fig1
        assert fig1.data[0].type == "bar"
        assert hasattr(fig1.data[0], "x"), "Bar chart should have x data"
        assert hasattr(fig1.data[0], "y"), "Bar chart should have y data"

        # Verify bar chart properties for fig2
        assert fig2.data[0].type == "bar"
        assert fig2.data[0].marker.color == "lightblue"

        # Verify bar chart properties for fig3
        if len(fig3.data) > 0:
            assert fig3.data[0].type == "bar"
            assert hasattr(fig3.data[0], "name"), "Bar chart should have a name"

    def test_large_number_of_events(self, empty_graph, sample_equity):
        """Test handling of many regulatory events."""
        from src.models.financial_models import RegulatoryActivity, RegulatoryEvent

        empty_graph.add_asset(sample_equity)

        # Add many events
        for i in range(50):
            event = RegulatoryEvent(
                id=f"EVENT_{i:03d}",
                asset_id="TEST_AAPL",
                event_type=RegulatoryActivity.EARNINGS_REPORT,
                date=f"2024-01-{(i % 28) + 1:02d}",
                description=f"Event {i}",
                impact_score=(i % 10) / 10.0 - 0.5,
                related_assets=[],
            )
            empty_graph.add_regulatory_event(event)

        # Execute
        _, _, fig3 = visualize_metrics(empty_graph)

        # Verify all events are included
        bar_trace = fig3.data[0]
        assert len(bar_trace.x) == 50, "Should include all 50 events"
        assert len(bar_trace.y) == 50, "Should have 50 impact scores"
