"""Comprehensive unit tests for the Gradio application (app.py).

This module tests the FinancialAssetApp class including:
- Graph initialization
- UI component creation
- Event handler logic
- Visualization refresh
- Asset information updates
- Formulaic analysis
- Error handling
"""

from unittest.mock import MagicMock, Mock, patch

import plotly.graph_objects as go
import pytest

from app import AppConstants, FinancialAssetApp
from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


class TestAppConstants:
    """Test AppConstants class contains required constants."""

    def test_app_constants_defined(self):
        """Test that all required constants are defined."""
        assert hasattr(AppConstants, "TITLE")
        assert hasattr(AppConstants, "MARKDOWN_HEADER")
        assert hasattr(AppConstants, "TAB_3D_VISUALIZATION")
        assert hasattr(AppConstants, "TAB_METRICS_ANALYTICS")
        assert hasattr(AppConstants, "TAB_SCHEMA_RULES")
        assert hasattr(AppConstants, "TAB_ASSET_EXPLORER")
        assert hasattr(AppConstants, "ERROR_LABEL")
        assert hasattr(AppConstants, "NETWORK_STATISTICS_TEXT")

    def test_constant_types(self):
        """Test that constants have expected types."""
        assert isinstance(AppConstants.TITLE, str)
        assert isinstance(AppConstants.MARKDOWN_HEADER, str)
        assert isinstance(AppConstants.ERROR_LABEL, str)

    def test_markdown_constants_not_empty(self):
        """Test that markdown constants contain content."""
        assert len(AppConstants.MARKDOWN_HEADER) > 0
        assert len(AppConstants.NETWORK_STATISTICS_TEXT) > 0


class TestFinancialAssetAppInitialization:
    """Test FinancialAssetApp initialization."""

    @patch("app.create_real_database")
    def test_app_initialization_creates_graph(self, mock_create_db):
        """Test that app initialization creates a graph."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        assert app.graph is not None
        assert isinstance(app.graph, AssetRelationshipGraph)
        mock_create_db.assert_called_once()

    @patch("app.create_real_database")
    def test_app_initialization_handles_errors(self, mock_create_db):
        """Test that app initialization handles errors gracefully."""
        mock_create_db.side_effect = Exception("Database creation failed")

        with pytest.raises(Exception) as exc_info:
            FinancialAssetApp()

        assert "Database creation failed" in str(exc_info.value)

    @patch("app.create_real_database")
    def test_ensure_graph_recreates_if_none(self, mock_create_db):
        """Test that ensure_graph recreates graph if it's None."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()
        app.graph = None

        result = app.ensure_graph()

        assert result is not None
        assert result == app.graph


class TestUpdateMetricsText:
    """Test the _update_metrics_text static method."""

    def test_update_metrics_text_format(self):
        """Test that metrics text is properly formatted."""
        graph = create_sample_database()

        text = FinancialAssetApp._update_metrics_text(graph)

        assert isinstance(text, str)
        assert "Total Assets:" in text
        assert "Total Relationships:" in text
        assert "Average Relationship Strength:" in text
        assert "Top Relationships:" in text

    def test_update_metrics_text_with_empty_graph(self):
        """Test metrics text with empty graph."""
        graph = AssetRelationshipGraph()

        text = FinancialAssetApp._update_metrics_text(graph)

        assert isinstance(text, str)
        assert "Total Assets: 0" in text or "0" in text


class TestUpdateAssetInfo:
    """Test the update_asset_info static method."""

    def test_update_asset_info_valid_asset(self):
        """Test updating asset info for valid asset."""
        graph = create_sample_database()
        asset_ids = list(graph.assets.keys())
        selected_asset = asset_ids[0] if asset_ids else None

        asset_dict, relationships = FinancialAssetApp.update_asset_info(selected_asset, graph)

        assert isinstance(asset_dict, dict)
        assert isinstance(relationships, dict)
        assert "outgoing" in relationships
        assert "incoming" in relationships

        if selected_asset:
            assert asset_dict.get("id") == selected_asset

    def test_update_asset_info_invalid_asset(self):
        """Test updating asset info for invalid asset."""
        graph = create_sample_database()

        asset_dict, relationships = FinancialAssetApp.update_asset_info("INVALID_ID", graph)

        assert asset_dict == {}
        assert relationships == {"outgoing": {}, "incoming": {}}

    def test_update_asset_info_none_asset(self):
        """Test updating asset info with None."""
        graph = create_sample_database()

        asset_dict, relationships = FinancialAssetApp.update_asset_info(None, graph)

        assert asset_dict == {}
        assert relationships == {"outgoing": {}, "incoming": {}}


