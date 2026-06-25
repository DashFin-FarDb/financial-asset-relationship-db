"""Behavioural tests for asset pagination values."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from tests.helpers.api_pagination_graph_factory import build_asset_pagination_graph

pytestmark = pytest.mark.unit


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Provide an API client with graph state reset around each test."""
    api_main.reset_graph()
    test_client = TestClient(api_main.app)
    try:
        yield test_client
    finally:
        api_main.reset_graph()


def test_has_more_is_true_before_final_page_and_false_on_final_page(client: TestClient) -> None:
    """Asset pagination should set hasMore only before the final page."""
    api_main.set_graph(build_asset_pagination_graph(3))

    first_page = client.get("/api/assets", params={"page": 1, "per_page": 2})
    final_page = client.get("/api/assets", params={"page": 2, "per_page": 2})

    assert first_page.status_code == 200
    assert final_page.status_code == 200
    assert first_page.json()["hasMore"] is True
    assert final_page.json()["hasMore"] is False


def test_per_page_upper_boundary_is_accepted(client: TestClient) -> None:
    """Asset pagination should accept the maximum configured per-page value."""
    api_main.set_graph(build_asset_pagination_graph(3))

    response = client.get("/api/assets", params={"page": 1, "per_page": 1000})

    assert response.status_code == 200
    payload = response.json()
    assert payload["per_page"] == 1000
    assert payload["total"] == 3
    assert payload["hasMore"] is False
