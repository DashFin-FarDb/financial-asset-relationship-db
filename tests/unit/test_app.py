# ruff: noqa: S101
"""Unit tests for the main Gradio application (app.py).

This module contains comprehensive unit tests for:
- AppConstants class and all constant values
- FinancialAssetApp initialization and graph creation
- Database factory pattern with fallback logic
- Metrics text generation and formatting
- Asset information retrieval
- Error handling and edge cases
- UI update logic

Note: This test file uses assert statements which is the standard and recommended
approach for pytest. The S101 rule is suppressed because tests are not run with
Python optimization flags that would remove assert statements.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from app import AppConstants, FinancialAssetApp


@pytest.mark.unit
class TestAppConstants:
    """Test cases for AppConstants class."""

    @staticmethod
    def test_title_constant():
        """Test that TITLE constant is defined and non-empty."""
        assert hasattr(AppConstants, "TITLE")
        assert isinstance(AppConstants.TITLE, str)
        assert len(AppConstants.TITLE) > 0

    @staticmethod
    def test_markdown_header_constant():
        """Test that MARKDOWN_HEADER contains expected content."""
        assert hasattr(AppConstants, "MARKDOWN_HEADER")
        assert isinstance(AppConstants.MARKDOWN_HEADER, str)
        assert "Financial" in AppConstants.MARKDOWN_HEADER
        assert "Asset" in AppConstants.MARKDOWN_HEADER

    @staticmethod
    def test_tab_constants_defined():
        """Test that all tab label constants are defined."""
        expected_tabs = [
            "TAB_3D_VISUALIZATION",
            "TAB_METRICS_ANALYTICS",
            "TAB_SCHEMA_RULES",
            "TAB_ASSET_EXPLORER",
            "TAB_DOCUMENTATION",
        ]
        for tab in expected_tabs:
            assert hasattr(AppConstants, tab)
            assert isinstance(getattr(AppConstants, tab), str)
            assert len(getattr(AppConstants, tab)) > 0

    @staticmethod
    def test_label_constants_defined():
        """Test that all UI label constants are defined."""
        expected_labels = [
            "ERROR_LABEL",
            "REFRESH_BUTTON_LABEL",
            "GENERATE_SCHEMA_BUTTON_LABEL",
            "SELECT_ASSET_LABEL",
            "ASSET_DETAILS_LABEL",
            "RELATED_ASSETS_LABEL",
            "NETWORK_STATISTICS_LABEL",
            "SCHEMA_REPORT_LABEL",
        ]
        for label in expected_labels:
            assert hasattr(AppConstants, label)
            assert isinstance(getattr(AppConstants, label), str)
            assert len(getattr(AppConstants, label)) > 0

    @staticmethod
    def test_error_message_constants():
        """Test that error message constants are defined."""
        error_constants = [
            "INITIAL_GRAPH_ERROR",
            "REFRESH_OUTPUTS_ERROR",
            "APP_START_ERROR",
        ]
        for error_const in error_constants:
            assert hasattr(AppConstants, error_const)
            assert isinstance(getattr(AppConstants, error_const), str)
            assert len(getattr(AppConstants, error_const)) > 0

    @staticmethod
    def test_info_message_constants():
        """Test that info message constants are defined."""
        info_constants = [
            "APP_START_INFO",
            "APP_LAUNCH_INFO",
        ]
        for info_const in info_constants:
            assert hasattr(AppConstants, info_const)
            assert isinstance(getattr(AppConstants, info_const), str)

    @staticmethod
    def test_markdown_documentation_constants():
        """Test that all markdown documentation constants are defined."""
        doc_constants = [
            "INTERACTIVE_3D_GRAPH_MD",
            "NETWORK_METRICS_ANALYSIS_MD",
            "SCHEMA_RULES_GUIDE_MD",
            "DETAILED_ASSET_INFO_MD",
            "DOC_MARKDOWN",
        ]
        for doc_const in doc_constants:
            assert hasattr(AppConstants, doc_const)
            assert isinstance(getattr(AppConstants, doc_const), str)
            assert len(getattr(AppConstants, doc_const)) > 0

    @staticmethod
    def test_network_statistics_template():
        """Test that network statistics template has placeholders."""
        assert hasattr(AppConstants, "NETWORK_STATISTICS_TEXT")
        template = AppConstants.NETWORK_STATISTICS_TEXT
        assert "{total_assets}" in template
        assert "{total_relationships}" in template
        assert "{average_relationship_strength}" in template
        assert "{relationship_density}" in template
        assert "{regulatory_event_count}" in template
        assert "{asset_class_distribution}" in template

    @staticmethod
    def test_documentation_includes_quick_start():
        """Test that documentation markdown includes quick start guide."""
        assert "Quick Start" in AppConstants.DOC_MARKDOWN
        assert "Features" in AppConstants.DOC_MARKDOWN

    @staticmethod
    def test_asset_colors_documented():
        """Test that asset colors are documented in 3D graph markdown."""
        md = AppConstants.INTERACTIVE_3D_GRAPH_MD
        assert "Blue" in md or "Equities" in md
        assert "Asset Colors:" in md or "node" in md.lower()


@pytest.mark.unit
class TestFinancialAssetAppInitialization:
    """Test cases for FinancialAssetApp initialization."""

    @staticmethod
    @patch("app.real_data_fetcher")
    def test_app_initialization_creates_graph(mock_fetcher):
        """Test that app initialization creates an asset graph."""
        mock_graph = MagicMock()
        mock_graph.assets = {"TEST_001": MagicMock()}
        mock_fetcher.create_real_database = Mock(return_value=mock_graph)

        app = FinancialAssetApp()

        assert app.graph is not None
        assert app.graph == mock_graph

    @staticmethod
    @patch("app.real_data_fetcher")
    def test_app_initialization_with_sample_database(mock_fetcher):
        """Test that app falls back to create_sample_database."""
        mock_graph = MagicMock()
        mock_graph.assets = {}

        # Remove create_real_database, add create_sample_database
        del mock_fetcher.create_real_database
        mock_fetcher.create_sample_database = Mock(return_value=mock_graph)

        app = FinancialAssetApp()

        assert app.graph is not None
        mock_fetcher.create_sample_database.assert_called_once()

    @staticmethod
    @patch("app.real_data_fetcher")
    def test_create_database_tries_multiple_candidates(mock_fetcher):
        """Test that _create_database tries multiple function names."""
        mock_graph = MagicMock()

        # Only third candidate exists
        del mock_fetcher.create_real_database
        del mock_fetcher.create_sample_database
        mock_fetcher.create_database = Mock(return_value=mock_graph)

        result = FinancialAssetApp._create_database()

        assert result == mock_graph
        mock_fetcher.create_database.assert_called_once()

    @staticmethod
    @patch("app.real_data_fetcher")
    def test_create_database_raises_if_no_factory_found(mock_fetcher):
        """Test that _create_database raises AttributeError if no factory exists."""
        # Remove all candidate functions
        for attr in [
            "create_real_database",
            "create_sample_database",
            "create_database",
            "create_real_data_database",
        ]:
            if hasattr(mock_fetcher, attr):
                delattr(mock_fetcher, attr)

        with pytest.raises(AttributeError, match="No known database factory found"):
            FinancialAssetApp._create_database()

    @staticmethod
    @patch("app.real_data_fetcher")
    def test_create_database_raises_if_wrong_type_returned(mock_fetcher):
        """Test that _create_database raises TypeError if return type is wrong."""
        mock_fetcher.create_real_database = Mock(return_value="not a graph")

        with pytest.raises(TypeError, match="expected AssetRelationshipGraph"):
            FinancialAssetApp._create_database()

    @staticmethod
    @patch("app.real_data_fetcher")
    def test_ensure_graph_returns_existing_graph(mock_fetcher):
        """Test that ensure_graph returns existing graph without recreation."""
        mock_graph = MagicMock()
        mock_graph.assets = {}
        mock_fetcher.create_real_database = Mock(return_value=mock_graph)

        app = FinancialAssetApp()
        original_graph = app.graph

        result = app.ensure_graph()

        assert result is original_graph
        assert mock_fetcher.create_real_database.call_count == 1  # Only initial call

    @staticmethod
    @patch("app.real_data_fetcher")
    def test_ensure_graph_recreates_if_none(mock_fetcher):
        """Test that ensure_graph recreates graph if it's None."""
        mock_graph = MagicMock()
        mock_graph.assets = {}
        mock_fetcher.create_real_database = Mock(return_value=mock_graph)

        app = FinancialAssetApp()
        app.graph = None

        result = app.ensure_graph()

        assert result is not None
        assert result == mock_graph


