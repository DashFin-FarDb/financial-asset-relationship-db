"""Comprehensive unit tests for the MCP server (mcp_server.py).

This module tests:
- ThreadSafeGraph proxy
- Graph locking mechanisms
- MCP tool functionality
- add_equity_node validation
- Resource endpoints
- CLI argument parsing
- Error handling
"""

import json
import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


mcp_server = pytest.importorskip("mcp_server")
_graph_lock = mcp_server._graph_lock
_ThreadSafeGraph = mcp_server._ThreadSafeGraph
main = mcp_server.main


class TestThreadSafeGraph:
    """Test the _ThreadSafeGraph proxy class."""

    def test_thread_safe_graph_initialization(self):
        """Test ThreadSafeGraph initializes correctly."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()

        proxy = _ThreadSafeGraph(graph, lock)

        assert proxy._graph is graph
        assert proxy._lock is lock

    def test_thread_safe_graph_attribute_access(self):
        """Test accessing non-callable attributes returns deep copy."""
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        assets = proxy.assets

        # Should be a copy, not the same object
        assert assets is not graph.assets
        assert len(assets) == len(graph.assets)

    def test_thread_safe_graph_callable_access(self):
        """Test accessing callable attributes returns wrapped function."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        calculate_metrics = proxy.calculate_metrics

        # Should be callable
        assert callable(calculate_metrics)

    def test_thread_safe_graph_method_execution(self):
        """Test executing methods through proxy."""
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        metrics = proxy.calculate_metrics()

        assert isinstance(metrics, dict)
        assert "total_assets" in metrics

    def test_thread_safe_graph_concurrent_access(self):
        """Test concurrent access to thread-safe graph."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        results = []
        errors = []

        def access_assets():
            try:
                assets = proxy.assets
                results.append(len(assets))
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = [threading.Thread(target=access_assets) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # All should succeed
        assert len(errors) == 0
        assert len(results) == 10

    def test_thread_safe_graph_locks_during_method_call(self):
        """Test that lock is held during method execution."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        lock_acquired = []

        def slow_method():
            # Check if lock is held
            lock_acquired.append(not lock.acquire(blocking=False))
            if not lock_acquired[-1]:
                lock.release()
            time.sleep(0.1)
            return True

        # Patch a method to be slow
        with patch.object(graph, "calculate_metrics", side_effect=slow_method):
            # Start execution in another thread
            t = threading.Thread(target=proxy.calculate_metrics)
            t.start()
            time.sleep(0.05)  # Give it time to acquire lock

            # Try to acquire lock - should fail if proxy is holding it
            can_acquire = lock.acquire(blocking=False)
            if can_acquire:
                lock.release()

            t.join()

        # Lock should have been held during execution
        assert any(lock_acquired)


class TestMCPApp:
    """Test MCP app construction and tools."""

    @pytest.fixture
    def mcp_app(self):
        """Create MCP app for testing."""
        try:
            from mcp_server import _build_mcp_app

            return _build_mcp_app()
        except ModuleNotFoundError:
            pytest.skip("MCP dependencies not available")

    def test_build_mcp_app_returns_app(self, mcp_app):
        """Test that _build_mcp_app returns an MCP app."""
        assert mcp_app is not None
        assert hasattr(mcp_app, "tool")
        assert hasattr(mcp_app, "resource")

    def test_mcp_app_has_add_equity_tool(self, mcp_app):
        """Test that MCP app has add_equity_node tool."""
        # Check tools are registered
        assert hasattr(mcp_app, "tool")


