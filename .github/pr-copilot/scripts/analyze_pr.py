#!/usr/bin/env python3
"""
Analyze PR complexity, scope, and health.

This script evaluates a PR to determine:
- File count and types changed
- Line change magnitude
- Potential scope issues
- Related issues/PRs
- Overall complexity score
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import traceback
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Graceful import handling
try:
    import yaml
    from github import Github, GithubException
except ImportError:
    print("Error: Required packages not installed.", file=sys.stderr)
    print("Run: pip install PyGithub pyyaml", file=sys.stderr)
    sys.exit(1)


# --- Configuration & Constants ---

CONFIG_PATH = ".github/pr-copilot-config.yml"

EXTENSION_MAP = {
    "py": "python",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "javascript",
    "tsx": "javascript",
    "html": "markup",
    "xml": "markup",
    "css": "style",
    "scss": "style",
    "sass": "style",
    "less": "style",
    "json": "config",
    "yaml": "config",
    "yml": "config",
    "toml": "config",
    "ini": "config",
    "md": "documentation",
    "rst": "documentation",
    "txt": "documentation",
    "sql": "database",
    "db": "database",
    "sqlite": "database",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "fish": "shell",
}


@dataclass(frozen=True)
class AnalysisData:
    """Container for PR analysis results."""

    file_analysis: Dict[str, Any]
    complexity_score: int
    risk_level: str
    scope_issues: List[str]
    related_issues: List[Dict[str, str]]
    commit_count: int


# --- Core Logic ---


def load_config() -> Dict[str, Any]:
    """
    Load repository configuration from the expected YAML file path.

    If the config file does not exist, cannot be read, or fails YAML parsing, an empty
    dictionary is returned and an informational or warning message is written to
    standard error.

    Returns:
        config (dict): Parsed configuration mapping from the YAML file, or an empty
        dict when the file is missing or on parse/I/O errors.
    """
    if not os.path.exists(CONFIG_PATH):
        print(
            f"Info: Config file not found at {CONFIG_PATH}, using defaults.",
            file=sys.stderr,
        )
        return {}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        print(f"Warning: Failed to load config: {e}", file=sys.stderr)
        return {}


def categorize_filename(filename: str) -> str:
    """Determine category based on filename or extension."""
    lower_name = filename.lower()

    # FIX: Check specific paths (workflows) BEFORE generic patterns (tests)
    if ".github/workflows" in filename:
        return "workflow"

    if any(x in lower_name for x in ["test", "spec"]):
        return "test"

    # Extract extension safely
    suffix = Path(filename).suffix.lstrip(".").lower()
    return EXTENSION_MAP.get(suffix, "other")


def analyze_pr_files(pr_files_iterable: Any) -> Dict[str, Any]:
    """
    Aggregate file-level statistics for a pull request's changed files.
    
    Parameters:
        pr_files_iterable (Iterable): An iterable of file-like objects representing changed files.
            Each object must provide `filename` (str), `additions` (int), and `deletions` (int).
    
    Returns:
        dict: Summary dictionary with keys:
            - file_count (int): total number of files processed
            - file_categories (Dict[str, int]): mapping from category name to count
            - total_additions (int): sum of all additions
            - total_deletions (int): sum of all deletions
            - total_changes (int): sum of additions and deletions
            - large_files (List[Dict[str, Any]]): list of files with more than 500 total changes;
              each entry contains `filename`, `changes`, `additions`, and `deletions`
            - has_large_files (bool): True if any large files were found, False otherwise
    """
    categories: Dict[str, int] = defaultdict(int)
    stats = {"additions": 0, "deletions": 0, "changes": 0}
    large_files: List[Dict[str, Any]] = []
    file_count = 0

    for pr_file in pr_files_iterable:
        file_count += 1
        category = categorize_filename(pr_file.filename)
        categories[category] += 1

        adds = pr_file.additions
        dels = pr_file.deletions
        total = adds + dels

        stats["additions"] += adds
        stats["deletions"] += dels
        stats["changes"] += total

        if total > 500:
            large_files.append(
                {
                    "filename": pr_file.filename,
                    "changes": total,
                    "additions": adds,
                    "deletions": dels,
                }
            )

    return {
        "file_count": file_count,
        "file_categories": dict(categories),
        "total_additions": stats["additions"],
        "total_deletions": stats["deletions"],
        "total_changes": stats["changes"],
        "large_files": large_files,
        "has_large_files": bool(large_files),
    }


def calculate_score(
    value: int,
    thresholds: List[Tuple[int, int]],
    default: int,
) -> int:
    """
    Map a numeric value to a score using an ordered list of thresholds.

    Parameters:
        value (int): The value to evaluate against thresholds.
        thresholds (List[Tuple[int, int]]): Ordered pairs of (limit, points); the first pair whose `limit` is less than `value` determines the returned points.
        default (int): The score to return if no threshold matches.

    Returns:
        int: The points associated with the first matching threshold, or `default` if none match.
    """
    for limit, points in thresholds:
        if value > limit:
            return points
    return default


def assess_complexity(
    file_data: Dict[str, Any],
    commit_count: int,
) -> Tuple[int, str]:
    """
    Estimate a pull request's complexity and assign a risk level.
    
    Parameters:
        file_data (dict): Aggregated file metrics containing at least:
            - file_count: total number of files changed
            - total_changes: sum of additions and deletions across files
            - has_large_files: boolean indicating presence of large-file changes
            - large_files: list of large-file entries used to compute penalties
        commit_count (int): Number of commits in the pull request.
    
    Returns:
        tuple: Two-item tuple describing the assessment.
            - score (int): Complexity score (higher values indicate greater complexity).
            - risk_level (str): Risk band: `"High"` if score >= 70, `"Medium"` if score >= 40, `"Low"` otherwise.
    """
    score = 0

    # File count impact
    score += calculate_score(
        file_data["file_count"],
        [(50, 30), (20, 20), (10, 10)],
        default=5,
    )

    # Line change impact
    score += calculate_score(
        file_data["total_changes"],
        [(2000, 30), (1000, 20), (500, 15)],
        default=5,
    )

    # Large file penalty (capped at 20)
    if file_data["has_large_files"]:
        penalty = len(file_data["large_files"]) * 5
        score += min(penalty, 20)

    # Commit count impact
    score += calculate_score(
        commit_count,
        [(50, 20), (20, 15), (10, 10)],
        default=5,
    )

    if score >= 70:
        return score, "High"
    if score >= 40:
        return score, "Medium"
    return score, "Low"


def find_scope_issues(
    pr_title: str,
    file_data: Dict[str, Any],
    config: Dict[str, Any],
) -> List[str]:
    """
    Detects potential PR scope issues based on title length/content, overall size, and diversity of changed file types.

    Parameters:
        pr_title (str): The pull request title.
        file_data (dict): Aggregated file metrics containing at least:
            - "file_count" (int): number of files changed
            - "total_changes" (int): total lines changed (additions + deletions)
            - "file_categories" (dict): mapping of category -> count of files (used to determine distinct types)
        config (dict): Configuration mapping with optional "scope" keys:
            - "warn_on_long_title" (int): max title length before warning (default 72)
            - "max_files_changed" (int): max files changed before warning (default 30)
            - "max_total_changes" (int): max total line changes before warning (default 1500)
            - "max_file_types_changed" (int): max distinct file categories before warning (default 5)

    Returns:
        List[str]: Human-readable issue descriptions identifying scope concerns; empty if no issues detected.
    """
    issues = []
    scope_conf = config.get("scope", {})

    # Title checks
    max_len = int(scope_conf.get("warn_on_long_title", 72))
    if len(pr_title) > max_len:
        issues.append(f"Title too long ({len(pr_title)} > {max_len})")

    if any(k in pr_title.lower() for k in [" and ", " & ", ", "]):
        issues.append("Title suggests multiple responsibilities")

    # Size checks - File Count
    max_files = int(scope_conf.get("max_files_changed", 30))
    if file_data["file_count"] > max_files:
        issues.append(f"Too many files changed ({file_data['file_count']} > {max_files})")

    # FIX: Re-added missing logic for Total Changes
    max_total_changes = int(scope_conf.get("max_total_changes", 1500))
    if file_data["total_changes"] > max_total_changes:
        issues.append(f"Large changeset ({file_data['total_changes']} lines > {max_total_changes})")

    # Context switching check
    distinct_types = len(file_data["file_categories"])
    max_types = int(scope_conf.get("max_file_types_changed", 5))
    if distinct_types > max_types:
        issues.append(f"High context switching ({distinct_types} file types changed)")

    return issues


def find_related_issues(
    pr_body: Optional[str],
    repo_url: str,
) -> List[Dict[str, str]]:
    """
    Extract issue references from a pull request body and return their numbers and URLs.

    Recognizes bare references like `#123` and keyword forms such as `fix #123`, `closes #123`, or `resolves #123` (case-insensitive). Deduplicates matches while preserving the order of first occurrence.

    Parameters:
        pr_body (Optional[str]): The pull request description text to scan.
        repo_url (str): Repository base URL used to build issue links.

    Returns:
        List[Dict[str, str]]: A list of dictionaries with keys `number` (issue number as a string)
        and `url` (full issue URL formed as `{repo_url}/issues/{number}`).
    """
    if not pr_body:
        return []

    patterns = [r"#(\d+)", r"(?:fix|close|resolve)s?\s+#(\d+)"]
    found_ids = set()
    results = []

    for pattern in patterns:
        for match in re.finditer(pattern, pr_body, re.IGNORECASE):
            group_index = match.lastindex if match.lastindex is not None else 1
            issue_num = match.group(group_index)
            if issue_num not in found_ids:
                found_ids.add(issue_num)
                results.append(
                    {
                        "number": issue_num,
                        "url": f"{repo_url}/issues/{issue_num}",
                    }
                )
    return results


# --- Reporting ---


def _format_list_items(items: List[str], header: str) -> str:
    """
    Format a Markdown bullet list section with a bold header when items are present.

    Parameters:
        items (List[str]): Lines to include as bullet points.
        header (str): Section title placed in bold above the list.

    Returns:
        str: Markdown string containing the bold header and bullet list, or an empty string if `items` is empty.
    """
    if not items:
        return ""
    return f"\n**{header}**\n" + "".join([f"- {item}\n" for item in items])


def _format_file_categories(file_analysis: Dict[str, Any]) -> str:
    """
    Format file category counts into a Markdown bullet list.

    Parameters:
        file_analysis (dict): Analysis dictionary containing a "file_categories" mapping of
            category name (str) to count (int).

    Returns:
        str: Markdown-formatted bullets, one per category (e.g., "- Python: 5").
    """
    return "\n".join([f"- {name.title()}: {count}" for name, count in file_analysis["file_categories"].items()])


def _format_large_files(file_analysis: Dict[str, Any]) -> str:
    """
    Return a Markdown section listing files with more than 500 changed lines.
    
    Parameters:
        file_analysis (dict): Analysis dictionary containing a "large_files" list of dicts, each with at least "filename" and "changes".
    
    Returns:
        str: Markdown-formatted section with a bold header and one bullet per large file; empty string if no large files are present.
    """
    large_files = file_analysis["large_files"]
    if not large_files:
        return ""
    lines = [f"- `{item['filename']}`: {item['changes']} lines" for item in large_files]
    return "\n**Large Files (>500 lines):**\n" + "\n".join(lines) + "\n"


def _format_related_issues(related_issues: List[Dict[str, str]]) -> str:
    """
    Builds a Markdown "Related Issues" section from extracted issue metadata.

    Parameters:
        related_issues (List[Dict[str, str]]): Iterable of issue descriptors where each dict contains at least a `'number'` key (issue number as a string or int) and may include a `'url'`.

    Returns:
        str: A Markdown string with a "**Related Issues:**" header followed by bullet lines like `- #123`, or an empty string if `related_issues` is empty.
    """
    if not related_issues:
        return ""
    return "\n**Related Issues:**\n" + "".join([f"- #{issue['number']}\n" for issue in related_issues])


def _get_recommendations(risk_level: str) -> List[str]:
    """
    Provide a short list of recommendation bullets appropriate for the given risk level.

    Parameters:
        risk_level (str): Risk band label, typically "High", "Medium", or other values treated as low risk.

    Returns:
        List[str]: Ordered recommendation strings suitable for inclusion in the report.
    """
    recommendations = {
        "High": [
            "⚠️ Split into smaller changes",
            "📋 Comprehensive testing required",
            "👥 Request multiple reviewers",
        ],
        "Medium": [
            "✅ Complexity manageable",
            "📝 Ensure adequate tests",
        ],
    }
    return recommendations.get(
        risk_level,
        ["✅ Low complexity", "🚀 Fast merge candidate"],
    )


def generate_markdown(pr: Any, data: AnalysisData) -> str:
    """
    Constructs a Markdown report summarizing a pull request analysis.

    Parameters:
        pr (Any): Pull request object (expects at least `.number` and `.user.login`).
        data (AnalysisData): AnalysisData containing file_analysis, complexity_score, risk_level, scope_issues, and related_issues used to populate the report.

    Returns:
        str: Markdown-formatted report with an overview, file breakdown (categories and large files), potential scope issues, related issues, and recommendations.
    """
    emoji_map = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}
    risk_emoji = emoji_map.get(data.risk_level, "⚪")
    cat_str = _format_file_categories(data.file_analysis)
    large_files_str = _format_large_files(data.file_analysis)
    related_str = _format_related_issues(data.related_issues)
    recs = _get_recommendations(data.risk_level)

    return f"""
