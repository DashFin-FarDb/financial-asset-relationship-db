"""Comprehensive tests for app.py (Gradio application)"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

# Import the module
from app import AppConstants, FinancialAssetApp


class TestAppConstants:
    """Test AppConstants class."""

    def test_constants_exist(self):
        """Test that all required constants are defined."""
        assert hasattr(AppConstants, "TITLE")
        assert hasattr(AppConstants, "MARKDOWN_HEADER")
        assert hasattr(AppConstants, "TAB_3D_VISUALIZATION")
        assert hasattr(AppConstants, "ERROR_LABEL")

    def test_constant_values(self):
        """Test constant values are strings."""
        assert isinstance(AppConstants.TITLE, str)
        assert isinstance(AppConstants.MARKDOWN_HEADER, str)
        assert len(AppConstants.TITLE) > 0


class TestFinancialAssetAppInit:
    """Test FinancialAssetApp initialization."""

    @patch("app.FinancialAssetApp._create_database")
    def test_init_creates_graph(self, mock_create_db):
        """Test that initialization creates a graph."""
        mock_graph = MagicMock()
        mock_create_db.return_value = mock_graph

        app_instance = FinancialAssetApp()

        assert app_instance.graph == mock_graph
        mock_create_db.assert_called_once()

    @patch("app.FinancialAssetApp._create_database")
    def test_init_handles_creation_error(self, mock_create_db):
        """Test that initialization handles creation errors."""
        mock_create_db.side_effect = Exception("Creation failed")

        with pytest.raises(Exception):
            FinancialAssetApp()


class TestCreateDatabase:
    """Test _create_database static method."""

    @patch("app.real_data_fetcher")
    def test_create_database_tries_multiple_candidates(self, mock_fetcher):
        """Test that _create_database tries multiple function candidates."""
        mock_graph = MagicMock()
        mock_fetcher.create_real_database = Mock(return_value=mock_graph)

        result = FinancialAssetApp._create_database()

        assert result == mock_graph

    @patch("app.real_data_fetcher")
    def test_create_database_raises_when_no_factory_found(self, mock_fetcher):
        """Test that _create_database raises when no factory is found."""
        # Remove all candidate attributes
        for attr in ["create_real_database", "create_sample_database", "create_database"]:
            if hasattr(mock_fetcher, attr):
                delattr(mock_fetcher, attr)

        with pytest.raises(AttributeError, match="No known database factory"):
            FinancialAssetApp._create_database()

    @patch("app.real_data_fetcher")
    def test_create_database_validates_return_type(self, mock_fetcher):
        """Test that _create_database validates return type."""
        from src.logic.asset_graph import AssetRelationshipGraph

        mock_fetcher.create_real_database = Mock(return_value="not a graph")

        with pytest.raises(TypeError, match="expected AssetRelationshipGraph"):
            FinancialAssetApp._create_database()


class TestEnsureGraph:
    """Test ensure_graph method."""

    @patch("app.FinancialAssetApp._create_database")
    def test_ensure_graph_returns_existing(self, mock_create):
        """Test that ensure_graph returns existing graph."""
        mock_graph = MagicMock()
        mock_create.return_value = mock_graph

        app_instance = FinancialAssetApp()
        result = app_instance.ensure_graph()

        assert result == mock_graph
        # Should only create once during init
        assert mock_create.call_count == 1

    @patch("app.FinancialAssetApp._create_database")
    def test_ensure_graph_recreates_if_none(self, mock_create):
        """Test that ensure_graph recreates if graph is None."""
        mock_graph = MagicMock()
        mock_create.return_value = mock_graph

        app_instance = FinancialAssetApp()
        app_instance.graph = None

        result = app_instance.ensure_graph()

        assert result == mock_graph
        # Should be called twice: init + ensure_graph
        assert mock_create.call_count == 2


class TestUpdateMetricsText:
    """Test _update_metrics_text static method."""

    @patch("app.FinancialAssetApp._create_database")
    def test_update_metrics_text_formats_correctly(self, mock_create):
        """Test that _update_metrics_text formats metrics correctly."""
        mock_graph = MagicMock()
        mock_graph.calculate_metrics.return_value = {
            "total_assets": 10,
            "total_relationships": 20,
            "average_relationship_strength": 0.75,
            "relationship_density": 15.5,
            "regulatory_event_count": 3,
            "asset_class_distribution": {"equity": 5, "bond": 5},
            "top_relationships": [
                ("AAPL", "MSFT", "same_sector", 0.8),
                ("AAPL", "GOOGL", "correlation", 0.7),
            ],
        }
        mock_create.return_value = mock_graph

        app_instance = FinancialAssetApp()
        result = app_instance._update_metrics_text(mock_graph)

        assert "Total Assets: 10" in result
        assert "Total Relationships: 20" in result
        assert "0.750" in result  # Average strength
        assert "15.50%" in result  # Density

    @patch("app.FinancialAssetApp._create_database")
    def test_update_metrics_text_handles_missing_data(self, mock_create):
        """Test that _update_metrics_text handles missing data."""
        mock_graph = MagicMock()
        mock_graph.calculate_metrics.return_value = {}
        mock_create.return_value = mock_graph

        app_instance = FinancialAssetApp()
        result = app_instance._update_metrics_text(mock_graph)

        # Should handle missing keys gracefully
        assert "Total Assets: 0" in result


class TestUpdateAssetInfo:
    """Test update_asset_info static method."""

    @patch("app.FinancialAssetApp._create_database")
    def test_update_asset_info_returns_asset_data(self, mock_create):
        """Test that update_asset_info returns asset data."""
        from src.models.financial_models import AssetClass, Equity

        mock_asset = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
        )

        mock_graph = MagicMock()
        mock_graph.assets = {"AAPL": mock_asset}
        mock_graph.relationships = {
            "AAPL": [("MSFT", "same_sector", 0.8)]
        }
        mock_create.return_value = mock_graph

        app_instance = FinancialAssetApp()
        asset_dict, rels = app_instance.update_asset_info("AAPL", mock_graph)

        assert asset_dict["symbol"] == "AAPL"
        assert asset_dict["name"] == "Apple Inc."
        assert "outgoing" in rels
        assert "MSFT" in rels["outgoing"]

    @patch("app.FinancialAssetApp._create_database")
    def test_update_asset_info_handles_missing_asset(self, mock_create):
        """Test that update_asset_info handles missing asset."""
        mock_graph = MagicMock()
        mock_graph.assets = {}
        mock_create.return_value = mock_graph

        app_instance = FinancialAssetApp()
        asset_dict, rels = app_instance.update_asset_info("INVALID", mock_graph)

        assert asset_dict == {}
        assert rels == {"outgoing": {}, "incoming": {}}


class TestRefreshVisualization:
    """Test refresh_visualization method."""

    @patch("app.FinancialAssetApp._create_database")
    @patch("app.visualize_2d_graph")
    @patch("app.visualize_3d_graph_with_filters")
    def test_refresh_visualization_2d(self, mock_3d, mock_2d, mock_create):
        """Test refreshing visualization in 2D mode."""
        mock_graph = MagicMock()
        mock_create.return_value = mock_graph
        mock_fig = MagicMock()
        mock_2d.return_value = mock_fig

        app_instance = FinancialAssetApp()
        result_fig, result_update = app_instance.refresh_visualization(
            mock_graph,
            view_mode="2D",
            layout_type="spring",
            show_same_sector=True,
            show_market_cap=True,
            show_correlation=True,
            show_corporate_bond=True,
            show_commodity_currency=True,
            show_income_comparison=True,
            show_regulatory=True,
            show_all_relationships=True,
            toggle_arrows=True,
        )

        assert result_fig == mock_fig
        mock_2d.assert_called_once()

    @patch("app.FinancialAssetApp._create_database")
    @patch("app.visualize_3d_graph_with_filters")
    def test_refresh_visualization_3d(self, mock_3d, mock_create):
        """Test refreshing visualization in 3D mode."""
        mock_graph = MagicMock()
        mock_create.return_value = mock_graph
        mock_fig = MagicMock()
        mock_3d.return_value = mock_fig

        app_instance = FinancialAssetApp()
        result_fig, result_update = app_instance.refresh_visualization(
            mock_graph,
            view_mode="3D",
            layout_type="spring",
            show_same_sector=True,
            show_market_cap=False,
            show_correlation=False,
            show_corporate_bond=False,
            show_commodity_currency=False,
            show_income_comparison=False,
            show_regulatory=False,
            show_all_relationships=False,
            toggle_arrows=False,
        )

        assert result_fig == mock_fig
        mock_3d.assert_called_once()


class TestGenerateFormulaicAnalysis:
    """Test generate_formulaic_analysis method."""

    @patch("app.FinancialAssetApp._create_database")
    @patch("app.FormulaicAnalyzer")
    @patch("app.FormulaicVisualizer")
    def test_generate_formulaic_analysis_success(self, mock_visualizer_class, mock_analyzer_class, mock_create):
        """Test successful formulaic analysis generation."""
        mock_graph = MagicMock()
        mock_create.return_value = mock_graph

        mock_analyzer = MagicMock()
        mock_visualizer = MagicMock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_visualizer_class.return_value = mock_visualizer

        # Mock analysis results
        mock_formula = MagicMock()
        mock_formula.name = "Test Formula"
        analysis_results = {
            "formulas": [mock_formula],
            "empirical_relationships": {},
            "summary": {"key_insights": []},
        }
        mock_analyzer.analyze_graph.return_value = analysis_results

        # Mock visualizations
        mock_fig = MagicMock()
        mock_visualizer.create_formula_dashboard.return_value = mock_fig
        mock_visualizer.create_correlation_network.return_value = mock_fig
        mock_visualizer.create_metric_comparison_chart.return_value = mock_fig

        app_instance = FinancialAssetApp()
        results = app_instance.generate_formulaic_analysis(mock_graph)

        assert len(results) == 6
        # Verify figures returned
        assert results[0] == mock_fig  # dashboard
        assert results[1] == mock_fig  # correlation
        assert results[2] == mock_fig  # comparison


class TestRefreshAllOutputs:
    """Test refresh_all_outputs method."""

    @patch("app.FinancialAssetApp._create_database")
    @patch("app.visualize_3d_graph")
    @patch("app.visualize_metrics")
    @patch("app.generate_schema_report")
    @patch("app.gr")
    def test_refresh_all_outputs_success(self, mock_gr, mock_schema, mock_metrics, mock_viz, mock_create):
        """Test successful refresh of all outputs."""
        mock_graph = MagicMock()
        mock_graph.assets = {"AAPL": MagicMock(), "MSFT": MagicMock()}
        mock_create.return_value = mock_graph

        mock_fig = MagicMock()
        mock_viz.return_value = mock_fig
        mock_metrics.return_value = (mock_fig, mock_fig, mock_fig)
        mock_schema.return_value = "Schema report"

        mock_gr_update = MagicMock()
        mock_gr.update.return_value = mock_gr_update

        app_instance = FinancialAssetApp()
        results = app_instance.refresh_all_outputs(mock_graph)

        # Should return 8 items
        assert len(results) == 8


class TestCreateInterface:
    """Test create_interface method."""

    @patch("app.FinancialAssetApp._create_database")
    @patch("app.gr.Blocks")
    def test_create_interface_returns_blocks(self, mock_blocks, mock_create):
        """Test that create_interface returns Gradio Blocks."""
        mock_graph = MagicMock()
        mock_create.return_value = mock_graph

        mock_blocks_instance = MagicMock()
        mock_blocks.return_value.__enter__.return_value = mock_blocks_instance

        app_instance = FinancialAssetApp()

        # Mock all gradio components
        with patch("app.gr.Markdown"), \
             patch("app.gr.Textbox"), \
             patch("app.gr.Tabs"), \
             patch("app.gr.Tab"), \
             patch("app.gr.Row"), \
             patch("app.gr.Column"), \
             patch("app.gr.Radio"), \
             patch("app.gr.Checkbox"), \
             patch("app.gr.Plot"), \
             patch("app.gr.Button"), \
             patch("app.gr.Dropdown"), \
             patch("app.gr.JSON"), \
             patch("app.gr.State"):
            result = app_instance.create_interface()

        assert result is not None


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("app.FinancialAssetApp._create_database")
    def test_update_metrics_text_with_none_values(self, mock_create):
        """Test metrics text with None values."""
        mock_graph = MagicMock()
        mock_graph.calculate_metrics.return_value = {
            "total_assets": None,
            "total_relationships": None,
            "average_relationship_strength": None,
        }
        mock_create.return_value = mock_graph

        app_instance = FinancialAssetApp()
        # Should not raise
        result = app_instance._update_metrics_text(mock_graph)
        assert isinstance(result, str)

    @patch("app.FinancialAssetApp._create_database")
    @patch("app.visualize_3d_graph_with_filters")
    def test_refresh_visualization_handles_error(self, mock_viz, mock_create):
        """Test that refresh_visualization handles errors."""
        mock_graph = MagicMock()
        mock_create.return_value = mock_graph
        mock_viz.side_effect = Exception("Visualization error")

        app_instance = FinancialAssetApp()
        result_fig, result_update = app_instance.refresh_visualization(
            mock_graph,
            "3D",
            "spring",
            True, True, True, True, True, True, True, True, True,
        )

        # Should return empty figure and error message
        assert result_fig is not None

    @patch("app.FinancialAssetApp._create_database")
    def test_update_all_metrics_outputs(self, mock_create):
        """
        Verifies that update_all_metrics_outputs produces three metric figures plus a metrics text entry.
        
        Sets up a mocked graph with calculated metrics and patches the visualize_metrics function to return three Plotly figures, then asserts the method returns a list of four items (three figures and one text/summary element).
        """
        from plotly import graph_objects as go

        mock_graph = MagicMock()
        mock_graph.calculate_metrics.return_value = {
            "total_assets": 5,
            "total_relationships": 10,
            "average_relationship_strength": 0.5,
            "relationship_density": 20.0,
            "regulatory_event_count": 2,
            "asset_class_distribution": {},
            "top_relationships": [],
        }
        mock_create.return_value = mock_graph

        with patch("app.visualize_metrics") as mock_viz_metrics:
            mock_fig = go.Figure()
            mock_viz_metrics.return_value = (mock_fig, mock_fig, mock_fig)

            app_instance = FinancialAssetApp()
            results = app_instance.update_all_metrics_outputs(mock_graph)

            assert len(results) == 4  # 3 figures + text

    @patch("app.FinancialAssetApp._create_database")
    def test_format_formula_summary(self, mock_create):
        """Test _format_formula_summary static method."""
        mock_graph = MagicMock()
        mock_create.return_value = mock_graph

        summary = {
            "formula_categories": {"Valuation": 5, "Risk": 3},
            "key_insights": ["Insight 1", "Insight 2"],
        }
        analysis_results = {
            "empirical_relationships": {
                "strongest_correlations": [
                    {"pair": "AAPL-MSFT", "correlation": 0.85, "strength": "strong"}
                ]
            }
        }

        app_instance = FinancialAssetApp()
        result = app_instance._format_formula_summary(summary, analysis_results)

        assert "Valuation: 5" in result
        assert "Insight 1" in result
        assert "AAPL-MSFT" in result

    @patch("app.FinancialAssetApp._create_database")
    @patch("app.FormulaicVisualizer.show_formula_details")
    def test_show_formula_details(self, mock_show_details, mock_create):
        """Test show_formula_details method."""
        from plotly import graph_objects as go

        mock_graph = MagicMock()
        mock_create.return_value = mock_graph

        mock_fig = go.Figure()
        mock_show_details.return_value = mock_fig

        app_instance = FinancialAssetApp()

        with patch("app.gr.update") as mock_update:
            mock_update.return_value = MagicMock()
            result_fig, result_update = app_instance.show_formula_details("Test Formula", mock_graph)

            assert result_fig is not None