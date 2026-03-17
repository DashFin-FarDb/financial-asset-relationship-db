"""Targeted regression tests for formulaic analysis/example edge cases."""

from __future__ import annotations

import pytest

from src.analysis.formulaic_analysis import FormulaicAnalyzer
from src.analysis.formulaic_examples import calculate_dividend_examples, calculate_pb_examples
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass


@pytest.mark.unit
def test_build_correlation_matrix_collapses_bidirectional_pairs() -> None:
    """Bidirectional pairs should collapse into one canonical matrix key."""
    graph = AssetRelationshipGraph()
    graph.relationships = {
        "AAPL": [("MSFT", "same_sector", 0.5)],
        "MSFT": [("AAPL", "same_sector", 0.8)],
    }

    correlation_matrix = FormulaicAnalyzer._build_correlation_matrix(graph)

    assert correlation_matrix == {"AAPL-MSFT": 0.8}


@pytest.mark.unit
def test_build_strongest_correlations_keeps_perfect_non_self_values() -> None:
    """Valid perfect correlations between distinct assets should be retained."""
    strongest = FormulaicAnalyzer._build_strongest_correlations({"AAPL-MSFT": 1.0})

    assert len(strongest) == 1
    assert strongest[0]["pair"] == "AAPL-MSFT"
    assert strongest[0]["correlation"] == 1.0


@pytest.mark.unit
def test_calculate_dividend_examples_skips_assets_without_price() -> None:
    """Dividend examples should skip malformed assets missing a usable price."""
    graph = AssetRelationshipGraph()
    malformed_asset = type(
        "MalformedEquity",
        (),
        {
            "asset_class": AssetClass.EQUITY,
            "symbol": "MISS",
            "dividend_yield": 0.02,
            "price": None,
        },
    )()
    graph.assets = {"MISS": malformed_asset}

    assert calculate_dividend_examples(graph).startswith("Example:")


@pytest.mark.unit
def test_calculate_pb_examples_skips_assets_without_price() -> None:
    """P/B examples should skip malformed assets missing a usable price."""
    graph = AssetRelationshipGraph()
    malformed_asset = type(
        "MalformedEquity",
        (),
        {
            "asset_class": AssetClass.EQUITY,
            "symbol": "MISS",
            "book_value": 5.0,
            "price": None,
        },
    )()
    graph.assets = {"MISS": malformed_asset}

    assert calculate_pb_examples(graph).startswith("Example:")