🔍 **PR Analysis Report**

**Overview**
- **PR:** #{pr.number} by @{pr.user.login}
- **Score:** {data.complexity_score}/100 ({risk_emoji} {data.risk_level})
- **Changes:** {data.file_analysis["file_count"]} files, {data.file_analysis["total_changes"]} lines

**File Breakdown**
{cat_str}
{large_files_str}
{_format_list_items(data.scope_issues, "⚠️ Potential Scope Issues")}
{related_str}
{_format_list_items(recs, "Recommendations")}
\n---\n*Generated by PR Copilot*
"""


def write_output(report: str) -> None:
    """
    Write the analysis report to the GitHub Actions step summary (when allowed), a secure temporary markdown file, and standard output.
    
    If the GITHUB_STEP_SUMMARY environment variable is set and its resolved path resides inside the system temporary directory, append the report to that file; if the path is outside the temp directory the summary write is skipped and a warning is printed to stderr. Always create a securely-named temporary file (prefix "pr_analysis_", suffix ".md", delete=False), write the report there, and print the temporary file path to stdout. Any I/O errors while writing either destination are caught and reported to stderr. Finally, print the full report to stdout.
    
    Parameters:
        report (str): The Markdown-formatted analysis report to write.
    """
    # 1. GitHub Actions Summary
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        try:
            summary_path = os.path.realpath(gh_summary)
            temp_root = os.path.realpath(tempfile.gettempdir())
            if os.path.commonpath([summary_path, temp_root]) != temp_root:
                print(
                    "Warning: Ignoring GITHUB_STEP_SUMMARY outside temp dir",
                    file=sys.stderr,
                )
            else:
                with open(summary_path, "a", encoding="utf-8") as f:
                    f.write(report)
        except (IOError, ValueError) as e:
            print(
                f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}",
                file=sys.stderr,
            )

    # 2. FIX: Secure Temp File (Address Bandit B303)
    try:
        # delete=False ensures other steps can read it,
        # while keeping a random, secure filename.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            suffix=".md",
            prefix="pr_analysis_",
        ) as tmp:
            tmp.write(report)
            print(f"Report written to: {tmp.name}")
    except IOError as e:
        print(f"Warning: Failed to write temp report: {e}", file=sys.stderr)

    # 3. Stdout
    print(report)


# --- Main ---


def run() -> None:
    """
    Run the end-to-end PR analysis and produce a Markdown report.
    
    Validates required environment variables, loads configuration, fetches the referenced pull request from GitHub, analyzes files and commits to compute a complexity score and risk level, detects scope issues and related issue references, and writes a Markdown report to configured outputs (CI step summary when allowed, a secure temp file, and stdout). Exits the process with status 0 on success or a non-zero status on missing/invalid environment, GitHub API errors, or other runtime failures. Emits a CI warning when the computed risk level is High.
    """
    env_vars = {var: os.environ.get(var) for var in ("GITHUB_TOKEN", "PR_NUMBER", "REPO_OWNER", "REPO_NAME")}

    if not all(env_vars.values()):
        print(f"Error: Missing vars: {[k for k, v in env_vars.items() if not v]}", file=sys.stderr)
        sys.exit(1)

    try:
        pr_num = int(env_vars["PR_NUMBER"])  # type: ignore
    except ValueError:
        print("Error: PR_NUMBER must be an integer", file=sys.stderr)
        sys.exit(1)

    config = load_config()

    try:
        g = Github(env_vars["GITHUB_TOKEN"])
        repo = g.get_repo(f"{env_vars['REPO_OWNER']}/{env_vars['REPO_NAME']}")
        pr = repo.get_pull(pr_num)

        print(f"Analyzing PR #{pr_num}: {pr.title}...", file=sys.stderr)

        # Gather Data
        files_data = analyze_pr_files(pr.get_files())
        commit_count = pr.commits

        # Analyze
        score, risk = assess_complexity(files_data, commit_count)
        scope_issues = find_scope_issues(pr.title, files_data, config)
        related = find_related_issues(pr.body, repo.html_url)

        analysis = AnalysisData(
            file_analysis=files_data,
            complexity_score=score,
            risk_level=risk,
            scope_issues=scope_issues,
            related_issues=related,
            commit_count=commit_count,
        )

        write_output(generate_markdown(pr, analysis))

        if risk == "High":
            print("::warning::PR Risk is High! Careful review required.")

        sys.exit(0)

    except GithubException as ge:
        print(f"GitHub API Error: {ge}", file=sys.stderr)
        sys.exit(1)
    except (IOError, OSError, RuntimeError, TypeError, ValueError):
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run()