@pytest.mark.unit
class TestUpdateMetricsText:
    """Test cases for metrics text generation."""

    @staticmethod
    def test_update_metrics_text_with_valid_data():
        """Test metrics text generation with valid data."""
        mock_graph = MagicMock()
        mock_graph.calculate_metrics.return_value = {
            "total_assets": 100,
            "total_relationships": 250,
            "average_relationship_strength": 0.75,
            "relationship_density": 45.5,
            "regulatory_event_count": 10,
            "asset_class_distribution": {"EQUITY": 50, "BOND": 30},
            "top_relationships": [
                ("AAPL", "GOOGL", "SAME_SECTOR", 0.95),
                ("MSFT", "AMZN", "CORRELATION", 0.88),
            ],
        }

        text = FinancialAssetApp._update_metrics_text(mock_graph)

        assert "Total Assets: 100" in text
        assert "Total Relationships: 250" in text
        assert "0.750" in text  # average strength
        assert "45.50%" in text  # density
        assert "Regulatory Events: 10" in text
        assert "AAPL → GOOGL" in text
        assert "95.0%" in text

    @staticmethod
    def test_update_metrics_text_with_missing_data():
        """Test metrics text generation with missing fields."""
        mock_graph = MagicMock()
        mock_graph.calculate_metrics.return_value = {
            "total_assets": 0,
            "total_relationships": 0,
        }

        text = FinancialAssetApp._update_metrics_text(mock_graph)

        assert "Total Assets: 0" in text
        assert "Total Relationships: 0" in text

    @staticmethod
    def test_update_metrics_text_with_invalid_relationship_format():
        """Test metrics text handles invalid relationship format gracefully."""
        mock_graph = MagicMock()
        mock_graph.calculate_metrics.return_value = {
            "total_assets": 10,
            "total_relationships": 5,
            "average_relationship_strength": 0.5,
            "relationship_density": 25.0,
            "regulatory_event_count": 2,
            "asset_class_distribution": {},
            "top_relationships": [
                ("AAPL", "GOOGL"),  # Invalid: missing rel_type and strength
                "invalid_format",  # Invalid: not a tuple
            ],
        }

        # Should not raise exception
        text = FinancialAssetApp._update_metrics_text(mock_graph)
        assert "Total Assets: 10" in text


