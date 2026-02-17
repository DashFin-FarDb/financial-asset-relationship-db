# ruff: noqa: S101
"""Unit tests for mcp_server.py MCP server implementation.

This module contains comprehensive unit tests for the MCP server including:
- ThreadSafeGraph wrapper functionality
- add_equity_node tool validation and execution
- get_3d_layout resource handler
- CLI entry point and argument parsing
- Error handling for missing dependencies
- Thread-safety mechanisms

Note: This test file uses assert statements which is the standard and recommended
approach for pytest. The S101 rule is suppressed because tests are not run with
Python optimization flags that would remove assert statements.
"""

import json
import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


@pytest.mark.unit
class TestThreadSafeGraph:
    """Test cases for the _ThreadSafeGraph wrapper class."""

    @staticmethod
    def test_thread_safe_graph_initialization() -> None:
        """Test that _ThreadSafeGraph initializes correctly."""
        from mcp_server import _ThreadSafeGraph

        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        safe_graph = _ThreadSafeGraph(graph, lock)

        assert safe_graph._graph is graph
        assert safe_graph._lock is lock

    @staticmethod
    def test_thread_safe_graph_callable_attribute_wrapping():
        """Test that callable attributes are wrapped with lock protection."""
        from mcp_server import _ThreadSafeGraph

        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        safe_graph = _ThreadSafeGraph(graph, lock)

        # Access a callable method
        add_asset_method = safe_graph.add_asset

        # Should return a wrapped callable
        assert callable(add_asset_method)

    @staticmethod
    def test_thread_safe_graph_non_callable_attribute_copy():
        """Test that non-callable attributes return defensive copies."""
        from mcp_server import _ThreadSafeGraph

        graph = AssetRelationshipGraph()
        graph.assets = {"TEST": Mock()}
        lock = threading.Lock()
        safe_graph = _ThreadSafeGraph(graph, lock)

        # Access a non-callable attribute
        assets = safe_graph.assets

        # Should be a deep copy, not the same object
        assert assets is not graph.assets
        assert isinstance(assets, dict)

    @staticmethod
    def test_thread_safe_graph_method_execution_under_lock():
        """Test that wrapped methods execute under lock protection."""
        from mcp_server import _ThreadSafeGraph

        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        safe_graph = _ThreadSafeGraph(graph, lock)

        # Track lock acquisition
        lock_acquired = []

        original_acquire = lock.acquire
        original_release = lock.release

        def tracked_acquire(*args, **kwargs):
            """
            Record a lock acquire event by appending "acquired" to the tracking list, then forward the call to the original acquire method.

            Returns:
                The value returned by the original acquire call (e.g., boolean indicating success, or whatever the underlying lock returns).
            """
            lock_acquired.append("acquired")
            return original_acquire(*args, **kwargs)

        def tracked_release(*args, **kwargs):
            """
            Record a lock release event and forward the call to the original release callable.

            Each invocation records a release event in the surrounding tracking list and then calls the original release callable with the provided arguments.

            Returns:
                The value returned by the original release callable.
            """
            lock_acquired.append("released")
            return original_release(*args, **kwargs)

        lock.acquire = tracked_acquire
        lock.release = tracked_release

        # Call a method
        equity = Equity(
            id="TEST",
            symbol="TST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        safe_graph.add_asset(equity)

        # Lock should have been acquired and released
        assert "acquired" in lock_acquired
        assert "released" in lock_acquired


@pytest.mark.unit
class TestAddEquityNode:
    """Test cases for the add_equity_node MCP tool."""

    @staticmethod
    def test_add_equity_node_successful_addition():
        """Test successful equity node addition."""
        from mcp_server import _build_mcp_app, graph

        # Reset graph state
        graph._graph.assets.clear()
        graph._graph.relationships.clear()

        mcp_app = _build_mcp_app()

        # Access the registered tool
        tool_func = next(
            (
                tool.fn
                for tool in mcp_app.list_tools()
                if tool.name == "add_equity_node"
            ),
            None,
        )
        assert tool_func is not None, "add_equity_node tool not found"

        result = tool_func(
            asset_id="AAPL_TEST",
            symbol="AAPL",
            name="Apple Inc Test",
            sector="Technology",
            price=150.0,
        )

        assert "Successfully" in result
        assert "Apple Inc Test" in result
        assert "AAPL" in result

    @staticmethod
    def test_add_equity_node_validation_error_negative_price():
        """Test that validation catches negative price."""
        from mcp_server import _build_mcp_app

        mcp_app = _build_mcp_app()

        tool_func = None
        for tool in mcp_app.list_tools():
            if tool.name == "add_equity_node":
                tool_func = tool.fn
                break

        assert tool_func is not None, "add_equity_node tool not found"
        result = tool_func(
            asset_id="TEST",
            symbol="TST",
            name="Test",
            sector="Tech",
            price=-100.0,  # Invalid negative price
        )

        assert "Validation Error" in result if isinstance(result, str) else False
        assert "price" in result.lower() if isinstance(result, str) else False

    @staticmethod
    def test_add_equity_node_validation_error_empty_id():
        """Test that validation catches empty asset ID."""
        from mcp_server import _build_mcp_app

        mcp_app = _build_mcp_app()

        tool_func = None
        for tool in mcp_app.list_tools():
            if tool.name == "add_equity_node":
                tool_func = tool.fn
                break

        result = tool_func(
            asset_id="",  # Invalid empty ID
            symbol="TST",
            name="Test",
            sector="Tech",
            price=100.0,
        )

        assert "Validation Error" in result
        assert "id" in result.lower()

    @staticmethod
    def test_add_equity_node_fallback_without_add_asset():
        """
        Verify add_equity_node falls back to validation-only behavior when the global graph lacks an add_asset method.

        Asserts the tool returns a message indicating validation-only mode or a success message when invoked against a graph mock that does not provide `add_asset`.
        """
        from mcp_server import _build_mcp_app

        # Create a minimal graph mock without add_asset method
        with patch("mcp_server.graph") as mock_graph:
            # Make getattr return None for add_asset
            mock_graph.__getattr__ = Mock(return_value=None)

            mcp_app = _build_mcp_app()

            tool_func = None
            for tool in mcp_app.list_tools():
                if tool.name == "add_equity_node":
                    tool_func = tool.fn
                    break

            result = tool_func(
                asset_id="TEST",
                symbol="TST",
                name="Test",
                sector="Tech",
                price=100.0,
            )

            # Should indicate validation-only mode
            assert "validation" in result.lower() or "Successfully" in result


@pytest.mark.unit
class TestGet3DLayout:
    """Test cases for the get_3d_layout MCP resource."""

    @staticmethod
    def test_get_3d_layout_returns_valid_json():
        """
        Verify the 3D layout resource returns JSON containing the expected keys and types.

        Asserts that the registered "3d-layout" resource produces JSON with the keys
        `asset_ids`, `positions`, `colors`, and `hover`, and that `asset_ids` and
        `positions` are arrays.
        """
        from mcp_server import _build_mcp_app, graph

        # Add a test asset
        equity = Equity(
            id="TEST",
            symbol="TST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        graph._graph.assets["TEST"] = equity

        mcp_app = _build_mcp_app()

        # Access the registered resource
        resource_func = next(
            (
                resource.fn
                for resource in mcp_app.list_resources()
                if "3d-layout" in resource.uri
            ),
            None,
        )
        assert resource_func is not None, "3d-layout resource not found"

        result = resource_func()

        # Should return valid JSON
        data = json.loads(result)
        assert "asset_ids" in data
        assert "positions" in data
        assert "colors" in data
        assert "hover" in data
        assert isinstance(data["asset_ids"], list)
        assert isinstance(data["positions"], list)

    @staticmethod
    def test_get_3d_layout_structure():
        """Test the structure of data returned by get_3d_layout."""
        from mcp_server import _build_mcp_app, graph

        # Clear and add test assets
        graph._graph.assets.clear()
        equity1 = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=150.0,
        )
        equity2 = Equity(
            id="MSFT",
            symbol="MSFT",
            name="Microsoft",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=300.0,
        )
        graph._graph.assets["AAPL"] = equity1
        graph._graph.assets["MSFT"] = equity2

        mcp_app = _build_mcp_app()

        resource_func = None
        for resource in mcp_app.list_resources():
            if "3d-layout" in resource.uri:
                resource_func = resource.fn
                break

        result = resource_func()
        data = json.loads(result)

        # Verify structure
        assert len(data["asset_ids"]) == len(data["positions"])
        assert len(data["asset_ids"]) == len(data["colors"])
        assert len(data["asset_ids"]) == len(data["hover"])

        # Verify positions are 3D coordinates
        for pos in data["positions"]:
            assert len(pos) == 3  # x, y, z coordinates


@pytest.mark.unit
class TestMainCLI:
    """Test cases for the MCP server CLI entry point."""

    @staticmethod
    def test_main_with_version_flag():
        """Test main function with --version flag."""
        from mcp_server import main

        result = main(["--version"])

        assert result == 0

    @staticmethod
    def test_main_without_version_runs_server():
        """Test main function runs server when no version flag."""
        from mcp_server import main

        with patch("mcp_server._build_mcp_app") as mock_build:
            mock_mcp = MagicMock()
            mock_build.return_value = mock_mcp

            result = main([])

            assert result == 0
            mock_mcp.run.assert_called_once()

    @staticmethod
    def test_main_handles_missing_mcp_dependency():
        """Test main function handles missing MCP dependency gracefully."""
        from mcp_server import main

        with patch("mcp_server._build_mcp_app") as mock_build:
            # Simulate ModuleNotFoundError
            error = ModuleNotFoundError("No module named 'mcp'")
            error.name = "mcp"
            mock_build.side_effect = error

            with pytest.raises(SystemExit) as exc_info:
                main([])

            # Should exit with error message
            assert "Missing dependency" in str(exc_info.value)

    @staticmethod
    def test_main_argument_parsing():
        """Test that main correctly parses command line arguments."""
        from mcp_server import main

        # Test with empty argv (no arguments)
        with patch("mcp_server._build_mcp_app") as mock_build:
            mock_mcp = MagicMock()
            mock_build.return_value = mock_mcp

            result = main([])

            assert result == 0

    @staticmethod
    def test_main_with_none_argv():
        """Test main function with None argv (uses sys.argv)."""
        from mcp_server import main

        with patch("sys.argv", ["mcp_server.py", "--version"]):
            result = main(None)

            assert result == 0


@pytest.mark.unit
class TestBuildMcpApp:
    """Test cases for _build_mcp_app function."""

    @staticmethod
    def test_build_mcp_app_creates_fastmcp_instance():
        """Test that _build_mcp_app creates a FastMCP instance."""
        from mcp_server import _build_mcp_app

        mcp_app = _build_mcp_app()

        assert mcp_app is not None
        assert hasattr(mcp_app, "run")
        assert hasattr(mcp_app, "list_tools")
        assert hasattr(mcp_app, "list_resources")

    @staticmethod
    def test_build_mcp_app_registers_add_equity_tool():
        """Test that add_equity_node tool is registered."""
        from mcp_server import _build_mcp_app

        mcp_app = _build_mcp_app()

        tools = mcp_app.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "add_equity_node" in tool_names

    @staticmethod
    def test_build_mcp_app_registers_3d_layout_resource():
        """Test that 3d-layout resource is registered."""
        from mcp_server import _build_mcp_app

        mcp_app = _build_mcp_app()

        resources = mcp_app.list_resources()
        resource_uris = [resource.uri for resource in resources]

        assert any("3d-layout" in uri for uri in resource_uris)

    @staticmethod
    def test_build_mcp_app_tool_has_correct_signature():
        """
        Verify the registered "add_equity_node" tool exposes the expected function parameters.

        Builds the MCP app, locates the tool named "add_equity_node", and confirms the tool's callable `fn`
        accepts the parameters: `asset_id`, `symbol`, `name`, `sector`, and `price`.
        """
        from mcp_server import _build_mcp_app

        mcp_app = _build_mcp_app()

        tool = None
        for t in mcp_app.list_tools():
            if t.name == "add_equity_node":
                tool = t
                break

        assert tool is not None

        # Check that tool function has expected parameters
        import inspect

        sig = inspect.signature(tool.fn)
        params = list(sig.parameters.keys())

        assert "asset_id" in params
        assert "symbol" in params
        assert "name" in params
        assert "sector" in params
        assert "price" in params


@pytest.mark.unit
class TestGlobalGraphInstance:
    """Test cases for the global graph instance."""

    @staticmethod
    def test_global_graph_is_thread_safe():
        """Test that global graph instance is a ThreadSafeGraph."""
        from mcp_server import _ThreadSafeGraph, graph

        assert isinstance(graph, _ThreadSafeGraph)

    @staticmethod
    def test_global_graph_uses_shared_lock():
        """Test that global graph uses the shared lock."""
        from mcp_server import _graph_lock, graph

        assert graph._lock is _graph_lock

    @staticmethod
    def test_global_graph_wraps_asset_relationship_graph():
        """Test that global graph wraps AssetRelationshipGraph."""
        from mcp_server import graph

        assert isinstance(graph._graph, AssetRelationshipGraph)


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error conditions."""

    @staticmethod
    def test_thread_safe_graph_with_exception_in_method():
        """Test that lock is released even if wrapped method raises exception."""
        from mcp_server import _ThreadSafeGraph

        graph = AssetRelationshipGraph()
        lock = threading.Lock()
        safe_graph = _ThreadSafeGraph(graph, lock)

        # Calling add_asset with invalid data should raise ValueError, but the
        # lock must still be released after the exception.
        with pytest.raises(ValueError):
            safe_graph.add_asset(None)

        # Lock should not be held after exception
        acquired = lock.acquire(blocking=False)
        if acquired:
            lock.release()
        assert acquired, "Lock was not released after exception"

    @staticmethod
    def test_add_equity_node_with_special_characters():
        """Test add_equity_node with special characters in name."""
        from mcp_server import _build_mcp_app

        mcp_app = _build_mcp_app()

        tool_func = None
        for tool in mcp_app.list_tools():
            if tool.name == "add_equity_node":
                tool_func = tool.fn
                break

        result = tool_func(
            asset_id="TEST_SPECIAL",
            symbol="TST",
            name="Test & Company, Inc.",
            sector="Technology",
            price=100.0,
        )

        # Should handle special characters without error
        assert "Validation Error" not in result

    @staticmethod
    def test_get_3d_layout_with_empty_graph():
        """Test get_3d_layout with empty graph."""
        from mcp_server import _build_mcp_app, graph

        # Clear graph
        graph._graph.assets.clear()
        graph._graph.relationships.clear()

        mcp_app = _build_mcp_app()

        resource_func = None
        for resource in mcp_app.list_resources():
            if "3d-layout" in resource.uri:
                resource_func = resource.fn
                break

        result = resource_func()
        data = json.loads(result)

        # Should return valid structure even with empty graph
        assert "asset_ids" in data
        assert "positions" in data
        assert "colors" in data
        assert "hover" in data

    @staticmethod
    def test_main_with_invalid_arguments():
        """Test main function with unrecognized arguments."""
        from mcp_server import main

        # Should handle unrecognized arguments gracefully
        with pytest.raises(SystemExit):
            main(["--invalid-arg"])

    @staticmethod
    def test_add_equity_node_with_very_large_price():
        """Test add_equity_node with very large price value (boundary case)."""
        from mcp_server import _build_mcp_app

        mcp_app = _build_mcp_app()

        tool_func = None
        for tool in mcp_app.list_tools():
            if tool.name == "add_equity_node":
                tool_func = tool.fn
                break

        result = tool_func(
            asset_id="TEST_LARGE_PRICE",
            symbol="TLP",
            name="Large Price Company",
            sector="Technology",
            price=1e15,  # Very large price
        )

        # Should accept very large valid price
        assert "Validation Error" not in result
        assert "Successfully" in result