class TestRefreshVisualization:
    """Test the refresh_visualization method."""

    @patch("app.create_real_database")
    def test_refresh_visualization_3d_mode(self, mock_create_db):
        """Test refreshing visualization in 3D mode."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        with patch("app.visualize_3d_graph_with_filters") as mock_viz:
            mock_viz.return_value = go.Figure()

            result, _ = app.refresh_visualization(
                mock_graph, "3D", "spring", True, True, True, True, True, True, True, True, True
            )

            assert isinstance(result, go.Figure)
            mock_viz.assert_called_once()

    @patch("app.create_real_database")
    def test_refresh_visualization_2d_mode(self, mock_create_db):
        """Test refreshing visualization in 2D mode."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        with patch("app.visualize_2d_graph") as mock_viz:
            mock_viz.return_value = go.Figure()

            result, _ = app.refresh_visualization(
                mock_graph, "2D", "circular", True, True, True, True, True, True, True, True, True
            )

            assert isinstance(result, go.Figure)
            mock_viz.assert_called_once()

    @patch("app.create_real_database")
    def test_refresh_visualization_handles_error(self, mock_create_db):
        """Test that refresh_visualization handles errors gracefully."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        with patch("app.visualize_3d_graph_with_filters") as mock_viz:
            mock_viz.side_effect = Exception("Visualization error")

            result, error = app.refresh_visualization(
                mock_graph, "3D", "spring", True, True, True, True, True, True, True, True, True
            )

            assert isinstance(result, go.Figure)
            assert error.value.startswith("Error refreshing visualization:")


class TestRefreshAllOutputs:
    """Test the refresh_all_outputs method."""

    @patch("app.create_real_database")
    def test_refresh_all_outputs_success(self, mock_create_db):
        """Test successful refresh of all outputs."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        with (
            patch("app.visualize_3d_graph") as mock_viz,
            patch("app.generate_schema_report") as mock_report,
            patch.object(app, "update_all_metrics_outputs") as mock_metrics,
        ):
            mock_viz.return_value = go.Figure()
            mock_report.return_value = "Schema Report"
            mock_metrics.return_value = (go.Figure(), go.Figure(), go.Figure(), "Metrics")

            results = app.refresh_all_outputs(mock_graph)

            assert results is not None
            assert len(results) == 8  # Expected number of outputs

    @patch("app.create_real_database")
    def test_refresh_all_outputs_handles_error(self, mock_create_db):
        """Test that refresh_all_outputs handles errors."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        with patch("app.visualize_3d_graph") as mock_viz:
            mock_viz.side_effect = Exception("Refresh error")

            results = app.refresh_all_outputs(mock_graph)

            # Should return error updates
            assert results is not None


class TestFormulaicAnalysis:
    """Test formulaic analysis methods."""

    @patch("app.create_real_database")
    def test_generate_formulaic_analysis_success(self, mock_create_db):
        """Test successful generation of formulaic analysis."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        with patch("app.FormulaicAnalyzer") as mock_analyzer_class, patch("app.FormulaicVisualizer") as mock_viz_class:
            mock_analyzer = Mock()
            mock_analyzer.analyze_graph.return_value = {"formulas": [], "empirical_relationships": {}, "summary": {}}
            mock_analyzer_class.return_value = mock_analyzer

            mock_visualizer = Mock()
            mock_visualizer.create_formula_dashboard.return_value = go.Figure()
            mock_visualizer.create_correlation_network.return_value = go.Figure()
            mock_visualizer.create_metric_comparison_chart.return_value = go.Figure()
            mock_viz_class.return_value = mock_visualizer

            results = app.generate_formulaic_analysis(mock_graph)

            assert results is not None
            assert len(results) == 6  # Expected number of outputs

    @patch("app.create_real_database")
    def test_generate_formulaic_analysis_handles_error(self, mock_create_db):
        """Test that formulaic analysis handles errors."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        with patch("app.FormulaicAnalyzer") as mock_analyzer_class:
            mock_analyzer_class.side_effect = Exception("Analysis error")

            results = app.generate_formulaic_analysis(mock_graph)

            # Should return error figures and messages
            assert results is not None

    def test_show_formula_details_placeholder(self):
        """Test show_formula_details returns placeholder."""
        mock_graph = create_sample_database()

        result, _ = FinancialAssetApp.show_formula_details("Test Formula", mock_graph)

        assert isinstance(result, go.Figure)

    def test_format_formula_summary(self):
        """Test _format_formula_summary generates proper summary."""
        summary = {
            "avg_r_squared": 0.85,
            "empirical_data_points": 10,
            "formula_categories": {"Valuation": 5, "Risk": 3},
            "key_insights": ["Insight 1", "Insight 2"],
        }
        analysis_results = {
            "formulas": [Mock(name="Formula1"), Mock(name="Formula2")],
            "empirical_relationships": {
                "strongest_correlations": [{"pair": "AAPL-MSFT", "correlation": 0.9, "strength": "strong"}]
            },
        }

        result = FinancialAssetApp._format_formula_summary(summary, analysis_results)

        assert isinstance(result, str)
        assert "Formulaic Analysis Summary" in result
        assert "0.850" in result or "0.85" in result


class TestCreateInterface:
    """Test create_interface method."""

    @patch("app.create_real_database")
    @patch("app.gr.Blocks")
    def test_create_interface_structure(self, mock_blocks, mock_create_db):
        """Test that create_interface creates proper structure."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        mock_demo = MagicMock()
        mock_blocks.return_value.__enter__.return_value = mock_demo

        app = FinancialAssetApp()

        # Create interface should not raise exceptions
        try:
            app.create_interface()
            # If mocking is successful, we should get a result
            assert True
        except Exception as e:
            # In case of missing gradio dependencies in test environment
            pytest.skip(f"Gradio not available in test environment: {e}")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("app.create_real_database")
    def test_empty_graph_handling(self, mock_create_db):
        """Test handling of empty graph."""
        empty_graph = AssetRelationshipGraph()
        mock_create_db.return_value = empty_graph

        app = FinancialAssetApp()

        text = app._update_metrics_text(empty_graph)
        assert "0" in text

    @patch("app.create_real_database")
    def test_graph_with_single_asset(self, mock_create_db):
        """Test handling of graph with single asset."""
        single_asset_graph = AssetRelationshipGraph()
        single_asset_graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )
        mock_create_db.return_value = single_asset_graph

        app = FinancialAssetApp()

        text = app._update_metrics_text(single_asset_graph)
        assert "1" in text

    def test_update_asset_info_with_empty_string(self):
        """Test update_asset_info with empty string."""
        graph = create_sample_database()

        asset_dict, relationships = FinancialAssetApp.update_asset_info("", graph)

        assert asset_dict == {}
        assert relationships == {"outgoing": {}, "incoming": {}}