@pytest.mark.unit
class TestUpdateAssetInfo:
    """Test cases for asset information retrieval."""

    @staticmethod
    def test_update_asset_info_with_valid_asset():
        """Test retrieving info for a valid asset."""
        from src.models.financial_models import Asset, AssetClass

        mock_asset = Asset(
            id="TEST_001",
            symbol="TEST",
            name="Test Asset",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )

        mock_graph = MagicMock()
        mock_graph.assets = {"TEST_001": mock_asset}
        mock_graph.relationships = {
            "TEST_001": [
                ("TEST_002", "SAME_SECTOR", 0.8),
            ]
        }

        asset_dict, relationships = FinancialAssetApp.update_asset_info(
            "TEST_001", mock_graph
        )

        assert asset_dict["id"] == "TEST_001"
        assert asset_dict["symbol"] == "TEST"
        assert asset_dict["asset_class"] == AssetClass.EQUITY.value
        assert "TEST_002" in relationships["outgoing"]
        assert (
            relationships["outgoing"]["TEST_002"]["relationship_type"] == "SAME_SECTOR"
        )
        assert relationships["outgoing"]["TEST_002"]["strength"] == 0.8

    @staticmethod
    def test_update_asset_info_with_nonexistent_asset():
        """Test retrieving info for nonexistent asset."""
        mock_graph = MagicMock()
        mock_graph.assets = {}

        asset_dict, relationships = FinancialAssetApp.update_asset_info(
            "NONEXISTENT", mock_graph
        )

        assert asset_dict == {}
        assert relationships == {"outgoing": {}, "incoming": {}}

    @staticmethod
    def test_update_asset_info_with_none_selected():
        """Test retrieving info when no asset is selected."""
        mock_graph = MagicMock()
        mock_graph.assets = {"TEST_001": MagicMock()}

        asset_dict, relationships = FinancialAssetApp.update_asset_info(
            None, mock_graph
        )

        assert asset_dict == {}
        assert relationships == {"outgoing": {}, "incoming": {}}

    @staticmethod
    def test_update_asset_info_with_incoming_relationships():
        """Test retrieving asset info with incoming relationships if available."""
        from src.models.financial_models import Asset, AssetClass

        mock_asset = Asset(
            id="TEST_001",
            symbol="TEST",
            name="Test Asset",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )

        mock_graph = MagicMock()
        mock_graph.assets = {"TEST_001": mock_asset}
        mock_graph.relationships = {"TEST_001": []}
        mock_graph.incoming_relationships = {
            "TEST_001": [
                ("TEST_003", "CORRELATION", 0.7),
            ]
        }

        asset_dict, relationships = FinancialAssetApp.update_asset_info(
            "TEST_001", mock_graph
        )

        assert "TEST_003" in relationships["incoming"]
        assert (
            relationships["incoming"]["TEST_003"]["relationship_type"] == "CORRELATION"
        )


