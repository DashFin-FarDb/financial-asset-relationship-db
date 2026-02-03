from typing import Any, Dict

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.formulaic_analysis import Formula


class FormulaicVisualizer:
    """Visualizes mathematical formulas and relationships from financial analysis."""

    def __init__(self):
        self.color_scheme = {
            "Valuation": "#FF6B6B",
            """Formulaic Visualizations Module.

    This module provides tools to visualize formulaic analysis results,
    including creating dashboards, plotting reliability, and normalizing empirical relationships.
    """

            "Income": "#4ECDC4",
            "Fixed Income": "#45B7D1",
            "Risk Management": "#96CEB4",
            "Portfolio Theory": "#FFEAA7",
            "Statistical Analysis": "#DDA0DD",
            "Currency Markets": "#98D8C8",
            "Cross-Asset": "#F7DC6F",
        }

        @staticmethod
        def create_formula_dashboard(analysis_results: Dict[str, Any]) -> go.Figure:
            """Create a comprehensive dashboard showing all formulaic relationships"""
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

        def _plot_reliability(self, fig: go.Figure, formulas: Any) -> None:
            """Plot the formula reliability (R-squared) for each formula onto the dashboard figure."""
            raise NotImplementedError()

        @staticmethod
        def _normalize_empirical_relationships(
            empirical_relationships: Any,
        ) -> Dict[str, Dict[str, float]]:
            """Normalize empirical_relationships into a nested dict
            of the form {row: {col: value}}."""
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
                            str(col): float(val)
                            for col, val in cols.items()
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
        elif (
            hasattr(empirical_relationships, "index")
            and hasattr(empirical_relationships, "columns")
        ):
            for row in empirical_relationships.index:
                for col in empirical_relationships.columns:
                    matrix.setdefault(str(row), {})[str(col)] = float(
                        empirical_relationships.loc[row, col]
                    )
        else:
            raise ValueError(
                f"Unsupported type for empirical relationships: {type(empirical_relationships)}"
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

    def _plot_category_distribution(self, fig: go.Figure, formulas: Any) -> None:
        """Plot distribution of formulas across categories using pie and
        bar charts.
        """
        raise NotImplementedError()

    def _plot_reliability(self, fig: go.Figure, formulas: Any) -> None:
        """Plot reliability (R-squared) of formulas using pie and bar charts."""
        raise NotImplementedError()

    def _plot_empirical_correlation(
        self, fig: go.Figure, empirical_relationships: Any
    ) -> None:
        """Plot empirical correlation matrix and corresponding bar chart of
        relationships
        """
        raise NotImplementedError()

    def _plot_asset_class_relationships(self, fig: go.Figure, formulas: Any) -> None:
        """Plot relationships between asset classes based on provided formulas."""
        raise NotImplementedError()

    def _plot_sector_analysis(self, fig: go.Figure, formulas: Any) -> None:
        """Plot sector analysis charts illustrating formula performance by sector."""
        raise NotImplementedError()

    def _plot_key_formula_examples(self, fig: go.Figure, formulas: Any) -> None:
        """Populate the "Key Formula Examples" table with the top
        formulas, sorted by reliability.
        """
        # Populate the "Key Formula Examples" table in row 3, column 2.
        # Select a subset of formulas to keep the table readable.
        if not formulas:
            return None

        sorted_formulas = self._get_sorted_formulas(formulas)
        top_formulas = sorted_formulas[:10]
        names = [self._format_name(f.name) for f in top_formulas]
        categories = [f.category for f in top_formulas]
        r_squares = [f"{f.r_squared:.3f}" for f in top_formulas]

        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Formula", "Category", "R-squared"],
                    fill_color="#f2f2f2",
                    align="left",
                ),
                cells=dict(
                    values=[names, categories, r_squares],
                    fill_color="#ffffff",
                    align="left",
                ),
            )
        )
        return None

    @staticmethod
    def _get_sorted_formulas(formulas: Any) -> list:
        """Helper to sort formulas by r_squared descending with fallback."""
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
        return name if len(name) <= max_length else name[: max_length - 3] + "..."

    @staticmethod
    def _format_r_squared(r_value: Any) -> str:
        """Format r_squared value to 4 decimal places or N/A."""
        return f"{r_value:.4f}" if isinstance(r_value, (int, float)) else "N/A"

    @staticmethod
    def _extract_formula_table_data(formulas: Any) -> tuple:
        """Helper to extract names, categories, and r-squared values for table."""
        names = [
            FormulaicVisualizer._format_name(getattr(f, "name", None)) for f in formulas
        ]
        categories = [getattr(f, "category", "N/A") for f in formulas]
        r_squared_values = [
            FormulaicVisualizer._format_r_squared(getattr(f, "r_squared", None))
            for f in formulas
        ]
        return names, categories, r_squared_values

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """Create a detailed view of a specific formula"""
        fig = go.Figure()

        # Create a text-based visualization of the formula
        #
        fig.add_annotation(
            text=(
                f"<b>{formula.name}</b><br><br>"
                f"<b>Mathematical Expression:</b><br>"
                f"{formula.formula}<br><br>"
                f"<b>LaTeX:</b><br>"
                f"{formula.latex}<br><br>"
                f"<b>Description:</b><br>"
                f"{formula.description}<br><br>"
                f"<b>Category:</b> {formula.category}<br>"
                f"<b>Reliability (R²):</b> {formula.r_squared:.3f}<br><br>"
                "<b>Variables:</b><br>"
                + "<br>".join(
                    [f"• {var}: {desc}" for var, desc in formula.variables.items()]
                )
                + "<br><br><b>Example Calculation:</b><br>"
                + f"{formula.example_calculation}"
            ),
            showarrow=False,
        )

    @staticmethod
    def create_correlation_network(
        empirical_relationships: Dict[str, Any],
    ) -> go.Figure:
        """Create a network graph showing asset correlations."""
        strongest_correlations = empirical_relationships.get(
            "strongest_correlations", []
        )
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})

    @staticmethod
    def create_correlation_network(
        empirical_relationships: Dict[str, Any],
    ) -> go.Figure:
        """Create a network graph showing asset correlations."""
        strongest_correlations = empirical_relationships.get("strongest_correlations", [])
        correlation_matrix = empirical_relationships.get("correlation_matrix", {}) or {}

        # Empty state
        if not strongest_correlations and not correlation_matrix:
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

        # Derive assets from strongest correlations, falling back to correlation_matrix keys.
        assets = sorted(
            {c.get("asset1") for c in strongest_correlations if c.get("asset1")}
            | {c.get("asset2") for c in strongest_correlations if c.get("asset2")}
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
        return FormulaicVisualizer._create_empty_correlation_figure()

        return FormulaicVisualizer._build_and_render_correlation_network(
            strongest_correlations,
            correlation_matrix,
        )

    @staticmethod
    def create_metric_comparison_chart(
        analysis_results: Dict[str, Any],
    ) -> go.Figure:
        """Create a chart comparing different metrics derived from formulas."""
        # Example logic: Compare theoretical vs empirical values if available
        # For now, we plot R-squared distribution by category
        formulas = analysis_results.get("formulas", [])
        if not formulas:
            return go.Figure()

        categories = {}
        for f in formulas:
            if f.category not in categories:
                categories[f.category] = []
            categories[f.category].append(f.r_squared)

        fig = go.Figure()

        # Create bar chart for each category
        category_names = list(categories.keys())
        r_squared_by_category = []
        formula_counts = []

        for category in category_names:
            category_formulas = categories[category]
            if category_formulas:
                avg_r_squared = sum(category_formulas) / len(category_formulas)
            else:
                avg_r_squared = 0.0
            r_squared_by_category.append(avg_r_squared)
            formula_counts.append(len(category_formulas))

        # R-squared bars
        fig.add_trace(
            go.Bar(
                name="Average R-squared",
                x=category_names,
                y=r_squared_by_category,
                marker=dict(color="lightcoral"),
                yaxis="y",
                offsetgroup=1,
            )
        )

        fig.update_layout(
            title="Formula Reliability Distribution by Category",
            yaxis_title="R-Squared Score",
            xaxis_title="Formula Category",
            showlegend=False,
            template="plotly_white",
        )
        return fig
