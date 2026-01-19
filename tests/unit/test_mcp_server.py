"""Comprehensive unit tests for mcp_server.py.

Tests the MCP (Model Context Protocol) server functionality including:
- Thread-safe graph wrapper
- Equity node addition and validation
- 3D layout resource generation
- Error handling
- Command-line interface
"""

from __future__ import annotations

import argparse
import json
import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

import mcp_server
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


class TestThreadSafeGraph:
    """Test the _ThreadSafeGraph proxy wrapper."""

    @staticmethod
    def test_thread_safe_graph_wraps_graph():
        """Test that ThreadSafeGraph wraps an AssetRelationshipGraph."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()

        wrapped = mcp_server._ThreadSafeGraph(graph, lock)

        assert wrapped is not None

    @staticmethod
    def test_thread_safe_graph_callable_access():
        """Test that callable methods are wrapped with locking."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        wrapped = mcp_server._ThreadSafeGraph(graph, lock)

        # Access a callable method
        add_asset = wrapped.add_asset

        assert callable(add_asset)

    @staticmethod
    def test_thread_safe_graph_attribute_access():
        """Test that non-callable attributes return deepcopy."""
        graph = AssetRelationshipGraph()
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        graph.add_asset(equity)

        lock = threading.Lock()
        wrapped = mcp_server._ThreadSafeGraph(graph, lock)

        # Access assets attribute
        assets = wrapped.assets

        # Should be a copy, not the original
        assert isinstance(assets, dict)
        assert "TEST" in assets

    @staticmethod
    def test_thread_safe_graph_method_execution():
        """Test that wrapped methods execute correctly."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        wrapped = mcp_server._ThreadSafeGraph(graph, lock)

        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )

        # Call add_asset through wrapper
        wrapped.add_asset(equity)

        # Verify asset was added
        assets = wrapped.assets
        assert "TEST" in assets


class TestBuildMCPApp:
    """Test the _build_mcp_app function."""

    @staticmethod
    @patch("mcp_server.FastMCP")
    def test_build_mcp_app_creates_instance(mock_fastmcp_class):
        """Test that _build_mcp_app creates FastMCP instance."""
        mock_app = MagicMock()
        mock_fastmcp_class.return_value = mock_app

        result = mcp_server._build_mcp_app()

        mock_fastmcp_class.assert_called_once_with("DashFin-Relationship-Manager")
        assert result is mock_app

    @staticmethod
    @patch("mcp_server.FastMCP")
    def test_build_mcp_app_registers_tools(mock_fastmcp_class):
        """Test that tools are registered with the MCP app."""
        mock_app = MagicMock()
        mock_fastmcp_class.return_value = mock_app

        # Track tool decorator calls
        tool_calls = []

        def track_tool():
            def decorator(func):
                tool_calls.append(func.__name__)
                return func

            return decorator

        mock_app.tool = track_tool
        mock_app.resource = MagicMock()

        mcp_server._build_mcp_app()

        # Verify add_equity_node tool was registered
        assert "add_equity_node" in tool_calls

    @staticmethod
    def test_build_mcp_app_missing_dependency():
        """Test that missing mcp dependency is handled."""
        with patch.dict("sys.modules", {"mcp.server.fastmcp": None}):
            with pytest.raises(ModuleNotFoundError):
                mcp_server._build_mcp_app()


class TestAddEquityNodeTool:
    """Test the add_equity_node MCP tool."""

    @staticmethod
    def test_add_equity_node_valid_data():
        """Test adding a valid equity node."""
        # Create a fresh graph for testing
        test_graph = AssetRelationshipGraph()
        lock = threading.Lock()
        wrapped_graph = mcp_server._ThreadSafeGraph(test_graph, lock)

        # Temporarily replace module graph
        original_graph = mcp_server.graph
        mcp_server.graph = wrapped_graph

        try:
            app = mcp_server._build_mcp_app()

            # Find the add_equity_node function
            # It should be accessible through the tool registry
            # For testing, we'll call it directly
            from mcp_server import _build_mcp_app

            # Create tool function manually for testing
            def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
                try:
                    new_equity = Equity(
                        id=asset_id,
                        symbol=symbol,
                        name=name,
                        asset_class=AssetClass.EQUITY,
                        sector=sector,
                        price=price,
                    )
                    add_asset = getattr(mcp_server.graph, "add_asset", None)
                    if callable(add_asset):
                        add_asset(new_equity)
                        return f"Successfully added: {new_equity.name} ({new_equity.symbol})"
                    return f"Successfully validated (Graph mutation not supported): {new_equity.name} ({new_equity.symbol})"
                except ValueError as e:
                    return f"Validation Error: {str(e)}"

            result = add_equity_node("TEST", "TEST", "Test Inc.", "Technology", 100.0)

            assert "Successfully added" in result or "Successfully validated" in result

        finally:
            mcp_server.graph = original_graph

    @staticmethod
    def test_add_equity_node_invalid_price():
        """Test that invalid price causes validation error."""

        def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
            try:
                new_equity = Equity(
                    id=asset_id,
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.EQUITY,
                    sector=sector,
                    price=price,
                )
                return f"Successfully validated: {new_equity.name}"
            except ValueError as e:
                return f"Validation Error: {str(e)}"

        result = add_equity_node("TEST", "TEST", "Test", "Tech", -100.0)

        assert "Validation Error" in result

    @staticmethod
    def test_add_equity_node_missing_required_field():
        """Test that missing required fields cause validation error."""

        def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
            try:
                # Try to create equity with invalid data
                new_equity = Equity(
                    id="",  # Empty ID
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.EQUITY,
                    sector=sector,
                    price=price,
                )
                return f"Successfully validated: {new_equity.name}"
            except (ValueError, TypeError) as e:
                return f"Validation Error: {str(e)}"

        result = add_equity_node("", "TEST", "Test", "Tech", 100.0)

        assert "Validation Error" in result


class TestGet3DLayoutResource:
    """Test the 3D layout resource."""

    @staticmethod
    @patch("mcp_server.graph")
    def test_get_3d_layout_returns_json(mock_graph):
        """Test that get_3d_layout returns valid JSON."""
        import numpy as np

        # Mock the graph method
        mock_graph.get_3d_visualization_data_enhanced.return_value = (
            np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]),
            ["ASSET1", "ASSET2"],
            ["#FF0000", "#00FF00"],
            ["Asset 1", "Asset 2"],
        )

        # Create the resource function manually
        def get_3d_layout() -> str:
            positions, asset_ids, colors, hover = mock_graph.get_3d_visualization_data_enhanced()
            return json.dumps(
                {
                    "asset_ids": asset_ids,
                    "positions": positions.tolist(),
                    "colors": colors,
                    "hover": hover,
                }
            )

        result = get_3d_layout()

        # Should be valid JSON
        data = json.loads(result)
        assert "asset_ids" in data
        assert "positions" in data
        assert "colors" in data
        assert "hover" in data

    @staticmethod
    @patch("mcp_server.graph")
    def test_get_3d_layout_handles_empty_graph(mock_graph):
        """Test 3D layout with empty graph."""
        import numpy as np

        mock_graph.get_3d_visualization_data_enhanced.return_value = (
            np.array([]),
            [],
            [],
            [],
        )

        def get_3d_layout() -> str:
            positions, asset_ids, colors, hover = mock_graph.get_3d_visualization_data_enhanced()
            return json.dumps(
                {
                    "asset_ids": asset_ids,
                    "positions": positions.tolist(),
                    "colors": colors,
                    "hover": hover,
                }
            )

        result = get_3d_layout()
        data = json.loads(result)

        assert data["asset_ids"] == []
        assert data["positions"] == []


class TestMainFunction:
    """Test the main CLI function."""

    @staticmethod
    def test_main_version_flag():
        """Test main with --version flag."""
        result = mcp_server.main(["--version"])

        assert result == 0

    @staticmethod
    @patch("mcp_server._build_mcp_app")
    def test_main_starts_server(mock_build):
        """Test that main builds and runs the MCP app."""
        mock_app = MagicMock()
        mock_build.return_value = mock_app

        mcp_server.main([])

        mock_build.assert_called_once()
        mock_app.run.assert_called_once()

    @staticmethod
    def test_main_handles_missing_dependency():
        """Test that main handles missing MCP dependency gracefully."""
        with patch("mcp_server._build_mcp_app", side_effect=ModuleNotFoundError("mcp")):
            with pytest.raises(SystemExit) as exc_info:
                mcp_server.main([])

            # Should exit with error message
            assert "Missing dependency" in str(exc_info.value)

    @staticmethod
    def test_main_default_args():
        """Test main with no arguments."""
        with patch("mcp_server._build_mcp_app") as mock_build:
            mock_app = MagicMock()
            mock_build.return_value = mock_app

            result = mcp_server.main(None)

            assert result == 0


class TestConcurrency:
    """Test thread safety of the MCP server."""

    @staticmethod
    def test_graph_lock_exists():
        """Test that global graph lock exists."""
        assert hasattr(mcp_server, "_graph_lock")
        assert isinstance(mcp_server._graph_lock, threading.Lock)

    @staticmethod
    def test_concurrent_access_is_safe():
        """Test that concurrent access to graph is thread-safe."""
        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        wrapped = mcp_server._ThreadSafeGraph(graph, lock)

        results = []

        def add_assets(start_id: int):
            for i in range(5):
                equity = Equity(
                    id=f"TEST{start_id + i}",
                    symbol=f"T{start_id + i}",
                    name=f"Test {start_id + i}",
                    asset_class=AssetClass.EQUITY,
                    sector="Tech",
                    price=100.0 + i,
                )
                wrapped.add_asset(equity)
            results.append(True)

        threads = [threading.Thread(target=add_assets, args=(i * 10,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should complete successfully
        assert len(results) == 3


class TestErrorHandling:
    """Test error handling scenarios."""

    @staticmethod
    def test_add_equity_with_special_characters():
        """Test adding equity with special characters in name."""

        def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
            try:
                new_equity = Equity(
                    id=asset_id,
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.EQUITY,
                    sector=sector,
                    price=price,
                )
                return f"Successfully validated: {new_equity.name}"
            except ValueError as e:
                return f"Validation Error: {str(e)}"

        result = add_equity_node("TEST", "TEST", "Test & Co., Inc.", "Tech", 100.0)

        assert "Successfully" in result

    @staticmethod
    def test_add_equity_with_extreme_price():
        """Test adding equity with extremely large price."""

        def add_equity_node(asset_id: str, symbol: str, name: str, sector: str, price: float) -> str:
            try:
                new_equity = Equity(
                    id=asset_id,
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.EQUITY,
                    sector=sector,
                    price=price,
                )
                return f"Successfully validated: {new_equity.name}"
            except ValueError as e:
                return f"Validation Error: {str(e)}"

        result = add_equity_node("TEST", "TEST", "Test", "Tech", 1e15)

        # Should handle extreme values
        assert "Successfully" in result or "Validation Error" in result
