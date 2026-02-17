from __future__ import annotations

from typing import Any, Dict

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

    def calculate_metrics(self) -> Dict[str, Any]:
        return {
            "relationship_distribution": {
                "correlation": 4,
                "hedge": 2,
            },
            "total_assets": 3,
            "total_relationships": 6,
            "average_relationship_strength": 0.42,
            "relationship_density": 12.5,
            "regulatory_event_count": 1,
            "asset_class_distribution": {"Equity": 1, "Bond": 2},
            "top_relationships": [
                ("A", "B", "correlation", 0.9),
                ("X", "Y", "hedge", "0.7"),
            ],
            "quality_score": 0.82,
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_schema_report_contains_sections() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

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


def test_schema_report_relationship_distribution() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

    assert "- **correlation**: 4 instances" in md
    assert "- **hedge**: 2 instances" in md


def test_schema_report_top_relationships() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

    # Use simple arrow instead of Unicode arrow
    assert "**A** -> **B** (correlation, strength 0.90)" in md
    assert "**X** -> **Y** (hedge, strength 0.70)" in md


def test_schema_report_quality_score() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

    assert "### Data Quality Score: 82.0%" in md


def test_schema_report_recommendation_logic() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

    # density = 12.5 -> mid range → "Well-balanced"
    assert "Well-balanced" in md


# ---------------------------------------------------------------------------
# Additional edge case tests
# ---------------------------------------------------------------------------


class EmptyGraph:
    """Mock graph with no assets or relationships."""

    def calculate_metrics(self):
        return {
            "relationship_distribution": {},
            "total_assets": 0,
            "total_relationships": 0,
            "average_relationship_strength": 0.0,
            "relationship_density": 0.0,
            "regulatory_event_count": 0,
            "asset_class_distribution": {},
            "top_relationships": [],
            "quality_score": 0.0,
        }


def test_schema_report_with_empty_graph() -> None:
    """Test schema report generation with empty graph."""
    graph = EmptyGraph()
    md = generate_schema_report(graph)

    assert "# Financial Asset Relationship Database Schema & Rules" in md
    assert "**Total Assets**: 0" in md
    assert "**Total Relationships**: 0" in md
    assert "No relationships recorded yet" in md


class HighDensityGraph:
    """Mock graph with high relationship density."""

    def calculate_metrics(self):
        return {
            "relationship_distribution": {"correlation": 50},
            "total_assets": 10,
            "total_relationships": 45,
            "average_relationship_strength": 0.85,
            "relationship_density": 45.0,  # > 30%
            "regulatory_event_count": 5,
            "asset_class_distribution": {"Equity": 10},
            "top_relationships": [],
            "quality_score": 0.95,
        }


def test_schema_report_high_density_recommendation() -> None:
    """Test schema report recommendation for high density graphs."""
    graph = HighDensityGraph()
    md = generate_schema_report(graph)

    assert "High connectivity - consider normalization" in md


class SparseDensityGraph:
    """Mock graph with sparse relationship density."""

    def calculate_metrics(self):
        return {
            "relationship_distribution": {"correlation": 2},
            "total_assets": 20,
            "total_relationships": 2,
            "average_relationship_strength": 0.3,
            "relationship_density": 5.0,  # < 10%
            "regulatory_event_count": 0,
            "asset_class_distribution": {"Equity": 20},
            "top_relationships": [],
            "quality_score": 0.4,
        }


def test_schema_report_sparse_density_recommendation() -> None:
    """Test schema report recommendation for sparse density graphs."""
    graph = SparseDensityGraph()
    md = generate_schema_report(graph)

    assert "Sparse connections - consider adding more relationships" in md