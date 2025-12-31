#!/usr/bin/env python3
"""
Generate detailed status reports for PRs.

This script fetches comprehensive PR information from GitHub API and generates
a formatted status report including commits, files changed, reviews, checks, and tasks.
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict

try:
    import yaml
    from github import Github
except ImportError:
    print("Error: Required packages not installed. Run: pip install PyGithub pyyaml", file=sys.stderr)
    sys.exit(1)


def load_config() -> Dict[str, Any]:
    """Load configuration from pr-copilot-config.yml."""
    config_path = ".github/pr-copilot-config.yml"
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Warning: Config file not found at {config_path}, using defaults", file=sys.stderr)
        return {}


def get_pr_info(g: Github, repo_full_name: str, pr_number: int) -> Dict[str, Any]:
    """Fetch comprehensive PR information."""
    repo = g.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    # Get commits
    commits = list(pr.get_commits())
    commit_count = len(commits)

    # Get files changed
    files = list(pr.get_files())
    files_changed = len(files)

    # Get reviews
    reviews = list(pr.get_reviews())
    approved_reviews = [r for r in reviews if r.state == "APPROVED"]
    changes_requested = [r for r in reviews if r.state == "CHANGES_REQUESTED"]
    commented_reviews = [r for r in reviews if r.state == "COMMENTED"]

    # Get review comments (threads)
    review_comments = list(pr.get_review_comments())
    # Count top-level review comments as thread count (approximate)
    # Note: GitHub API doesn't expose resolved/unresolved status directly
    open_threads = len(review_comments)

    # Get labels
    labels = [label.name for label in pr.labels]

    # Get check runs
    check_runs = []
    try:
        commit = repo.get_commit(pr.head.sha)
        check_suites = commit.get_check_suites()
        for suite in check_suites:
            for run in suite.get_check_runs():
                check_runs.append({"name": run.name, "status": run.status, "conclusion": run.conclusion})
    except Exception as e:
        print(f"Warning: Could not fetch check runs: {e}", file=sys.stderr)

    return {
        "pr": pr,
        "commit_count": commit_count,
        "files_changed": files_changed,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "reviews": {
            "approved": len(approved_reviews),
            "changes_requested": len(changes_requested),
            "commented": len(commented_reviews),
            "total": len(reviews),
        },
        "labels": labels,
        "open_threads": open_threads,
        "check_runs": check_runs,
        "is_draft": pr.draft,
        "mergeable": pr.mergeable,
        "mergeable_state": pr.mergeable_state,
    }


def generate_review_status(info: Dict[str, Any]) -> str:
    """Generate review status section."""
    reviews = info["reviews"]

    status_lines = []
    status_lines.append(f"- ✅ **Approved:** {reviews['approved']}")
    status_lines.append(f"- 🔄 **Changes Requested:** {reviews['changes_requested']}")
    status_lines.append(f"- 💬 **Commented:** {reviews['commented']}")
    status_lines.append(f"- 📋 **Total Reviews:** {reviews['total']}")

    return "\n".join(status_lines)


def generate_check_status(info: Dict[str, Any]) -> str:
    """Generate check status section."""
    check_runs = info["check_runs"]

    if not check_runs:
        return "- ℹ️ No checks configured or pending"

    passed = len([c for c in check_runs if c["conclusion"] == "success"])
    failed = len([c for c in check_runs if c["conclusion"] == "failure"])
    pending = len([c for c in check_runs if c["status"] != "completed"])
    skipped = len([c for c in check_runs if c["conclusion"] in ["skipped", "neutral"]])

    status_lines = []
    status_lines.append(f"- ✅ **Passed:** {passed}")
    status_lines.append(f"- ❌ **Failed:** {failed}")
    status_lines.append(f"- ⏳ **Pending:** {pending}")
    status_lines.append(f"- ⏭️ **Skipped:** {skipped}")
    status_lines.append(f"- 📊 **Total:** {len(check_runs)}")

    # List failed checks
    if failed > 0:
        status_lines.append("\n**Failed Checks:**")
        for check in check_runs:
            if check["conclusion"] == "failure":
                status_lines.append(f"  - ❌ {check['name']}")

    return "\n".join(status_lines)


def generate_task_checklist(info: Dict[str, Any]) -> str:
    """Generate task checklist based on PR status."""
    pr = info["pr"]
    tasks = []

    # Check if draft
    if info["is_draft"]:
        tasks.append("- [ ] Mark PR as ready for review")
    else:
        tasks.append("- [x] Mark PR as ready for review")

    # Check for reviews
    if info["reviews"]["approved"] > 0:
        tasks.append("- [x] Get approval from reviewer")
    else:
        tasks.append("- [ ] Get approval from reviewer")

    # Check for passing checks
    passed_checks = len([c for c in info["check_runs"] if c["conclusion"] == "success"])
    total_checks = len(info["check_runs"])
    if total_checks > 0 and passed_checks == total_checks:
        tasks.append("- [x] All CI checks passing")
    elif total_checks > 0:
        tasks.append(f"- [ ] All CI checks passing ({passed_checks}/{total_checks} passed)")
    else:
        tasks.append("- [ ] CI checks pending/not configured")

    # Check for conflicts
    if info["mergeable_state"] == "dirty":
        tasks.append("- [ ] Resolve merge conflicts")
    elif info["mergeable"]:
        tasks.append("- [x] No merge conflicts")
    else:
        tasks.append("- [ ] Check for merge conflicts")

    # Check for changes requested
    if info["reviews"]["changes_requested"] > 0:
        tasks.append("- [ ] Address requested changes")
    else:
        tasks.append("- [x] No pending change requests")

    # Check for open threads
    if info["open_threads"] > 0:
        tasks.append(f"- [ ] Resolve open discussion threads ({info['open_threads']})")
    else:
        tasks.append("- [x] All discussion threads resolved")

    return "\n".join(tasks)


def generate_status_report(info: Dict[str, Any]) -> str:
    """Generate complete status report."""
    pr = info["pr"]

    # Format labels
    labels_str = ", ".join([f"`{label}`" for label in info["labels"]]) if info["labels"] else "None"

    report = f"""📊 **PR Status Report**

