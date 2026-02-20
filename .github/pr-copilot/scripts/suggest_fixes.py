#!/usr/bin/env python3
"""
Parse review suggestions and generate fix proposals.

This script analyzes review comments to extract actionable suggestions
and generates structured fix proposals for future enhancement.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from collections import defaultdict
from typing import Any, Dict, List, Tuple

try:
    import yaml
    from github import Github, GithubException
except ImportError:
    print(
        "Error: Required packages not installed. Run: pip install PyGithub pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)


# --- Configuration ---


def load_config() -> Dict[str, Any]:
    """Load configuration from pr-copilot-config.yml."""
    config_path = ".github/pr-copilot-config.yml"
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # Defaults if config missing
        return {
            "review_handling": {
                "actionable_keywords": [
                    "please",
                    "should",
                    "could you",
                    "nit",
                    "typo",
                    "fix",
                    "refactor",
                    "change",
                    "update",
                    "add",
                    "remove",
                ]
            }
        }


# --- Parsing Logic ---


def extract_code_suggestions(comment_body: str) -> List[Dict[str, str]]:
    """
    Extracts code suggestion snippets from a comment body.

    Scans the provided text for fenced suggestion blocks marked with ```suggestion``` and for inline backticked code preceded by common suggestion phrases.

    Parameters:
        comment_body (str): The comment text to search for code suggestions.

    Returns:
        suggestions (List[Dict[str, str]]): A list of suggestion dictionaries. Each dictionary has:
            - "type": either "code_suggestion" for fenced suggestion blocks or "inline_suggestion" for inline backticked suggestions.
            - "content": the extracted suggested code or inline snippet.
    """
    suggestions = []

    # Pattern 1: Code blocks with suggestion marker
    suggestion_pattern = r"```suggestion\s*\n(.*?)\n```"
    matches = re.finditer(suggestion_pattern, comment_body, re.DOTALL)
    for match in matches:
        suggestions.append({"type": "code_suggestion", "content": match.group(1).strip()})

    # Pattern 2: Inline code in quotes with suggestion words
    inline_pattern = r"(?:should be|change to|replace with|use)\s+`([^`]+)`"
    matches = re.finditer(inline_pattern, comment_body, re.IGNORECASE)
    for match in matches:
        suggestions.append({"type": "inline_suggestion", "content": match.group(1).strip()})

    return suggestions


def categorize_comment(comment_body: str) -> Tuple[str, int]:
    """
    Categorize comment by type and priority.
    Returns: (category, priority)
    """
    body_lower = comment_body.lower()

    # Define category keywords with their priorities
    categories = [
        (
            "critical",
            1,
            ["security", "vulnerability", "exploit", "critical", "breaking"],
        ),
        ("bug", 1, ["bug", "error", "fails", "broken", "incorrect", "wrong"]),
        ("question", 3, ["why", "what", "how", "?", "clarify", "explain"]),
        ("style", 3, ["style", "format", "lint", "naming", "convention"]),
        ("improvement", 2, ["refactor", "improve", "optimize", "enhance", "consider"]),
    ]

    # Check each category in priority order
    for category, priority, keywords in categories:
        if any(kw in body_lower for kw in keywords):
            return category, priority

    # Default
    return "improvement", 2


def is_actionable(comment_body: str, actionable_keywords: List[str]) -> bool:
    """
    Determine whether a comment contains any actionable keyword.

    Matches each keyword against the comment body using a case-insensitive substring check.

    Parameters:
        comment_body (str): The comment text to inspect.
        actionable_keywords (List[str]): Keywords to look for in the comment; each is matched case-insensitively as a substring.

    Returns:
        bool: `True` if any keyword is present in the comment body, `False` otherwise.
    """
    body_lower = comment_body.lower()
    return any(keyword in body_lower for keyword in actionable_keywords)


def parse_review_comments(pr: Any, actionable_keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Collect actionable review comments from a pull request and return them as structured items.

    This scans file-level review comments and top-level reviews with state "CHANGES_REQUESTED", extracts actionable entries using the provided actionable keywords, and sorts the results by priority (1 = highest) and creation date.

    Parameters:
        pr (Any): GitHub PullRequest-like object to inspect (must provide get_review_comments and get_reviews).
        actionable_keywords (List[str]): Keywords used to decide if a comment is actionable (case-insensitive).

    Returns:
        List[Dict[str, Any]]: A list of actionable item dictionaries, each containing:
            - id: comment or review identifier
            - author: username of the comment author
            - body: full comment text
            - category: assigned category (e.g., "bug", "style", "improvement", etc.)
            - priority: numeric priority (1 = high, 2 = medium, 3 = low)
            - file: file path the comment refers to, or None
            - line: original line number the comment refers to, or None
            - code_suggestions: extracted code suggestion entries (type/content pairs)
            - url: URL to the original comment
            - created_at: timestamp when the comment or review was created/submitted
    """
    actionable_items = []

    # Helper to process a raw comment object
    def process_comment(comment_obj: Any, is_review: bool = False) -> None:
        body = comment_obj.body or ""
        if not is_actionable(body, actionable_keywords):
            return

        category, priority = categorize_comment(body)
        code_suggestions = extract_code_suggestions(body)

        # Handle difference between Review object and Comment object
        created_at = comment_obj.submitted_at if is_review else comment_obj.created_at
        file_path = getattr(comment_obj, "path", None)
        line_num = getattr(comment_obj, "original_line", None)

        actionable_items.append(
            {
                "id": comment_obj.id,
                "author": comment_obj.user.login,
                "body": body,
                "category": category,
                "priority": priority,
                "file": file_path,
                "line": line_num,
                "code_suggestions": code_suggestions,
                "url": comment_obj.html_url,
                "created_at": created_at,
            }
        )

    # 1. File-level comments
    for comment in pr.get_review_comments():
        process_comment(comment)

    # 2. High-level Review comments (Changes Requested only)
    for review in pr.get_reviews():
        if review.state == "CHANGES_REQUESTED":
            process_comment(review, is_review=True)

    # Sort: Priority (1=High) asc, then Date asc
    actionable_items.sort(key=lambda x: (x["priority"], x["created_at"]))
    return actionable_items


