"""Behavioural tests for asset pagination values."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity

pytestmark = pytest.mark.unit


def _asset(asset_id: str) -> Equity:
    return Equity(
        id=asset_id,
        symbol=asset_id,
        name=f"{asset_id} Equity",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=100.0,
    )


def _graph(asset_count: int) -> AssetRelationshipGraph:
    graph = AssetRelationshipGraph()
    for index in range(asset_count):
        graph.add_asset(_asset(f"ASSET_{index:02d}"))
    return graph


@pytest.fixture()
def client() -> Iterator[TestClient]:
    api_main.reset_graph()
    with TestClient(api_main.app) as test_client:
        yield test_client
    api_main.reset_graph()


def test_has_more_is_true_before_final_page_and_false_on_final_page(client: TestClient) -> None:
    api_main.set_graph(_graph(3))

    first_page = client.get("/api/assets", params={"page": 1, "per_page": 2})
    final_page = client.get("/api/assets", params={"page": 2, "per_page": 2})

    assert first_page.status_code == 200
    assert final_page.status_code == 200
    assert first_page.json()["hasMore"] is True
    assert final_page.json()["hasMore"] is False


def test_per_page_upper_boundary_is_accepted(client: TestClient) -> None:
    api_main.set_graph(_graph(3))

    response = client.get("/api/assets", params={"page": 1, "per_page": 1000})

    assert response.status_code == 200
    payload = response.json()
    assert payload["per_page"] == 1000
    assert payload["total"] == 3
    assert payload["hasMore"] is False
