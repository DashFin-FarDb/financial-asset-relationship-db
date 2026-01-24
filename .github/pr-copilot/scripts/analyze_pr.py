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

    file_analysis: dict[str, Any]
    complexity_score: int
    risk_level: str
    scope_issues: List[str]
    related_issues: list[dict[str, str]]
    commit_count: int


# --- Core Logic ---


def load_config() -> dict[str, Any]:
    """
    Load repository configuration from the YAML config file.

    Reads and parses the file at CONFIG_PATH and returns its contents as a dictionary.
    If the config file does not exist or cannot be parsed/read, an informational or
    warning message is written to stderr and an empty dictionary is returned.

    Returns:
        config (dict[str, Any]): Parsed configuration dictionary, or an empty dict if
        the file is missing or cannot be loaded.
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


def analyze_pr_files(pr_files_iterable: Any) -> dict[str, Any]:
    """
    Analyze an iterable of pull request file objects and summarize file-level change statistics.

    Parameters:
        pr_files_iterable (Iterable): An iterable of objects exposing `filename` (str), `additions` (int), and `deletions` (int).

    Returns:
        dict[str, Any]: A summary dictionary with the following keys:
            - "file_count": total number of files processed.
            - "file_categories": mapping of category name to count of files in that category.
            - "total_additions": sum of all additions across files.
            - "total_deletions": sum of all deletions across files.
            - "total_changes": sum of additions and deletions across files.
            - "large_files": list of dicts for files with more than 500 changes; each dict contains "filename", "changes", "additions", and "deletions".
            - "has_large_files": `True` if any large files were found, `False` otherwise.
    """
    categories: dict[str, int] = defaultdict(int)
    stats = {"additions": 0, "deletions": 0, "changes": 0}
    large_files: list[dict[str, Any]] = []
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


def calculate_score(value: int, thresholds: List[Tuple[int, int]], default: int) -> int:
    """Helper to calculate score based on value thresholds."""
    for limit, points in thresholds:
        if value > limit:
            return points
    return default


def assess_complexity(file_data: dict[str, Any], commit_count: int) -> tuple[int, str]:
    """
    Assess overall PR complexity and map it to a risk level.

    Parameters:
        file_data (dict[str, Any]): Aggregated file change data with keys:
            - file_count (int): number of files changed
            - total_changes (int): sum of additions and deletions across files
            - has_large_files (bool): whether any files exceed the large-file threshold
            - large_files (List[dict[str, int]]): list of large-file entries (used to compute a penalty)
        commit_count (int): number of commits in the pull request

    Returns:
        Tuple[int, str]: A tuple (score, risk_level) where `score` is an integer complexity score (typically in the 0–100 range) and `risk_level` is one of "High", "Medium", or "Low".
    """
    score = 0

    # File count impact
    score += calculate_score(
        file_data["file_count"], [(50, 30), (20, 20), (10, 10)], default=5
    )

    # Line change impact
    score += calculate_score(
        file_data["total_changes"], [(2000, 30), (1000, 20), (500, 15)], default=5
    )

    # Large file penalty (capped at 20)
    if file_data["has_large_files"]:
        penalty = len(file_data["large_files"]) * 5
        score += min(penalty, 20)

    # Commit count impact
    score += calculate_score(commit_count, [(50, 20), (20, 15), (10, 10)], default=5)

    if score >= 70:
        return score, "High"
    if score >= 40:
        return score, "Medium"
    return score, "Low"


def find_scope_issues(
    pr_title: str, file_data: dict[str, Any], config: dict[str, Any]
) -> list[str]:
    """
    Identify scope-related issues in a pull request based on its title and aggregated file-change data.

    Parameters:
        pr_title (str): The pull request title to evaluate.
        file_data (dict[str, Any]): Aggregated file-change metrics produced by analyze_pr_files(), expected to contain
            'file_count' (int), 'total_changes' (int), and 'file_categories' (mapping of category->count).
        config (dict[str, Any]): Configuration dictionary; relevant keys under 'scope' include
            'warn_on_long_title', 'max_files_changed', 'max_total_changes', and 'max_file_types_changed'.

    Returns:
        List[str]: A list of human-readable scope issue messages detected for the PR; empty if no issues found.
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
        issues.append(
            f"Too many files changed ({file_data['file_count']} > {max_files})"
        )

    # FIX: Re-added missing logic for Total Changes
    max_total_changes = int(scope_conf.get("max_total_changes", 1500))
    if file_data["total_changes"] > max_total_changes:
        issues.append(
            f"Large changeset ({file_data['total_changes']} lines > {max_total_changes})"
        )

    # Context switching check
    distinct_types = len(file_data["file_categories"])
    max_types = int(scope_conf.get("max_file_types_changed", 5))
    if distinct_types > max_types:
        issues.append(f"High context switching ({distinct_types} file types changed)")

    return issues


def find_related_issues(pr_body: Optional[str], repo_url: str) -> List[dict[str, str]]:
    """
    Extract referenced issue numbers and build their issue URLs from a pull request body.

    Parses the PR body for issue references (e.g., "#123", "fixes #123", "closes #123") and returns a list of unique issues in the order they are first found.

    Parameters:
        pr_body (Optional[str]): The pull request body text to scan. If empty or None, no issues are returned.
        repo_url (str): Base repository URL used to construct issue links (e.g., "https://github.com/owner/repo").

    Returns:
        List[dict[str, str]]: A list of dictionaries with keys `"number"` (issue number as a string) and `"url"` (full issue URL). Duplicate issue references are omitted.
    """
    if not pr_body:
        return []

    patterns = [r"#(\d+)", r"(?:fix|close|resolve)s?\s+#(\d+)"]
    found_ids = set()
    results = []

    for pattern in patterns:
        for match in re.finditer(pattern, pr_body, re.IGNORECASE):
            issue_num = (
                match.group(1) if match.lastindex == 1 else match.group(match.lastindex)
            )
            if issue_num not in found_ids:
                found_ids.add(issue_num)
                results.append(
                    {"number": issue_num, "url": f"{repo_url}/issues/{issue_num}"}
                )
    return results


