"""Visualization helpers for formulaic financial analysis results."""

import math
from typing import Any, Dict, Mapping

import plotly.graph_objects as go  # type: ignore[import-untyped]
from plotly.subplots import make_subplots  # type: ignore[import-untyped]

from src.analysis.formulaic_analysis import Formula


class FormulaicVisualizer:
    """Visualize formulas and relationships from financial analysis."""

    def __init__(self) -> None:
        self.color_scheme = {
            "Valuation": "#FF6B6B",
            "Income": "#4ECDC4",
            "Fixed Income": "#45B7D1",
            "Risk Management": "#96CEB4",
            "Portfolio Theory": "#FFEAA7",Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.codacy/cli.sh around lines 140 - 143, The check comparing run_command to empty string is redundant because run_command is set from bin_path; instead verify the binary actually exists and is executable before proceeding: replace or supplement the current conditional that uses run_command with a filesystem check (e.g., test -f or test -x) against bin_path/run_command and call fatal with a clear message if the file is missing or not executable; update references around run_command, bin_path, and fatal so the script fails early with a descriptive error when the downloaded Codacy CLI binary isn't present or runnable.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.codacy/cli.sh at line 4, The script currently disables pipefail by using "+o pipefail" which hides pipeline errors (e.g., in get_latest_version()); update the shell options to enable pipefail instead—replace the "set -e +o pipefail" invocation with a form that enables pipefail (for example "set -e -o pipefail" or "set -eo pipefail") so pipeline failures cause the script to exit; ensure this change is made where the initial shell options are set (the line containing set and +o pipefail) and re-run tests that exercise get_latest_version().

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.codacy/cli.sh around lines 62 - 67, The script calls fatal() from functions like handle_rate_limit() but never defines it; add a simple fatal() function (e.g., fatal() { echo "Error: $*" >&2; exit 1; }) near the top of the script so any calls from handle_rate_limit(), the curl/wget checks, and other places print to stderr and exit non‑zero; ensure the function accepts a message parameter and uses >&2 and exit 1 so all existing fatal "..." usages work as intended.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.codacy/cli.sh around lines 122 - 127, The current assignment of version via command substitution of get_version_from_yaml can yield an empty string if get_version_from_yaml fails; update the conditional so that when CODACY_CLI_V2_VERSION is unset you call get_version_from_yaml and check its exit status and/or the resulting value before assigning to version—if get_version_from_yaml fails or returns empty, either set a sensible default or exit with an error; ensure this logic touches the conditional that references CODACY_CLI_V2_VERSION, the get_version_from_yaml invocation, and the version variable so we never proceed with an empty $version.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.codacy/cli.sh around lines 49 - 60, The get_latest_version function can return an empty string when the GitHub API fails, causing downstream invalid URLs; update get_latest_version to validate the parsed tag (the local variable version), check it's non-empty and matches expected pattern (e.g., semver or starts with "v"), and if invalid call handle_rate_limit if not already handled, print a clear error via process-style logger or stderr and exit with non-zero status (or return a failure code) instead of echoing an empty version; ensure callers of get_latest_version (download logic) only proceed when the function returns a valid version.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.editorconfig at line 17, The .editorconfig sets max_line_length = 88 which conflicts with the project's Python guideline of 120; update the configuration to enforce 120 (change max_line_length to 120) and ensure Black is configured to use 120 characters via pyproject.toml (or CI flags) so formatting is consistent, then reformat the repository or run Black to align files with the new limit; alternatively, if 88 is intended, update the project docs that reference the 120-character rule to avoid contradictions.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.flake8 at line 2, The .flake8 setting currently sets max-line-length = 88 which conflicts with the project's documented guideline of 120; reconcile by either updating CONTRIBUTING.md to state Black's default 88 if you intend to adopt Black's default, or change .flake8 back to max-line-length = 120 and ensure Black is configured with --line-length 120 (e.g., in pyproject.toml) so tools and docs match; update whichever files are necessary (CONTRIBUTING.md, .flake8, and Black configuration) so the canonical line-length is consistent across code, linter, and documentation.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.github/pr-copilot/scripts/analyze_pr.py around lines 373 - 379, The current validation uses temp_root and os.path.commonpath to reject GITHUB_STEP_SUMMARY paths that are valid on GitHub-hosted runners; update the check to use the runner-provided allowed roots and robust normalization: read RUNNER_TEMP (os.environ.get("RUNNER_TEMP")) and GITHUB_WORKSPACE as allowed roots, resolve gh_summary into summary_path via pathlib.Path(...).resolve(), ensure summary_path is inside at least one of those allowed roots (e.g., summary_path.is_relative_to(runner_temp) or workspace) and reject paths containing parent traversal by comparing resolved vs. original normalized path, leaving the rest of the logic around gh_summary, summary_path and the warning intact.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.github/pr-copilot/scripts/generate_status.py around lines 307 - 321, The path validation using temp_root and os.path.commonpath (summary_path, temp_root) incorrectly rejects real GITHUB_STEP_SUMMARY locations; remove the overly restrictive check and the associated warning so the code always appends to GITHUB_STEP_SUMMARY (keep the existing try/except around open and write), or if you must validate, replace the commonpath logic with a traversal-safe check: resolve summary_path with os.path.realpath/os.path.normpath, ensure it is absolute and does not contain ".." segments (or optionally verify it resides under the runner workspace by comparing against GITHUB_WORKSPACE), referencing the summary_path and temp_root/commonpath logic near the write block to locate the code to change.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.github/pr-copilot/scripts/suggest_fixes.py around lines 304 - 318, The current check comparing summary_path to tempfile.gettempdir() prevents writing GITHUB_STEP_SUMMARY on GitHub Actions; update the logic around gh_summary/summary_path to instead validate that the path exists and is writable (os.path.exists and os.access) or, if present, confirm it is under the RUNNER_TEMP directory from the environment (os.environ.get("RUNNER_TEMP")) before writing; modify the block that uses summary_path and temp_root so it falls back to a writable-existence check when RUNNER_TEMP is not set to avoid rejecting legitimate Action step summary locations.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/.github/scripts/schema_report_cli.py around lines 183 - 197, The cleanup currently can delete a finished report because safe_output points to the final file; change the logic so cleanup_partial_output only removes temporary/partial files (not the final target) by tracking completion and/or the temp path: update write_atomic to (1) write to a distinct temp Path (e.g., temp_path), only set safe_output to the final output after the atomic rename, and (2) catch BaseException (not just Exception) around the write/rename, call cleanup_partial_output(temp_path) when interrupted, then re-raise; adjust cleanup_partial_output signature to accept the temp_path or a completed flag and only unlink when the path is the temp/partial file (or completed is False) so a successfully renamed final file is never deleted (refer to functions write_atomic, cleanup_partial_output, safe_output, generate_report).

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/api/cors_utils.py around lines 17 - 22, The regex _HTTPS_DOMAIN_RE currently rejects origins with ports; update it to accept an optional port suffix or strip the port in _is_valid_https_idn before matching. E.g., modify _HTTPS_DOMAIN_RE to allow an optional ":\d{1,5}" immediately before the end anchor (so it still validates domains but permits ":<port>"), or alternatively parse the origin in _is_valid_https_idn (using urlparse) and pass only the hostname/IDN part to the regex; reference the symbols _HTTPS_DOMAIN_RE and _is_valid_https_idn when applying the change.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/api/graph_lifecycle.py around lines 43 - 44, Replace the runtime-only assert with an explicit check that graph_state.graph is not None before returning it: locate the code that currently does "assert graph_state.graph is not None" and "return graph_state.graph", change it to test the attribute and raise a clear exception (e.g., RuntimeError or ValueError with a descriptive message) if it's None so the function never returns None under optimized Python; keep references to graph_state.graph and the surrounding function or method when making the change.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/api/main.py around lines 700 - 706, Remove the stray FastAPI route decorator from the helper function _calculate_node_degrees so it is no longer registered as the "/api/visualization" endpoint; specifically, delete the @app.get("/api/visualization", response_model=VisualizationDataResponse) line that precedes the _calculate_node_degrees definition and leave the function as a private helper (accepting g: AssetRelationshipGraph) so the real route handler defined later remains the actual endpoint.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/frontend/app/components/AssetList.tsx around lines 167 - 174, The JSX in AssetList uses asset.price without guarding for null/undefined while asset.market_cap is type-checked; update the rendering for asset.price (in the AssetList component where asset.price is used) to mirror market_cap's defensive pattern — check typeof asset.price === "number" (or asset.price != null) before calling toFixed(2) and render a safe fallback like "N/A" or "-" when not a number; leave the existing market_cap handling as-is but ensure both fields use the same fallback format for consistency.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/pyproject.toml at line 167, The Pylint configuration in pyproject.toml sets max-line-length = 88 which conflicts with Black and the project guideline of 120; update the Pylint setting "max-line-length" in pyproject.toml to 120 so Pylint line-length checks align with Black's formatting and the project's agreed line-length policy.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/pyproject.toml at line 108, Ruff's line-length is currently set to 88 in pyproject.toml which conflicts with Black and the project guideline of 120; update the "line-length" setting in pyproject.toml from 88 to 120 so Ruff, Black, and the project's coding guideline all use a 120-character limit and avoid formatter/linter conflicts.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/src/models/financial_models.py around lines 88 - 92, The validator _validate_currency_code currently uppercases only for the regex check which lets lowercase inputs like "usd" pass but leaves self.currency unchanged; update the model to normalise and validate consistently by converting the incoming currency to uppercase in __post_init__ (e.g., set self.currency = self.currency.upper() before calling _validate_currency_code) and have _validate_currency_code validate the already-normalised value (remove the .upper() inside the regex check), or alternatively enforce uppercase strictly by making _validate_currency_code reject values that are not already uppercase; apply this change around __post_init__, _validate_currency_code and any constructor/assignment points that set self.currency.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/src/visualizations/formulaic_visuals.py around lines 616 - 619, The parameter _correlation_matrix in _build_and_render_correlation_network is declared but unused; update the function docstring to state that _correlation_matrix (the full correlation matrix) is intentionally reserved for future/contextual use and kept for API compatibility (or alternatively remove the parameter if you prefer to simplify the signature). Locate the _build_and_render_correlation_network function and either add a single-line docstring note mentioning that _correlation_matrix is intentionally unused/reserved, or remove the _correlation_matrix parameter from the signature and update any callers to stop passing it.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/src/visualizations/graph_2d_visuals.py around lines 308 - 325, _spring_or_fallback_positions can return a dict missing entries for some asset_ids when get_3d_visualization_data_enhanced() returns a different asset_ids_ordered; ensure every id in the input asset_ids gets a position by merging fallback positions for missing items before calling _create_spring_layout_2d or before returning. Specifically, after building positions_3d from graph.get_3d_visualization_data_enhanced(), compute a circular fallback via _create_circular_layout(asset_ids) and for any asset_id in asset_ids that is not in positions_3d add the circular position to positions_3d (or otherwise supply a 2D position) so _create_spring_layout_2d and later _build_node_visual_components will not KeyError on missing asset ids.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/src/visualizations/graph_2d_visuals_traces.py around lines 177 - 197, _build_relationship_trace currently returns a line trace with no hover info; update it to build a parallel hovertext list (one entry per x/y point) populated for each relationship (e.g., f"{rel_type}: {source_id} → {target_id}" or include other rel fields from rel) and insert None for the separators, then pass that list into the returned go.Scatter via hovertext=... and set hoverinfo="text" (or hovermode-appropriate property) so each relationship line segment shows the intended hover content; keep the existing color logic using REL_TYPE_COLORS and the same edges_x/edges_y construction in _build_relationship_trace.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/src/visualizations/graph_visuals.py around lines 1100 - 1107, _fix the unexpected in-place mutation in _ensure_numeric_positions: do not modify the caller's array (positions[:]=...) — instead change the function to validate and return a numeric array (e.g., def _ensure_numeric_positions(positions: np.ndarray) -> np.ndarray), returning positions unchanged if it's already numeric, otherwise return positions.astype(float) (so readonly arrays are handled) and raise ValueError only if astype(float) fails; update any callers to use the returned array.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/src/visualizations/graph_visuals.py around lines 56 - 61, The regex in rgb_or_rgba_pattern is double-escaped and therefore matches literal backslashes; update the pattern in graph_visuals.py (variable rgb_or_rgba_pattern) to use single backslashes (preferably a raw string) so metacharacters work as intended, e.g. r"^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(,\s*[\d.]+\s*)?\)$", and keep the existing re.match(color) usage that returns True when it matches.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/src/visualizations/graph_visuals_traces.py around lines 345 - 354, Remove the broad try/except in _coerce_positions_to_numeric so conversion errors are not swallowed: delete the try/except block and return positions.astype(float) directly (allowing numpy to raise its own exceptions); if you need validation instead, perform explicit checks on positions (e.g., verify dtype or use np.isfinite/np.can_cast) before calling astype rather than catching Exception.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/test_db_module.py around lines 18 - 20, The test_database_connection function's docstring is missing required Returns and Raises sections; update the docstring for test_database_connection() to include a brief description, a Returns section stating it returns bool (True on successful connection, False or as appropriate), and a Raises section documenting any exceptions the function may raise (e.g., DatabaseConnectionError or generic Exception used by the database module) so it conforms to the project's docstring guidelines.

- Verify each finding against the current code and only fix it if needed.

In @financial-asset-relationship-db/test_supabase.py around lines 101 - 108, The function _execute_smoke_query is missing a return type annotation; update its signature to include an appropriate return type such as typing.Any (import Any from typing at top of file) so the signature becomes def _execute_smoke_query(client: Client, url: str) -> Any:, and ensure the import for Any is added alongside existing imports; keep the existing exception handling and return behavior unchanged.
            "Statistical Analysis": "#DDA0DD",
            "Currency Markets": "#98D8C8",
            "Cross-Asset": "#F7DC6F",
        }

    def create_formula_dashboard(
        self,
        analysis_results: Dict[str, Any],
    ) -> go.Figure:
        """Create a dashboard for formulaic relationships."""
        formulas = analysis_results.get("formulas", [])
        empirical_relationships = analysis_results.get(
            "empirical_relationships",
            {},
        )

        # Pre-aggregate formula statistics to prevent redundant iterations
        category_stats = self._aggregate_category_stats(formulas)

        fig = self._initialize_dashboard_figure()

        self._plot_category_distribution(fig, category_stats)
        self._plot_reliability(fig, category_stats)
        self._plot_empirical_correlation(fig, empirical_relationships)
        self._plot_asset_class_relationships(fig, category_stats)
        self._plot_sector_analysis(fig, category_stats)
        self._plot_key_formula_examples(fig, formulas)

        self._apply_dashboard_layout(fig)

        return fig

    @staticmethod
    def _initialize_dashboard_figure() -> go.Figure:
        """Initialize the empty subplot grid for the formula dashboard."""
        return make_subplots(
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

    @staticmethod
    def _apply_dashboard_layout(fig: go.Figure) -> None:
        """Apply final layout configurations to the dashboard figure."""
        fig.update_layout(
            title="📊 Financial Formulaic Analysis Dashboard",
            height=1000,
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
        )

    # ------------------------------------------------------------------
    # Dashboard plotting methods
    # ------------------------------------------------------------------

    def _aggregate_category_stats(self, formulas: Any) -> Dict[str, Dict[str, float]]:
        """Compute counts and average R-squared per category once."""
        stats: Dict[str, Dict[str, float]] = {}
        if not formulas:
            return stats
        
        for formula in formulas:
            cat = getattr(formula, "category", None) or "Unknown"
            r2 = getattr(formula, "r_squared", 0.0) or 0.0
            if cat not in stats:
                stats[cat] = {"count": 0.0, "total_r2": 0.0}
            stats[cat]["count"] += 1.0
            stats[cat]["total_r2"] += r2
            
        for data in stats.values():
            data["avg_r2"] = data["total_r2"] / data["count"] if data["count"] > 0 else 0.0
            
        return stats

    def _plot_category_distribution(self, fig: go.Figure, category_stats: Dict[str, Dict[str, float]]) -> None:
        """Plot distribution of formulas across categories."""
        if not category_stats:
            return

        categories = list(category_stats.keys())
        counts = [data["count"] for data in category_stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in categories]

        fig.add_trace(
            go.Pie(
                labels=categories,
                values=counts,
                hole=0.4,
                marker={"colors": colors},
            ),
            row=1,
            col=1,
        )

    def _plot_reliability(self, fig: go.Figure, category_stats: Dict[str, Dict[str, float]]) -> None:
        """
        Add a bar chart of average R-squared by formula category to the given
        figure.

        Aggregates R-squared values from `formulas` grouped by each formula's
        `category`, computes the average R-squared for each category, and
        adds a bar trace to the subplot at row 1, column 2. If `formulas` is
        empty or falsy, the function does nothing.

        Parameters:
            fig (go.Figure): Plotly figure to which
                the bar trace will be added.
            category_stats (Dict[str, Dict[str, float]]): Pre-aggregated
                statistics per category containing 'avg_r2' values.
        """
        if not category_stats:
            return

        categories = list(category_stats.keys())
        avgs = [data["avg_r2"] for data in category_stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in categories]

        fig.add_trace(
            go.Bar(
                x=categories,
                y=avgs,
                marker={"color": colors},
            ),
            row=1,
            col=2,
        )

    @staticmethod
    def _plot_empirical_correlation(
        fig: go.Figure,
        empirical_relationships: Mapping[str, Any],
    ) -> None:
        """
        Add an empirical correlation heatmap to the provided subplot
        figure when a valid correlation matrix is available.

        If ``empirical_relationships`` contains a
        ``correlation_matrix`` mapping of asset names to numeric
        correlations, this function adds a heatmap trace to row 2,
        column 1 showing correlations for the ordered asset list. If
        no valid correlation matrix is present, the function returns
        without modifying the figure.

        Parameters:
            fig (go.Figure): The Plotly Figure (with subplots) to
                receive the heatmap trace.
            empirical_relationships (Mapping[str, Any]): Mapping
                expected to contain a "correlation_matrix" key whose
                value is a dict mapping asset names to dictionaries
                of asset-to-correlation values.
        """
        correlation_matrix = FormulaicVisualizer._extract_correlation_matrix(
            empirical_relationships
        )
        if not correlation_matrix:
            return

        assets, z = FormulaicVisualizer._build_correlation_grid(
            correlation_matrix
        )
        if not assets:
            return

        fig.add_trace(
            go.Heatmap(
                z=z,
                x=assets,
                y=assets,
                colorscale="RdYlBu_r",
                zmin=-1,
                zmax=1,
            ),
            row=2,
            col=1,
        )

    @staticmethod
    def _extract_correlation_matrix(
        empirical_relationships: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Extract a dictionary-like correlation matrix from relationships."""
        if not isinstance(empirical_relationships, dict):
            return {}
        matrix = empirical_relationships.get("correlation_matrix")
        return matrix if isinstance(matrix, dict) else {}

    @staticmethod
    def _build_correlation_grid(
        correlation_matrix: Mapping[str, Any],
    ) -> tuple[list[str], list[list[float]]]:
        """Build ordered assets and matrix values for correlation heatmaps."""
        first_val = next(iter(correlation_matrix.values()), None)
        if isinstance(first_val, (int, float)):
            return FormulaicVisualizer._build_flat_correlation_grid(
                correlation_matrix
            )
        return FormulaicVisualizer._build_nested_correlation_grid(
            correlation_matrix
        )

    @staticmethod
    def _build_flat_correlation_grid(
        correlation_matrix: Mapping[str, Any],
    ) -> tuple[list[str], list[list[float]]]:
        """Build a heatmap grid from flat pair-keyed correlations."""
        assets = FormulaicVisualizer._collect_flat_assets(correlation_matrix)
        z = [
            FormulaicVisualizer._build_flat_correlation_row(
                source,
                assets,
                correlation_matrix,
            )
            for source in assets
        ]
        return assets, z

    @staticmethod
    def _collect_flat_assets(
        correlation_matrix: Mapping[str, Any]
    ) -> list[str]:
        """Collect sorted asset IDs from flat pair-keyed correlations."""
        assets_set: set[str] = set()
        for key in correlation_matrix:
            source, target = FormulaicVisualizer._split_pair_key(key)
            if source and target:
                assets_set.add(source)
                assets_set.add(target)
        return sorted(assets_set)[:8]

    @staticmethod
    def _build_flat_correlation_row(
        source: str,
        assets: list[str],
        correlation_matrix: Mapping[str, Any],
    ) -> list[float]:
        """Build one heatmap row for a source asset."""
        return [
            FormulaicVisualizer._flat_correlation_value(
                source,
                target,
                correlation_matrix,
            )
            for target in assets
        ]

    @staticmethod
    def _flat_correlation_value(
        source: str,
        target: str,
        correlation_matrix: Mapping[str, Any],
    ) -> float:
        """Return a correlation value for an unordered asset pair."""
        if source == target:
            return 1.0
        key1 = f"{source}-{target}"
        key2 = f"{target}-{source}"
        raw = correlation_matrix.get(key1, correlation_matrix.get(key2, 0.0))
        return FormulaicVisualizer._to_float(raw)

    @staticmethod
    def _split_pair_key(key: str) -> tuple[str, str]:
        """Split a `SOURCE-TARGET` key into parts."""
        if "-" not in key:
            return "", ""
        source, target = key.split("-", 1)
        return source, target

    @staticmethod
    def _build_nested_correlation_grid(
        correlation_matrix: Mapping[str, Any],
    ) -> tuple[list[str], list[list[float]]]:
        """Build a heatmap grid from nested asset correlation mappings."""
        assets = sorted(correlation_matrix.keys())[:8]
        z: list[list[float]] = []
        for source in assets:
            source_map = correlation_matrix.get(source, {})
            source_map = source_map if isinstance(source_map, dict) else {}
            row = [
                FormulaicVisualizer._to_float(source_map.get(target, 0.0))
                for target in assets
            ]
            z.append(row)
        return assets, z

    @staticmethod
    def _to_float(value: Any) -> float:
        """Safely coerce input values to float."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _plot_asset_class_relationships(self, fig: go.Figure, category_stats: Dict[str, Dict[str, float]]) -> None:
        """Plot relationships between asset classes."""
        if not category_stats:
            return

        categories = list(category_stats.keys())
        counts = [data["count"] for data in category_stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in categories]

        fig.add_trace(
            go.Bar(
                x=categories,
                y=counts,
                marker={"color": colors},
            ),
            row=2,
            col=2,
        )

    def _plot_sector_analysis(self, fig: go.Figure, category_stats: Dict[str, Dict[str, float]]) -> None:
        """
        Visualizes average R-squared by formula category as a bar chart and
        adds it to the dashboard.

        Parameters:
            fig (go.Figure): Plotly Figure containing
                the subplot grid where the
                bar trace will be added (row 3, col 1).
            category_stats (Dict[str, Dict[str, float]]): Pre-aggregated
                statistics per category containing 'avg_r2' values.
        """
        if not category_stats:
            return

        categories = list(category_stats.keys())
        avgs = [data["avg_r2"] for data in category_stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in categories]

        fig.add_trace(
            go.Bar(
                x=categories,
                y=avgs,
                marker={"color": colors},
            ),
            row=3,
            col=1,
        )

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _plot_key_formula_examples(
        self,
        fig: go.Figure,
        formulas: Any,
    ) -> None:
        """
        Add a "Key Formula Examples" table to the figure showing the
        top 10 formulas ranked by R-squared.

        The table is placed at row 3, column 2 and lists each formula's
        name, category, and formatted R-squared.
        If `formulas` is falsy, no trace is added.

        Parameters:
            fig (go.Figure): Plotly Figure with a subplot grid to which
                the table trace will be added.
            formulas (Any): Iterable of formula objects or mappings;
                items should provide `name`, `category`, and `r_squared`
                (missing or invalid fields are handled).
        """
        if not formulas:
            return

        sorted_formulas = self._get_sorted_formulas(formulas)
        top_formulas = sorted_formulas[:10]

        names, categories, r_squared_values = self._extract_formula_table_data(
            top_formulas
        )

        fig.add_trace(
            go.Table(
                header={
                    "values": ["Formula", "Category", "R-squared"],
                    "fill_color": "#f2f2f2",
                    "align": "left",
                },
                cells={
                    "values": [names, categories, r_squared_values],
                    "fill_color": "#ffffff",
                    "align": "left",
                },
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
        """
        Prepare parallel lists of formula display names, categories, and
        formatted R-squared values for table rendering.

        Parameters:
                formulas (Iterable): An iterable of objects
                    (typically Formula instances)
                    from which `name`, `category`, and
                    `r_squared` attributes are read.
                    Missing values are handled gracefully.

        Returns:
                tuple[list[str], list[str], list[str]]: Three lists in order:
                        - names: Display-ready formula names
                            (truncated with ellipsis when long or
                             "N/A" if unavailable).
                        - categories: Formula category strings
                            or "N/A" if missing.
                        - r_squared_values: R-squared values formatted as
                            strings (four decimals) or "N/A" if not numeric.
        """
        names = [
            FormulaicVisualizer._format_name(getattr(f, "name", None))
            for f in formulas
        ]
        categories = [getattr(f, "category", "N/A") for f in formulas]
        r_squared_values = [
            FormulaicVisualizer._format_r_squared(
                getattr(f, "r_squared", None)
            )
            for f in formulas
        ]
        return names, categories, r_squared_values

    # ------------------------------------------------------------------
    # Detail & comparison views
    # ------------------------------------------------------------------

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """
        Builds an annotated Plotly figure
        presenting full details for a Formula.

        The figure contains a single annotation that displays the formula's
        mathematical expression, LaTeX representation, descriptive text,
        category, R² reliability, variables with descriptions, and an example
        calculation.

        Parameters:
            formula (Formula): The formula object to render;
                expected to provide
                attributes name, formula, latex, description, category,
                r_squared, variables (mapping of variable name to
                description), and example_calculation.

        Returns:
            go.Figure: A Plotly Figure with a formatted annotation summarizing
                the provided formula.
        """
        fig = go.Figure()

        fig.add_annotation(
            text=(
                f"<b>{formula.name}</b><br><br>"
                "<b>Mathematical Expression:</b><br>"
                f"{formula.expression}<br><br>"
                "<b>LaTeX:</b><br>"
                f"{formula.latex}<br><br>"
                "<b>Description:</b><br>"
                f"{formula.description}<br><br>"
                f"<b>Category:</b> {formula.category}<br>"
                f"<b>Reliability (R²):</b> {formula.r_squared:.3f}<br><br>"
                "<b>Variables:</b><br>"
                + (
                    "<br>".join(
                        f"• {var}: {desc}"
                        for var, desc in formula.variables.items()
                    )
                )
                + "<br><br><b>Example Calculation:</b><br>"
                f"{formula.example_calculation}"
            ),
            showarrow=False,
        )

        fig.update_layout(
            title=f"Formula Details: {formula.name}",
            height=600,
            plot_bgcolor="white",
        )

        return fig

    # ------------------------------------------------------------------
    # Correlation network (stubbed safely)
    # ------------------------------------------------------------------

    @staticmethod
    def create_correlation_network(
        empirical_relationships: Mapping[str, Any],
    ) -> go.Figure:
        """
        Builds a network visualization of asset correlations.

        Parameters:
            empirical_relationships (Mapping[str, Any]):
                Mapping that may include:
                - "strongest_correlations": an iterable of
                  correlation items (each item can be a dict or sequence
                  describing an asset pair and their correlation value).
                - "correlation_matrix": optional matrix or mapping of pairwise
                  correlations used for reference or weighting.

        Returns:
            go.Figure: A Plotly Figure showing a network of the
                strongest asset correlations, or an empty placeholder Figure
                with an explanatory title when no strongest correlations are
                provided.
        """
        strongest_correlations = empirical_relationships.get(
            "strongest_correlations", []
        )
        correlation_matrix = empirical_relationships.get(
            "correlation_matrix", {}
        )

        if not strongest_correlations:
            return FormulaicVisualizer._create_empty_correlation_figure()

        return FormulaicVisualizer._build_and_render_correlation_network(
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
        _correlation_matrix: Any,
    ) -> go.Figure:
        """
        Builds a network graph visualizing the strongest asset correlations.

        Parameters:
            strongest_correlations (Any): Iterable of correlation items
                (e.g., dicts or sequences) describing pairwise relationships
                to render as edges.
            _correlation_matrix (Any): Optional full
                correlation matrix or mapping
                used as contextual data for the network. Intentionally reserved
                for future/contextual use and kept for API compatibility.

        Returns:
            A Plotly Figure containing edge traces and a node trace
                representing the correlation network, or a Figure titled
                "No valid asset correlations found" when no assets can be
                extracted.
        """
        top_correlations = (
            strongest_correlations[:10]
            if isinstance(strongest_correlations, (list, tuple))
            else list(strongest_correlations)[:10]
        )

        assets = FormulaicVisualizer._extract_assets_from_correlations(
            top_correlations
        )
        if not assets:
            fig = go.Figure()
            fig.update_layout(title="No valid asset correlations found")
            return fig

        positions = FormulaicVisualizer._create_circular_positions(assets)
        edge_traces = FormulaicVisualizer._create_edge_traces(
            top_correlations, positions
        )
        node_trace = FormulaicVisualizer._create_node_trace(assets, positions)

        fig = go.Figure(data=edge_traces + [node_trace])
        fig.update_layout(
            title="Asset Correlation Network",
            showlegend=False,
            hovermode="closest",
            xaxis={
                "showgrid": False,
                "zeroline": False,
                "showticklabels": False,
            },
            yaxis={
                "showgrid": False,
                "zeroline": False,
                "showticklabels": False,
            },
        )
        return fig

    @staticmethod
    def _extract_assets_from_correlations(correlations: Any) -> list[str]:
        """Extract unique sorted assets from correlation data."""
        assets = set()
        for corr in correlations:
            asset1, asset2, _ = FormulaicVisualizer._parse_correlation_item(
                corr
            )
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
        """
        Compute evenly spaced coordinates on the unit circle for each asset.

        Positions start at angle 0 (point (1.0, 0.0)) and proceed
        counterclockwise, placing assets evenly by index.

        Parameters:
            assets (list[str]): Ordered list of asset identifiers.

        Returns:
            Dict[str, tuple[float, float]]:
                Mapping from asset identifier to its (x, y)
                coordinate on the unit circle.
        """
        n = len(assets)
        positions = {}
        for i, asset in enumerate(assets):
            angle = 2 * math.pi * i / n
            positions[asset] = (math.cos(angle), math.sin(angle))
        return positions

    @staticmethod
    def _create_edge_traces(
        correlations: Any,
        positions: Dict[str, tuple[float, float]],
    ) -> list[go.Scatter]:
        """
        Builds Plotly line traces for correlations
        connecting positioned assets.

        Parameters:
            correlations (Any):
                Iterable of correlation items parsable by
                _parse_correlation_item (each should yield asset1,
                asset2, value).
            positions (Dict[str, tuple[float, float]]):
                Mapping from asset name to (x, y) coordinates for node
                placement.
        Returns:
            list[go.Scatter]:
                Scatter line traces for each correlation where both assets
                have defined positions.
        """
        edge_traces = []
        if not isinstance(correlations, (list, tuple)):
            return []
        for corr in correlations:
            asset1, asset2, value = FormulaicVisualizer._parse_correlation_item(
                corr
            )
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
        """
        Create a Plotly line trace representing
        a correlation edge between two assets.

        The trace connects the (x, y) positions for asset1 and asset2,
        uses red for
        negative correlations and green for
        non-negative correlations. The line width
        is scaled as max(1, abs(value) * 5), and the hover text is set to
        "asset1 - asset2: value" with the value formatted to three decimals.

        Parameters:
            asset1 (str): Identifier of the first asset.
            asset2 (str): Identifier of the second asset.
            value (float): Correlation value between
                the two assets; sign determines
                trace color.
            positions (Dict[str, tuple[float, float]]):
                Mapping from asset identifiers
                to (x, y) coordinates.

        Returns:
            go.Scatter: A line trace connecting
                the two asset positions with color
                and width reflecting the correlation value.
        """
        x0, y0 = positions[asset1]
        x1, y1 = positions[asset2]
        color = "red" if value < 0 else "green"
        width = max(1, abs(value) * 5)

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
        """
        Create a Plotly scatter trace representing
        asset nodes positioned on a plane.

        Each asset is rendered as a labeled marker placed at the
        (x, y) coordinates from `positions`; markers include hover text and
        display the asset name above the marker.

        Parameters:
            assets (list[str]): Ordered list of
                asset names to include in the trace.
            positions (Dict[str, tuple[float, float]]):
                Mapping from asset name to its
                (x, y) coordinates.

        Returns:
            go.Scatter: A Scatter trace with markers and text labels
                for the provided assets.
        """
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
                "line": {
                    "color": "black",
                    "width": 2,
                },
            },
            hoverinfo="text",
            showlegend=False,
        )

    # ------------------------------------------------------------------
    # Metric comparison
    # ------------------------------------------------------------------

    def create_metric_comparison_chart(
        self,
        analysis_results: Dict[str, Any],
    ) -> go.Figure:
        """
        Generate a bar chart comparing average R-squared per formula
        category.

        Parameters:
            analysis_results (Dict[str, Any]): Analysis output that may
                include a "formulas" key with a list of Formula objects.
                Each object provides `category` and `r_squared`
                attributes.

        Returns:
            go.Figure: A Plotly Figure containing a bar chart of average
                R-squared per category.
                Returns an empty Figure if no formulas are present.
        """
        formulas = analysis_results.get("formulas", [])
        fig = go.Figure()

        if not formulas:
            return fig

        stats = self._aggregate_category_stats(formulas)
        category_names = list(stats.keys())
        r_squared_by_category = [data["avg_r2"] for data in stats.values()]
        count_by_category = [data["count"] for data in stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in category_names]

        fig.add_trace(
            go.Bar(
                name="Average R-squared",
                x=category_names,
                y=r_squared_by_category,
                marker={"color": colors},
            )
        )

        fig.add_trace(
            go.Bar(
                name="Formula Count",
                x=category_names,
                y=count_by_category,
                marker={"color": colors},
            )
        )

        self._apply_metric_comparison_layout(fig)

        return fig

    @staticmethod
    def _apply_metric_comparison_layout(fig: go.Figure) -> None:
        """Apply layout configurations to the metric comparison chart."""
        fig.update_layout(
            title="Formula Categories: Reliability vs Count",
            xaxis_title="Formula Category",
            yaxis_title="Value",
            barmode="group",
            plot_bgcolor="white",
        )
