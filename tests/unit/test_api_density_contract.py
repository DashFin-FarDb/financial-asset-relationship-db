"""Behavioural API tests for graph density semantics."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity

pytestmark = pytest.mark.unit


def _equity(asset_id: str) -> Equity:
    """Create a mock Equity asset."""
    return Equity(
        id=asset_id,
        symbol=asset_id,
        name=f"{asset_id} Equity",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=100.0,
    )


def _graph_with_assets(count: int) -> AssetRelationshipGraph:
    """Create an AssetRelationshipGraph with a given number of assets."""
    graph = AssetRelationshipGraph()
    for index in range(count):
        graph.add_asset(_equity(f"ASSET_{index:02d}"))
    return graph


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Provide a TestClient with a clean graph state reset after each test."""
    api_main.reset_graph()
    with TestClient(api_main.app) as test_client:
        yield test_client
    api_main.reset_graph()


def _assert_density(client: TestClient, expected: float) -> None:
    """Assert the density from both the metrics and visualization endpoints matches expected."""
    metrics_response = client.get("/api/graph/metrics")
    visualization_response = client.get("/api/visualization")

    assert metrics_response.status_code == 200
    assert visualization_response.status_code == 200

    metrics_density = metrics_response.json()["network_density"]
    visualization_density = visualization_response.json()["network_density"]

    assert metrics_density == pytest.approx(expected)
    assert visualization_density == pytest.approx(expected)
    assert visualization_density == pytest.approx(metrics_density)


@pytest.mark.parametrize("asset_count", [0, 1])
def test_api_density_is_zero_for_empty_and_single_node_graphs(client: TestClient, asset_count: int) -> None:
    """Ensure density calculation returns 0.0 for empty or single-node networks."""
    api_main.set_graph(_graph_with_assets(asset_count))

    _assert_density(client, 0.0)


def test_api_density_reports_known_fraction_and_visualization_metrics_parity(client: TestClient) -> None:
    """Verify density returns expected fraction and matches between metrics and viz endpoints."""
    graph = _graph_with_assets(4)
    graph.add_relationship("ASSET_00", "ASSET_01", "observed", 0.5, bidirectional=False)
    graph.add_relationship("ASSET_01", "ASSET_02", "observed", 0.5, bidirectional=False)
    graph.add_relationship("ASSET_02", "ASSET_03", "observed", 0.5, bidirectional=False)
    api_main.set_graph(graph)

    _assert_density(client, 0.25)


def test_model_density_flows_through_graph_metrics_response(client: TestClient) -> None:
    """Confirm the computed density flows to the /api/graph/metrics endpoint and old key is absent."""
    graph = _graph_with_assets(3)
    graph.add_relationship("ASSET_00", "ASSET_01", "observed", 0.5, bidirectional=False)
    graph.add_relationship("ASSET_01", "ASSET_02", "observed", 0.5, bidirectional=False)
    expected_density = graph.calculate_metrics()["network_density"]
    api_main.set_graph(graph)

    payload = client.get("/api/graph/metrics").json()

    assert payload["network_density"] == pytest.approx(expected_density)
    assert "relationship_density" not in payload