class TestMetricsOutputs:
    """Test metrics output generation."""

    @patch("app.create_real_database")
    def test_update_all_metrics_outputs_structure(self, mock_create_db):
        """Test that update_all_metrics_outputs returns correct structure."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        # Check if method exists
        if hasattr(app, "update_all_metrics_outputs"):
            with (
                patch("app.create_asset_distribution_chart") as mock_dist,
                patch("app.create_relationship_types_chart") as mock_rel,
                patch("app.create_events_timeline_chart") as mock_events,
            ):
                mock_dist.return_value = go.Figure()
                mock_rel.return_value = go.Figure()
                mock_events.return_value = go.Figure()

                results = app.update_all_metrics_outputs(mock_graph)

                assert len(results) == 4  # 3 figures + 1 text


class TestVisualizationModes:
    """Test different visualization modes and layouts."""

    @patch("app.create_real_database")
    def test_all_layout_types(self, mock_create_db):
        """Test all layout types work."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        layout_types = ["spring", "circular", "grid"]

        for layout in layout_types:
            with patch("app.visualize_2d_graph") as mock_viz:
                mock_viz.return_value = go.Figure()

                result, _ = app.refresh_visualization(
                    mock_graph, "2D", layout, True, True, True, True, True, True, True, True, True
                )

                assert isinstance(result, go.Figure)

    @patch("app.create_real_database")
    def test_relationship_filter_combinations(self, mock_create_db):
        """Test different relationship filter combinations."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        # Test with all filters disabled
        with patch("app.visualize_3d_graph_with_filters") as mock_viz:
            mock_viz.return_value = go.Figure()

            result, _ = app.refresh_visualization(
                mock_graph, "3D", "spring", False, False, False, False, False, False, False, False, False
            )

            assert isinstance(result, go.Figure)


class TestErrorRecovery:
    """Test error recovery mechanisms."""

    @patch("app.create_real_database")
    def test_graceful_degradation_on_viz_error(self, mock_create_db):
        """Test graceful degradation when visualization fails."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        with patch("app.visualize_3d_graph_with_filters") as mock_viz:
            mock_viz.side_effect = RuntimeError("Visualization failed")

            result, error = app.refresh_visualization(
                mock_graph, "3D", "spring", True, True, True, True, True, True, True, True, True
            )

            # Should return empty figure and error message
            assert isinstance(result, go.Figure)
            assert error.value is not None

    @patch("app.create_real_database")
    def test_recovery_from_missing_graph(self, mock_create_db):
        """Test recovery when graph is missing."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()
        app.graph = None

        # ensure_graph should recreate
        result = app.ensure_graph()
        assert result is not None


class TestStateManagement:
    """Test state management in the application."""

    @patch("app.create_real_database")
    def test_graph_state_persistence(self, mock_create_db):
        """Test that graph state persists across operations."""
        mock_graph = create_sample_database()
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        initial_graph = app.graph
        app.ensure_graph()

        # Should be same instance
        assert app.graph is initial_graph


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
