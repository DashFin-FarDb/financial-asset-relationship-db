"""Comprehensive unit tests for app.py Gradio application.

This module tests:
- Application initialization and graph setup
- Metrics calculation and formatting
- Asset information retrieval
- Visualization data generation
- Formulaic analysis features
- UI component interactions
- Edge cases and error handling
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app import AppConstants, FinancialAssetApp
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Bond, Equity

`@pytest.mark.unit`
class TestUpdateAssetInfo:
    """Test the update_asset_info method."""

    @patch('app.create_real_database')
    def test_update_asset_info_returns_asset_details(self, mock_create_db):
        """Test that update_asset_info returns asset dict and relationships."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        asset = Equity(
            id='AAPL',
            symbol='AAPL',
            name='Apple Inc.',
            asset_class=AssetClass.EQUITY,
            sector='Technology',
            price=150.0,
        )
        mock_graph.assets = {'AAPL': asset}
        mock_graph.relationships = {
            'AAPL': [('GOOGL', 'same_sector', 0.8)]
        }
        mock_graph.incoming_relationships = {
            'AAPL': [('MSFT', 'correlation', 0.7)]
        }
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()
        asset_dict, relationships = app.update_asset_info('AAPL', mock_graph)

        assert asset_dict['id'] == 'AAPL'
        assert asset_dict['symbol'] == 'AAPL'
        assert 'outgoing' in relationships
        assert 'incoming' in relationships
        assert 'GOOGL' in relationships['outgoing']
        assert 'MSFT' in relationships['incoming']

    @patch('app.create_real_database')
    def test_update_asset_info_nonexistent_asset(self, mock_create_db):
        """Test that update_asset_info returns empty dicts for nonexistent asset."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()
        asset_dict, relationships = app.update_asset_info('NONEXISTENT', mock_graph)

        assert asset_dict == {}
        assert relationships == {'outgoing': {}, 'incoming': {}}

    @patch('app.create_real_database')
    def test_update_asset_info_none_selected(self, mock_create_db):
        """Test that update_asset_info returns empty dicts when None selected."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()
        asset_dict, relationships = app.update_asset_info(None, mock_graph)

        assert asset_dict == {}
        assert relationships == {'outgoing': {}, 'incoming': {}}

    @patch('app.create_real_database')
    def test_update_asset_info_asset_with_no_relationships(self, mock_create_db):
        """Test update_asset_info for asset with no relationships."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        asset = Equity(
            id='ISOLATED',
            symbol='ISO',
            name='Isolated Asset',
            asset_class=AssetClass.EQUITY,
            sector='Misc',
            price=100.0,
        )
        mock_graph.assets = {'ISOLATED': asset}
        mock_graph.relationships = {}
        mock_graph.incoming_relationships = {}
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()
        asset_dict, relationships = app.update_asset_info('ISOLATED', mock_graph)

        assert asset_dict['id'] == 'ISOLATED'
        assert relationships['outgoing'] == {}
        assert relationships['incoming'] == {}


class TestRefreshAllOutputs:
    """Test the refresh_all_outputs method."""

    @patch('app.create_real_database')
    @patch('app.visualize_3d_graph')
    @patch('app.visualize_2d_graph')
    @patch('app.visualize_metrics')
    @patch('app.generate_schema_report')
    def test_refresh_all_outputs_calls_all_visualizations(
        self, mock_schema, mock_metrics, mock_2d, mock_3d, mock_create_db
    ):
        """Test that refresh_all_outputs calls all visualization functions."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_graph.calculate_metrics.return_value = {
            'total_assets': 10,
            'total_relationships': 5,
            'average_relationship_strength': 0.5,
            'relationship_density': 0.3,
            'regulatory_event_count': 1,
            'asset_class_distribution': {'EQUITY': 10},
            'top_relationships': []
        }
        mock_create_db.return_value = mock_graph

        mock_3d.return_value = Mock()
        mock_2d.return_value = Mock()
        mock_metrics.return_value = (Mock(), Mock(), Mock())
        mock_schema.return_value = "Schema Report"

        app = FinancialAssetApp()
        result = app.refresh_all_outputs(mock_graph)

        # Check that all visualization functions were called
        mock_3d.assert_called_once()
        mock_2d.assert_called_once()
        mock_metrics.assert_called_once()
        mock_schema.assert_called_once()

        # Result should be a tuple with multiple elements
        assert isinstance(result, tuple)


