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
        """
        Return a deterministic metrics dictionary used to mock an asset relationship graph for tests.

        The dictionary contains pre-defined values for schema-report generation and assertions:
        - relationship_distribution: mapping of relationship type to occurrence count.
        - total_assets: total number of assets (int).
        - total_relationships: total number of relationships (int).
        - average_relationship_strength: mean relationship strength (float).
        - relationship_density: density metric used for recommendation logic (float).
        - regulatory_event_count: number of regulatory events (int).
        - asset_class_distribution: mapping of asset class name to count.
        - top_relationships: list of tuples (source, target, relationship_type, strength).
        - quality_score: data quality score as a float between 0 and 1.

        Returns:
            Dict[str, Any]: The deterministic metrics dictionary described above.
        """
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
                ("X", "Y", "hedge", 0.7),
            ],
            "quality_score": 0.82,
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
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


@pytest.mark.unit
def test_schema_report_relationship_distribution() -> None:
    """
    Verify the generated schema report includes relationship distribution counts for `correlation` and `hedge`.

    Asserts that the markdown contains the exact lines "- **correlation**: 4 instances" and "- **hedge**: 2 instances".
    """
    graph = MockGraph()
    md = generate_schema_report(graph)

    assert "- **correlation**: 4 instances" in md
    assert "- **hedge**: 2 instances" in md


@pytest.mark.unit
def test_schema_report_top_relationships() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

    assert "**A** → **B** (correlation, strength 0.90)" in md
    assert "**X** → **Y** (hedge, strength 0.70)" in md


@pytest.mark.unit
def test_schema_report_quality_score() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

    assert "### Data Quality Score: 82.0%" in md


@pytest.mark.unit
def test_schema_report_recommendation_logic() -> None:
    graph = MockGraph()
    md = generate_schema_report(graph)

    # density = 12.5 -> mid range → "Well-balanced"
    assert "Well-balanced" in md
