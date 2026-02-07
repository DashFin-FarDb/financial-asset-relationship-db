import math
from typing import Any, Dict, Mapping

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
        self.color_scheme = {
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
        """Normalize empirical_relationships into a nested dict
        of the form {row: {col: value}}.
        """
        if not empirical_relationships:
            return {}

        matrix: Dict[str, Dict[str, float]] = {}

        if isinstance(empirical_relationships, dict):
            is_nested = all(
                isinstance(v, dict) for v in empirical_relationships.values()
            )
            if is_nested:
                for row, cols in empirical_relationships.items():
                    row_key = str(row)
                    matrix[row_key] = {
                        str(col): float(val) for col, val in cols.items()
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
    def _plot_empirical_correlation(
        fig: go.Figure, empirical_relationships: Any
    ) -> None:
        """Populate the empirical correlation matrix heatmap in row 2, column 1."""
        matrix = FormulaicVisualizer._normalize_empirical_relationships(
            empirical_relationships
        )
        if not matrix:
            # Nothing to plot if no empirical relationships are provided.
            return

        rows = sorted(matrix.keys())
        cols = sorted({col for cols in matrix.values() for col in cols})
        z = [[matrix[row].get(col, math.nan) for col in cols] for row in rows]

        heatmap = go.Heatmap(
            z=z, x=cols, y=rows, coloraxis="coloraxis", showscale=False
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

        categories = {}
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

        categories = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            r_squared = getattr(formula, "r_squared", 0.0)
            if category not in categories:
                categories[category] = []
            categories[category].append(r_squared)

        avg_r_squared = {
            cat: sum(vals) / len(vals) if vals else 0.0
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
        fig: go.Figure, empirical_relationships: Mapping[str, Any]
    ) -> None:
        """Plot empirical correlation matrix."""
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})

        if not correlation_matrix:
            return

        if isinstance(correlation_matrix, dict):
            assets = sorted(correlation_matrix.keys())
            z = [
                [correlation_matrix.get(a1, {}).get(a2, 0.0) for a2 in assets]
                for a1 in assets
            ]
        else:
            # Assume it's already a matrix-like structure
            return

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

        # Group formulas by category and count relationships
        categories = {}
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

        # Simple sector distribution based on categories
        categories = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            r_squared = getattr(formula, "r_squared", 0.0)
            if category not in categories:
                categories[category] = {"count": 0, "total_r2": 0.0}
            categories[category]["count"] += 1
            categories[category]["total_r2"] += r_squared

        sector_performance = {
            cat: data["total_r2"] / data["count"] if data["count"] > 0 else 0.0
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

        names, categories, r_squared_values = self._extract_formula_table_data(
            top_formulas
        )

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
    def _get_sorted_formulas(formulas: Any) -> list[Any]:
        """Sort formulas by descending r_squared with safe fallback."""
        try:
            return sorted(
                formulas,
                key=lambda f: getattr(f, "r_squared", float("-inf")),
                reverse=True,
            )
        except TypeError:
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
        formulas: Any,
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

        fig.add_annotation(
            text=(
                f"<b>{formula.name}</b><br><br>"
                "<b>Mathematical Expression:</b><br>"
                f"{formula.formula}<br><br>"
                "<b>LaTeX:</b><br>"
                f"{formula.latex}<br><br>"
                "<b>Description:</b><br>"
                f"{formula.description}<br><br>"
                f"<b>Category:</b> {formula.category}<br>"
                f"<b>Reliability (R²):</b> {formula.r_squared:.3f}<br><br>"
                "<b>Variables:</b><br>"
                + "<br>".join(
                    f"• {var}: {desc}" for var, desc in formula.variables.items()
                )
                + "<br><br><b>Example Calculation:</b><br>"
                f"{formula.example_calculation}"
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

    @staticmethod
    def _empty_correlation_network_fig() -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(
            text="No correlation data available.",
            x=0.5,
            y=0.5,
            xref="paper",
            showarrow=False,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
        return fig

    @staticmethod
    def _extract_correlation_assets(
        strongest_correlations: List[Dict[str, Any]],
        correlation_matrix: Dict[str, Any],
    ) -> List[str]:
        if strongest_correlations:
            return sorted(
                {c.get("asset1") for c in strongest_correlations if c.get("asset1")}
                | {c.get("asset2") for c in strongest_correlations if c.get("asset2")}
            )
        return sorted(correlation_matrix.keys())

    @staticmethod
    def create_correlation_network(
        empirical_relationships: Dict[str, Any],
    ) -> go.Figure:
        """Create a network graph showing asset correlations."""
        strongest_correlations = empirical_relationships.get(
            "strongest_correlations", []
        )
        correlation_matrix = empirical_relationships.get("correlation_matrix", {}) or {}

        # Empty state
        if not strongest_correlations and not correlation_matrix:
            return FormulaicVisualizer._empty_correlation_network_fig()

        # Derive assets
        assets = FormulaicVisualizer._extract_correlation_assets(
            strongest_correlations, correlation_matrix
        )
        if not assets and correlation_matrix:
            asset_components = set()
            for key in correlation_matrix.keys():
                if isinstance(key, str) and "-" in key:
                    part1, part2 = key.split("-", 1)
                    asset_components.add(part1)
                    asset_components.add(part2)
            assets = sorted(asset_components)

        # Build a graph from the top correlations.
        G = nx.Graph()
        G.add_nodes_from(assets)

        for corr in (strongest_correlations or [])[:10]:
            a1, a2 = corr.get("asset1"), corr.get("asset2")
            value = corr.get("correlation")
            if not a1 or not a2 or not isinstance(value, (int, float)):
                continue
            G.add_edge(a1, a2, weight=float(value))

        # Ensure we have at least something to lay out.
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

        # Edge traces
        edge_traces = []
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

        # Node trace (colored by degree)
        node_x = []
        node_y = []
        node_text = []
        node_degree = []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(node)
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
        """Return an empty placeholder correlation figure."""
        fig = go.Figure()
        fig.update_layout(title="No correlation data available")
        return fig

    @staticmethod
    def _build_and_render_correlation_network(
        strongest_correlations: Any,
        correlation_matrix: Any,
    ) -> go.Figure:
        """Build and render a correlation network visualization."""
        assets = FormulaicVisualizer._extract_assets_from_correlations(
            strongest_correlations
        )
        if not assets:
            fig = go.Figure()
            fig.update_layout(title="No valid asset correlations found")
            return fig

        positions = FormulaicVisualizer._create_circular_positions(assets)
        edge_traces = FormulaicVisualizer._create_edge_traces(
            strongest_correlations, positions
        )
        node_trace = FormulaicVisualizer._create_node_trace(assets, positions)

        fig = go.Figure(data=edge_traces + [node_trace])
        fig.update_layout(
            title="Asset Correlation Network",
            showlegend=False,
            hovermode="closest",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
        return fig

    @staticmethod
    def _extract_assets_from_correlations(correlations: Any) -> list[str]:
        """Extract unique sorted assets from correlation data."""
        assets = set()
        for corr in correlations:
            asset1, asset2, _ = FormulaicVisualizer._parse_correlation_item(corr)
            if asset1:
                assets.add(asset1)
            if asset2:
                assets.add(asset2)
        return sorted([a for a in assets if a])

    @staticmethod
    def _parse_correlation_item(corr: Any) -> tuple[str, str, float]:
        """Parse a correlation item into (asset1, asset2, value)."""
        if isinstance(corr, dict):
            return (
                corr.get("asset1", ""),
                corr.get("asset2", ""),
                corr.get("correlation", 0.0),
            )
        if isinstance(corr, (list, tuple)) and len(corr) >= 3:
            return (corr[0], corr[1], corr[2])
        if isinstance(corr, (list, tuple)) and len(corr) >= 2:
            return (corr[0], corr[1], 0.0)
        return ("", "", 0.0)

    @staticmethod
    def _create_circular_positions(assets: list[str]) -> Dict[str, tuple[float, float]]:
        """Create circular layout positions for assets."""
        import math

        n = len(assets)
        positions = {}
        for i, asset in enumerate(assets):
            angle = 2 * math.pi * i / n
            positions[asset] = (math.cos(angle), math.sin(angle))
        return positions

    @staticmethod
    def _create_edge_traces(
        correlations: Any, positions: Dict[str, tuple[float, float]]
    ) -> list[go.Scatter]:
        """Create edge traces for all correlations."""
        edge_traces = []
        for corr in correlations:
            asset1, asset2, value = FormulaicVisualizer._parse_correlation_item(corr)
            if asset1 in positions and asset2 in positions:
                trace = FormulaicVisualizer._create_single_edge_trace(
                    asset1, asset2, value, positions
                )
                edge_traces.append(trace)
        return edge_traces

    @staticmethod
    def _create_single_edge_trace(
        asset1: str,
        asset2: str,
        value: float,
        positions: Dict[str, tuple[float, float]],
    ) -> go.Scatter:
        """Create a single edge trace between two assets."""
        x0, y0 = positions[asset1]
        x1, y1 = positions[asset2]
        color = "red" if value < 0 else "green"
        width = max(1, abs(value) * 5)

        return go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(color=color, width=width),
            hoverinfo="text",
            text=f"{asset1} - {asset2}: {value:.3f}",
            showlegend=False,
        )

    @staticmethod
    def _create_node_trace(
        assets: list[str], positions: Dict[str, tuple[float, float]]
    ) -> go.Scatter:
        """Create node trace for all assets."""
        node_x = [positions[asset][0] for asset in assets]
        node_y = [positions[asset][1] for asset in assets]

        return go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=assets,
            textposition="top center",
            marker=dict(
                size=20,
                color="lightblue",
                line=dict(
                    color="black",
                    width=2,
                ),
            ),
            hoverinfo="text",
            showlegend=False,
        )

    # ------------------------------------------------------------------
    # Metric comparison
    # ------------------------------------------------------------------

    @staticmethod
    def create_metric_comparison_chart(
        analysis_results: Dict[str, Any],
    ) -> go.Figure:
        """Create a chart comparing different metrics derived from formulas."""
        formulas = analysis_results.get("formulas", [])
        fig = go.Figure()

        if not formulas:
            return go.Figure()

        categories: Dict[str, list[float]] = {}
        for formula in formulas:
            categories.setdefault(formula.category, []).append(formula.r_squared)

        category_names = list(categories.keys())
        r_squared_by_category = [
            sum(values) / len(values) if values else 0.0
            for values in categories.values()
        ]

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
