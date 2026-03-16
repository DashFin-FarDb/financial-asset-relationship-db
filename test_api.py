#!/usr/bin/env python3
"""Quick test script to verify API endpoints work"""

import sys

from fastapi.testclient import TestClient

from api.main import app


def _assert_ok(response, endpoint_name: str) -> None:
    """Assert successful response status code for endpoint tests."""
    assert response.status_code == 200, (
        f"{endpoint_name} failed: {response.status_code}"
    )


def _test_health(client: TestClient) -> None:
    print("1. Testing health check endpoint...")
    response = client.get("/api/health")
    _assert_ok(response, "Health check")
    print("   ✅ Health check passed")


def _test_root(client: TestClient) -> None:
    print("2. Testing root endpoint...")
    response = client.get("/")
    _assert_ok(response, "Root endpoint")
    print("   ✅ Root endpoint passed")


def _test_assets(client: TestClient) -> None:
    print("3. Testing assets endpoint...")
    response = client.get("/api/assets")
    _assert_ok(response, "Assets endpoint")
    assets = response.json()
    print(f"   ✅ Assets endpoint passed (found {len(assets)} assets)")


def _test_metrics(client: TestClient) -> None:
    print("4. Testing metrics endpoint...")
    response = client.get("/api/metrics")
    _assert_ok(response, "Metrics endpoint")
    metrics = response.json()
    print("   ✅ Metrics endpoint passed")
    print(f"      - Total assets: {metrics['total_assets']}")
    print(f"      - Total relationships: {metrics['total_relationships']}")


def _test_visualization(client: TestClient) -> None:
    print("5. Testing visualization endpoint...")
    response = client.get("/api/visualization")
    _assert_ok(response, "Visualization endpoint")
    viz_data = response.json()
    print("   ✅ Visualization endpoint passed")
    print(f"      - Nodes: {len(viz_data['nodes'])}")
    print(f"      - Edges: {len(viz_data['edges'])}")


def _test_relationships(client: TestClient) -> None:
    print("6. Testing relationships endpoint...")
    response = client.get("/api/relationships")
    _assert_ok(response, "Relationships endpoint")
    relationships = response.json()
    print(
        "   ✅ Relationships endpoint passed "
        f"(found {len(relationships)} relationships)"
    )


def _test_asset_classes(client: TestClient) -> None:
    print("7. Testing asset classes endpoint...")
    response = client.get("/api/asset-classes")
    _assert_ok(response, "Asset classes endpoint")
    asset_classes = response.json()
    print(
        "   ✅ Asset classes endpoint passed "
        f"(found {len(asset_classes['asset_classes'])} classes)"
    )


def _test_sectors(client: TestClient) -> None:
    print("8. Testing sectors endpoint...")
    response = client.get("/api/sectors")
    _assert_ok(response, "Sectors endpoint")
    sectors = response.json()
    print(
        f"   ✅ Sectors endpoint passed (found {len(sectors['sectors'])} "
        "sectors)"
    )


def test_api() -> bool:
    """Test basic API functionality."""
    print("🧪 Testing Financial Asset Relationship API...")
    print()

    client = TestClient(app)
    _test_health(client)
    _test_root(client)
    _test_assets(client)
    _test_metrics(client)
    _test_visualization(client)
    _test_relationships(client)
    _test_asset_classes(client)
    _test_sectors(client)

    print()
    print("🎉 All API tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_api()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
