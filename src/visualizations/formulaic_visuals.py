import math
from typing import Any, Dict, List, Mapping, Tuple

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.formulaic_analysis import Formula

_MAX_HEATMAP_ASSETS = 8
_MAX_CORRELATION_EDGES = 10


class FormulaicVisualizer:
    """Visualizes mathematical formulas and relationships from financial analysis."""

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

    # ------------------------------------------------------------------ #
    # Dashboard                                                            #
    # ------------------------------------------------------------------ #

    def create_formula_dashboard(self, analysis_results: Dict[str, Any]) -> go.Figure:
        """Create comprehensive dashboard showing all formulaic relationships."""
        formulas = analysis_results.get("formulas", [])
        empirical_relationships = analysis_results.get("empirical_relationships", {})

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
            specs=[
                [{"type": "pie"}, {"type": "bar"}],
                [{"type": "heatmap"}, {"type": "bar"}],
                [{"type": "bar"}, {"type": "table"}],
            ],
            vertical_spacing=0.12,
            horizontal_spacing=0.1,
        )

        self._plot_category_distribution(fig, formulas)
        self._plot_reliability(fig, formulas)
        self._plot_empirical_correlation(fig, empirical_relationships)
        self._plot_asset_class_relationships(fig, formulas)
        self._plot_sector_analysis(fig, formulas)
        self._plot_key_formula_examples(fig, formulas)

        fig.update_layout(
            title="📊 Financial Formulaic Analysis Dashboard",
            height=1000,
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
        )
        # Preserve established dashboard layout expectations
        fig.update_layout(
            title="📊 Financial Formulaic Analysis Dashboard",
            height=1000,
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
        )

    @staticmethod
    def _plot_category_distribution(fig: go.Figure, formulas: Any) -> None:
        if not formulas:
            return
        categories: Dict[str, int] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
        fig.add_trace(
            go.Pie(
                labels=list(categories.keys()),
                values=list(categories.values()),
                hole=0.4,
            ),
            row=1,
            col=1,
        )

    @staticmethod
    def _plot_reliability(fig: go.Figure, formulas: Any) -> None:
        if not formulas:
            return
        categories: Dict[str, List[float]] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            categories.setdefault(cat, []).append(getattr(formula, "r_squared", 0.0))
        avg_r2 = {
            cat: sum(vals) / len(vals) for cat, vals in categories.items() if vals
        }
        fig.add_trace(
            go.Bar(
                x=list(avg_r2.keys()),
                y=list(avg_r2.values()),
                marker=dict(color="lightcoral"),
            ),
            row=1,
            col=2,
        )

    @staticmethod
    def _parse_correlation_matrix(
        correlation_matrix: Dict[str, Any],
    ) -> Tuple[List[str], List[List[float]]]:
        """Parse a flat {"asset1-asset2": value} dict into (assets, z_matrix)."""
        pair_values: Dict[Tuple[str, str], float] = {}
        asset_set: set = set()
        for key, value in correlation_matrix.items():
            parts = key.split("-")
            if len(parts) < 2:
                continue
            a1, a2 = parts[0], "-".join(parts[1:])
            pair_values[(a1, a2)] = float(value)
            pair_values[(a2, a1)] = float(value)
            asset_set.add(a1)
            asset_set.add(a2)
        assets = sorted(asset_set)[:_MAX_HEATMAP_ASSETS]
        z = [
            [pair_values.get((a1, a2), 1.0 if a1 == a2 else 0.0) for a2 in assets]
            for a1 in assets
        ]
        return assets, z

    @staticmethod
    def _plot_empirical_correlation(
        fig: go.Figure, empirical_relationships: Mapping[str, Any]
    ) -> None:
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})
        if not correlation_matrix or not isinstance(correlation_matrix, dict):
            return
        assets, z = FormulaicVisualizer._parse_correlation_matrix(correlation_matrix)
        if not assets:
            return
        fig.add_trace(
            go.Heatmap(z=z, x=assets, y=assets, colorscale="RdYlBu_r", zmin=-1, zmax=1),
            row=2,
            col=1,
        )

    @staticmethod
    def _plot_asset_class_relationships(fig: go.Figure, formulas: Any) -> None:
        if not formulas:
            return
        categories: Dict[str, int] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
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
        if not formulas:
            return
        categories: Dict[str, Dict[str, Any]] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            entry = categories.setdefault(cat, {"count": 0, "total_r2": 0.0})
            entry["count"] += 1
            entry["total_r2"] += getattr(formula, "r_squared", 0.0)
        performance = {
            cat: d["total_r2"] / d["count"]
            for cat, d in categories.items()
            if d["count"] > 0
        }
        fig.add_trace(
            go.Bar(
                x=list(performance.keys()),
                y=list(performance.values()),
                marker=dict(color="lightblue"),
            ),
            row=3,
            col=1,
        )

    def _plot_key_formula_examples(self, fig: go.Figure, formulas: Any) -> None:
        if not formulas:
            return
        top = self._get_sorted_formulas(formulas)[:10]
        names, categories, r2_values = self._extract_formula_table_data(top)
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Formula", "Category", "R-squared"],
                    fill_color="#f2f2f2",
                    align="left",
                ),
                cells=dict(
                    values=[names, categories, r2_values],
                    fill_color="#ffffff",
                    align="left",
                ),
            ),
            row=3,
            col=2,
        )

    # ------------------------------------------------------------------ #
    # Detail view                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """Create a detailed view of a specific formula."""
        variables_text = "<br>".join(
            f"• {var}: {desc}" for var, desc in formula.variables.items()
        )
        annotation_text = (
            f"<b>{formula.name}</b><br><br>"
            f"<b>Mathematical Expression:</b><br>{formula.expression}<br><br>"
            f"<b>LaTeX:</b><br>{formula.latex}<br><br>"
            f"<b>Description:</b><br>{formula.description}<br><br>"
            f"<b>Category:</b> {formula.category}<br>"
            f"<b>Reliability (R²):</b> {formula.r_squared:.3f}<br><br>"
            f"<b>Variables:</b><br>{variables_text}<br><br>"
            f"<b>Example Calculation:</b><br>{formula.example_calculation}"
        )
        fig = go.Figure()
        fig.add_annotation(
            text=annotation_text,
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            align="left",
            font=dict(size=12),
        )
        fig.update_layout(
            title=f"Formula Details: {formula.name}",
            height=600,
            plot_bgcolor="white",
        )
        return fig

    # ------------------------------------------------------------------ #
    # Correlation network                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_correlation_network(
        empirical_relationships: Mapping[str, Any],
    ) -> go.Figure:
        """Create a network graph showing asset correlations."""
        strongest_correlations = empirical_relationships.get(
            "strongest_correlations", []
        )
        if not strongest_correlations:
            return FormulaicVisualizer._create_empty_correlation_figure()
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})
        return FormulaicVisualizer._build_and_render_correlation_network(
            strongest_correlations[:_MAX_CORRELATION_EDGES],
            correlation_matrix,
        )

    @staticmethod
    def _create_empty_correlation_figure() -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(text="No correlation data available", showarrow=False)
        return fig

    @staticmethod
    def _build_and_render_correlation_network(
        strongest_correlations: Any,
        correlation_matrix: Any,
    ) -> go.Figure:
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
    def _extract_assets_from_correlations(correlations: Any) -> List[str]:
        assets: set = set()
        for corr in correlations:
            a1, a2, _ = FormulaicVisualizer._parse_correlation_item(corr)
            if a1:
                assets.add(a1)
            if a2:
                assets.add(a2)
        return sorted(a for a in assets if a)

    @staticmethod
    def _parse_correlation_item(corr: Any) -> Tuple[str, str, float]:
        if isinstance(corr, dict):
            return (
                corr.get("asset1", ""),
                corr.get("asset2", ""),
                corr.get("correlation", 0.0),
            )
        if isinstance(corr, (list, tuple)) and len(corr) >= 3:
            return corr[0], corr[1], corr[2]
        if isinstance(corr, (list, tuple)) and len(corr) >= 2:
            return corr[0], corr[1], 0.0
        return "", "", 0.0

    @staticmethod
    def _create_circular_positions(assets: List[str]) -> Dict[str, Tuple[float, float]]:
        n = len(assets)
        return {
            asset: (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
            for i, asset in enumerate(assets)
        }

    @staticmethod
    def _create_edge_traces(
        correlations: Any, positions: Dict[str, Tuple[float, float]]
    ) -> List[go.Scatter]:
        traces = []
        for corr in correlations:
            a1, a2, val = FormulaicVisualizer._parse_correlation_item(corr)
            if a1 in positions and a2 in positions:
                traces.append(
                    FormulaicVisualizer._create_single_edge_trace(
                        a1, a2, val, positions
                    )
                )
        return traces

    @staticmethod
    def _create_single_edge_trace(
        asset1: str,
        asset2: str,
        value: float,
        positions: Dict[str, Tuple[float, float]],
    ) -> go.Scatter:
        x0, y0 = positions[asset1]
        x1, y1 = positions[asset2]
        color = "red" if value > 0.7 else ("orange" if value > 0.4 else "lightgray")
        return go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(color=color, width=max(1, abs(value) * 5)),
            hoverinfo="text",
            text=f"{asset1} - {asset2}: {value:.3f}",
            showlegend=False,
        )

    @staticmethod
    def _create_node_trace(
        assets: List[str], positions: Dict[str, Tuple[float, float]]
    ) -> go.Scatter:
        return go.Scatter(
            x=[positions[a][0] for a in assets],
            y=[positions[a][1] for a in assets],
            mode="markers+text",
            text=assets,
            textposition="top center",
            marker=dict(size=20, color="lightblue", line=dict(color="black", width=2)),
            hoverinfo="text",
            showlegend=False,
        )

    # ------------------------------------------------------------------ #
    # Metric comparison                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_metric_comparison_chart(analysis_results: Dict[str, Any]) -> go.Figure:
        """Create a chart comparing metrics derived from formulas by category."""
        formulas = analysis_results.get("formulas", [])
        fig = go.Figure()

        if formulas:
            categories: Dict[str, List[float]] = {}
            for formula in formulas:
                cat = getattr(formula, "category", None) or (
                    formula.get("category", "Unknown")
                    if isinstance(formula, dict)
                    else "Unknown"
                )
                r2 = (
                    getattr(formula, "r_squared", None)
                    if not isinstance(formula, dict)
                    else formula.get("r_squared", 0.0)
                )
                categories.setdefault(cat, []).append(float(r2 or 0.0))

            names = list(categories.keys())
            avg_r2 = [sum(v) / len(v) for v in categories.values()]
            counts = [len(v) for v in categories.values()]

            fig.add_trace(go.Bar(name="Average R-squared", x=names, y=avg_r2))
            fig.add_trace(go.Bar(name="Formula Count", x=names, y=counts))

        fig.update_layout(
            title="Formula Categories: Reliability vs Count",
            xaxis_title="Formula Category",
            yaxis_title="Value",
            barmode="group",
            plot_bgcolor="white",
        )

        return fig

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_sorted_formulas(formulas: Any) -> List[Any]:
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
        if not isinstance(name, str) or not name:
            return "N/A"
        return name if len(name) <= max_length else f"{name[: max_length - 3]}..."

    @staticmethod
    def _format_r_squared(r_value: Any) -> str:
        if isinstance(r_value, (int, float)):
            return f"{r_value:.4f}"
        return "N/A"

    @staticmethod
    def _extract_formula_table_data(
        formulas: Any,
    ) -> Tuple[List[str], List[str], List[str]]:
        names = [
            FormulaicVisualizer._format_name(getattr(f, "name", None)) for f in formulas
        ]
        categories = [getattr(f, "category", "N/A") for f in formulas]
        r2_values = [
            FormulaicVisualizer._format_r_squared(getattr(f, "r_squared", None))
            for f in formulas
        ]
        return names, categories, r2_values