# --- Reporting ---


def generate_markdown(pr: Any, data: AnalysisData) -> str:
    """
    Compose a markdown-formatted PR analysis report suitable for display in CI summaries.

    Parameters:
        pr (Any): Pull request object used for metadata (e.g., number and author).
        data (AnalysisData): Analysis results including file breakdown, complexity score, risk level, scope issues, large files, and related issues.

    Returns:
        str: A Markdown string summarizing the PR overview, file breakdown, large-file highlights, scope issues, related issues, and recommended actions.
    """
    emoji_map = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}
    risk_emoji = emoji_map.get(data.risk_level, "⚪")

    def list_items(items: List[str], header: str) -> str:
        """
        Render a Markdown bullet list with a bold header from the provided items.

        Parameters:
                items (List[str]): Lines to include as bullet points. If empty, an empty string is returned.
                header (str): Text displayed as a bold header above the bullet list.

        Returns:
                markdown (str): Empty string when `items` is empty; otherwise a Markdown block with the header in bold followed by each item as a `- ` bullet on its own line.
        """
        if not items:
            return ""
        return f"\n**{header}**\n" + "".join([f"- {i}\n" for i in items])

    cat_str = "\n".join(
        [
            f"- {k.title()}: {v}"
            for k, v in data.file_analysis["file_categories"].items()
        ]
    )

    large_files_str = ""
    if data.file_analysis["large_files"]:
        lines = [
            f"- `{f['filename']}`: {f['changes']} lines"
            for f in data.file_analysis["large_files"]
        ]
        large_files_str = "\n**Large Files (>500 lines):**\n" + "\n".join(lines) + "\n"

    related_str = ""
    if data.related_issues:
        related_str = "\n**Related Issues:**\n" + "".join(
            [f"- #{i['number']}\n" for i in data.related_issues]
        )

    recs = []
    if data.risk_level == "High":
        recs = [
            "⚠️ Split into smaller changes",
            "📋 Comprehensive testing required",
            "👥 Request multiple reviewers",
        ]
    elif data.risk_level == "Medium":
        recs = ["✅ Complexity manageable", "📝 Ensure adequate tests"]
    else:
        recs = ["✅ Low complexity", "🚀 Fast merge candidate"]

    return f"""
🔍 **PR Analysis Report**

**Overview**
- **PR:** #{pr.number} by @{pr.user.login}
- **Score:** {data.complexity_score}/100 ({risk_emoji} {data.risk_level})
- **Changes:** {data.file_analysis["file_count"]} files, {data.file_analysis["total_changes"]} lines

**File Breakdown**
{cat_str}
{large_files_str}
{list_items(data.scope_issues, "⚠️ Potential Scope Issues")}
{related_str}
{list_items(recs, "Recommendations")}
\n---\n*Generated by PR Copilot*
"""


def write_output(report: str) -> None:
    """
    Write the given report to the GitHub Actions summary (if configured), to a securely-created temporary file, and to standard output.

    If the GITHUB_STEP_SUMMARY environment variable is set, the report is appended to that file. A temporary file with a randomized name is created (its path is printed) to persist the report for other steps. The report is also printed to stdout.
    """
    # 1. GitHub Actions Summary
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        try:
            with open(gh_summary, "a", encoding="utf-8") as f:
                f.write(report)
        except IOError as e:
            print(
                f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}", file=sys.stderr
            )

    # 2. FIX: Secure Temp File (Address Bandit B303)
    try:
        # delete=False ensures other steps can read it, but the name is random/secure
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
    Execute the PR analysis workflow and emit a Markdown report for the specified pull request.

    This function reads required environment variables (GITHUB_TOKEN, PR_NUMBER, REPO_OWNER, REPO_NAME), loads configuration, fetches the referenced pull request from GitHub, analyzes changed files and commits, computes a complexity score and risk level, identifies scope issues and related issues, generates a Markdown report, and writes the report to the GitHub Actions summary, a secure temporary file, and stdout. On success it exits with code 0. If the computed risk is "High" a GitHub Actions warning annotation is emitted.

    Error behavior:
    - Prints an error to stderr and exits with code 1 if any required environment variable is missing.
    - Prints an error to stderr and exits with code 1 if PR_NUMBER cannot be parsed as an integer.
    - Prints GitHub API errors to stderr and exits with code 1 for GitHub-related failures.
    - Prints a full traceback and exits with code 1 for any other unexpected exceptions.
    """
    required_vars = ["GITHUB_TOKEN", "PR_NUMBER", "REPO_OWNER", "REPO_NAME"]
    env_vars = {var: os.environ.get(var) for var in required_vars}

    if not all(env_vars.values()):
        print(
            f"Error: Missing vars: {[k for k, v in env_vars.items() if not v]}",
            file=sys.stderr,
        )
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

        report = generate_markdown(pr, analysis)
        write_output(report)

        if risk == "High":
            print("::warning::PR Risk is High! Careful review required.")

        sys.exit(0)

    except GithubException as ge:
        print(f"GitHub API Error: {ge}", file=sys.stderr)
        sys.exit(1)
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run()