# --- Formatting Helpers ---


def _format_code_suggestions(suggestions: List[Dict[str, str]]) -> str:
    """Format the code suggestion blocks."""
    output = "   - **Suggested Code:**\n"
    for suggestion in suggestions:
        if suggestion["type"] == "code_suggestion":
            output += f"     ```\n     {suggestion['content']}\n     ```\n"
        else:
            output += f"     `{suggestion['content']}`\n"
    return output


def _format_item(index: int, item: Dict[str, Any]) -> str:
    """Format a single actionable item entry."""
    priority_map = {1: "🔴 High", 2: "🟡 Medium", 3: "🟢 Low"}

    # Text truncation
    body_excerpt = item["body"][:200]
    if len(item["body"]) > 200:
        body_excerpt += "..."

    report = f"**{index}. Comment by @{item['author']}**\n"
    if item["file"] and item["line"]:
        report += f"   - **Location:** `{item['file']}:{item['line']}`\n"

    report += f"   - **Priority:** {priority_map.get(item['priority'], 'Medium')}\n"
    report += f"   - **Feedback:** {body_excerpt}\n"

    if item["code_suggestions"]:
        report += _format_code_suggestions(item["code_suggestions"])

    report += f"   - [View Comment]({item['url']})\n\n"
    return report


def _generate_summary(items: List[Dict[str, Any]]) -> str:
    """Generate the statistical summary footer."""
    counts = defaultdict(int)
    for item in items:
        counts[item["category"]] += 1

    summary = "\n---\n\n**Summary:**\n"
    summary += f"- **Total Actionable Items:** {len(items)}\n"

    if counts["critical"] > 0:
        summary += f"- 🚨 **Critical Issues:** {counts['critical']}\n"
    if counts["bug"] > 0:
        summary += f"- 🐛 **Bugs:** {counts['bug']}\n"

    summary += f"- 💡 **Improvements:** {counts['improvement']}\n"
    summary += f"- 🎨 **Style:** {counts['style']}\n"
    summary += f"- ❓ **Questions:** {counts['question']}\n"

    if counts["critical"] > 0 or counts["bug"] > 0:
        summary += "\n⚠️ **Priority:** Address critical issues and bugs first.\n"

    return summary + "\n*Generated by PR Copilot Fix Suggestion Tool*\n"


