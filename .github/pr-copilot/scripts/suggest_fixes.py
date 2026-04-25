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


def load_config() -> Dict[str, Any]:
    """Load PR copilot configuration."""
    config_path = ".github/pr-copilot-config.yml"
    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            return yaml.safe_load(config_file) or {}
    except FileNotFoundError:
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


def extract_code_suggestions(comment_body: str) -> List[Dict[str, str]]:
    """Extract code change suggestions from a review comment body."""
    suggestions = []

    suggestion_pattern = r"```suggestion\s*\n(.*?)\n```"
    matches = re.finditer(suggestion_pattern, comment_body, re.DOTALL)
    for match in matches:
        suggestions.append(
            {
                "type": "code_suggestion",
                "content": match.group(1).strip(),
            }
        )

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
    """Determine the category and priority for a review comment."""
    body_lower = comment_body.lower()

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

    for category, priority, keywords in categories:
        if any(keyword in body_lower for keyword in keywords):
            return category, priority

    return "improvement", 2


def is_actionable(comment_body: str, actionable_keywords: List[str]) -> bool:
    """Return whether the comment contains any actionable keyword."""
    body_lower = comment_body.lower()
    return any(keyword in body_lower for keyword in actionable_keywords)


def parse_review_comments(
    pr: Any,
    actionable_keywords: List[str],
) -> List[Dict[str, Any]]:
    """Collect actionable items from a GitHub pull request's review comments."""
    actionable_items = []

    def process_comment(comment_obj: Any, is_review: bool = False) -> None:
        body = comment_obj.body or ""
        if not is_actionable(body, actionable_keywords):
            return

        category, priority = categorize_comment(body)
        code_suggestions = extract_code_suggestions(body)
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

    for comment in pr.get_review_comments():
        process_comment(comment)

    for review in pr.get_reviews():
        if review.state == "CHANGES_REQUESTED":
            process_comment(review, is_review=True)

    actionable_items.sort(key=lambda item: (item["priority"], item["created_at"]))
    return actionable_items


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
    """Create a Markdown footer summarizing actionable items by category."""
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

    categorized = defaultdict(list)
    for item in actionable_items:
        categorized[item["category"]].append(item)

    report = "🔧 **Fix Proposals from Review Comments**\n\n"
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
        for index, item in enumerate(items, 1):
            report += _format_item(index, item)

    report += _generate_summary(actionable_items)
    return report


def write_output(report: str) -> None:
    """Persist the Markdown report to configured outputs and print it."""
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        try:
            summary_path = os.path.realpath(gh_summary)
            runner_temp = os.environ.get("RUNNER_TEMP")
            if runner_temp:
                runner_temp_path = os.path.realpath(runner_temp)
                if os.path.commonpath([summary_path, runner_temp_path]) != runner_temp_path:
                    print(
                        "Warning: Ignoring GITHUB_STEP_SUMMARY outside RUNNER_TEMP",
                        file=sys.stderr,
                    )
                    return
            with open(summary_path, "a", encoding="utf-8") as summary_file:
                summary_file.write(report)
        except (OSError, ValueError) as error:
            print(
                f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {error}",
                file=sys.stderr,
            )

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
    except OSError as error:
        print(f"Error writing temp file: {error}", file=sys.stderr)

    print(report)


def main() -> None:
    """Run the CLI flow to collect actionable review comments from a pull request."""
    required = ["GITHUB_TOKEN", "PR_NUMBER", "REPO_OWNER", "REPO_NAME"]
    env_vars = {var: os.environ.get(var) for var in required}

    if not all(env_vars.values()):
        print("Error: Missing required environment variables", file=sys.stderr)
        sys.exit(1)

    try:
        pr_number = int(env_vars["PR_NUMBER"])  # type: ignore[arg-type]
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
        github_client = Github(env_vars["GITHUB_TOKEN"])
        repo = github_client.get_repo(f"{env_vars['REPO_OWNER']}/{env_vars['REPO_NAME']}")
        pr = repo.get_pull(pr_number)

        print(f"Parsing review comments for PR #{pr_number}...", file=sys.stderr)
        items = parse_review_comments(pr, keywords)
        report = generate_fix_proposals(items)
        write_output(report)

    except GithubException as github_error:
        print(f"GitHub API Error: {github_error}", file=sys.stderr)
        sys.exit(1)
    except Exception as unexpected_error:  # noqa: BLE001
        print(f"Unexpected Error: {unexpected_error}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