class TestRefreshVisualization:
    """Test the refresh_visualization method."""

    @patch('app.create_real_database')
    @patch('app.visualize_3d_graph_with_filters')
    def test_refresh_visualization_with_all_filters(
        self, mock_visualize, mock_create_db
    ):
        """Test refresh_visualization with 3D view and all relationships enabled."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        mock_fig = Mock()
        mock_visualize.return_value = mock_fig

        app = FinancialAssetApp()
        graph_viz, error_state = app.refresh_visualization(
            graph_state=mock_graph,
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

        assert graph_viz is mock_fig
        mock_visualize.assert_called_once()
        assert error_state is not None

    @patch('app.create_real_database')
    @patch('app.visualize_3d_graph_with_filters')
    def test_refresh_visualization_with_no_filters(
        self, mock_visualize, mock_create_db
    ):
        """Test refresh_visualization with 3D view and all filters disabled."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        mock_fig = Mock()
        mock_visualize.return_value = mock_fig

        app = FinancialAssetApp()
        graph_viz, _ = app.refresh_visualization(
            graph_state=mock_graph,
            view_mode="3D",
            layout_type="spring",
            show_same_sector=False,
            show_market_cap=False,
            show_correlation=False,
            show_corporate_bond=False,
            show_commodity_currency=False,
            show_income_comparison=False,
            show_regulatory=False,
            show_all_relationships=False,
            toggle_arrows=False,
        )

        assert graph_viz is mock_fig
        call_kwargs = mock_visualize.call_args.kwargs
        assert call_kwargs["show_same_sector"] is False
        assert call_kwargs["show_all_relationships"] is False

    @patch('app.create_real_database')
    @patch('app.visualize_3d_graph_with_filters')
    def test_refresh_visualization_handles_exception(
        self, mock_visualize, mock_create_db
    ):
        """Test refresh_visualization handles exceptions gracefully."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        mock_visualize.side_effect = Exception("Visualization error")

        app = FinancialAssetApp()

        # The method should catch the exception and return an empty figure plus an error update,
        # not propagate the exception.
        graph_viz, error_state = app.refresh_visualization(
            graph_state=mock_graph,
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

        assert graph_viz is not None
        assert error_state is not None


class TestGenerateFormulaicAnalysis:
    """Test the generate_formulaic_analysis method."""

    @patch('app.create_real_database')
    @patch('app.FormulaicVisualizer')
    def test_generate_formulaic_analysis_returns_plots_and_summary(
        self, mock_visualizer_class, mock_create_db
    ):
        """Test that formulaic analysis returns plots and summary text."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        mock_visualizer = Mock()
        mock_visualizer.create_formula_overview.return_value = Mock()
        mock_visualizer.create_category_charts.return_value = (Mock(), Mock())
        mock_visualizer_class.return_value = mock_visualizer

        mock_analyzer = Mock()
        mock_analyzer.analyze_graph.return_value = {
            'formulas': [],
            'empirical_relationships': [],
            'formula_count': 5,
            'categories': {},
            'summary': {}
        }

        app = FinancialAssetApp()
        with patch('app.FormulaicdAnalyzer', return_value=mock_analyzer):
            result = app.generate_formulaic_analysis(mock_graph)

        assert isinstance(result, tuple)
        assert len(result) == 4  # overview, chart1, chart2, summary


class TestShowFormulaDetails:
    """Test the show_formula_details method."""

    @patch('app.create_real_database')
    def test_show_formula_details_returns_formatted_details(self, mock_create_db):
        """Test that show_formula_details returns formatted formula information."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        mock_analyzer = Mock()
        mock_analyzer.analyze_graph.return_value = {
            'formulas': [
                {
                    'name': 'Price-to-Earnings Ratio',
                    'formula': 'PE = P / EPS',
                    'latex': r'PE = \frac{P}{EPS}',
                    'description': 'Valuation metric',
                    'variables': {'PE': 'Price-to-Earnings', 'P': 'Price', 'EPS': 'Earnings Per Share'},
                    'category': 'Valuation'
                }
            ],
            'empirical_relationships': [],
            'formula_count': 1,
            'categories': {},
            'summary': {}
        }

        app = FinancialAssetApp()
        with patch('app.FormulaicdAnalyzer', return_value=mock_analyzer):
            result = app.show_formula_details('Price-to-Earnings Ratio', mock_graph)

        assert isinstance(result, str)
        assert 'Price-to-Earnings Ratio' in result
        assert 'PE = P / EPS' in result

    @patch('app.create_real_database')
    def test_show_formula_details_nonexistent_formula(self, mock_create_db):
        """Test show_formula_details with nonexistent formula name."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        mock_analyzer = Mock()
        mock_analyzer.analyze_graph.return_value = {
            'formulas': [],
            'empirical_relationships': [],
            'formula_count': 0,
            'categories': {},
            'summary': {}
        }

        app = FinancialAssetApp()
        with patch('app.FormulaicdAnalyzer', return_value=mock_analyzer):
            result = app.show_formula_details('Nonexistent Formula', mock_graph)

        assert 'not found' in result.lower() or 'select a formula' in result.lower()


