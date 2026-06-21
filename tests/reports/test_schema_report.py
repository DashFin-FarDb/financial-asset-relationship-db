"""Unit tests for the schema report generator."""

from __future__ import annotations

from typing import Any

import pytest

from src.reports.schema_report import generate_schema_report

# ---------------------------------------------------------------------------
# Mock graph object
# ---------------------------------------------------------------------------


class MockGraph:
    """
    Lightweight mock of AssetRelationshipGraph for testing.

    Only implements calculate_metrics(), returning a controlled,
    deterministic metrics dictionary for predictable output.
    """

    def calculate_metrics(self) -> dict[str, Any]:
        """
        Provide deterministic mock metrics for testing schema report generation.

        Returns:
            dict: Fixed schema metrics including:
                - relationship_distribution: mapping of relationship type to instance count (e.g., {"correlation": 4, "hedge": 2})
                - total_assets: total number of assets
                - total_relationships: total number of relationships
                - average_relationship_strength: average strength value across relationships
                - network_density: network_density metric used for recommendations
                - regulatory_event_count: count of regulatory events
                - asset_class_distribution: mapping of asset class to count
                - top_relationships: list of tuples (source, target, type, strength) for top relationships
                - quality_score: overall data quality score (0.0–1.0)
        """
        return {
            "relationship_distribution": {
                "correlation": 4,
                "hedge": 2,
            },
            "total_assets": 3,
            "total_relationships": 6,
            "average_relationship_strength": 0.42,
            "network_density": 0.125,
            "regulatory_event_count": 1,
            "asset_class_distribution": {"Equity": 1, "Bond": 2},
            "top_relationships": [
                ("A", "B", "correlation", 0.9),
                ("X", "Y", "hedge", 0.7),
            ],
            "quality_score": 0.82,
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_schema_report_contains_sections() -> None:
    """Test that all expected sections are in the markdown output."""
    graph = MockGraph()
    md = generate_schema_report(graph)  # type: ignore[arg-type]

    # Basic section anchors must exist
    required_sections = [
        "# Financial Asset Relationship Database Schema & Rules",
        "## Schema Overview",
        "### Relationship Types",
        "## Calculated Metrics",
        "### Asset Class Distribution",
        "## Top Relationships",
        "## Business Rules & Constraints",
        "## Schema Optimization Metrics",
        "## Implementation Notes",
    ]

    for section in required_sections:
        assert section in md


@pytest.mark.unit
def test_schema_report_relationship_distribution() -> None:
    """Test that the relationship distribution is present."""
    graph = MockGraph()
    md = generate_schema_report(graph)  # type: ignore[arg-type]

    assert "- **correlation**: 4 instances" in md
    assert "- **hedge**: 2 instances" in md


@pytest.mark.unit
def test_schema_report_top_relationships() -> None:
    """Test that top relationships are formatted correctly."""
    graph = MockGraph()
    md = generate_schema_report(graph)  # type: ignore[arg-type]

    assert "**A** → **B** (correlation, strength 0.90)" in md
    assert "**X** → **Y** (hedge, strength 0.70)" in md


@pytest.mark.unit
def test_schema_report_quality_score() -> None:
    """Test that the data quality score is included."""
    graph = MockGraph()
    md = generate_schema_report(graph)  # type: ignore[arg-type]

    assert "### Data Quality Score: 82.0%" in md


@pytest.mark.unit
def test_schema_report_recommendation_logic() -> None:
    """Test that optimization recommendations are correctly calculated and included."""
    graph = MockGraph()
    md = generate_schema_report(graph)  # type: ignore[arg-type]

    # network_density = 12.5 -> mid range → "Well-balanced"
    assert "Well-balanced" in md
