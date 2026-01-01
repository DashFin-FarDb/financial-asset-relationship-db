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
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

try:
    import yaml
    from github import Github
except ImportError:
    print("Error: Required packages not installed. Run: pip install PyGithub pyyaml", file=sys.stderr)
    sys.exit(1)


CONFIG_PATH = ".github/pr-copilot-config.yml"


@dataclass(frozen=True)
class AnalysisData:
    """Container for PR analysis data."""

    file_analysis: Dict[str, Any]
    complexity_score: int
    risk_level: str
    scope_issues: List[str]
    related_issues: List[Dict[str, str]]
    commit_count: int


def load_config() -> Dict[str, Any]:
    """Load configuration from pr-copilot-config.yml."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Warning: Config file not found at {CONFIG_PATH}, using defaults", file=sys.stderr)
        return {}


def categorize_file(filename: str) -> str:
    """Categorize file by type."""
    name_lower = filename.lower()

    # Check for test files by name pattern first
    if "test" in name_lower or "spec" in name_lower:
        return "test"

    # Check for workflow files by path
    if ".github/workflows" in filename:
        return "workflow"

    # Get file extension
    if "." not in filename:
        return "other"

    ext = filename.rsplit(".", 1)[1].lower()

    categories = {
        "python": {"py"},
        "javascript": {"js", "jsx", "ts", "tsx"},
        "markup": {"html", "xml"},
        "style": {"css", "scss", "sass", "less"},
        "config": {"json", "yaml", "yml", "toml", "ini", "cfg", "conf"},
        "documentation": {"md", "rst", "txt"},
        "database": {"sql", "db", "sqlite"},
        "shell": {"sh", "bash", "zsh", "fish"},
    }

    for category, extensions in categories.items():
        if ext in extensions:
            return category

    return "other"


def analyze_file_changes(files: List[Any]) -> Dict[str, Any]:
    """Analyze the files changed in the PR."""
    file_categories: Dict[str, int] = defaultdict(int)
    total_additions = 0
    total_deletions = 0
    total_changes = 0
    large_files: List[Dict[str, Any]] = []

    for file in files:
        category = categorize_file(file.filename)
        file_categories[category] += 1

        additions = int(getattr(file, "additions", 0))
        deletions = int(getattr(file, "deletions", 0))
        changes = additions + deletions

        total_additions += additions
        total_deletions += deletions
        total_changes += changes

        # Flag large files (>500 lines changed)
        if changes > 500:
            large_files.append(
                {"filename": file.filename, "changes": changes, "additions": additions, "deletions": deletions}
            )

    return {
        "file_count": len(files),
        "file_categories": dict(file_categories),
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "total_changes": total_changes,
        "large_files": large_files,
        "has_large_files": bool(large_files),
    }


def _score_from_thresholds(value: int, thresholds: List[Tuple[int, int]], default_points: int) -> int:
    """Return points based on descending thresholds."""
    for min_value, points in thresholds:
        if value > min_value:
            return points
    return default_points


def calculate_complexity_score(file_analysis: Dict[str, Any], commit_count: int) -> Tuple[int, str]:
    """
    Calculate complexity score (0-100) and risk level.

    Returns:
        Tuple of (score, risk_level)
    """
    score = 0

    file_count = int(file_analysis.get("file_count", 0))
    score += _score_from_thresholds(
        file_count,
        thresholds=[(50, 30), (20, 20), (10, 10)],
        default_points=5,
    )

    total_changes = int(file_analysis.get("total_changes", 0))
    score += _score_from_thresholds(
        total_changes,
        thresholds=[(2000, 30), (1000, 20), (500, 15)],
        default_points=5,
    )

    if file_analysis.get("has_large_files"):
        score += min(len(file_analysis.get("large_files", [])) * 5, 20)

    score += _score_from_thresholds(
        int(commit_count),
        thresholds=[(50, 20), (20, 15), (10, 10)],
        default_points=5,
    )

    if score >= 70:
        return score, "High"
    if score >= 40:
        return score, "Medium"
    return score, "Low"


def check_scope_issues(pr: Any, file_analysis: Dict[str, Any], config: Dict[str, Any]) -> List[str]:
    """Check for potential scope issues."""
    issues: List[str] = []

    title_max_len = int(config.get("scope", {}).get("warn_on_long_title", 72))
    if len(pr.title) > title_max_len:
        issues.append(f"Long PR title ({len(pr.title)} chars, recommended <{title_max_len})")

    title_lower = pr.title.lower()
    multi_keywords = [" and ", " & ", " or ", ", "]
    if any(keyword in title_lower for keyword in multi_keywords):
        issues.append("PR title suggests multiple changes (contains 'and', 'or', '&', or commas)")

    scope_config = config.get("scope", {})
    max_files = int(scope_config.get("max_files_changed", 30))
    if int(file_analysis.get("file_count", 0)) > max_files:
        issues.append(f"Large number of files changed ({file_analysis['file_count']} files)")

    categories = file_analysis.get("file_categories", {})
    category_count = len(categories)
    max_types = int(scope_config.get("max_file_types_changed", 5))
    if category_count > max_types:
        issues.append(f"Multiple file types changed ({category_count} different types)")

    max_total_changes = int(scope_config.get("max_total_changes", 1500))
    if int(file_analysis.get("total_changes", 0)) > max_total_changes:
        issues.append(f"Large changeset ({file_analysis['total_changes']} lines changed)")

    return issues


def find_related_issues(pr: Any) -> List[Dict[str, str]]:
    """Find related issues mentioned in PR body."""
    if not getattr(pr, "body", None):
        return []

    related: List[Dict[str, str]] = []
    patterns = [
        r"#(\d+)",
        r"(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#(\d+)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, pr.body, re.IGNORECASE):
            issue_num = match.group(1)
            related.append({"type": "issue", "number": issue_num, "url": f"{pr.base.repo.html_url}/issues/{issue_num}"})

    # Remove duplicates
    seen = set()
    unique_related: List[Dict[str, str]] = []
    for item in related:
        key = f"{item['type']}:{item['number']}"
        if key not in seen:
            seen.add(key)
            unique_related.append(item)

    return unique_related


def _format_file_categories(file_analysis: Dict[str, Any]) -> str:
    return "\n".join([f"  - {cat.title()}: {count}" for cat, count in file_analysis.get("file_categories", {}).items()])


def _format_large_files(file_analysis: Dict[str, Any]) -> str:
    large_files = file_analysis.get("large_files") or []
    if not large_files:
        return ""

    lines = ["\n**Large Files (>500 lines changed):**"]
    for file in large_files:
        lines.append(f"  - `{file['filename']}`: {file['changes']} lines (+{file['additions']}/-{file['deletions']})")
    return "\n" + "\n".join(lines) + "\n"


def _format_scope_issues(scope_issues: List[str]) -> str:
    if not scope_issues:
        return ""
    return "\n**⚠️ Potential Scope Issues:**\n" + "".join([f"  - {issue}\n" for issue in scope_issues])


def _format_related_issues(related_issues: List[Dict[str, str]]) -> str:
    if not related_issues:
        return ""
    return "\n**Related Issues:**\n" + "".join([f"  - #{item['number']}\n" for item in related_issues])


def _recommendations(risk_level: str, file_analysis: Dict[str, Any], related_issues: List[Dict[str, str]]) -> str:
    report = ""
    if risk_level == "High":
        report += "  - ⚠️ Consider splitting this PR into smaller, focused changes\n"
        report += "  - 📋 Ensure comprehensive testing due to high complexity\n"
        report += "  - 👥 Request review from multiple team members\n"
    elif risk_level == "Medium":
        report += "  - ✅ Complexity is manageable\n"
        report += "  - 📝 Ensure adequate test coverage\n"
        report += "  - 👀 Standard review process recommended\n"
    else:
        report += "  - ✅ Low complexity, straightforward to review\n"
        report += "  - 🚀 Should merge quickly after review\n"

    if file_analysis.get("has_large_files"):
        report += f"  - 📊 {len(file_analysis.get('large_files', []))} large file(s) need careful review\n"

    if not related_issues:
        report += "  - 💡 Consider linking to related issue(s) in PR description\n"

    return report


def generate_analysis_report(pr: Any, analysis: AnalysisData) -> str:
    """Generate comprehensive analysis report."""
    file_analysis = analysis.file_analysis
    complexity_score = analysis.complexity_score
    risk_level = analysis.risk_level
    scope_issues = analysis.scope_issues
    related_issues = analysis.related_issues
    commit_count = analysis.commit_count

    categories_str = _format_file_categories(file_analysis)
    large_files_str = _format_large_files(file_analysis)
    scope_issues_str = _format_scope_issues(scope_issues)
    related_str = _format_related_issues(related_issues)

    complexity_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}

    report = f"""🔍 **PR Analysis Report**

