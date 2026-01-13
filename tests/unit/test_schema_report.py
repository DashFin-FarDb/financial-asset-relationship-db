"""Unit tests for schema report generation.

This module contains comprehensive unit tests for schema report generation including:
- Report structure and formatting
- Metrics inclusion and accuracy
- Business rules documentation
- Markdown formatting
- Edge cases and empty graphs
"""

from src.reports.schema_report import generate_schema_report


class TestSchemaReportGeneration:
    """Test cases for schema report generation."""

    @staticmethod
    def test_generate_report_returns_string(populated_graph):
        """Test that generate_schema_report returns a string."""
        report = generate_schema_report(populated_graph)
        assert isinstance(report, str)
        assert len(report) > 0

    @staticmethod
    def test_report_contains_title(populated_graph):
        """Test that report contains main title."""
        report = generate_schema_report(populated_graph)
        assert "# Financial Asset Relationship Database Schema & Rules" in report

    @staticmethod
    def test_report_contains_schema_overview(populated_graph):
        """Test that report contains schema overview section."""
        report = generate_schema_report(populated_graph)
        assert "## Schema Overview" in report
        assert "### Entity Types" in report

    @staticmethod
    def test_report_lists_entity_types(populated_graph):
        """Test that report lists all entity types."""
        report = generate_schema_report(populated_graph)
        assert "**Equity**" in report
        assert "**Bond**" in report
        assert "**Commodity**" in report
        assert "**Currency**" in report

    @staticmethod
    def test_report_contains_relationship_types(populated_graph):
        """Test that report contains relationship types section."""
        report = generate_schema_report(populated_graph)
        assert "### Relationship Types" in report

    @staticmethod
    def test_report_contains_calculated_metrics(populated_graph):
        """Test that report contains calculated metrics section."""
        report = generate_schema_report(populated_graph)
        assert "## Calculated Metrics" in report
        assert "### Network Statistics" in report

    @staticmethod
    def test_report_includes_total_assets(populated_graph):
        """Test that report includes total assets metric."""
        report = generate_schema_report(populated_graph)
        assert "**Total Assets**:" in report
        # Should show the actual count
        assert "4" in report  # populated_graph has 4 assets

    @staticmethod
    def test_report_includes_relationship_metrics(populated_graph):
        """Test that report includes relationship metrics."""
        report = generate_schema_report(populated_graph)
        assert "**Total Relationships**:" in report
        assert "**Average Relationship Strength**:" in report
        assert "**Relationship Density**:" in report

    @staticmethod
    def test_report_includes_asset_class_distribution(populated_graph):
        """Test that report includes asset class distribution."""
        report = generate_schema_report(populated_graph)
        assert "### Asset Class Distribution" in report

    @staticmethod
    def test_report_includes_business_rules(populated_graph):
        """Test that report includes business rules section."""
        report = generate_schema_report(populated_graph)
        assert "## Business Rules & Constraints" in report
        assert "### Cross-Asset Rules" in report

    @staticmethod
    def test_report_includes_regulatory_rules(populated_graph):
        """Test that report includes regulatory rules."""
        report = generate_schema_report(populated_graph)
        assert "### Regulatory Rules" in report

    @staticmethod
    def test_report_includes_valuation_rules(populated_graph):
        """Test that report includes valuation rules."""
        report = generate_schema_report(populated_graph)
        assert "### Valuation Rules" in report

    @staticmethod
    def test_report_includes_optimization_metrics(populated_graph):
        """Test that report includes schema optimization metrics."""
        report = generate_schema_report(populated_graph)
        assert "## Schema Optimization Metrics" in report
        assert "### Data Quality Score:" in report

    @staticmethod
    def test_report_includes_recommendations(populated_graph):
        """Test that report includes recommendations."""
        report = generate_schema_report(populated_graph)
        assert "### Recommendation:" in report

    @staticmethod
    def test_report_includes_implementation_notes(populated_graph):
        """Test that report includes implementation notes."""
        report = generate_schema_report(populated_graph)
        assert "## Implementation Notes" in report


