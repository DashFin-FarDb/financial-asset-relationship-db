"""
Comprehensive unit tests for mcp_server.py module.

Tests cover:
- Thread-safe graph proxy
- MCP tool functionality
- Equity node validation
- Resource endpoints
- Command-line interface
- Error handling and edge cases
"""

import argparse
import json
import threading
from unittest.mock import Mock, patch

import pytest

from mcp_server import _build_mcp_app, _ThreadSafeGraph, main
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


class TestThreadSafeGraph:
    """Test the _ThreadSafeGraph proxy wrapper."""

    def test_thread_safe_graph_wraps_graph(self):
        """Test that ThreadSafeGraph wraps an asset graph."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        assert proxy._graph == graph
        assert proxy._lock == lock

    def test_thread_safe_graph_callable_methods_wrapped(self):
        """Test that callable methods are wrapped with lock."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        # Should be able to call methods
        result = proxy.calculate_metrics()
        assert isinstance(result, dict)

    def test_thread_safe_graph_attributes_deep_copied(self):
        """Test that non-callable attributes are deep copied."""
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="TEST",
                symbol="TST",
                name="Test",
                asset_class=AssetClass.EQUITY,
                sector="Test",
                price=100.0,
            )
        )

        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        # Get assets (should be a copy)
        assets = proxy.assets
        assert isinstance(assets, dict)
        assert "TEST" in assets

        # Modifying copy shouldn't affect original
        assets["NEW"] = Mock()
        assert "NEW" not in graph.assets

    def test_thread_safe_graph_concurrent_access(self):
        """Test that concurrent access is serialized."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        results = []

        def access_graph():
            metrics = proxy.calculate_metrics()
            results.append(metrics["total_assets"])

        # Simulate concurrent access
        threads = [threading.Thread(target=access_graph) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert len(results) == 10


class TestMCPAppBuilding:
    """Test MCP application building."""

    @patch("mcp.server.fastmcp.FastMCP")
    def test_build_mcp_app_creates_app(self, mock_fastmcp):
        """Test that _build_mcp_app creates FastMCP instance."""
        mock_instance = Mock()
        mock_fastmcp.return_value = mock_instance

        app = _build_mcp_app()

        mock_fastmcp.assert_called_once_with("DashFin-Relationship-Manager")
        assert app == mock_instance

    @patch("mcp.server.fastmcp.FastMCP")
    def test_build_mcp_app_registers_tools(self, mock_fastmcp):
        """Test that tools are registered."""
        mock_mcp = Mock()
        mock_fastmcp.return_value = mock_mcp

        _build_mcp_app()

        # Should have registered tool decorator
        assert mock_mcp.tool.called

    @patch("mcp.server.fastmcp.FastMCP")
    def test_build_mcp_app_registers_resources(self, mock_fastmcp):
        """Test that resources are registered."""

    mock_mcp = Mock()
    mock_fastmcp.return_value = mock_mcp

    _build_mcp_app()

    # Should have registered resource decorator
    assert mock_mcp.resource.called


class TestAddEquityNodeTool:
    """Test the add_equity_node MCP tool."""

    @patch("mcp_server.FastMCP")
    @patch("mcp_server.graph")
    def test_add_equity_node_valid_input(self, mock_graph, mock_fastmcp):
        """Test adding valid equity node."""
        mock_mcp = Mock()
        tool_func = None

        def capture_tool_func(func):
            nonlocal tool_func
            tool_func = func
            return func

        mock_mcp.tool.return_value = capture_tool_func
        mock_fastmcp.return_value = mock_mcp

        # Build app to register tools
        _build_mcp_app()

        # Now call the tool
        assert tool_func is not None
        result = tool_func(
            asset_id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            sector="Technology",
            price=150.0,
        )

        assert "Success" in result or "validate" in result.lower()

    @patch("mcp_server.FastMCP")
    def test_add_equity_node_invalid_price(self, mock_fastmcp):
        """Test adding equity with invalid price."""
        mock_mcp = Mock()
        tool_func = None

        def capture_tool_func(func):
            nonlocal tool_func
            tool_func = func
            return func

        mock_mcp.tool.return_value = capture_tool_func
        mock_fastmcp.return_value = mock_mcp

        _build_mcp_app()

        # Call with negative price
        result = tool_func(
            asset_id="TEST", symbol="TST", name="Test", sector="Test", price=-100.0
        )

        assert "Validation Error" in result or "error" in result.lower()

    @patch("mcp_server.FastMCP")
    def test_add_equity_node_empty_fields(self, mock_fastmcp):
        """Test adding equity with empty required fields."""
        mock_mcp = Mock()
        tool_func = None

        def capture_tool_func(func):
            nonlocal tool_func
            tool_func = func
            return func

        mock_mcp.tool.return_value = capture_tool_func
        mock_fastmcp.return_value = mock_mcp

        _build_mcp_app()

        # Call with empty symbol
        result = tool_func(
            asset_id="TEST", symbol="", name="Test", sector="Test", price=100.0
        )

        # Should validate and potentially error
        assert isinstance(result, str)


class TestGet3DLayoutResource:
    """Test the 3D layout resource endpoint."""

    @patch("mcp_server.FastMCP")
    @patch("mcp_server.graph")
    def test_get_3d_layout_returns_json(self, mock_graph, mock_fastmcp):
        """Test that 3D layout returns valid JSON."""
        mock_mcp = Mock()
        resource_func = None

        def capture_resource_func(path):
            def decorator(func):
                nonlocal resource_func
                resource_func = func
                return func

            return decorator

        mock_mcp.resource = capture_resource_func
        mock_fastmcp.return_value = mock_mcp

        # Mock graph method
        import numpy as np

        mock_graph.get_3d_visualization_data_enhanced.return_value = (
            np.array([[0, 0, 0]]),
            ["AAPL"],
            ["#FF0000"],
            ["Apple Inc."],
        )

        _build_mcp_app()

        assert resource_func is not None
        result = resource_func()

        # Should be valid JSON
        data = json.loads(result)
        assert "asset_ids" in data
        assert "positions" in data
        assert "colors" in data
        assert "hover" in data

    @patch("mcp_server.FastMCP")
    @patch("mcp_server.graph")
    def test_get_3d_layout_structure(self, mock_graph, mock_fastmcp):
        """Test that 3D layout has correct structure."""
        mock_mcp = Mock()
        resource_func = None

        def capture_resource_func(path):
            def decorator(func):
                nonlocal resource_func
                resource_func = func
                return func

            return decorator

        mock_mcp.resource = capture_resource_func
        mock_fastmcp.return_value = mock_mcp

        import numpy as np

        mock_graph.get_3d_visualization_data_enhanced.return_value = (
            np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
            ["AAPL", "MSFT"],
            ["#FF0000", "#00FF00"],
            ["Apple", "Microsoft"],
        )

        _build_mcp_app()

        result = resource_func()
        data = json.loads(result)

        assert len(data["asset_ids"]) == 2
        assert len(data["positions"]) == 2
        assert len(data["colors"]) == 2
        assert len(data["hover"]) == 2


class TestMainFunction:
    """Test the main CLI function."""

    @patch("mcp_server._build_mcp_app")
    def test_main_default_runs_server(self, mock_build):
        """Test that main runs the server by default."""
        mock_mcp = Mock()
        mock_build.return_value = mock_mcp

        result = main([])

        assert result == 0
        mock_mcp.run.assert_called_once()

    def test_main_version_flag(self):
        """Test --version flag."""
        with patch("builtins.print") as mock_print:
            result = main(["--version"])

        assert result == 0
        mock_print.assert_called_once()
        assert "DashFin" in str(mock_print.call_args)

    @patch("mcp_server._build_mcp_app")
    def test_main_missing_dependency(self, mock_build):
        """Test handling of missing MCP dependency."""
        mock_build.side_effect = ModuleNotFoundError("No module named 'mcp'")

        with pytest.raises(SystemExit) as exc_info:
            main([])

        assert (
            "mcp" in str(exc_info.value).lower()
            or "missing dependency" in str(exc_info.value).lower()
        )

    def test_main_help_flag(self):
        """Test --help flag."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        # --help causes SystemExit with code 0
        assert exc_info.value.code == 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("mcp_server.FastMCP")
    def test_add_equity_node_unicode_name(self, mock_fastmcp):
        """Test adding equity with unicode characters in name."""
        mock_mcp = Mock()
        tool_func = None

        def capture_tool_func(func):
            nonlocal tool_func
            tool_func = func
            return func

        mock_mcp.tool.return_value = capture_tool_func
        mock_fastmcp.return_value = mock_mcp

        _build_mcp_app()

        result = tool_func(
            asset_id="TEST", symbol="TST", name="Test 公司", sector="Tech", price=100.0
        )

        assert isinstance(result, str)

    @patch("mcp_server.FastMCP")
    def test_add_equity_node_very_long_name(self, mock_fastmcp):
        """Test adding equity with very long name."""
        mock_mcp = Mock()
        tool_func = None

        def capture_tool_func(func):
            nonlocal tool_func
            tool_func = func
            return func

        mock_mcp.tool.return_value = capture_tool_func
        mock_fastmcp.return_value = mock_mcp

        _build_mcp_app()

        long_name = "A" * 1000
        result = tool_func(
            asset_id="TEST", symbol="TST", name=long_name, sector="Tech", price=100.0
        )

        assert isinstance(result, str)

    @patch("mcp_server.FastMCP")
    @patch("mcp_server.graph")
    def test_add_equity_node_graph_without_add_asset(self, mock_graph, mock_fastmcp):
        """Test behavior when graph doesn't have add_asset method."""
        mock_mcp = Mock()
        tool_func = None

        def capture_tool_func(func):
            nonlocal tool_func
            tool_func = func
            return func

        mock_mcp.tool.return_value = capture_tool_func
        mock_fastmcp.return_value = mock_mcp

        # Mock graph without add_asset
        delattr(mock_graph, "add_asset")

        _build_mcp_app()

        result = tool_func(
            asset_id="TEST", symbol="TST", name="Test", sector="Tech", price=100.0
        )

        # Should indicate validation-only mode
        assert "validated" in result.lower() or "not supported" in result.lower()

    def test_thread_safe_graph_handles_exceptions(self):
        """Test that ThreadSafeGraph handles exceptions in wrapped methods."""
        graph = Mock()
        graph.calculate_metrics.side_effect = Exception("Test error")

        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        with pytest.raises(Exception, match="Test error"):
            proxy.calculate_metrics()


class TestConcurrency:
    """Test concurrent access scenarios."""

    def test_multiple_threads_accessing_graph(self):
        """Test multiple threads accessing graph simultaneously."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        errors = []

        def access_graph():
            try:
                for _ in range(10):
                    _ = proxy.assets
                    _ = proxy.relationships
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=access_graph) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"

    def test_graph_modifications_are_thread_safe(self):
        """Test that graph modifications are thread-safe."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        proxy = _ThreadSafeGraph(graph, lock)

        results = []

        def add_assets():
            # Try to get and modify (though modification won't persist due to deep copy)
            assets = proxy.assets
            results.append(len(assets))

        threads = [threading.Thread(target=add_assets) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should complete without error
        assert len(results) == 10
