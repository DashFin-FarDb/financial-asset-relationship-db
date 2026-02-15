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

    assert "**A** → **B** (correlation, strength 0.90)" in md
    assert "**X** → **Y** (hedge, strength 0.70)" in md


def test_schema_report_quality_score() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

    assert "### Data Quality Score: 82.0%" in md


def test_schema_report_recommendation_logic() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

    # density = 12.5 -> mid range → "Well-balanced"
    assert "Well-balanced" in md