@pytest.mark.unit
class TestRefreshVisualization:
    """Test cases for visualization refresh logic."""

    @staticmethod
    @patch("app.visualize_2d_graph")
    @patch("app.real_data_fetcher")
    def test_refresh_visualization_2d_mode(mock_fetcher, mock_viz_2d):
        """Test refresh visualization in 2D mode."""
        import plotly.graph_objects as go

        mock_graph = MagicMock()
        mock_graph.assets = {}
        mock_fetcher.create_real_database = Mock(return_value=mock_graph)

        mock_fig = go.Figure()
        mock_viz_2d.return_value = mock_fig

        app = FinancialAssetApp()
        result_fig, error_update = app.refresh_visualization(
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
            toggle_arrows=False,
        )

        assert result_fig == mock_fig
        mock_viz_2d.assert_called_once()

    @staticmethod
    @patch("app.visualize_3d_graph_with_filters")
    @patch("app.real_data_fetcher")
    def test_refresh_visualization_3d_mode(mock_fetcher, mock_viz_3d):
        """Test refresh visualization in 3D mode."""
        import plotly.graph_objects as go

        mock_graph = MagicMock()
        mock_graph.assets = {}
        mock_fetcher.create_real_database = Mock(return_value=mock_graph)

        mock_fig = go.Figure()
        mock_viz_3d.return_value = mock_fig

        app = FinancialAssetApp()
        result_fig, error_update = app.refresh_visualization(
            mock_graph,
            view_mode="3D",
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
        mock_viz_3d.assert_called_once()

    @staticmethod
    @patch("app.visualize_2d_graph")
    @patch("app.real_data_fetcher")
    def test_refresh_visualization_handles_errors(mock_fetcher, mock_viz_2d):
        """Test that refresh visualization handles errors gracefully."""
        mock_graph = MagicMock()
        mock_graph.assets = {}
        mock_fetcher.create_real_database = Mock(return_value=mock_graph)

        mock_viz_2d.side_effect = Exception("Visualization error")

        app = FinancialAssetApp()
        result_fig, error_update = app.refresh_visualization(
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
            toggle_arrows=False,
        )

        # Should return empty figure and error message
        assert result_fig is not None


@pytest.mark.unit
class TestFormulaSummaryFormatting:
    """Test cases for formula summary text formatting."""

    @staticmethod
    def test_format_formula_summary_with_complete_data():
        """Test formatting formula summary with all fields present."""
        summary = {
            "formula_categories": {
                "Financial Ratios": 5,
                "Valuation Models": 3,
            },
            "key_insights": [
                "Strong correlation between tech stocks",
                "High P/E ratios in growth sector",
            ],
        }
        analysis_results = {
            "empirical_relationships": {
                "strongest_correlations": [
                    {
                        "pair": "AAPL-GOOGL",
                        "correlation": 0.95,
                        "strength": "Very Strong",
                    },
                    {"pair": "MSFT-AMZN", "correlation": 0.88, "strength": "Strong"},
                ]
            }
        }

        text = FinancialAssetApp._format_formula_summary(summary, analysis_results)

        assert "Financial Ratios: 5 formulas" in text
        assert "Valuation Models: 3 formulas" in text
        assert "Strong correlation between tech stocks" in text
        assert "AAPL-GOOGL: 0.950 (Very Strong)" in text

    @staticmethod
    def test_format_formula_summary_with_missing_fields():
        """Test formatting formula summary with missing fields."""
        summary = {}
        analysis_results = {}

        # Should not raise exception
        text = FinancialAssetApp._format_formula_summary(summary, analysis_results)

        assert isinstance(text, str)
        assert "Key Insights:" in text

    @staticmethod
    def test_format_formula_summary_with_invalid_correlation_data():
        """Test formatting handles invalid correlation data gracefully."""
        summary = {"key_insights": []}
        analysis_results = {
            "empirical_relationships": {
                "strongest_correlations": [
                    {"pair": "TEST", "correlation": "invalid", "strength": "Strong"},
                    "not_a_dict",
                ]
            }
        }

        # Should not raise exception
        text = FinancialAssetApp._format_formula_summary(summary, analysis_results)
        assert isinstance(text, str)


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @staticmethod
    @patch("app.real_data_fetcher")
    def test_initialization_logs_error_on_failure(mock_fetcher, caplog):
        """Test that initialization failure is logged."""
        mock_fetcher.create_real_database = Mock(
            side_effect=Exception("Database error")
        )

        with pytest.raises(Exception, match="Database error"):
            FinancialAssetApp()

        assert (
            "Failed to create sample database" in caplog.text
            or "Database error" in caplog.text
        )

    @staticmethod
    @patch("app.real_data_fetcher")
    def test_empty_graph_handled_correctly(mock_fetcher):
        """Test that empty graph (no assets) is handled correctly."""
        mock_graph = MagicMock()
        mock_graph.assets = {}
        mock_graph.relationships = {}
        mock_graph.calculate_metrics.return_value = {
            "total_assets": 0,
            "total_relationships": 0,
            "average_relationship_strength": 0.0,
            "relationship_density": 0.0,
            "regulatory_event_count": 0,
            "asset_class_distribution": {},
            "top_relationships": [],
        }
        mock_fetcher.create_real_database = Mock(return_value=mock_graph)

        app = FinancialAssetApp()
        text = app._update_metrics_text(mock_graph)

        assert "Total Assets: 0" in text

    @staticmethod
    def test_update_asset_info_with_empty_string_id():
        """Test update_asset_info with empty string asset ID."""
        mock_graph = MagicMock()
        mock_graph.assets = {"": MagicMock()}

        asset_dict, relationships = FinancialAssetApp.update_asset_info("", mock_graph)

        # Empty string should be treated as falsy
        assert asset_dict == {}
        assert relationships == {"outgoing": {}, "incoming": {}}
