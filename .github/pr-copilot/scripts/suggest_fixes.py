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
from typing import Any, Dict, List, Optional, Tuple

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


def load_config() -> dict[str, Any]:
    """
    Load PR Copilot configuration from .github/pr-copilot-config.yml.

    When the configuration file exists, returns its parsed YAML content as a dictionary.
    If the file is missing, returns a default configuration containing
    `review_handling.actionable_keywords` with common actionable phrasing.

    Returns:
        dict[str, Any]: Configuration mapping (either parsed file contents or the default configuration).
    """
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


def extract_code_suggestions(comment_body: str) -> list[dict[str, str]]:
    """
    Extract suggested code changes from a review comment body.

    Searches the Markdown comment for:
    - fenced suggestion blocks begun with ```suggestion``` and captures their inner content as `code_suggestion`.
    - inline suggestions introduced by phrases like "should be", "change to", "replace with", or "use" followed by backticked text, captured as `inline_suggestion`.

    Parameters:
        comment_body (str): Raw comment text (Markdown) to analyze.

    Returns:
        list[dict[str, str]]: A list of suggestion objects where each object contains:
            - `type`: `"code_suggestion"` or `"inline_suggestion"`.
            - `content`: the extracted suggestion text.
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
    Assigns a category and priority to a review comment based on keyword matching.

    Parameters:
        comment_body (str): The review comment text to classify.

    Returns:
        tuple: (category, priority) where `category` is one of 'critical', 'bug', 'question', 'style', or 'improvement', and `priority` is 1 (high), 2 (medium), or 3 (low). Defaults to ('improvement', 2) when no keywords match.
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
    Check whether a review comment contains any of the provided actionable keywords.

    Parameters:
        comment_body (str): The text of the comment to inspect.
        actionable_keywords (List[str]): Substring keywords to search for; matches are performed case-insensitively.

    Returns:
        bool: `true` if any actionable keyword appears in the comment body, `false` otherwise.
    """
    body_lower = comment_body.lower()
    return any(keyword in body_lower for keyword in actionable_keywords)


def parse_review_comments(pr: Any, actionable_keywords: List[str]) -> List[dict[str, Any]]:
    """
    Collect actionable review comments from a pull request and return them as structured items.

    Parameters:
        pr (Any): The GitHub pull request object to scan for review comments and reviews.
        actionable_keywords (List[str]): Keywords used to determine whether a comment is actionable.

    Returns:
        List[dict[str, Any]]: A list of actionable item dictionaries with the following keys:
            - id (int): Comment or review identifier.
            - author (str): Comment author's login.
            - body (str): Full comment text.
            - category (str): Assigned category (e.g., "critical", "bug", "style", "improvement", "question").
            - priority (int): Numeric priority where lower is higher importance (1 = High).
            - file (str | None): Path of the file the comment refers to, if any.
            - line (int | None): Line number the comment refers to, if available.
            - code_suggestions (List[dict[str, str]]): Extracted code suggestions (type and content).
            - url (str): URL to the original comment or review.
            - created_at (datetime): Timestamp when the comment or review was created/submitted.
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


def _format_code_suggestions(suggestions: list[dict[str, str]]) -> str:
    """
    Render a list of code suggestions into a markdown fragment.

    Parameters:
        suggestions (list[dict[str, str]]): Each dict must include:
            - "type": either "code_suggestion" or "inline_suggestion".
            - "content": the suggestion text to include.

    Returns:
        str: A markdown-formatted string that starts with a "Suggested Code" bullet.
             For items with type "code_suggestion" the content is placed in a fenced
             code block; for "inline_suggestion" the content is formatted as inline code.
    """
    output = "   - **Suggested Code:**\n"
    for suggestion in suggestions:
        if suggestion["type"] == "code_suggestion":
            output += f"     ```\n     {suggestion['content']}\n     ```\n"
        else:
            output += f"     `{suggestion['content']}`\n"
    return output


def _format_item(index: int, item: dict[str, Any]) -> str:
    """
    Format a single actionable review comment into a markdown snippet for the report.

    Parameters:
        index (int): 1-based position of the item in the category list used for numbering.
        item (dict): Actionable item with expected keys:
            - 'author' (str): GitHub username of the commenter.
            - 'body' (str): Full comment text; will be truncated to 200 characters for the excerpt.
            - 'priority' (int): Numeric priority (1, 2, or 3) mapped to an emoji label.
            - 'file' (str | None): File path the comment refers to, if any.
            - 'line' (int | None): Line number in the file the comment refers to, if any.
            - 'code_suggestions' (list): List of extracted suggestion dicts to be rendered below the excerpt.
            - 'url' (str): Link to the original GitHub comment.

    Returns:
        str: A markdown-formatted string representing the item, including author, optional location,
        priority label, truncated feedback excerpt, any formatted code suggestions, and a link to the original comment.
    """
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


def _generate_summary(items: List[dict[str, Any]]) -> str:
    """
    Builds a markdown-formatted statistical summary for a list of actionable review items.

    Generates a footer that includes the total count, per-category counts for
    critical, bug, improvement, style, and question items, an optional priority
    note when critical issues or bugs are present, and a generated-by footer.

    Parameters:
        items (List[dict[str, Any]]): List of actionable item dictionaries. Each
            item must include a "category" key whose value is one of:
            "critical", "bug", "improvement", "style", or "question".

    Returns:
        str: Markdown string containing the summary footer.
    """
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


def generate_fix_proposals(actionable_items: List[dict[str, Any]]) -> str:
    """
    Generate a human-readable, categorized report of fix proposals based on actionable review items.

    Parameters:
        actionable_items (List[dict[str, Any]]): A list of actionable item dictionaries (as returned by parse_review_comments),
            where each item contains keys such as "category", "priority", "body", "file", "line", "code_suggestions", "url", and "created_at".

    Returns:
        report (str): A formatted markdown string that groups items by category (critical, bug, improvement, style, question),
            includes per-item summaries and suggested code, and ends with a statistical summary. If the input list is empty,
            returns a short message indicating no actionable items were found.
    """
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
    Write the report to the GitHub Actions step summary (if configured), save it to a secure temporary Markdown file, and print it to standard output.

    If the GITHUB_STEP_SUMMARY environment variable is set, the report is appended to that file. The report is also written to a temporary file with a `.md` suffix and the temp file path is printed to stderr. I/O errors encountered while writing either file are reported to stderr but are not raised.
    Parameters:
        report (str): The formatted report content to persist and print.
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
    """
    Orchestrates end-to-end processing to generate and write fix proposals for a pull request.

    Validates required environment variables, loads configuration, retrieves the pull request, parses review comments for actionable items, generates a markdown report of fix proposals, and writes the report to the GitHub step summary file (if present), a secure temporary Markdown file, and standard output. Exits with status 1 on missing or invalid environment variables, GitHub API errors, or other unexpected errors.
    """
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
