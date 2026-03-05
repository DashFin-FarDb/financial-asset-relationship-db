from __future__ import annotations

import html
import math
from typing import Any, Dict, Mapping

import plotly.graph_objects as go

from src.analysis.formulaic_analysis import Formula


class FormulaicVisualsNetworkMixin:
    """Detail, correlation-network, and metric-comparison visualizations."""

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """Build an annotated Plotly figure presenting full details for a Formula."""
        fig = go.Figure()
        safe_name = html.escape(str(getattr(formula, "name", "")))
        safe_expression = html.escape(str(getattr(formula, "expression", "")))
        safe_latex = html.escape(str(getattr(formula, "latex", "")))
        safe_description = html.escape(str(getattr(formula, "description", "")))
        safe_category = html.escape(str(getattr(formula, "category", "")))
        safe_example = html.escape(str(getattr(formula, "example_calculation", "")))
        variables = getattr(formula, "variables", {})
        if isinstance(variables, Mapping):
            safe_variables = "<br>".join(
                f"• {html.escape(str(var))}: {html.escape(str(desc))}" for var, desc in variables.items()
            )
        else:
            safe_variables = ""
        r_squared = FormulaicVisualsNetworkMixin._safe_float(getattr(formula, "r_squared", 0.0), 0.0)

        fig.add_annotation(
            text=(
                f"<b>{safe_name}</b><br><br>"
                "<b>Mathematical Expression:</b><br>"
                f"{safe_expression}<br><br>"
                "<b>LaTeX:</b><br>"
                f"{safe_latex}<br><br>"
                "<b>Description:</b><br>"
                f"{safe_description}<br><br>"
                f"<b>Category:</b> {safe_category}<br>"
                f"<b>Reliability (R²):</b> {r_squared:.3f}<br><br>"
                "<b>Variables:</b><br>"
                + safe_variables
                + "<br><br><b>Example Calculation:</b><br>"
                f"{safe_example}"
            ),
            showarrow=False,
        )

        fig.update_layout(
            title=f"Formula Details: {formula.name}",
            height=600,
            plot_bgcolor="white",
        )
        return fig

    @staticmethod
    def create_correlation_network(empirical_relationships: Mapping[str, Any]) -> go.Figure:
        """Build a network visualization of asset correlations."""
        strongest_correlations = empirical_relationships.get("strongest_correlations", [])
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})

        if not strongest_correlations:
            return FormulaicVisualsNetworkMixin._create_empty_correlation_figure()

        return FormulaicVisualsNetworkMixin._build_and_render_correlation_network(
            strongest_correlations,
            correlation_matrix,
        )

    @staticmethod
    def _create_empty_correlation_figure() -> go.Figure:
        """Return an empty placeholder correlation figure."""
        fig = go.Figure()
        fig.add_annotation(
            text="No correlation data available",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
        )
        fig.update_layout(title="No Correlation Data")
        return fig

    @staticmethod
    def _build_and_render_correlation_network(
        strongest_correlations: Any,
        correlation_matrix: Any,
    ) -> go.Figure:
        """Build and render a network graph of the strongest correlations."""
        _ = correlation_matrix
        top_correlations = (
            strongest_correlations[:10]
            if isinstance(strongest_correlations, (list, tuple))
            else list(strongest_correlations)[:10]
        )

        assets = FormulaicVisualsNetworkMixin._extract_assets_from_correlations(top_correlations)
        if not assets:
            fig = go.Figure()
            fig.update_layout(title="No valid asset correlations found")
            return fig

        positions = FormulaicVisualsNetworkMixin._create_circular_positions(assets)
        edge_traces = FormulaicVisualsNetworkMixin._create_edge_traces(top_correlations, positions)
        node_trace = FormulaicVisualsNetworkMixin._create_node_trace(assets, positions)

        fig = go.Figure(data=edge_traces + [node_trace])
        fig.update_layout(
            title="Asset Correlation Network",
            showlegend=False,
            hovermode="closest",
            xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
        )
        return fig

    @staticmethod
    def _extract_assets_from_correlations(correlations: Any) -> list[str]:
        """Extract unique sorted assets from correlation data."""
        assets = set()
        for corr in correlations:
            asset1, asset2, _ = FormulaicVisualsNetworkMixin._parse_correlation_item(corr)
            if asset1:
                assets.add(asset1)
            if asset2:
                assets.add(asset2)
        return sorted([a for a in assets if a])

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Safely coerce numeric-like values to float."""
        if isinstance(value, bool):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_correlation_item(corr: Any) -> tuple[str, str, float]:
        """Parse a correlation item into (asset1, asset2, value)."""
        if isinstance(corr, dict):
            correlation_value = FormulaicVisualsNetworkMixin._safe_float(corr.get("correlation", 0.0), 0.0)
            return (
                corr.get("asset1", ""),
                corr.get("asset2", ""),
                correlation_value,
            )
        if isinstance(corr, (list, tuple)) and len(corr) >= 3:
            return (str(corr[0]), str(corr[1]), FormulaicVisualsNetworkMixin._safe_float(corr[2], 0.0))
        if isinstance(corr, (list, tuple)) and len(corr) >= 2:
            return (str(corr[0]), str(corr[1]), 0.0)
        return ("", "", 0.0)

    @staticmethod
    def _create_circular_positions(assets: list[str]) -> Dict[str, tuple[float, float]]:
        """Compute evenly spaced coordinates on the unit circle for each asset."""
        n = len(assets)
        positions: Dict[str, tuple[float, float]] = {}
        for i, asset in enumerate(assets):
            angle = 2 * math.pi * i / n
            positions[asset] = (math.cos(angle), math.sin(angle))
        return positions

    @staticmethod
    def _create_edge_traces(
        correlations: Any,
        positions: Dict[str, tuple[float, float]],
    ) -> list[go.Scatter]:
        """Build Plotly line traces for correlations connecting positioned assets."""
        edge_traces = []
        if not isinstance(correlations, (list, tuple)):
            return []
        for corr in correlations:
            asset1, asset2, value = FormulaicVisualsNetworkMixin._parse_correlation_item(corr)
            if asset1 in positions and asset2 in positions:
                trace = FormulaicVisualsNetworkMixin._create_single_edge_trace(asset1, asset2, value, positions)
                edge_traces.append(trace)
        return edge_traces

    @staticmethod
    def _create_single_edge_trace(
        asset1: str,
        asset2: str,
        value: float,
        positions: Dict[str, tuple[float, float]],
    ) -> go.Scatter:
        """Create a Plotly line trace representing a correlation edge."""
        x0, y0 = positions[asset1]
        x1, y1 = positions[asset2]
        color = "red" if value < 0 else "green"
        width = max(1.0, abs(FormulaicVisualsNetworkMixin._safe_float(value, 0.0)) * 5.0)

        return go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line={"color": color, "width": width},
            hoverinfo="text",
            text=f"{asset1} - {asset2}: {value:.3f}",
            showlegend=False,
        )

    @staticmethod
    def _create_node_trace(
        assets: list[str],
        positions: Dict[str, tuple[float, float]],
    ) -> go.Scatter:
        """Create a Plotly scatter trace representing asset nodes."""
        node_x = [positions[asset][0] for asset in assets]
        node_y = [positions[asset][1] for asset in assets]

        return go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=assets,
            textposition="top center",
            marker={
                "size": 20,
                "color": "lightblue",
                "line": {"color": "black", "width": 2},
            },
            hoverinfo="text",
            showlegend=False,
        )

    @staticmethod
    def create_metric_comparison_chart(analysis_results: Dict[str, Any]) -> go.Figure:
        """Generate a bar chart comparing average R-squared per formula category."""
        formulas = analysis_results.get("formulas", [])
        fig = go.Figure()

        if not formulas:
            return fig

        categories: Dict[str, list[float]] = {}
        for formula in formulas:
            category = getattr(formula, "category", None) or "Unknown"
            r_sq = getattr(formula, "r_squared", 0.0) or 0.0
            categories.setdefault(category, []).append(r_sq)

        category_names = list(categories.keys())
        r_squared_by_category = [sum(values) / len(values) if values else 0.0 for values in categories.values()]
        count_by_category = [len(values) for values in categories.values()]

        fig.add_trace(
            go.Bar(
                name="Average R-squared",
                x=category_names,
                y=r_squared_by_category,
            )
        )
        fig.add_trace(
            go.Bar(
                name="Formula Count",
                x=category_names,
                y=count_by_category,
                yaxis="y2",
            )
        )

        fig.update_layout(
            title="Formula Categories: Reliability vs Count",
            xaxis_title="Formula Category",
            yaxis={"title": "Average R-squared"},
            yaxis2={"title": "Formula Count", "overlaying": "y", "side": "right", "showgrid": False},
            barmode="group",
            plot_bgcolor="white",
        )
        return fig