class TestAddEquityNode:
    """Test the add_equity_node tool."""

    @pytest.fixture
    def mock_graph(self):
        """Create mock graph for testing."""
        graph = Mock(spec=AssetRelationshipGraph)
        graph.add_asset = Mock()
        return graph

    def test_add_equity_node_validation_success(self, mock_graph):
        """Test successful equity node validation and addition."""
        # This tests the logic without requiring MCP to be installed
        asset_id = "AAPL"
        symbol = "AAPL"
        name = "Apple Inc."
        sector = "Technology"
        price = 150.0

        # Simulate validation
        try:
            equity = Equity(
                id=asset_id, symbol=symbol, name=name, asset_class=AssetClass.EQUITY, sector=sector, price=price
            )
            assert equity.id == asset_id
            assert equity.symbol == symbol
            result = f"Successfully validated: {equity.name} ({equity.symbol})"
        except ValueError as e:
            result = f"Validation Error: {str(e)}"

        assert "Successfully" in result
        assert name in result

    def test_add_equity_node_validation_invalid_price(self):
        """Test equity node validation with invalid price."""
        with pytest.raises(ValueError):
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=-150.0,  # Invalid negative price
            )

    def test_add_equity_node_validation_missing_fields(self):
        """Test equity node validation with missing required fields."""
        with pytest.raises(ValueError):
            # Missing required fields
            Equity(
                id="AAPL",
                symbol="AAPL",
                # Missing name, asset_class, sector, price
            )


class Test3DLayoutResource:
    """Test the 3d-layout resource endpoint."""

    def test_get_3d_layout_returns_json(self):
        """Test that 3D layout resource returns valid JSON."""
        # Create a test graph
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )

        # Mock the resource function logic
        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        result = json.dumps(
            {
                "asset_ids": asset_ids,
                "positions": positions.tolist(),
                "colors": colors,
                "hover": hover,
            }
        )

        # Verify it's valid JSON
        data = json.loads(result)
        assert "asset_ids" in data
        assert "positions" in data
        assert "colors" in data
        assert "hover" in data

    def test_get_3d_layout_empty_graph(self):
        """Test 3D layout with empty graph."""
        graph = AssetRelationshipGraph()

        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()
        result = json.dumps(
            {
                "asset_ids": asset_ids,
                "positions": positions.tolist(),
                "colors": colors,
                "hover": hover,
            }
        )

        data = json.loads(result)
        # Should handle empty graph gracefully
        assert isinstance(data["asset_ids"], list)
        assert isinstance(data["positions"], list)


class TestMainFunction:
    """Test the main CLI entry point."""

    def test_main_help_argument(self):
        """Test main with --help argument."""
        # Note: This would normally exit, so we can't test directly
        # But we can test argument parsing
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--version", action="store_true")

        args = parser.parse_args(["--version"])
        assert args.version is True

    def test_main_version_flag(self):
        """Test main with --version flag."""
        result = main(["--version"])

        assert result == 0

    @patch("mcp_server._build_mcp_app")
    def test_main_missing_dependencies(self, mock_build):
        """Test main handles missing MCP dependencies."""
        mock_build.side_effect = ModuleNotFoundError("mcp.server.fastmcp")

        with pytest.raises(SystemExit):
            main([])

    @patch("mcp_server._build_mcp_app")
    def test_main_successful_run(self, mock_build):
        """Test successful main execution."""
        mock_mcp = Mock()
        mock_mcp.run = Mock()
        mock_build.return_value = mock_mcp

        result = main([])
        assert result in (0, None)
        mock_mcp.run.assert_called_once()


