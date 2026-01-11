import math
from typing import Any, Dict

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.formulaic_analysis import Formula


class FormulaicVisualizer:
    """Visualizes mathematical formulas and relationships from financial analysis"""

    def __init__(self):
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
        """Create a comprehensive dashboard showing all formulaic relationships"""
        formulas = analysis_results.get("formulas", [])
        empirical_relationships = analysis_results.get("empirical_relationships", {})

        # Create subplots
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

        # 1. Formula Categories Pie Chart
        categories = analysis_results.get("categories", {})
        if categories:
            fig.add_trace(
                go.Pie(
                    labels=list(categories.keys()),
                    values=list(categories.values()),
                    hole=0.4,
                    marker=dict(colors=[self.color_scheme.get(cat, "#CCCCCC") for cat in categories.keys()]),
                    textinfo="label+percent",
                    textposition="auto",
                ),
                row=1,
                col=1,
            )

        # 2. Formula Reliability Bar Chart
        if formulas:
            formula_names = [f.name[:20] + "..." if len(f.name) > 20 else f.name for f in formulas]
            r_squared_values = [f.r_squared for f in formulas]
            colors = [self.color_scheme.get(f.category, "#CCCCCC") for f in formulas]

            fig.add_trace(
                go.Bar(
                    x=formula_names,
                    y=r_squared_values,
                    marker=dict(color=colors),
                    text=[f"{r:.2f}" for r in r_squared_values],
                    textposition="auto",
                    name="R-squared",
                ),
                row=1,
                col=2,
            )

        # 3. Empirical Correlation Heatmap
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})
        if correlation_matrix:
            # Convert correlation matrix to heatmap format
            assets = list(
                set(
                    [pair.split("-")[0] for pair in correlation_matrix.keys()]
                    + [pair.split("-")[1] for pair in correlation_matrix.keys()]
                )
            )

            # Create correlation matrix
            n_assets = min(len(assets), 8)  # Limit to 8x8 for visibility
            assets = assets[:n_assets]

            z_matrix = []
            for i, asset1 in enumerate(assets):
                row = []
                for j, asset2 in enumerate(assets):
                    if i == j:
                        corr = 1.0
                    else:
                        key1 = f"{asset1}-{asset2}"
                        key2 = f"{asset2}-{asset1}"
                        corr = correlation_matrix.get(key1, correlation_matrix.get(key2, 0.5))
                    row.append(corr)
                z_matrix.append(row)

            fig.add_trace(
                go.Heatmap(
                    z=z_matrix,
                    x=assets,
                    y=assets,
                    colorscale="RdYlBu_r",
                    zmin=-1,
                    zmax=1,
                    text=[[f"{val:.2f}" for val in row] for row in z_matrix],
                    texttemplate="%{text}",
                    textfont={"size": 10},
                    colorbar=dict(title="Correlation"),
                ),
                row=2,
                col=1,
            )

        # 4. Asset Class Relationships
        asset_class_data = empirical_relationships.get("asset_class_relationships", {})
        if asset_class_data:
            classes = list(asset_class_data.keys())
            asset_counts = [data["asset_count"] for data in asset_class_data.values()]

            fig.add_trace(
                go.Bar(
                    x=classes,
                    y=asset_counts,
                    name="Asset Count",
                    marker=dict(color="lightblue"),
                    yaxis="y",
                    offsetgroup=1,
                ),
                row=2,
                col=2,
            )

        # 5. Sector Analysis
        sector_data = empirical_relationships.get("sector_relationships", {})
        if sector_data:
            sectors = list(sector_data.keys())[:6]  # Limit to top 6 sectors
            sector_counts = [sector_data[sector]["asset_count"] for sector in sectors]

            fig.add_trace(
                go.Bar(
                    x=sectors, y=sector_counts, marker=dict(color="lightgreen"), text=sector_counts, textposition="auto"
                ),
                row=3,
                col=1,
            )

        # 6. Key Formula Examples Table
        if formulas:
            top_formulas = sorted(formulas, key=lambda f: f.r_squared, reverse=True)[:5]

            table_data = {
                "Formula": [f.name for f in top_formulas],
                "Category": [f.category for f in top_formulas],
                "R²": [f"{f.r_squared:.3f}" for f in top_formulas],
                "Mathematical Expression": [f.formula for f in top_formulas],
            }

            fig.add_trace(
                go.Table(
                    header=dict(
                        values=list(table_data.keys()), fill_color="paleturquoise", align="left", font=dict(size=10)
                    ),
                    cells=dict(
                        values=list(table_data.values()),
                        fill_color="lavender",
                        align="left",
                        font=dict(size=9),
                        height=25,
                    ),
                ),
                row=3,
                col=2,
            )

        # Update layout
        fig.update_layout(
            title=dict(text="📊 Financial Formulaic Analysis Dashboard", x=0.5, font=dict(size=20, color="#2C3E50")),
            height=1000,
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
            font=dict(family="Arial, sans-serif", size=10),
        )

        # Update axes
        fig.update_yaxes(title_text="Count", row=2, col=2)
        fig.update_yaxes(title_text="Asset Count", row=3, col=1)
        fig.update_xaxes(title_text="Asset Class", row=2, col=2)
        fig.update_xaxes(title_text="Sector", row=3, col=1)
        fig.update_yaxes(title_text="R-squared Value", row=1, col=2)

        return fig

    def create_formula_detail_view(self, formula: Formula) -> go.Figure:
        """Create a detailed view of a specific formula"""
        fig = go.Figure()

        # Create a text-based visualization of the formula
        fig.add_annotation(
            text=f"<b>{formula.name}</b><br><br>"
            + f"<b>Mathematical Expression:</b><br>{formula.formula}<br><br>"
            + f"<b>LaTeX:</b><br>{formula.latex}<br><br>"
            + f"<b>Description:</b><br>{formula.description}<br><br>"
            + f"<b>Category:</b> {formula.category}<br>"
            + f"<b>Reliability (R²):</b> {formula.r_squared:.3f}<br><br>"
            + "<b>Variables:</b><br>"
            + "<br>".join([f"• {var}: {desc}" for var, desc in formula.variables.items()])
            + f"<br><br><b>Example Calculation:</b><br>{formula.example_calculation}",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=12, family="Arial, sans-serif"),
            align="left",
            bgcolor=self.color_scheme.get(formula.category, "#F0F0F0"),
            bordercolor="#CCCCCC",
            borderwidth=2,
        )

        fig.update_layout(
            title=f"Formula Details: {formula.name}",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
            height=600,
            margin=dict(l=50, r=50, t=80, b=50),
        )

        return fig

    @staticmethod
    def create_correlation_network(empirical_relationships: Dict[str, Any]) -> go.Figure:
        """Create a network graph showing asset correlations"""
        strongest_correlations = empirical_relationships.get("strongest_correlations", [])

        if not strongest_correlations:
            fig = go.Figure()
            fig.add_annotation(
                text="No correlation data available",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=16),
            )
            return fig

        # Extract unique assets
        assets = list(
            set(
                [corr["asset1"] for corr in strongest_correlations]
                + [corr["asset2"] for corr in strongest_correlations]
            )
        )

        # Create positions in a circle
        n_assets = len(assets)
        angles = [2 * math.pi * i / n_assets for i in range(n_assets)]
        positions = {asset: (math.cos(angle), math.sin(angle)) for asset, angle in zip(assets, angles)}

        # Create edge traces
        edge_traces = []
        for corr in strongest_correlations[:10]:  # Limit to top 10 correlations
            asset1, asset2 = corr["asset1"], corr["asset2"]
            x0, y0 = positions[asset1]
            x1, y1 = positions[asset2]

            # Color based on correlation strength
            if corr["correlation"] > 0.7:
                color = "red"
                width = 4
            elif corr["correlation"] > 0.4:
                color = "orange"
                width = 3
            else:
                color = "lightgray"
                width = 2

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

        # Create node trace
        node_x = [positions[asset][0] for asset in assets]
        node_y = [positions[asset][1] for asset in assets]

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=assets,
            textposition="middle center",
            marker=dict(size=30, color="lightblue", line=dict(width=2, color="darkblue")),
            hoverinfo="text",
            hovertext=[f"Asset: {asset}" for asset in assets],
            showlegend=False,
        )

        # Create figure
        fig = go.Figure(data=edge_traces + [node_trace])

        fig.update_layout(
            title="📈 Asset Correlation Network",
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            annotations=[
                dict(
                    text="Node size represents asset importance<br>Line thickness represents correlation strength",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.005,
                    y=-0.002,
                    xanchor="left",
                    font=dict(size=10),
                )
            ],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
        )

        return fig

    @staticmethod
    def create_metric_comparison_chart(analysis_results: Dict[str, Any]) -> go.Figure:
        """Create a comparison chart of different financial metrics"""
        formulas = analysis_results.get("formulas", [])

        # Group formulas by category
        categories = {}
        for formula in formulas:
            if formula.category not in categories:
                categories[formula.category] = []
            categories[formula.category].append(formula)

        fig = go.Figure()

        # Create bar chart for each category
        category_names = list(categories.keys())
        r_squared_by_category = []
        formula_counts = []

        for category in category_names:
            category_formulas = categories[category]
            avg_r_squared = sum(f.r_squared for f in category_formulas) / len(category_formulas)
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

        # Formula count bars
        fig.add_trace(
            go.Bar(
                name="Formula Count",
                x=category_names,
                y=formula_counts,
                marker=dict(color="lightblue"),
                yaxis="y2",
                offsetgroup=2,
            )
        )

        fig.update_layout(
            title="📊 Formula Categories: Reliability vs Count",
            xaxis=dict(title="Category"),
            yaxis=dict(title="Average R-squared", side="left"),
            yaxis2=dict(title="Number of Formulas", side="right", overlaying="y"),
            barmode="group",
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
            legend=dict(x=0.7, y=1),
        )

        return fig
