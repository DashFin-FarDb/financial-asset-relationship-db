from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping

import networkx as nx
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.formulaic_analysis import Formula


class FormulaicVisualizer:
    """Formulaic Visualizations Module.

    Visualizes mathematical formulas and relationships from financial analysis.

    This module provides tools to visualize formulaic analysis results,
    including creating dashboards, plotting reliability,
    and normalizing empirical relationships.
    """

    def __init__(self) -> None:
        self.color_scheme: Dict[str, str] = {
            "Valuation": "#FF6B6B",
            "Income": "#4ECDC4",
            "Fixed Income": "#45B7D1",
            "Risk Management": "#96CEB4",
            "Portfolio Theory": "#FFEAA7",
            "Statistical Analysis": "#DDA0DD",
            "Currency Markets": "#98D8C8",
            "Cross-Asset": "#F7DC6F",
        }

    def create_formula_dashboard(self, analysis_results: Dict[str, Any]) -> go.Figure:
        """Create a comprehensive dashboard showing all formulaic relationships."""
        _ = analysis_results  # Intentionally unused in this excerpt; reserved for future traces.

        fig = make_subplots(
            rows=3,
            cols=2,
            subplot_titles=(
                "Formula Categories Distribution",
                "Formula Reliability (R-squared)",
                "Empirical Correlation Matrix",
                "Asset Class Relationships",
                "Sector Analysis",
                "Key Formula Examples",
            ),
        )
        return fig

    @staticmethod
    def _normalize_empirical_relationships(
        empirical_relationships: Any,
    ) -> Dict[str, Dict[str, float]]:
        """Normalize empirical relationships into {row: {col: value}}."""
        if not empirical_relationships:
            return {}

        matrix: Dict[str, Dict[str, float]] = {}

        if isinstance(empirical_relationships, dict):
            is_nested = all(
                isinstance(value, dict) for value in empirical_relationships.values()
            )
            if is_nested:
                for row, col_map in empirical_relationships.items():
                    row_key = str(row)
                    matrix[row_key] = {
                        str(col): float(val) for col, val in col_map.items()
                    }
            else:
                for key, value in empirical_relationships.items():
                    if isinstance(key, (tuple, list)) and len(key) == 2:
                        row, col = key
                    else:
                        parts = str(key).split("|")
                        if len(parts) == 2:
                            row, col = parts
                        else:
                            continue

                    r, c = str(row), str(col)
                    matrix.setdefault(r, {})[c] = float(value)
                    matrix.setdefault(c, {})[r] = float(value)

        elif hasattr(empirical_relationships, "index") and hasattr(
            empirical_relationships, "columns"
        ):
            for row in empirical_relationships.index:
                for col in empirical_relationships.columns:
                    matrix.setdefault(str(row), {})[str(col)] = float(
                        empirical_relationships.loc[row, col]
                    )
        else:
            raise ValueError(
                "Unsupported type for empirical relationships: "
                f"{type(empirical_relationships)}"
            )

        return matrix

    @staticmethod
    def _plot_empirical_correlation(fig: go.Figure, empirical_relationships: Any) -> None:
        """Populate the empirical correlation matrix heatmap in row 2, column 1."""
        matrix = FormulaicVisualizer._normalize_empirical_relationships(
            empirical_relationships
        )
        if not matrix:
            # Nothing to plot if no empirical relationships are provided.
            return

        rows = sorted(matrix.keys())
        all_cols = sorted({col for col_map in matrix.values() for col in col_map})
        z = [[matrix[row].get(col, math.nan) for col in all_cols] for row in rows]

        heatmap = go.Heatmap(
            z=z,
            x=all_cols,
            y=rows,
            coloraxis="coloraxis",
            showscale=False,
        )
        fig.add_trace(heatmap, row=2, col=1)

    # ------------------------------------------------------------------
    # Dashboard plotting methods
    # ------------------------------------------------------------------

    @staticmethod
    def _plot_category_distribution(fig: go.Figure, formulas: Any) -> None:
        """Plot distribution of formulas across categories."""
        if not formulas:
            return

        categories: dict[str, int] = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            categories[category] = categories.get(category, 0) + 1

        fig.add_trace(
            go.Pie(
                labels=list(categories.keys()),
                values=list(categories.values()),
                hole=0.3,
            ),
            row=1,
            col=1,
        )

    @staticmethod
    def _plot_reliability(fig: go.Figure, formulas: Any) -> None:
        """Plot reliability (R-squared) of formulas."""
        if not formulas:
            return

        categories: DefaultDict[str, list[float]] = defaultdict(list)
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            r_squared = float(getattr(formula, "r_squared", 0.0))
            categories[category].append(r_squared)

        avg_r_squared = {
            cat: (sum(vals) / len(vals) if vals else 0.0)
            for cat, vals in categories.items()
        }

        fig.add_trace(
            go.Bar(
                x=list(avg_r_squared.keys()),
                y=list(avg_r_squared.values()),
                marker=dict(color="lightcoral"),
            ),
            row=1,
            col=2,
        )

    @staticmethod
    def _plot_empirical_correlation(
        fig: go.Figure,
        empirical_relationships: Mapping[str, Any],
    ) -> None:
        """Plot empirical correlation matrix."""
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})
        if not correlation_matrix:
            return

        # Only dict-of-dict is supported here; otherwise do nothing (original behaviour).
        if not isinstance(correlation_matrix, dict):
            return

        assets = sorted(str(k) for k in correlation_matrix.keys())
        z = [
            [
                float(correlation_matrix.get(a1, {}).get(a2, 0.0))
                for a2 in assets
            ]
            for a1 in assets
        ]

        fig.add_trace(
            go.Heatmap(
                z=z,
                x=assets,
                y=assets,
                colorscale="RdBu",
                zmid=0,
            ),
            row=2,
            col=1,
        )

    @staticmethod
    def _plot_asset_class_relationships(fig: go.Figure, formulas: Any) -> None:
        """Plot relationships between asset classes."""
        if not formulas:
            return

        categories: dict[str, int] = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            categories[category] = categories.get(category, 0) + 1

        fig.add_trace(
            go.Bar(
                x=list(categories.keys()),
                y=list(categories.values()),
                marker=dict(color="lightgreen"),
            ),
            row=2,
            col=2,
        )

    @staticmethod
    def _plot_sector_analysis(fig: go.Figure, formulas: Any) -> None:
        """Plot sector analysis."""
        if not formulas:
            return

        categories: dict[str, dict[str, float]] = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            r_squared = float(getattr(formula, "r_squared", 0.0))
            if category not in categories:
                categories[category] = {"count": 0.0, "total_r2": 0.0}
            categories[category]["count"] += 1.0
            categories[category]["total_r2"] += r_squared

        sector_performance = {
            cat: (data["total_r2"] / data["count"] if data["count"] > 0 else 0.0)
            for cat, data in categories.items()
        }

        fig.add_trace(
            go.Bar(
                x=list(sector_performance.keys()),
                y=list(sector_performance.values()),
                marker=dict(color="lightblue"),
            ),
            row=3,
            col=1,
        )

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _plot_key_formula_examples(self, fig: go.Figure, formulas: Any) -> None:
    """Populate the 'Key Formula Examples' table."""
    if not formulas:
        return

    sorted_formulas = self._get_sorted_formulas(formulas)
    top_formulas = sorted_formulas[:10]

    names, categories, r_squared_values = self._extract_formula_table_data(top_formulas)

    fig.add_trace(
        go.Table(
            header=dict(
                values=["Formula", "Category", "R-squared"],
                fill_color="#f2f2f2",
                align="left",
            ),
            cells=dict(
                values=[names, categories, r_squared_values],
                fill_color="#ffffff",
                align="left",
            ),
        ),
        row=3,
        col=2,
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_sorted_formulas(formulas: Iterable[Any]) -> list[Any]:
        """Sort formulas by descending r_squared with safe fallback."""
        try:
            return sorted(
                formulas,
                key=lambda f: getattr(f, "r_squared", float("-inf")),
                reverse=True,
            )
        except TypeError:
            # Sorting may fail if objects are not comparable or iterable
            return list(formulas)

    @staticmethod
    def _format_name(name: Any, max_length: int = 30) -> str:
        """Format formula name with truncation."""
        if not isinstance(name, str) or not name:
            return "N/A"
        return name if len(name) <= max_length else f"{name[: max_length - 3]}..."

    @staticmethod
    def _format_r_squared(r_value: Any) -> str:
        """Format r_squared value to four decimal places or N/A."""
        if isinstance(r_value, (int, float)):
            return f"{r_value:.4f}"
        return "N/A"

    @staticmethod
    def _extract_formula_table_data(
        formulas: Iterable[Any],
    ) -> tuple[list[str], list[str], list[str]]:
        """Extract table values for formula name, category, and r-squared."""
        names = [
            FormulaicVisualizer._format_name(getattr(f, "name", None)) for f in formulas
        ]
        categories = [getattr(f, "category", "N/A") for f in formulas]
        r_squared_values = [
            FormulaicVisualizer._format_r_squared(getattr(f, "r_squared", None))
            for f in formulas
        ]
        return names, categories, r_squared_values

    # ------------------------------------------------------------------
    # Detail & comparison views
    # ------------------------------------------------------------------

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """Create a detailed view of a specific formula."""
        fig = go.Figure()

        variables = getattr(formula, "variables", {}) or {}
        description = getattr(formula, "description", "N/A")
        example = getattr(formula, "example_calculation", "N/A")
        latex = getattr(formula, "latex", "N/A")
        formula_text = getattr(formula, "formula", "N/A")
        category = getattr(formula, "category", "N/A")

        r_squared = getattr(formula, "r_squared", None)
        r_squared_str = f"{r_squared:.3f}" if isinstance(r_squared, (int, float)) else "N/A"

        variables_block = "<br>".join(
            f"• {var}: {desc}" for var, desc in variables.items()
        ) or "N/A"

        fig.add_annotation(
            text=(
                f"<b>{formula.name}</b><br><br>"
                "<b>Mathematical Expression:</b><br>"
                f"{formula_text}<br><br>"
                "<b>LaTeX:</b><br>"
                f"{latex}<br><br>"
                "<b>Description:</b><br>"
                f"{description}<br><br>"
                f"<b>Category:</b> {category}<br>"
                f"<b>Reliability (R²):</b> {r_squared_str}<br><br>"
                "<b>Variables:</b><br>"
                f"{variables_block}<br><br>"
                "<b>Example Calculation:</b><br>"
                f"{example}"
            ),
            showarrow=False,
        )

        return fig

    # ------------------------------------------------------------------
    # Correlation network (stubbed safely)
    # ------------------------------------------------------------------

    @staticmethod
    def create_correlation_network_mapping(
        empirical_relationships: Mapping[str, Any],
    ) -> go.Figure:
        """Create a network graph showing asset correlations."""
        # Preserve behaviour: accept Mapping and delegate to the canonical builder.
        return FormulaicVisualizer.create_correlation_network(dict(empirical_relationships))

    @staticmethod
    def _empty_correlation_network_fig() -> go.Figure:
        """Return a consistent empty-state figure for correlation network plots."""
        fig = go.Figure()
        fig.add_annotation(
            text="No correlation data available.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
        fig.update_layout(
            title="Correlation Network Graph",
            showlegend=False,
            template="plotly_white",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
        return fig

    @staticmethod
    def _extract_correlation_assets(
        strongest_correlations: List[Dict[str, Any]],
        correlation_matrix: Dict[str, Any],
    ) -> List[str]:
        """Extract unique assets from either strongest_correlations or correlation_matrix."""
        if strongest_correlations:
            return sorted(
                {c.get("asset1") for c in strongest_correlations if c.get("asset1")}
                | {c.get("asset2") for c in strongest_correlations if c.get("asset2")}
            )
        return sorted(str(k) for k in correlation_matrix.keys())

    @staticmethod
    def create_correlation_network(empirical_relationships: Dict[str, Any]) -> go.Figure:
        """Create a network graph showing asset correlations."""
        strongest_correlations = empirical_relationships.get("strongest_correlations", []) or []
        correlation_matrix = empirical_relationships.get("correlation_matrix", {}) or {}

        if not strongest_correlations and not correlation_matrix:
            return FormulaicVisualizer._empty_correlation_network_fig()

        assets = FormulaicVisualizer._extract_correlation_assets(
            strongest_correlations,
            correlation_matrix,
        )

        # Fallback: attempt to parse correlation_matrix keys like "AAA-BBB"
        if not assets and correlation_matrix:
            asset_components: set[str] = set()
            for key in correlation_matrix.keys():
                if isinstance(key, str) and "-" in key:
                    part1, part2 = key.split("-", 1)
                    if part1:
                        asset_components.add(part1)
                    if part2:
                        asset_components.add(part2)
            assets = sorted(asset_components)

        G = nx.Graph()
        G.add_nodes_from(assets)

        for corr in strongest_correlations[:10]:
            a1, a2 = corr.get("asset1"), corr.get("asset2")
            value = corr.get("correlation")
            if not a1 or not a2 or not isinstance(value, (int, float)):
                continue
            G.add_edge(a1, a2, weight=float(value))

        if G.number_of_nodes() == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No assets found to render.",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
            )
            fig.update_layout(
                title="Correlation Network Graph",
                showlegend=False,
                template="plotly_white",
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            )
            return fig

        pos = nx.circular_layout(G)

        edge_traces: list[go.Scatter] = []
        for u, v, data in G.edges(data=True):
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            weight = float(data.get("weight", 0.0))

            if weight > 0.7:
                color, width = "red", 4
            elif weight > 0.4:
                color, width = "orange", 3
            else:
                color, width = "lightgray", 2

            edge_traces.append(
                go.Scatter(
                    x=[x0, x1, None],
                    y=[y0, y1, None],
                    mode="lines",
                    line=dict(color=color, width=width),
                    hoverinfo="none",
                    showlegend=False,
                )
            )

        node_x: list[float] = []
        node_y: list[float] = []
        node_text: list[str] = []
        node_degree: list[int] = []

        for node in G.nodes():
            x, y = pos[node]
            node_x.append(float(x))
            node_y.append(float(y))
            node_text.append(str(node))
            node_degree.append(int(G.degree(node)))

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=node_text,
            textposition="top center",
            hoverinfo="text",
            marker=dict(
                showscale=True,
                colorscale="YlGnBu",
                color=node_degree,
                size=10,
                line_width=2,
                colorbar=dict(
                    thickness=15,
                    title="Node Connections",
                    xanchor="left",
                    titleside="right",
                ),
            ),
            showlegend=False,
        )

        fig = go.Figure(
            data=[*edge_traces, node_trace],
            layout=go.Layout(
                title="Correlation Network Graph",
                titlefont_size=16,
                showlegend=False,
                hovermode="closest",
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                template="plotly_white",
            ),
        )
        return fig

    @staticmethod
    def _create_empty_correlation_figure() -> go.Figure:
        """Backward-compatible empty placeholder correlation figure."""
        return FormulaicVisualizer._empty_correlation_network_fig()

    @staticmethod
    def _build_and_render_correlation_network(
        strongest_correlations: Any,
        correlation_matrix: Any,
    ) -> go.Figure:
        """
        Backward-compatible entry point.

        The implementation is delegated to `create_correlation_network` to avoid
        duplicate logic and divergence.
        """
        data: Dict[str, Any] = {
            "strongest_correlations": strongest_correlations or [],
            "correlation_matrix": correlation_matrix or {},
        }
        return FormulaicVisualizer.create_correlation_network(data)
    # ------------------------------------------------------------------
    # Metric comparison
    # ------------------------------------------------------------------

    @staticmethod
    def create_metric_comparison_chart(
        analysis_results: Dict[str, Any],
    ) -> go.Figure:
        """Create a chart comparing different metrics derived from formulas."""
        formulas = analysis_results.get("formulas", [])
        if not formulas:
            return go.Figure()

        categories: dict[str, list[float]] = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            r_squared = getattr(formula, "r_squared", 0.0)
            if isinstance(r_squared, (int, float)):
                categories.setdefault(category, []).append(float(r_squared))

        category_names = list(categories.keys())
        r_squared_by_category = [
            (sum(values) / len(values)) if values else 0.0 for values in categories.values()
        ]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                name="Average R-squared",
                x=category_names,
                y=r_squared_by_category,
            )
        )

        fig.update_layout(
            title="Formula Reliability Distribution by Category",
            xaxis_title="Formula Category",
            yaxis_title="R-Squared Score",
            showlegend=False,
            template="plotly_white",
        )

        return fig