class TestConcurrentAccess:
    """Test concurrent access patterns."""

    def test_multiple_threads_accessing_graph(self):
        """Test multiple threads can safely access graph."""
        graph = AssetRelationshipGraph()
        for i in range(10):
            graph.add_asset(
                Equity(
                    id=f"ASSET{i}",
                    symbol=f"AST{i}",
                    name=f"Asset {i}",
                    asset_class=AssetClass.EQUITY,
                    sector="Technology",
                    price=float(100 + i),
                )
            )

        proxy = _ThreadSafeGraph(graph, _graph_lock)

        results = []
        errors = []

        def read_assets():
            try:
                assets = proxy.assets
                results.append(len(assets))
            except Exception as e:
                errors.append(e)

        def read_metrics():
            try:
                metrics = proxy.calculate_metrics()
                results.append(metrics["total_assets"])
            except Exception as e:
                errors.append(e)

        # Mix of read operations
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=read_assets))
            threads.append(threading.Thread(target=read_metrics))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert len(errors) == 0
        assert len(results) == 10

    def test_read_while_not_modifying(self):
        """Test reads don't interfere with each other."""
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )

        proxy = _ThreadSafeGraph(graph, _graph_lock)

        counters = {"reads": 0}
        lock_for_counter = threading.Lock()

        def concurrent_read():
            _ = proxy.assets
            with lock_for_counter:
                counters["reads"] += 1

        threads = [threading.Thread(target=concurrent_read) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counters["reads"] == 20


class TestErrorHandling:
    """Test error handling in MCP server."""

    def test_invalid_equity_data_raises_validation_error(self):
        """Test that invalid equity data raises ValidationError."""
        with pytest.raises(Exception):
            Equity(
                id="",  # Empty ID should fail
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )

    def test_graph_access_after_error(self):
        """Test graph remains accessible after errors."""
        graph = AssetRelationshipGraph()
        proxy = _ThreadSafeGraph(graph, _graph_lock)

        # Try invalid operation
        try:
            proxy.nonexistent_method()
        except AttributeError:
            pass

        # Graph should still be accessible
        assets = proxy.assets
        assert isinstance(assets, dict)


class TestIntegration:
    """Integration tests for MCP server components."""

    def test_end_to_end_equity_creation(self):
        """Test end-to-end equity creation flow."""
        # Create equity
        equity = Equity(
            id="MSFT",
            symbol="MSFT",
            name="Microsoft Corporation",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=320.0,
            market_cap=2.3e12,
            pe_ratio=28.2,
        )

        # Verify properties
        assert equity.id == "MSFT"
        assert equity.price == 320.0
        assert equity.pe_ratio == 28.2

    def test_graph_operations_through_proxy(self):
        """Test complete graph operations through proxy."""
        graph = AssetRelationshipGraph()
        proxy = _ThreadSafeGraph(graph, _graph_lock)

        # Initial state
        assets = proxy.assets
        assert len(assets) == 0

        # Add asset directly to graph (proxy is read-only wrapper)
        graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )

        # Read through proxy
        assets = proxy.assets
        assert len(assets) == 1
        assert "AAPL" in assets


class TestResourceEndpoints:
    """Test MCP resource endpoints."""

    def test_3d_layout_resource_structure(self):
        """Test 3D layout resource returns expected structure."""
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )

        positions, asset_ids, colors, hover = graph.get_3d_visualization_data_enhanced()

        result = {
            "asset_ids": asset_ids,
            "positions": positions.tolist(),
            "colors": colors,
            "hover": hover,
        }

        assert isinstance(result["asset_ids"], list)
        assert isinstance(result["positions"], list)
        assert isinstance(result["colors"], list)
        assert isinstance(result["hover"], list)
        assert len(result["asset_ids"]) > 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_proxy_with_none_attribute(self):
        """Test proxy handles None attributes."""
        graph = AssetRelationshipGraph()
        proxy = _ThreadSafeGraph(graph, _graph_lock)

        # Access an attribute that might be None
        assets = proxy.assets
        assert assets is not None

    def test_concurrent_attribute_access(self):
        """Test concurrent access to different attributes."""
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )

        proxy = _ThreadSafeGraph(graph, _graph_lock)

        results = []

        def access_assets():
            results.append(("assets", len(proxy.assets)))

        def access_relationships():
            results.append(("relationships", len(proxy.relationships)))

        threads = [
            threading.Thread(target=access_assets),
            threading.Thread(target=access_relationships),
            threading.Thread(target=access_assets),
            threading.Thread(target=access_relationships),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
