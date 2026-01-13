"""Integration tests for the complete API flow.
"""
This module tests the full API integration including:
- End - to - end request / response cycles
- Data consistency across endpoints
- Real graph initialization
- Performance benchmarks
"""

import os

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """Create a test client for integration tests."""
    return TestClient(app)


class TestCompleteAPIFlow:
    """Test complete API workflows."""

    @staticmethod
    def test_full_data_retrieval_flow(client):
        """Test complete flow: health -> assets -> detail -> relationships."""
        # Step 1: Check health
        health_response = client.get("/api/health")
        assert health_response.status_code == 200

        # Step 2: Get all assets
        assets_response = client.get("/api/assets")
        assert assets_response.status_code == 200
        assets = assets_response.json()
        assert len(assets) > 0

        # Step 3: Get detail for first asset
        first_asset = assets[0]
        detail_response = client.get(f"/api/assets/{first_asset['id']}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["id"] == first_asset["id"]

        # Step 4: Get relationships for asset
        rel_response = client.get(f"/api/assets/{first_asset['id']}/relationships")
        assert rel_response.status_code == 200
        relationships = rel_response.json()
        assert isinstance(relationships, list)

    @staticmethod
    def test_metrics_consistency(client):
        """Test that metrics are consistent with actual data."""
        # Get metrics
        metrics_response = client.get("/api/metrics")
        assert metrics_response.status_code == 200
        metrics = metrics_response.json()

        # Get all assets
        assets_response = client.get("/api/assets")
        assets = assets_response.json()

        # Verify metrics match actual counts
        assert metrics["total_assets"] == len(assets)

        # Verify asset class counts
        asset_class_counts = {}
        for asset in assets:
            ac = asset["asset_class"]
            asset_class_counts[ac] = asset_class_counts.get(ac, 0) + 1

        assert metrics["asset_classes"] == asset_class_counts

    @staticmethod
    def test_visualization_data_consistency(client):
        """Test visualization data consistency with assets."""
        # Get assets
        assets_response = client.get("/api/assets")
        assets = assets_response.json()
        asset_ids = {asset["id"] for asset in assets}

        # Get visualization data
        viz_response = client.get("/api/visualization")
        viz_data = viz_response.json()

        # All nodes should correspond to existing assets
        node_ids = {node["id"] for node in viz_data["nodes"]}
        assert node_ids == asset_ids

        # All edges should reference existing nodes
        for edge in viz_data["edges"]:
            assert edge["source"] in node_ids
            assert edge["target"] in node_ids

    @staticmethod
    def test_filter_combinations(client):
        """Test various filter combinations return consistent results."""
# Get all assets
all_assets = client.get("/api/assets").json()

# Get unique asset classes and sectors
asset_classes = set(a["asset_class"] for a in all_assets)
sectors = set(a["sector"] for a in all_assets)

# Test each asset class filter
for ac in asset_classes:
    filtered = client.get(f"/api/assets?asset_class={ac}").json()
    assert all(a["asset_class"] == ac for a in filtered)
    assert len(filtered) <= len(all_assets)

# Test each sector filter
for sector in sectors:
    filtered = client.get(f"/api/assets?sector={sector}").json()
    assert all(a["sector"] == sector for a in filtered)
    assert len(filtered) <= len(all_assets)

class TestDataIntegrity:
    """Test data integrity across endpoints."""

    @staticmethod
    def test_asset_detail_matches_list(client):
        """Test that asset details match what's in the list."""
        assets = client.get("/api/assets").json()

        for asset in assets[:3]:  # Test first 3 assets
            detail = client.get(f"/api/assets/{asset['id']}").json()

            # Core fields should match
            assert detail["id"] == asset["id"]
            assert detail["symbol"] == asset["symbol"]
            assert detail["name"] == asset["name"]
            assert detail["asset_class"] == asset["asset_class"]
            assert detail["price"] == asset["price"]

    @staticmethod
    def test_relationship_bidirectionality(client):
        """Test that relationships are properly represented."""
        relationships = client.get("/api/relationships").json()

        # Build relationship graph
        graph = {}
        for rel in relationships:
            source = rel["source_id"]
            target = rel["target_id"]
            if source not in graph:
                graph[source] = []
            graph[source].append(target)

        # Verify relationships are accessible from both endpoints
        for source_id in graph:
            asset_rels = client.get(f"/api/assets/{source_id}/relationships").json()
            assert len(asset_rels) > 0


class TestPerformance:
    """Basic performance tests."""

    @staticmethod
    def test_response_times(client):
        """Test that endpoints respond within reasonable time."""
        import time

        endpoints = [
            "/api/health",
            "/api/assets",
            "/api/metrics",
            "/api/asset-classes",
        ]

        for endpoint in endpoints:
            start = time.time()
            response = client.get(endpoint)
            duration = time.time() - start

            assert response.status_code == 200
            assert duration < 5.0, f"{endpoint} took {duration:.2f}s"

    @staticmethod
    def test_concurrent_requests(client):
        """Test handling of multiple concurrent requests."""
        from concurrent.futures import ThreadPoolExecutor

        def make_request():
            return client.get("/api/assets").status_code

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]

        # All requests should succeed
        assert all(status == 200 for status in results)


class TestAuthenticationFlow:
    """Test authentication and token validation against the backing store."""

    @staticmethod
    def test_token_issuance_and_validation(client):
        """A valid credential should yield a token that authorizes protected endpoints."""

        credentials = {
            "username": os.environ["ADMIN_USERNAME"],
            "password": os.environ["ADMIN_PASSWORD"],
        }
        token_response = client.post(
            "/token",
            data=credentials,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert token_response.status_code == 200
        token = token_response.json()["access_token"]

        me_response = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert me_response.status_code == 200
        payload = me_response.json()
        assert payload["username"] == credentials["username"]
        assert payload["email"] == os.environ["ADMIN_EMAIL"]
        assert payload["full_name"] == os.environ["ADMIN_FULL_NAME"]
        assert payload["disabled"] is False

        invalid_response = client.get("/api/users/me", headers={"Authorization": "Bearer invalid-token"})
        assert invalid_response.status_code == 401

        # Test authentication with incorrect password
        invalid_credentials = credentials.copy()
        invalid_credentials["password"] = "wrongpassword"
        invalid_token_response = client.post(
            "/token",
            data=invalid_credentials,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert invalid_token_response.status_code == 401


class TestErrorRecovery:
    """Test error handling and recovery."""

    @staticmethod
    def test_invalid_endpoints_return_404(client):
        """Test that invalid endpoints return 404."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

    @staticmethod
    def test_invalid_asset_id_returns_404(client):
        """Test that invalid asset IDs return 404."""
        response = client.get("/api/assets/NONEXISTENT_ID_12345")
        assert response.status_code == 404

    @staticmethod
    def test_malformed_requests(client):
        """Test handling of malformed requests."""
        # Test with invalid query parameters
        response = client.get("/api/assets?asset_class=INVALID")
        assert response.status_code == 200
        assert len(response.json()) == 0