**PR Information:**
- **Author:** @{pr.user.login}
- **Title:** {pr.title}
- **Number:** #{pr.number}
- **Base Branch:** `{pr.base.ref}` ← **Head Branch:** `{pr.head.ref}`
- **Commits:** {info['commit_count']}
- **Files Changed:** {info['files_changed']}
- **Lines:** +{info['additions']} / -{info['deletions']}
- **Labels:** {labels_str}
- **Draft:** {"📝 Yes" if info['is_draft'] else "✅ No"}

**Review Status:**
{generate_review_status(info)}

**CI/Check Status:**
{generate_check_status(info)}

**Open Discussion Threads:** {info['open_threads']}

**Merge Status:**
- **Mergeable:** {("✅ Yes" if info['mergeable'] else "❌ No") if info['mergeable'] is not None else "⏳ Checking..."}
- **State:** `{info['mergeable_state']}`

**Task Checklist:**
{generate_task_checklist(info)}

---
*Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*
*Generated by PR Copilot Status Generator*"""

    return report


def main():
    """Main execution function."""
    # Get environment variables
    github_token = os.environ.get("GITHUB_TOKEN")
    pr_number = os.environ.get("PR_NUMBER")
    repo_owner = os.environ.get("REPO_OWNER")
    repo_name = os.environ.get("REPO_NAME")

    if not all([github_token, pr_number, repo_owner, repo_name]):
        print("Error: Missing required environment variables", file=sys.stderr)
        print("Required: GITHUB_TOKEN, PR_NUMBER, REPO_OWNER, REPO_NAME", file=sys.stderr)
        sys.exit(1)

    try:
        pr_number = int(pr_number)
    except ValueError:
        print(f"Error: PR_NUMBER must be an integer, got: {pr_number}", file=sys.stderr)
        sys.exit(1)

    # Load configuration
    config = load_config()

    # Initialize GitHub client
    g = Github(github_token)
    repo_full_name = f"{repo_owner}/{repo_name}"

    try:
        # Fetch PR information
        print(f"Fetching information for PR #{pr_number}...", file=sys.stderr)
        info = get_pr_info(g, repo_full_name, pr_number)

        # Generate report
        report = generate_status_report(info)

        # Write to file
        output_file = "/tmp/pr_status_report.md"
        with open(output_file, "w") as f:
            f.write(report)

        print(f"Status report generated successfully: {output_file}", file=sys.stderr)
        print(report)  # Also print to stdout

    except Exception as e:
        print(f"Error generating status report: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
