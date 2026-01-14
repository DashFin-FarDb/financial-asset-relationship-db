#!/usr/bin/env python3
"""Quick test script to verify API endpoints work"""

import sys

from fastapi.testclient import TestClient

from api.main import app


def test_api():
    """Test basic API functionality"""
    print("🧪 Testing Financial Asset Relationship API...")
    print()

    # Create test client
    client = TestClient(app)

    # Test health check
    print("1. Testing health check endpoint...")
    response = client.get("/api/health")
    assert response.status_code == 200, f"Health check failed: {response.status_code}"
    print("   ✅ Health check passed")

    # Test root endpoint
    print("2. Testing root endpoint...")
    response = client.get("/")
    assert response.status_code == 200, f"Root endpoint failed: {response.status_code}"
    print("   ✅ Root endpoint passed")

    # Test assets endpoint
    print("3. Testing assets endpoint...")
    response = client.get("/api/assets")
    assert response.status_code == 200, f"Assets endpoint failed: {response.status_code}"
    assets = response.json()
    print(f"   ✅ Assets endpoint passed (found {len(assets)} assets)")

    # Test metrics endpoint
    print("4. Testing metrics endpoint...")
    response = client.get("/api/metrics")
    assert response.status_code == 200, f"Metrics endpoint failed: {response.status_code}"
    metrics = response.json()
    print("   ✅ Metrics endpoint passed")
    print(f"      - Total assets: {metrics['total_assets']}")
    print(f"      - Total relationships: {metrics['total_relationships']}")

    # Test visualization endpoint
    print("5. Testing visualization endpoint...")
    response = client.get("/api/visualization")
    assert response.status_code == 200, f"Visualization endpoint failed: {response.status_code}"
    viz_data = response.json()
    print("   ✅ Visualization endpoint passed")
    print(f"      - Nodes: {len(viz_data['nodes'])}")
    print(f"      - Edges: {len(viz_data['edges'])}")

    # Test relationships endpoint
    print("6. Testing relationships endpoint...")
    response = client.get("/api/relationships")
    assert response.status_code == 200, f"Relationships endpoint failed: {response.status_code}"
    relationships = response.json()
    print(f"   ✅ Relationships endpoint passed (found {len(relationships)} relationships)")

    # Test asset classes endpoint
    print("7. Testing asset classes endpoint...")
    response = client.get("/api/asset-classes")
    assert response.status_code == 200, f"Asset classes endpoint failed: {response.status_code}"
    asset_classes = response.json()
    print(f"   ✅ Asset classes endpoint passed (found {len(asset_classes['asset_classes'])} classes)")

    # Test sectors endpoint
    print("8. Testing sectors endpoint...")
    response = client.get("/api/sectors")
    assert response.status_code == 200, f"Sectors endpoint failed: {response.status_code}"
    sectors = response.json()
    print(f"   ✅ Sectors endpoint passed (found {len(sectors['sectors'])} sectors)")

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