def generate_fix_proposals(actionable_items: List[Dict[str, Any]]) -> str:
    """Generate structured fix proposals from actionable items."""
    if not actionable_items:
        return "✅ No actionable items found in review comments."

    # Grouping
    categorized = defaultdict(list)
    for item in actionable_items:
        categorized[item["category"]].append(item)

    report = "🔧 **Fix Proposals from Review Comments**\n\n"

    # Order of presentation
    priority_order = ["critical", "bug", "improvement", "style", "question"]
    emoji_map = {
        "critical": "🚨",
        "bug": "🐛",
        "improvement": "💡",
        "style": "🎨",
        "question": "❓",
    }

    for category in priority_order:
        items = categorized.get(category, [])
        if not items:
            continue

        report += f"\n### {emoji_map.get(category, '📝')} {category.title()} ({len(items)})\n\n"

        for i, item in enumerate(items, 1):
            report += _format_item(i, item)

    report += _generate_summary(actionable_items)
    return report


# --- Main ---


def write_output(report: str) -> None:
    """
    Write the provided report to the GitHub Actions step summary (when configured), save it to a secure temporary markdown file, and print the report to standard output.

    If the GITHUB_STEP_SUMMARY environment variable is set, the report is appended to that file path. A temporary file is created with prefix "fix_proposals_" and suffix ".md"; its path is printed to standard error. IO errors when writing either destination are reported to standard error.

    Parameters:
        report (str): The full report text to write.
    """
    # 1. GitHub Summary
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        try:
            with open(gh_summary, "a", encoding="utf-8") as f:
                f.write(report)
        except IOError as e:
            print(f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)

    # 2. Secure Temp File
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            suffix=".md",
            prefix="fix_proposals_",
        ) as tmp:
            tmp.write(report)
            print(f"Fix proposals generated: {tmp.name}", file=sys.stderr)
    except IOError as e:
        print(f"Error writing temp file: {e}", file=sys.stderr)

    print(report)


def main():
    """Main execution function."""
    required = ["GITHUB_TOKEN", "PR_NUMBER", "REPO_OWNER", "REPO_NAME"]
    env_vars = {var: os.environ.get(var) for var in required}

    if not all(env_vars.values()):
        print("Error: Missing required environment variables", file=sys.stderr)
        sys.exit(1)

    try:
        pr_number = int(env_vars["PR_NUMBER"])  # type: ignore
    except ValueError:
        print("Error: PR_NUMBER must be an integer", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    keywords = config.get("review_handling", {}).get(
        "actionable_keywords",
        ["please", "should", "fix", "refactor", "change", "update", "add", "remove"],
    )

    try:
        g = Github(env_vars["GITHUB_TOKEN"])
        repo = g.get_repo(f"{env_vars['REPO_OWNER']}/{env_vars['REPO_NAME']}")
        pr = repo.get_pull(pr_number)

        print(f"Parsing review comments for PR #{pr_number}...", file=sys.stderr)
        items = parse_review_comments(pr, keywords)

        report = generate_fix_proposals(items)
        write_output(report)

    except GithubException as ge:
        # Added specific handler for GithubException to satisfy F401 and improve robustness
        print(f"GitHub API Error: {ge}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
