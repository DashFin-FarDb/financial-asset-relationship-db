"""Integration coverage for asset pagination value contracts."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from tests.helpers.api_pagination_graph_factory import build_asset_pagination_graph

pytestmark = pytest.mark.integration


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Provide an API client with a seeded three-asset graph."""
    api_main.reset_graph()
    api_main.set_graph(build_asset_pagination_graph(3))
    try:
        with TestClient(api_main.app) as test_client:
            yield test_client
    finally:
        api_main.reset_graph()

def test_assets_endpoint_reports_has_more_values_across_pages(client: TestClient) -> None:
    """Assets endpoint should report hasMore until the final page."""
    first_page = client.get("/api/assets", params={"page": 1, "per_page": 2})
    final_page = client.get("/api/assets", params={"page": 2, "per_page": 2})

    assert first_page.status_code == 200
    assert final_page.status_code == 200
    assert first_page.json()["hasMore"] is True
    assert final_page.json()["hasMore"] is False


def test_assets_endpoint_accepts_per_page_upper_boundary(client: TestClient) -> None:
    """Assets endpoint should accept the documented per-page upper bound."""
    response = client.get("/api/assets", params={"page": 1, "per_page": 1000})

    assert response.status_code == 200
    payload = response.json()
    assert payload["per_page"] == 1000
    assert payload["total"] == 3
    assert payload["hasMore"] is False
