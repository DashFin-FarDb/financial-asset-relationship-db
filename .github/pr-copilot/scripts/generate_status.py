#!/usr/bin/env python3
"""
Generate detailed status reports for PRs.

This script fetches comprehensive PR information from GitHub API and
generates a formatted status report including commits, files changed,
reviews, checks, and tasks.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from github import Github, GithubException
except ImportError:
    print("Error: Required package 'PyGithub' not installed.", file=sys.stderr)
    print("Run: pip install PyGithub", file=sys.stderr)
    sys.exit(1)


@dataclass(frozen=True)
class CheckRunInfo:
    """Summary of a single CI check run."""

    name: str
    status: str
    conclusion: Optional[str]


@dataclass(frozen=True)
# pylint: disable=too-many-instance-attributes
class PRStatus:
    """Container for all PR status information."""

    # Metadata
    number: int
    title: str
    author: str
    base_ref: str
    head_ref: str
    is_draft: bool
    url: str

    # Stats
    commit_count: int
    file_count: int
    additions: int
    deletions: int

    # State
    labels: List[str]
    mergeable: Optional[bool]
    mergeable_state: str

    # Reviews & Checks
    review_stats: Dict[str, int]
    open_thread_count: int
    check_runs: List[CheckRunInfo]


def fetch_pr_status(g: Github, repo_name: str, pr_num: int) -> PRStatus:
    """
    Fetch aggregated pull request data from GitHub and return a PRStatus
    describing metadata, stats, review and CI state.

    Parameters:
        g (Github): Authenticated PyGithub Github client.
        repo_name (str): Repository name in "owner/name" form.
        pr_num (int): Pull request number.

    Returns:
        PRStatus: Aggregated PR information including:
        - number, title, author, base/head refs, draft flag, and URL
        - commit/file/addition/deletion counts and label names
        - mergeability state (defaults to "unknown" if absent)
        - review statistics and proxy review-thread count
        - check run entries with name, status, and conclusion
    """
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_num)

    # 1. Reviews (Must iterate to classify)
    reviews = list(pr.get_reviews())
    review_stats = {
        "approved": len([r for r in reviews if r.state == "APPROVED"]),
        "changes_requested": len([r for r in reviews if r.state == "CHANGES_REQUESTED"]),
        "commented": len([r for r in reviews if r.state == "COMMENTED"]),
        "total": len(reviews),
    }

    # 2. Review Threads
    # Note: get_review_comments returns individual comments.
    # Grouping by position/path is complex; counting total comments
    # is a decent proxy for "activity".
    # For distinct threads, we'd need to map reply_to_id.
    # Sticking to simple count for performance.
    open_threads = pr.get_review_comments().totalCount

    # 3. Check Runs
    # Optimization: Get runs directly from commit, skipping Suite iteration
    head_commit = repo.get_commit(pr.head.sha)
    check_runs_data = []

    # We use list() here because we need to inspect properties
    for run in head_commit.get_check_runs():
        check_runs_data.append(
            CheckRunInfo(
                name=run.name,
                status=run.status,
                conclusion=run.conclusion,
            )
        )

    return PRStatus(
        number=pr.number,
        title=pr.title,
        author=pr.user.login,
        base_ref=pr.base.ref,
        head_ref=pr.head.ref,
        is_draft=pr.draft,
        url=pr.html_url,
        commit_count=pr.commits,  # API Attribute (Fast)
        file_count=pr.changed_files,  # API Attribute (Fast)
        additions=pr.additions,
        deletions=pr.deletions,
        labels=[label.name for label in pr.labels],
        mergeable=pr.mergeable,
        mergeable_state=pr.mergeable_state or "unknown",
        review_stats=review_stats,
        open_thread_count=open_threads,
        check_runs=check_runs_data,
    )


def format_checklist(status: PRStatus) -> str:
    """
    Create a Markdown task checklist summarizing a PR's readiness, review status, CI check results, mergeability, and pending change requests.

    Parameters:
        status (PRStatus): Aggregated pull request data used to determine checklist items (reads draft status, review_stats, check_runs, mergeable, and mergeable_state).

    Returns:
        markdown_checklist (str): Newline-separated Markdown task list where each line is a checked/unchecked item for: ready for review, approval, CI passing (with counts when partial), merge conflict resolution, and pending change requests.
    """
    tasks = []

    # Ready for review
    is_ready = not status.is_draft
    tasks.append(f"- [{'x' if is_ready else ' '}] Mark PR as ready for review")

    # Approval
    approved = status.review_stats["approved"] > 0
    tasks.append(f"- [{'x' if approved else ' '}] Get approval from reviewer")

    # CI Checks
    total_checks = len(status.check_runs)
    passed_checks = len([c for c in status.check_runs if c.conclusion == "success"])

    if total_checks == 0:
        tasks.append("- [ ] CI checks pending/not configured")
    elif passed_checks == total_checks:
        tasks.append("- [x] All CI checks passing")
    else:
        tasks.append(f"- [ ] All CI checks passing ({passed_checks}/{total_checks} passed)")

    # Conflicts
    clean_merge = status.mergeable is True
    dirty_merge = status.mergeable_state == "dirty"

    if dirty_merge:
        tasks.append("- [ ] Resolve merge conflicts")
    elif clean_merge:
        tasks.append("- [x] No merge conflicts")
    else:
        tasks.append("- [ ] Check for merge conflicts")

    # Change Requests
    has_cr = status.review_stats["changes_requested"] > 0
    tasks.append(f"- [{' ' if has_cr else 'x'}] No pending change requests")

    return "\n".join(tasks)


def format_checks_section(checks: List[CheckRunInfo]) -> str:
    """Format the CI status section."""
    if not checks:
        return "- ℹ️ No checks configured or pending"

    passed = len([c for c in checks if c.conclusion == "success"])
    failed = len([c for c in checks if c.conclusion == "failure"])
    pending = len([c for c in checks if c.status != "completed"])
    skipped = len(checks) - passed - failed - pending

    lines = [
        f"- ✅ **Passed:** {passed}",
        f"- ❌ **Failed:** {failed}",
        f"- ⏳ **Pending:** {pending}",
        f"- ⏭️ **Skipped:** {skipped}",
        f"- 📊 **Total:** {len(checks)}",
    ]

    if failed > 0:
        lines.append("\n**Failed Checks:**")
        for c in checks:
            if c.conclusion == "failure":
                lines.append(f"  - ❌ {c.name}")

    return "\n".join(lines)


def generate_markdown(status: PRStatus) -> str:
    """
    Builds a Markdown-formatted status report for the provided pull request.

    Generate a complete PR report including PR metadata, review statistics, CI/check details, mergeability, a task checklist, and a UTC timestamp footer.

    Parameters:
        status (PRStatus): Aggregated data and metrics for the pull request used to populate the report.

    Returns:
        report (str): The Markdown document summarizing the PR status.
    """

    # Review Section
    revs = status.review_stats
    review_section = (
        f"- ✅ **Approved:** {revs['approved']}\n"
        f"- 🔄 **Changes Requested:** {revs['changes_requested']}\n"
        f"- 💬 **Commented:** {revs['commented']}\n"
        f"- 📋 **Total Reviews:** {revs['total']}"
    )

    labels_str = ", ".join([f"`{label}`" for label in status.labels]) if status.labels else "None"
    draft_status = "📝 Yes" if status.is_draft else "✅ No"

    # Merge Status
    merge_icon = "✅ Yes" if status.mergeable else "❌ No"
    if status.mergeable is None:
        merge_icon = "⏳ Checking..."

    return f"""📊 **PR Status Report**

