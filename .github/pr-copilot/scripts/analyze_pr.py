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

    file_analysis: Dict[str, Any]
    complexity_score: int
    risk_level: str
    scope_issues: List[str]
    related_issues: List[Dict[str, str]]
    commit_count: int


# --- Core Logic ---


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file safely."""
    if not os.path.exists(CONFIG_PATH):
        print(f"Info: Config file not found at {CONFIG_PATH}, using defaults.", file=sys.stderr)
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
    """Iterate through files to gather stats."""
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
            large_files.append({"filename": pr_file.filename, "changes": total, "additions": adds, "deletions": dels})

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


def assess_complexity(file_data: Dict[str, Any], commit_count: int) -> Tuple[int, str]:
    """Calculate 0-100 complexity score and risk level."""
    score = 0

    # File count impact
    score += calculate_score(file_data["file_count"], [(50, 30), (20, 20), (10, 10)], default=5)

    # Line change impact
    score += calculate_score(file_data["total_changes"], [(2000, 30), (1000, 20), (500, 15)], default=5)

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


def find_scope_issues(pr_title: str, file_data: Dict[str, Any], config: Dict[str, Any]) -> List[str]:
    """Identify potential scope creep."""
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


def find_related_issues(pr_body: Optional[str], repo_url: str) -> List[Dict[str, str]]:
    """Parse PR body for linked issues."""
    if not pr_body:
        return []

    patterns = [r"#(\d+)", r"(?:fix|close|resolve)s?\s+#(\d+)"]
    found_ids = set()
    results = []

    for pattern in patterns:
        for match in re.finditer(pattern, pr_body, re.IGNORECASE):
            issue_num = match.group(1) if match.lastindex == 1 else match.group(match.lastindex)
            if issue_num not in found_ids:
                found_ids.add(issue_num)
                results.append({"number": issue_num, "url": f"{repo_url}/issues/{issue_num}"})
    return results


# --- Reporting ---


def generate_markdown(pr: Any, data: AnalysisData) -> str:
    """Build the markdown report."""
    emoji_map = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}
    risk_emoji = emoji_map.get(data.risk_level, "⚪")

    def list_items(items: List[str], header: str) -> str:
        if not items:
            return ""
        return f"\n**{header}**\n" + "".join([f"- {i}\n" for i in items])

    cat_str = "\n".join([f"- {k.title()}: {v}" for k, v in data.file_analysis["file_categories"].items()])

    large_files_str = ""
    if data.file_analysis["large_files"]:
        lines = [f"- `{f['filename']}`: {f['changes']} lines" for f in data.file_analysis["large_files"]]
        large_files_str = "\n**Large Files (>500 lines):**\n" + "\n".join(lines) + "\n"

    related_str = ""
    if data.related_issues:
        related_str = "\n**Related Issues:**\n" + "".join([f"- #{i['number']}\n" for i in data.related_issues])

    recs = []
    if data.risk_level == "High":
        recs = ["⚠️ Split into smaller changes", "📋 Comprehensive testing required", "👥 Request multiple reviewers"]
    elif data.risk_level == "Medium":
        recs = ["✅ Complexity manageable", "📝 Ensure adequate tests"]
    else:
        recs = ["✅ Low complexity", "🚀 Fast merge candidate"]

    return f"""
🔍 **PR Analysis Report**

**Overview**
- **PR:** #{pr.number} by @{pr.user.login}
- **Score:** {data.complexity_score}/100 ({risk_emoji} {data.risk_level})
- **Changes:** {data.file_analysis['file_count']} files, {data.file_analysis['total_changes']} lines

**File Breakdown**
{cat_str}
{large_files_str}
{list_items(data.scope_issues, "⚠️ Potential Scope Issues")}
{related_str}
{list_items(recs, "Recommendations")}
\n---\n*Generated by PR Copilot*
"""


def write_output(report: str) -> None:
    """Write report to GITHUB_STEP_SUMMARY and a secure temp file."""
    # 1. GitHub Actions Summary
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        try:
            with open(gh_summary, "a", encoding="utf-8") as f:
                f.write(report)
        except IOError as e:
            print(f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)

    # 2. FIX: Secure Temp File (Address Bandit B303)
    try:
        # delete=False ensures other steps can read it, but the name is random/secure
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, suffix=".md", prefix="pr_analysis_"
        ) as tmp:
            tmp.write(report)
            print(f"Report written to: {tmp.name}")
    except IOError as e:
        print(f"Warning: Failed to write temp report: {e}", file=sys.stderr)

    # 3. Stdout
    print(report)


# --- Main ---


def run() -> None:
    """Main execution flow."""
    required_vars = ["GITHUB_TOKEN", "PR_NUMBER", "REPO_OWNER", "REPO_NAME"]
    env_vars = {var: os.environ.get(var) for var in required_vars}

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