class TestReportMetrics:
    """Test cases for metrics included in report."""

    @staticmethod
    def test_report_shows_correct_asset_count(populated_graph):
        """Test that report shows correct asset count."""
        report = generate_schema_report(populated_graph)
        metrics = populated_graph.calculate_metrics()
        assert str(metrics["total_assets"]) in report

    @staticmethod
    def test_report_formats_average_strength(populated_graph):
        """Test that average strength is formatted correctly."""
        report = generate_schema_report(populated_graph)
        # Should have 3 decimal places
        import re

        pattern = r"Average Relationship Strength\*\*: \d+\.\d{3}"
        assert re.search(pattern, report)

    @staticmethod
    def test_report_formats_relationship_density(populated_graph):
        """Test that relationship density is formatted as percentage."""
        report = generate_schema_report(populated_graph)
        # Should have 2 decimal places and %
        import re

        pattern = r"Relationship Density\*\*: \d+\.\d{2}%"
        assert re.search(pattern, report)

    @staticmethod
    def test_report_includes_regulatory_event_count(populated_graph):
        """Test that report includes regulatory event count."""
        report = generate_schema_report(populated_graph)
        assert "**Regulatory Events**:" in report

    @staticmethod
    def test_report_shows_relationship_distribution(populated_graph):
        """Test that report shows relationship type distribution."""
        # Add a relationship first
        populated_graph.add_relationship("TEST_AAPL", "TEST_BOND", "test_rel", 0.5)
        report = generate_schema_report(populated_graph)
        # Should list relationship types
        metrics = populated_graph.calculate_metrics()
        if metrics["relationship_distribution"]:
            for rel_type in metrics["relationship_distribution"].keys():
                # Type should appear somewhere in report
                assert rel_type in report or rel_type.replace("_", " ") in report

    @staticmethod
    def test_report_shows_top_relationships(populated_graph):
        """Test that report shows top relationships."""
        populated_graph.add_relationship("TEST_AAPL", "TEST_BOND", "strong_rel", 0.9)
        report = generate_schema_report(populated_graph)
        assert "## Top Relationships" in report


class TestReportFormatting:
    """Test cases for report formatting."""

    @staticmethod
    def test_report_uses_markdown_headers(populated_graph):
        """Test that report uses proper markdown headers."""
        report = generate_schema_report(populated_graph)
        assert report.count("## ") >= 3  # At least 3 level-2 headers
        assert report.count("### ") >= 3  # At least 3 level-3 headers

    @staticmethod
    def test_report_uses_bold_formatting(populated_graph):
        """Test that report uses bold formatting for labels."""
        report = generate_schema_report(populated_graph)
        assert "**" in report
        assert report.count("**") >= 10  # Multiple bold items

    @staticmethod
    def test_report_uses_lists(populated_graph):
        """Test that report uses markdown lists."""
        report = generate_schema_report(populated_graph)
        assert "\n- " in report  # Unordered list items

    @staticmethod
    def test_report_has_proper_line_breaks(populated_graph):
        """Test that report has proper line breaks between sections."""
        report = generate_schema_report(populated_graph)
        assert "\n\n" in report  # Section separators

    @staticmethod
    def test_report_formats_percentages(populated_graph):
        """Test that percentages are formatted correctly."""
        report = generate_schema_report(populated_graph)
        # Check for percentage symbols
        assert "%" in report


class TestDataQualityScore:
    """Test cases for data quality score calculation."""

    @staticmethod
    def test_quality_score_included_in_report(populated_graph):
        """Test that quality score is included in report."""
        report = generate_schema_report(populated_graph)
        assert "### Data Quality Score:" in report

    @staticmethod
    def test_quality_score_is_percentage(populated_graph):
        """Test that quality score is formatted as percentage."""
        report = generate_schema_report(populated_graph)
        import re

        # Look for quality score pattern
        pattern = r"Data Quality Score: \d+\.\d%"
        assert re.search(pattern, report)

    @staticmethod
    def test_quality_score_calculation_with_events(populated_graph, sample_regulatory_event):
        """Test quality score calculation with regulatory events."""
        populated_graph.add_regulatory_event(sample_regulatory_event)
        report = generate_schema_report(populated_graph)
        assert "Data Quality Score:" in report