**PR Information**
- **Title:** {status.title} (#{status.number})
- **Author:** @{status.author}
- **Branch:** `{status.base_ref}` ← `{status.head_ref}`
- **Size:** {status.file_count} files ({status.commit_count} commits)
- **Diff:** +{status.additions} / -{status.deletions}
- **Labels:** {labels_str}
- **Draft:** {draft_status}

**Review Status**
{review_section}
- **Comments/Threads:** {status.open_thread_count}

**CI/Check Status**
{format_checks_section(status.check_runs)}

**Merge Status**
- **Mergeable:** {merge_icon}
- **State:** `{status.mergeable_state}`

**Task Checklist**
{format_checklist(status)}

---
*Last updated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC*
*Generated by PR Copilot*
"""


def write_output(content: str) -> None:
    """
    Write the Markdown report to the GitHub Actions step summary (when it is safe to do so), to a standard temp file, and to stdout.

    If the GITHUB_STEP_SUMMARY environment variable is set and points inside the system temporary directory, append content to that file; otherwise the step-summary write is skipped and a warning is printed to stderr. Overwrite the file named "pr_status_report.md" in the system temporary directory and print its path to stderr on success. I/O and path-related errors are caught and printed to stderr; the function does not raise.
    Parameters:
        content (str): The Markdown report content to write.
    """
    # 1. GitHub Step Summary (Native integration)
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
                    f.write(content)
        except (IOError, ValueError) as e:
            print(
                f"Warning: Could not write to GITHUB_STEP_SUMMARY: {e}",
                file=sys.stderr,
            )

    # 2. Standard Temp File
    # We use a standard temp path.
    # We do not crash if it exists; we overwrite.
    output_path = os.path.join(tempfile.gettempdir(), "pr_status_report.md")

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Report written to: {output_path}", file=sys.stderr)
    except IOError as e:
        print(f"Error writing to temp file: {e}", file=sys.stderr)

    # 3. Stdout
    print(content)


def main():
    """
    Main entry point for the CLI: validates environment, fetches PR status, generates a Markdown report, and writes the report to configured outputs.

    Requires the environment variables GITHUB_TOKEN, PR_NUMBER, REPO_OWNER, and REPO_NAME. Exits with status code 0 on success and with status code 1 on any validation, API, or runtime error; prints error details to stderr before exiting.
    """
    # Env Var Validation
    required = ["GITHUB_TOKEN", "PR_NUMBER", "REPO_OWNER", "REPO_NAME"]
    env = {var: os.environ.get(var) for var in required}

    if not all(env.values()):
        missing = [k for k, v in env.items() if not v]
        print(
            f"Error: Missing environment variables: {missing}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        pr_num = int(env["PR_NUMBER"])  # type: ignore
    except ValueError:
        print("Error: PR_NUMBER must be an integer", file=sys.stderr)
        sys.exit(1)

    try:
        # Connect
        g = Github(env["GITHUB_TOKEN"])
        repo_name = f"{env['REPO_OWNER']}/{env['REPO_NAME']}"

        print(f"Fetching status for PR #{pr_num}...", file=sys.stderr)

        # Execute
        status = fetch_pr_status(g, repo_name, pr_num)
        report = generate_markdown(status)
        write_output(report)

        sys.exit(0)

    except GithubException as e:
        print(f"GitHub API Error: {e.data.get('message', e)}", file=sys.stderr)
        sys.exit(1)
    except (IOError, OSError, RuntimeError, TypeError, ValueError):
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
