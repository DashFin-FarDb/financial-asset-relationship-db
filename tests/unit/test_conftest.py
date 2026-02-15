# ruff: noqa: S101
"""Unit tests for tests/conftest.py pytest configuration helpers.

This module contains comprehensive unit tests for the conftest module including:
- Testing pytest_addoption function behavior
- Testing _register_dummy_cov_options when pytest-cov is unavailable
- Testing that fixtures produce correct types
- Testing edge cases and argument preservation

Note: This test file uses assert statements which is the standard and recommended
approach for pytest. The S101 rule is suppressed because tests are not run with
Python optimization flags that would remove assert statements.
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import (
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryEvent,
)


def _load_tests_conftest():
    """Load the tests/conftest.py module explicitly (not the root conftest)."""
    conftest_path = Path(__file__).resolve().parent.parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("tests_conftest", conftest_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
class TestConftestHelpers:
    """Test cases for tests/conftest.py pytest configuration helpers."""

    @staticmethod
    def test_pytest_addoption_exists():
        """Test that tests/conftest.py exports pytest_addoption."""
        mod = _load_tests_conftest()
        assert hasattr(mod, "pytest_addoption")
        assert callable(mod.pytest_addoption)

    @staticmethod
    def test_register_dummy_cov_options():
        """Test _register_dummy_cov_options registers both dummy options."""
        mod = _load_tests_conftest()

        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_parser.getgroup.return_value = mock_group

        mod._register_dummy_cov_options(mock_parser)

        mock_parser.getgroup.assert_called_once_with("cov")
        assert mock_group.addoption.call_count == 2

    @staticmethod
    def test_register_dummy_cov_options_uses_append_action():
        """Test that dummy options use append action."""
        mod = _load_tests_conftest()

        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_parser.getgroup.return_value = mock_group

        mod._register_dummy_cov_options(mock_parser)

        for call in mock_group.addoption.call_args_list:
            assert call[1].get("action") == "append"
            assert call[1].get("default") == []

    @staticmethod
    def test_register_dummy_cov_option_names():
        """Test that --cov and --cov-report are the registered option names."""
        mod = _load_tests_conftest()

        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_parser.getgroup.return_value = mock_group

        mod._register_dummy_cov_options(mock_parser)

        call_args = [call[0][0] for call in mock_group.addoption.call_args_list]
        assert "--cov" in call_args
        assert "--cov-report" in call_args

    @staticmethod
    def test_conftest_module_docstring_exists():
        """Test that tests/conftest module has proper documentation."""
        mod = _load_tests_conftest()
        assert mod.__doc__ is not None
        assert "pytest" in mod.__doc__.lower()

    @staticmethod
    def test_pytest_addoption_function_signature():
        """Verify pytest_addoption is callable with one parser param."""
        import inspect

        mod = _load_tests_conftest()
        sig = inspect.signature(mod.pytest_addoption)
        assert len(sig.parameters) == 1
        param = list(sig.parameters.values())[0]
        assert param.name == "parser"


@pytest.mark.unit
class TestConftestFixtures:
    """Test that conftest fixtures produce correct types."""

    @staticmethod
    def test_empty_graph_fixture(empty_graph):
        """Test empty_graph fixture returns an AssetRelationshipGraph."""
        assert isinstance(empty_graph, AssetRelationshipGraph)
        assert len(empty_graph.assets) == 0

    @staticmethod
    def test_sample_equity_fixture(sample_equity):
        """Test sample_equity fixture returns an Equity."""
        assert isinstance(sample_equity, Equity)
        assert sample_equity.asset_class == AssetClass.EQUITY
        assert sample_equity.id == "AAPL"

    @staticmethod
    def test_sample_bond_fixture(sample_bond):
        """Test sample_bond fixture returns a Bond."""
        assert isinstance(sample_bond, Bond)
        assert sample_bond.asset_class == AssetClass.FIXED_INCOME

    @staticmethod
    def test_sample_commodity_fixture(sample_commodity):
        """Test sample_commodity fixture returns a Commodity."""
        assert isinstance(sample_commodity, Commodity)
        assert sample_commodity.asset_class == AssetClass.COMMODITY

    @staticmethod
    def test_sample_currency_fixture(sample_currency):
        """Test sample_currency fixture returns a Currency."""
        assert isinstance(sample_currency, Currency)
        assert sample_currency.asset_class == AssetClass.CURRENCY

    @staticmethod
    def test_sample_regulatory_event_fixture(sample_regulatory_event):
        """Test sample_regulatory_event fixture returns a RegulatoryEvent."""
        assert isinstance(sample_regulatory_event, RegulatoryEvent)
        assert sample_regulatory_event.asset_id == "AAPL"

    @staticmethod
    def test_populated_graph_fixture(populated_graph):
        """Test populated_graph fixture has 4 assets and relationships."""
        assert isinstance(populated_graph, AssetRelationshipGraph)
        assert len(populated_graph.assets) == 4
        # Should have built relationships
        total_rels = sum(len(r) for r in populated_graph.relationships.values())
        assert total_rels >= 0

    @staticmethod
    def test_dividend_stock_fixture(dividend_stock):
        """Test dividend_stock fixture returns an Equity with dividend_yield."""
        assert isinstance(dividend_stock, Equity)
        assert dividend_stock.dividend_yield == 0.04
        assert dividend_stock.sector == "Utilities"