class TestRecommendations:
    """Test cases for recommendations in report."""

    @staticmethod
    def test_high_density_recommendation(populated_graph):
        """Test recommendation for high connectivity graphs."""
        # Create high density graph
        assets = list(populated_graph.assets.keys())
        for i, source in enumerate(assets):
            for target in assets[i + 1 :]:
                populated_graph.add_relationship(source, target, "high_density", 0.8)

        report = generate_schema_report(populated_graph)
        metrics = populated_graph.calculate_metrics()

        if metrics["relationship_density"] > 30:
            assert "High connectivity" in report or "normalization" in report

    @staticmethod
    def test_balanced_recommendation(populated_graph):
        """Test recommendation for well-balanced graphs."""
        # Add moderate relationships
        populated_graph.add_relationship("TEST_AAPL", "TEST_BOND", "rel1", 0.5)

        report = generate_schema_report(populated_graph)
        metrics = populated_graph.calculate_metrics()

        if 10 < metrics["relationship_density"] <= 30:
            assert "Well-balanced" in report or "optimal" in report

    @staticmethod
    def test_sparse_recommendation(empty_graph, sample_equity):
        """Test recommendation for sparse graphs."""
        empty_graph.add_asset(sample_equity)
        report = generate_schema_report(empty_graph)

        metrics = empty_graph.calculate_metrics()
        if metrics["relationship_density"] <= 10:
            assert "Sparse" in report or "adding more relationships" in report


class TestBusinessRules:
    """Test cases for business rules documentation."""

    @staticmethod
    def test_corporate_bond_rule_documented(populated_graph):
        """Test that corporate bond rule is documented."""
        report = generate_schema_report(populated_graph)
        assert "Corporate Bond Linkage" in report or "corporate bond" in report.lower()

    @staticmethod
    def test_sector_affinity_rule_documented(populated_graph):
        """Test that sector affinity rule is documented."""
        report = generate_schema_report(populated_graph)
        assert "Sector Affinity" in report or "same sector" in report.lower()

    @staticmethod
    def test_currency_exposure_rule_documented(populated_graph):
        """Test that currency exposure rule is documented."""
        report = generate_schema_report(populated_graph)
        assert "Currency Exposure" in report or "currency" in report.lower()

    @staticmethod
    def test_event_propagation_rule_documented(populated_graph):
        """Test that event propagation rule is documented."""
        report = generate_schema_report(populated_graph)
        assert "Event Propagation" in report or "earnings events" in report.lower()

    @staticmethod
    def test_impact_scoring_rule_documented(populated_graph):
        """Test that impact scoring rule is documented."""
        report = generate_schema_report(populated_graph)
        assert "Impact Scoring" in report or "impact score" in report.lower()


class TestImplementationNotes:
    """Test cases for implementation notes."""

    @staticmethod
    def test_timestamp_format_noted(populated_graph):
        """Test that timestamp format is documented."""
        report = generate_schema_report(populated_graph)
        assert "ISO 8601" in report

    @staticmethod
    def test_strength_normalization_noted(populated_graph):
        """Test that strength normalization is documented."""
        report = generate_schema_report(populated_graph)
        assert "0-1 range" in report or "normalized" in report.lower()

    @staticmethod
    def test_impact_score_scale_noted(populated_graph):
        """Test that impact score scale is documented."""
        report = generate_schema_report(populated_graph)
        assert "-1 to +1" in report or "-1 to 1" in report

    @staticmethod
    def test_directionality_noted(populated_graph):
        """Test that relationship directionality is documented."""
        report = generate_schema_report(populated_graph)
        assert "bidirectional" in report.lower()


