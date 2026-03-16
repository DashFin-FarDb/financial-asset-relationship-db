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
import traceback
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
    """
    Load PR copilot configuration from .github/pr-copilot-config.yml, falling back to a built-in default when the file is absent.

    Returns:
        dict: Parsed configuration mapping. If the YAML file is missing, returns a default config containing a "review_handling" key with an "actionable_keywords" list.
    """
    config_path = ".github/pr-copilot-config.yml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
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
    Extracts code change suggestions from a review comment body.

    Recognizes two kinds of suggestions:
    - fenced suggestion blocks beginning with ```suggestion and ending with ``` (captured as `code_suggestion`).
    - inline suggestions expressed with phrases like "should be", "change to", "replace with", or "use" followed by backticked code (captured as `inline_suggestion`).

    Parameters:
        comment_body (str): Raw text of the review comment.

    Returns:
        List[Dict[str, str]]: A list of suggestion objects in the order found. Each object has:
            - `type`: either `"code_suggestion"` or `"inline_suggestion"`.
            - `content`: the suggested code or replacement text.
    """
    suggestions = []

    # Pattern 1: Code blocks with suggestion marker
    suggestion_pattern = r"```suggestion\s*\n(.*?)\n```"
    matches = re.finditer(suggestion_pattern, comment_body, re.DOTALL)
    for match in matches:
        suggestions.append(
            {
                "type": "code_suggestion",
                "content": match.group(1).strip(),
            }
        )

    # Pattern 2: Inline code in quotes with suggestion words
    inline_pattern = r"(?:should be|change to|replace with|use)\s+`([^`]+)`"
    matches = re.finditer(inline_pattern, comment_body, re.IGNORECASE)
    for match in matches:
        suggestions.append(
            {
                "type": "inline_suggestion",
                "content": match.group(1).strip(),
            }
        )

    return suggestions


def categorize_comment(comment_body: str) -> Tuple[str, int]:
    """
    Classifies a review comment into a category and assigns a priority.

    Parameters:
        comment_body (str): Full text of the review comment to classify.

    Returns:
        tuple: (category, priority) where `category` is one of "critical", "bug", "improvement", "style", or "question", and `priority` is an integer with 1 = high, 2 = medium, 3 = low.
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
        (
            "improvement",
            2,
            ["refactor", "improve", "optimize", "enhance", "consider"],
        ),
    ]

    # Check each category in priority order
    for category, priority, keywords in categories:
        if any(kw in body_lower for kw in keywords):
            return category, priority

    # Default
    return "improvement", 2


def is_actionable(comment_body: str, actionable_keywords: List[str]) -> bool:
    """
    Determine whether a comment contains any actionable keywords.

    Parameters:
        comment_body (str): The comment text to inspect.
        actionable_keywords (List[str]): Keywords considered actionable; matching is case-insensitive.

    Returns:
        bool: `true` if at least one actionable keyword appears in the comment (case-insensitive), `false` otherwise.
    """
    body_lower = comment_body.lower()
    return any(keyword in body_lower for keyword in actionable_keywords)


def parse_review_comments(
    pr: Any,
    actionable_keywords: List[str],
) -> List[Dict[str, Any]]:
    """
    Collect actionable items from a GitHub pull request's review comments.

    Parameters:
        pr (Any): A PullRequest-like object providing get_review_comments() and get_reviews().
        actionable_keywords (List[str]): Keywords used to determine whether a comment is actionable.

    Returns:
        List[Dict[str, Any]]: A list of actionable item dictionaries sorted by priority (ascending) then creation time (ascending). Each dictionary contains:
            - id: comment or review identifier
            - author: comment author's login
            - body: full comment text
            - category: classified category (e.g., critical, bug, improvement, style, question)
            - priority: numeric priority where lower is higher priority
            - file: file path the comment refers to, or None
            - line: original line number the comment refers to, or None
            - code_suggestions: list of extracted code suggestion entries
            - url: URL to the original comment
            - created_at: timestamp when the comment or review was submitted
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
    """
    Builds a Markdown summary footer with counts of actionable items by category.

    Produces a Markdown string containing the total actionable item count, individual counts for the categories `critical`, `bug`, `improvement`, `style`, and `question`, and a priority note if any critical issues or bugs are present.

    Parameters:
        items (List[Dict[str, Any]]): List of actionable item dictionaries that include a "category" key.

    Returns:
        str: Markdown-formatted summary footer with per-category counts and a generated-by notice.
    """
    counts: defaultdict[str, int] = defaultdict(int)
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
    # 1. GitHub Summary
    """
    Persist the generated Markdown report to configured outputs and print it.

    If the GITHUB_STEP_SUMMARY environment variable is set and points inside the system temporary directory,
    the report is appended to that file. The report is also written to a securely created temporary file
    with a `.md` suffix; the created temporary file path is printed to stderr. Finally, the full report is
    printed to stdout.
    """
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        try:
            summary_path = os.path.realpath(gh_summary)
            allowed_roots = {os.path.realpath(tempfile.gettempdir())}
            runner_temp = os.environ.get("RUNNER_TEMP")
            if runner_temp:
                allowed_roots.add(os.path.realpath(runner_temp))

            if not any(os.path.commonpath([summary_path, root]) == root for root in allowed_roots):
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
    Orchestrates loading configuration, fetching the specified pull request, extracting actionable review items, and writing a structured fix-proposal report.

    Requires the environment variables GITHUB_TOKEN, PR_NUMBER, REPO_OWNER, and REPO_NAME. Exits with status code 1 if required environment variables are missing, PR_NUMBER is not an integer, or a GitHub API error occurs. On other unexpected errors it prints a traceback and exits with status code 1.
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
        [
            "please",
            "should",
            "fix",
            "refactor",
            "change",
            "update",
            "add",
            "remove",
        ],
    )

    try:
        g = Github(env_vars["GITHUB_TOKEN"])
        repo = g.get_repo(f"{env_vars['REPO_OWNER']}/{env_vars['REPO_NAME']}")
        pr = repo.get_pull(pr_number)

        print(
            f"Parsing review comments for PR #{pr_number}...",
            file=sys.stderr,
        )
        items = parse_review_comments(pr, keywords)

        report = generate_fix_proposals(items)
        write_output(report)

    except GithubException as ge:
        # Specific GitHub API error handling for clearer failures.
        print(f"GitHub API Error: {ge}", file=sys.stderr)
        sys.exit(1)
    except (IOError, OSError, RuntimeError, TypeError, ValueError) as e:
        print(f"Unexpected Error: {e}", file=sys.stderr)

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
