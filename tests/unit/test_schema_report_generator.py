"""Unit tests for SchemaReportGenerator.

Covers the network_density-based changes in _render_calculated_metrics
and _render_schema_optimization added in the density semantics normalisation PR.
"""

from __future__ import annotations

# pylint: disable=protected-access,no-self-use,import-error,no-name-in-module
import pytest

from src.reports.schema_report_generator import SchemaReportGenerator


@pytest.fixture
def generator(populated_graph):
    """Return a SchemaReportGenerator wrapping the populated test graph."""
    return SchemaReportGenerator(populated_graph)


@pytest.mark.unit
class TestRenderCalculatedMetrics:
    """Tests for SchemaReportGenerator._render_calculated_metrics."""

    def test_reads_network_density_key(self, generator):
        """_render_calculated_metrics must read 'network_density', not 'relationship_density'."""
        metrics = {
            "network_density": 0.25,
            "total_assets": 4,
            "total_relationships": 3,
            "average_relationship_strength": 0.5,
            "regulatory_event_count": 1,
        }
        lines = generator._render_calculated_metrics(metrics)
        combined = "\n".join(lines)
        assert "Relationship Density" in combined
        assert "25.00%" in combined

    def test_density_formatted_as_percentage(self, generator):
        """Density value 0.123 should render as '12.30%'."""
        metrics = {
            "network_density": 0.123,
            "total_assets": 2,
            "total_relationships": 1,
            "average_relationship_strength": 0.8,
            "regulatory_event_count": 0,
        }
        lines = generator._render_calculated_metrics(metrics)
        combined = "\n".join(lines)
        assert "12.30%" in combined

    def test_zero_density(self, generator):
        """Zero network_density should render as '0.00%'."""
        metrics = {
            "network_density": 0.0,
            "total_assets": 5,
            "total_relationships": 0,
            "average_relationship_strength": 0.0,
            "regulatory_event_count": 0,
        }
        lines = generator._render_calculated_metrics(metrics)
        combined = "\n".join(lines)
        assert "0.00%" in combined

    def test_full_density(self, generator):
        """network_density of 1.0 should render as '100.00%'."""
        metrics = {
            "network_density": 1.0,
            "total_assets": 3,
            "total_relationships": 6,
            "average_relationship_strength": 1.0,
            "regulatory_event_count": 0,
        }
        lines = generator._render_calculated_metrics(metrics)
        combined = "\n".join(lines)
        assert "100.00%" in combined

    def test_returns_list_of_strings(self, generator):
        """Output must be a list of strings."""
        metrics = {"network_density": 0.1}
        result = generator._render_calculated_metrics(metrics)
        assert isinstance(result, list)
        assert all(isinstance(line, str) for line in result)


@pytest.mark.unit
class TestRenderSchemaOptimization:
    """Tests for SchemaReportGenerator._render_schema_optimization."""

    def test_sparse_recommendation(self, generator):
        """density_pct <= 10.0 should produce a 'Sparse' recommendation."""
        metrics = {"network_density": 0.05, "quality_score": 0.8}
        lines = generator._render_schema_optimization(metrics)
        combined = "\n".join(lines)
        assert "Sparse" in combined

    def test_well_balanced_recommendation(self, generator):
        """density_pct in (10.0, 30.0] should produce a 'Well-balanced' recommendation."""
        metrics = {"network_density": 0.20, "quality_score": 0.9}
        lines = generator._render_schema_optimization(metrics)
        combined = "\n".join(lines)
        assert "Well-balanced" in combined

    def test_high_connectivity_recommendation(self, generator):
        """density_pct > 30.0 should produce a 'High connectivity' recommendation."""
        metrics = {"network_density": 0.50, "quality_score": 0.7}
        lines = generator._render_schema_optimization(metrics)
        combined = "\n".join(lines)
        assert "High connectivity" in combined

    def test_reads_network_density_not_relationship_density(self, generator):
        """_render_schema_optimization must use 'network_density', not 'relationship_density'."""
        # Provide network_density but deliberately omit relationship_density.
        metrics = {"network_density": 0.40, "quality_score": 0.85}
        lines = generator._render_schema_optimization(metrics)
        combined = "\n".join(lines)
        # density_pct = 40.0 > 30.0 → "High connectivity"
        assert "High connectivity" in combined

    def test_returns_list_of_strings(self, generator):
        """Output must be a list of strings."""
        metrics = {"network_density": 0.1, "quality_score": 0.5}
        result = generator._render_schema_optimization(metrics)
        assert isinstance(result, list)
        assert all(isinstance(line, str) for line in result)