class TestEdgeCases:
    """Test edge cases in report generation."""

    @staticmethod
    def test_report_with_empty_graph(empty_graph):
        """Test report generation with empty graph."""
        report = generate_schema_report(empty_graph)
        assert isinstance(report, str)
        assert len(report) > 0
        assert "**Total Assets**: 0" in report

    @staticmethod
    def test_report_with_no_relationships(empty_graph, sample_equity):
        """Test report with assets but no relationships."""
        empty_graph.add_asset(sample_equity)
        report = generate_schema_report(empty_graph)
        assert "**Total Relationships**: 0" in report

    @staticmethod
    def test_report_with_single_asset(empty_graph, sample_equity):
        """Test report with single asset."""
        empty_graph.add_asset(sample_equity)
        report = generate_schema_report(empty_graph)
        assert "**Total Assets**: 1" in report

    @staticmethod
    def test_report_with_no_regulatory_events(populated_graph):
        """Test report with no regulatory events."""
        empty_graph.add_asset(sample_equity)
        report = generate_schema_report(empty_graph)
        assert "**Regulatory Events**: 0" in report

    @staticmethod
    def test_report_with_zero_average_strength(populated_graph):
        """Test report when average strength is zero."""
        populated_graph.add_relationship("TEST_AAPL", "TEST_BOND", "zero_rel", 0.0)
        report = generate_schema_report(populated_graph)
        # Should handle zero strength gracefully
        assert "Average Relationship Strength" in report

    @staticmethod
    def test_report_with_max_density(empty_graph, sample_equity, sample_bond):
        """Test report with maximum density."""
        empty_graph.add_asset(sample_equity)
        empty_graph.add_asset(sample_bond)
        # Create all possible relationships
        empty_graph.add_relationship(sample_equity.id, sample_bond.id, "rel1", 1.0)
        empty_graph.add_relationship(sample_bond.id, sample_equity.id, "rel2", 1.0)

        report = generate_schema_report(empty_graph)
        assert "Relationship Density" in report


class TestReportConsistency:
    """Test cases for report consistency."""

    @staticmethod
    def test_metrics_match_graph_state(populated_graph):
        """Test that reported metrics match actual graph state."""
        report = generate_schema_report(populated_graph)
        metrics = populated_graph.calculate_metrics()

        # Check that total assets matches
        assert str(metrics["total_assets"]) in report

        # Check that relationship count matches
        assert str(metrics["total_relationships"]) in report

    @staticmethod
    def test_asset_class_counts_match(populated_graph):
        """Test that asset class counts in report match actual counts."""
        report = generate_schema_report(populated_graph)
        metrics = populated_graph.calculate_metrics()

        for _asset_class, count in metrics["asset_class_distribution"].items():
            # Count should appear somewhere near the asset class name
            assert str(count) in report

    @staticmethod
    def test_quality_score_is_valid(populated_graph):
        """Test that quality score is within valid range."""
        report = generate_schema_report(populated_graph)

        # Extract quality score from report
        import re

        match = re.search(r"Data Quality Score: (\d+\.\d)%", report)
        if match:
            score_str = match.group(1)
            score = float(score_str)
            assert 0 <= score <= 100


class TestMultipleGenerations:
    """Test cases for multiple report generations."""

    @staticmethod
    def test_consistent_output_for_same_graph(populated_graph):
        """Test that multiple generations produce consistent output."""
        report1 = generate_schema_report(populated_graph)
        report2 = generate_schema_report(populated_graph)

        assert report1 == report2

    @staticmethod
    def test_different_output_for_modified_graph(populated_graph):
        """Test that output changes when graph is modified."""
        report1 = generate_schema_report(populated_graph)

        # Modify graph
        populated_graph.add_relationship("TEST_AAPL", "TEST_BOND", "new_rel", 0.8)

        report2 = generate_schema_report(populated_graph)

        # Reports should be different
        assert report1 != report2