class TestFormatFormulaSummary:
    """Test the _format_formula_summary method."""

    @patch('app.create_real_database')
    def test_format_formula_summary_includes_key_metrics(self, mock_create_db):
        """Test that formula summary includes key metrics."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        summary = {
            'total_formulas': 10,
            'categories': ['Valuation', 'Risk', 'Return']
        }
        analysis_results = {
            'formula_count': 10,
            'categories': {
                'Valuation': 4,
                'Risk': 3,
                'Return': 3
            }
        }

        app = FinancialAssetApp()
        result = app._format_formula_summary(summary, analysis_results)

        assert isinstance(result, str)
        assert '10' in result  # formula count
                    equity = Equity(
                        id='AAPL',
                        symbol='AAPL',
                        name='Apple Inc.',
                        asset_class=AssetClass.EQUITY,
                        sector='Technology',
                        price=150.0,
                    )
                    bond = Bond(
                        id='CORP_BOND',
                        symbol='CORP',
                        name='Corporate Bond',
                        asset_class=AssetClass.FIXED_INCOME,
                        sector='Corporate',
                        price=100.0,
                    )
            'total_assets': 1,
            'total_relationships': 0,
            'average_relationship_strength': 0.0,
            'relationship_density': 0.0,
            'regulatory_event_count': 0,
            'asset_class_distribution': {'EQUITY': 1},
            'top_relationships': []
        }
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        # Should not raise exception
        text = app._update_metrics_text(mock_graph)
        assert '1' in text  # single asset

    @patch('app.create_real_database')
    def test_update_asset_info_with_empty_string(self, mock_create_db):
        """Test update_asset_info with empty string asset ID."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()
        asset_dict, relationships = app.update_asset_info('', mock_graph)

        assert asset_dict == {}
        assert relationships == {'outgoing': {}, 'incoming': {}}

    @patch('app.create_real_database')
    def test_app_handles_asset_without_to_dict(self, mock_create_db):
        """Test app handles asset that doesn't have to_dict method."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        # Create an asset without to_dict method
        mock_asset = Mock(spec=[])  # Empty spec means no methods
        mock_graph.assets = {'BAD_ASSET': mock_asset}
        mock_create_db.return_value = mock_graph

        app = FinancialAssetApp()

        # Should handle the missing method gracefully
        with pytest.raises(AttributeError):
            app.update_asset_info('BAD_ASSET', mock_graph)


class TestIntegrationScenarios:
    """Test integration scenarios simulating real usage."""

    @patch('app.create_real_database')
    @patch('app.visualize_3d_graph_with_filters')
    @patch('app.visualize_metrics')
    def test_complete_workflow_simulation(
        self, mock_metrics_viz, mock_3d_viz, mock_create_db
    ):
        """Test a complete workflow from initialization to visualization."""
        # Setup mock graph with realistic data
        mock_graph = Mock(spec=AssetRelationshipGraph)
        equity = Mock(spec=Equity)
        equity.to_dict.return_value = {
            'id': 'AAPL',
            'symbol': 'AAPL',
            'name': 'Apple Inc.',
            'asset_class': 'EQUITY',
            'price': 150.0
        }
        bond = Mock(spec=Bond)
        bond.to_dict.return_value = {
            'id': 'CORP_BOND',
            'symbol': 'CORP',
            'name': 'Corporate Bond',
            'asset_class': 'FIXED_INCOME'
        }
        mock_graph.assets = {'AAPL': equity, 'CORP_BOND': bond}
        mock_graph.relationships = {'AAPL': [('CORP_BOND', 'corporate_link', 0.9)]}
        mock_graph.incoming_relationships = {'CORP_BOND': [('AAPL', 'corporate_link', 0.9)]}
        mock_graph.calculate_metrics.return_value = {
            'total_assets': 2,
            'total_relationships': 1,
            'average_relationship_strength': 0.9,
            'relationship_density': 0.5,
            'regulatory_event_count': 0,
            'asset_class_distribution': {'EQUITY': 1, 'FIXED_INCOME': 1},
            'top_relationships': [('AAPL', 'CORP_BOND', 'corporate_link', 0.9)]
        }
        mock_create_db.return_value = mock_graph

        mock_3d_viz.return_value = Mock()
        mock_metrics_viz.return_value = (Mock(), Mock(), Mock())

        # Initialize app
        app = FinancialAssetApp()

        # Get metrics
        text = app._update_metrics_text(mock_graph)
        assert '2' in text
        assert 'AAPL' in text

        # Get asset info
        asset_dict, rels = app.update_asset_info('AAPL', mock_graph)
        assert asset_dict['id'] == 'AAPL'
        assert 'CORP_BOND' in rels['outgoing']

        # Refresh visualization
        graph_viz, error_state = app.refresh_visualization(mock_graph)
        assert graph_viz is not None


class TestCreateInterface:
    """Test the create_interface method that builds the Gradio UI."""

    @patch('app.create_real_database')
    @patch('app.gr.Blocks')
    def test_create_interface_returns_gradio_blocks(self, mock_blocks, mock_create_db):
        """Test that create_interface returns a Gradio Blocks object."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_create_db.return_value = mock_graph

        mock_blocks_instance = Mock()
        mock_blocks.return_value.__enter__ = Mock(return_value=mock_blocks_instance)
        mock_blocks.return_value.__exit__ = Mock(return_value=False)

        app = FinancialAssetApp()

        # This will try to create the interface
        # We just verify it doesn't crash

        interface = app.create_interface()
        # Should return something (Gradio Blocks context manager)
        assert interface is not None
        assert callable(app.create_interface)
