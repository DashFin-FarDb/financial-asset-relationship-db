"""Behavioural tests for asset graph density and domain invariants."""

import pytest

from src.logic.asset_graph import AssetRelationshipGraph, calculate_graph_density
from src.models.financial_models import AssetClass, Equity

pytestmark = pytest.mark.unit


def _equity(asset_id: str, **overrides: object) -> Equity:
    """Build an equity asset with explicit, assertable fields."""
    values: dict[str, object] = {
        "id": asset_id,
        "symbol": asset_id,
        "name": f"{asset_id} Equity",
        "asset_class": AssetClass.EQUITY,
        "sector": "Technology",
        "price": 100.0,
        "currency": "USD",
    }
    values.update(overrides)
    return Equity(**values)


@pytest.mark.parametrize(
    ("asset_count", "relationship_count", "expected_density"),
    [
        (0, 0, 0.0),
        (1, 0, 0.0),
        # Directed two-node complete graph: A->B and B->A.
        (2, 2, 1.0),
        # Directed three-node complete graph: 3 * (3 - 1) = 6 edges.
        (3, 6, 1.0),
        # Partial four-node topology: 3 / (4 * 3) = 0.25.
        (4, 3, 0.25),
    ],
)
def test_calculate_graph_density_uses_directed_formula(
    asset_count: int,
    relationship_count: int,
    expected_density: float,
) -> None:
    """Pin the directed graph density formula exactly."""
    assert calculate_graph_density(asset_count, relationship_count) == pytest.approx(expected_density)


def test_calculate_graph_density_clamps_parallel_relationship_types() -> None:
    """Parallel relationship types can exceed the raw directed-edge denominator and must clamp to 1.0."""
    assert calculate_graph_density(asset_count=2, relationship_count=3) == pytest.approx(1.0)


def test_add_asset_duplicate_id_replaces_existing_asset() -> None:
    """Adding an asset with an existing ID intentionally replaces the previous asset object."""
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity("DUP", symbol="OLD", name="Old Name", sector="Technology", price=10.0, currency="USD"))
    graph.add_asset(_equity("DUP", symbol="NEW", name="New Name", sector="Healthcare", price=20.5, currency="gbp"))

    loaded = graph.assets["DUP"]
    assert loaded.symbol == "NEW"
    assert loaded.name == "New Name"
    assert loaded.sector == "Healthcare"
    assert loaded.price == pytest.approx(20.5)
    assert loaded.currency == "GBP"
    assert loaded.asset_class == AssetClass.EQUITY


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"same_sector_strength": -1.1}, "same_sector_strength"),
        ({"same_sector_strength": 1.1}, "same_sector_strength"),
        ({"corporate_bond_strength": -1.1}, "corporate_bond_strength"),
        ({"corporate_bond_strength": 1.1}, "corporate_bond_strength"),
    ],
)
def test_relationship_strength_guards_reject_values_outside_signed_unit_range(
    kwargs: dict[str, float],
    message: str,
) -> None:
    """Relationship-generation strengths are bounded to [-1.0, 1.0]."""
    with pytest.raises(ValueError, match=message):
        AssetRelationshipGraph(**kwargs)


def test_duplicate_relationships_are_deduped_by_target_and_type() -> None:
    """Duplicate detection is by `(target_id, rel_type)` and preserves the first stored strength."""
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity("SRC"))
    graph.add_asset(_equity("DST"))

    graph.add_relationship("SRC", "DST", "same_sector", 0.4, bidirectional=False)
    graph.add_relationship("SRC", "DST", "same_sector", 0.9, bidirectional=False)
    graph.add_relationship("SRC", "DST", "event_impact", 0.2, bidirectional=False)

    assert graph.relationships["SRC"] == [
        ("DST", "same_sector", 0.4),
        ("DST", "event_impact", 0.2),
    ]


def test_degree_metrics_exclude_zero_degree_assets() -> None:
    """Average and maximum degree are computed over relationship sources, not isolated zero-degree assets."""
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity("SRC"))
    graph.add_asset(_equity("DST"))
    graph.add_asset(_equity("ISOLATED"))
    graph.add_relationship("SRC", "DST", "observed", 0.5, bidirectional=False)

    metrics = graph.calculate_metrics()

    assert metrics["total_assets"] == 3
    assert metrics["total_relationships"] == 1
    assert metrics["avg_degree"] == pytest.approx(1.0)
    assert metrics["max_degree"] == 1