**PR Overview:**
- **Title:** {pr.title}
- **Number:** #{pr.number}
- **Author:** @{pr.user.login}
- **Base:** `{pr.base.ref}` ← **Head:** `{pr.head.ref}`

**Complexity Assessment:**
- **Complexity Score:** {complexity_score}/100
- **Risk Level:** {complexity_emoji.get(risk_level, "⚪")} **{risk_level}**

**File Changes:**
- **Total Files:** {file_analysis['file_count']}
- **Lines Changed:** {file_analysis['total_changes']} (+{file_analysis['total_additions']}/-{file_analysis['total_deletions']})
- **Commits:** {commit_count}

**File Types:**
{categories_str}
{large_files_str}{scope_issues_str}{related_str}

**Recommendations:**
"""
    report += _recommendations(risk_level, file_analysis, related_issues)
    report += "\n---\n*Generated by PR Copilot Analysis Tool*"
    return report


def main() -> None:
    """Main execution function."""
    github_token = os.environ.get("GITHUB_TOKEN")
    pr_number = os.environ.get("PR_NUMBER")
    repo_owner = os.environ.get("REPO_OWNER")
    repo_name = os.environ.get("REPO_NAME")

    if not all([github_token, pr_number, repo_owner, repo_name]):
        print("Error: Missing required environment variables", file=sys.stderr)
        print("Required: GITHUB_TOKEN, PR_NUMBER, REPO_OWNER, REPO_NAME", file=sys.stderr)
        sys.exit(1)

    try:
        pr_number_int = int(pr_number)
    except ValueError:
        print(f"Error: PR_NUMBER must be an integer, got: {pr_number}", file=sys.stderr)
        sys.exit(1)

    config = load_config()

    g = Github(github_token)
    repo_full_name = f"{repo_owner}/{repo_name}"

    try:
        print(f"Analyzing PR #{pr_number_int}...", file=sys.stderr)
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number_int)

        files = list(pr.get_files())
        commits = list(pr.get_commits())
        commit_count = len(commits)

        file_analysis = analyze_file_changes(files)
        complexity_score, risk_level = calculate_complexity_score(file_analysis, commit_count)
        scope_issues = check_scope_issues(pr, file_analysis, config=config)
        related_issues = find_related_issues(pr)

        analysis = AnalysisData(
            file_analysis=file_analysis,
            complexity_score=complexity_score,
            risk_level=risk_level,
            scope_issues=scope_issues,
            related_issues=related_issues,
            commit_count=commit_count,
        )

        report = generate_analysis_report(pr, analysis)

        output_file = "/tmp/pr_analysis_report.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"Analysis report generated successfully: {output_file}", file=sys.stderr)
        print(report)

        sys.exit(2 if risk_level == "High" else 0)

    except Exception as e:
        print(f"Error analyzing PR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
