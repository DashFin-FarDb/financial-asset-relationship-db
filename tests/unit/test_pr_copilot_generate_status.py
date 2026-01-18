# pylint: disable=redefined-outer-name, unused-argument
"""
Unit tests for PR Copilot generate_status.py script.

Tests the status report generation functionality including PR data fetching,
formatting, and output generation.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from generate_status import (
    CheckRunInfo,
    PRStatus,
    fetch_pr_status,
    format_checklist,
    format_checks_section,
    generate_markdown,
    write_output,
)

sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts"))


@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client."""
    return MagicMock()


@pytest.fixture
def mock_pr():
    """Create a mock PR object with typical data."""
    pr = Mock()
    pr.number = 123
    pr.title = "Add new feature"
    pr.user.login = "testuser"
    pr.base.ref = "main"
    pr.head.ref = "feature-branch"
    pr.head.sha = "abc123"
    pr.draft = False
    pr.html_url = "https://github.com/test/repo/pull/123"
    pr.commits = 5
    pr.changed_files = 10
    pr.additions = 100
    pr.deletions = 50

    label1 = Mock()
    label1.name = "bug"
    label2 = Mock()
    label2.name = "enhancement"
    pr.labels = [label1, label2]

    pr.mergeable = True
    pr.mergeable_state = "clean"
    return pr


@pytest.fixture
def mock_reviews():
    """Create mock review objects."""
    approved = Mock(state="APPROVED")
    changes_requested = Mock(state="CHANGES_REQUESTED")
    commented = Mock(state="COMMENTED")
    return [approved, changes_requested, commented]


@pytest.fixture
def mock_check_runs():
    """Create mock check run objects."""
    success_run = Mock(name="CI Test", status="completed", conclusion="success")
    failure_run = Mock(name="Lint", status="completed", conclusion="failure")
    pending_run = Mock(name="Build", status="in_progress", conclusion=None)
    return [success_run, failure_run, pending_run]


def test_check_run_info_creation():
    """Test CheckRunInfo dataclass creation."""
    check = CheckRunInfo(name="Test", status="completed", conclusion="success")
    assert check.name == "Test"
    assert check.status == "completed"
    assert check.conclusion == "success"


def test_pr_status_creation():
    """Test PRStatus dataclass creation with all fields."""
    status = PRStatus(
        number=1,
        title="Test PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://github.com/test/repo/pull/1",
        commit_count=3,
        file_count=5,
        additions=50,
        deletions=20,
        labels=["bug"],
        mergeable=True,
        mergeable_state="clean",
        review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
        open_thread_count=2,
        check_runs=[],
    )
    assert status.number == 1
    assert status.title == "Test PR"
    assert status.commit_count == 3
    assert status.file_count == 5
    assert status.additions == 50
    assert status.deletions == 20


def test_fetch_pr_status(mock_github_client, mock_pr, mock_reviews, mock_check_runs):
    """Test fetching PR status from GitHub API."""
    repo = Mock()
    mock_github_client.get_repo.return_value = repo
    repo.get_pull.return_value = mock_pr

    mock_pr.get_reviews.return_value = mock_reviews
    mock_pr.get_review_comments.return_value = Mock(totalCount=5)

    commit = Mock()
    commit.get_check_runs.return_value = mock_check_runs
    repo.get_commit.return_value = commit

    status = fetch_pr_status(mock_github_client, "test/repo", 123)

    assert status.number == 123
    assert status.title == "Add new feature"
    assert status.author == "testuser"
    assert status.commit_count == 5
    assert status.file_count == 10
    assert status.review_stats["approved"] == 1
    assert status.review_stats["changes_requested"] == 1
    assert status.review_stats["commented"] == 1
    assert status.open_thread_count == 5
    assert len(status.check_runs) == 3


def test_format_checklist_all_complete():
    """Test checklist formatting when all tasks are complete."""
    status = PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
        open_thread_count=0,
        check_runs=[CheckRunInfo("Test", "completed", "success")],
    )

    checklist = format_checklist(status)

    assert "- [x] Mark PR as ready for review" in checklist
    assert "- [x] Get approval from reviewer" in checklist
    assert "- [x] All CI checks passing" in checklist
    assert "- [x] No merge conflicts" in checklist
    assert "- [x] No pending change requests" in checklist


def test_format_checklist_incomplete():
    """Test checklist formatting with incomplete tasks."""
    status = PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=True,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=False,
        mergeable_state="dirty",
        review_stats={"approved": 0, "changes_requested": 1, "commented": 0, "total": 1},
        open_thread_count=3,
        check_runs=[
            CheckRunInfo("Test1", "completed", "success"),
            CheckRunInfo("Test2", "completed", "failure"),
        ],
    )

    checklist = format_checklist(status)

    assert "- [ ] Mark PR as ready for review" in checklist
    assert "- [ ] Get approval from reviewer" in checklist
    assert "- [ ] All CI checks passing (1/2 passed)" in checklist
    assert "- [ ] Resolve merge conflicts" in checklist
    assert "- [ ] No pending change requests" in checklist


def test_format_checks_section_no_checks():
    """Test check section formatting with no checks."""
    result = format_checks_section([])
    assert "No checks configured or pending" in result


def test_format_checks_section_with_checks():
    """Test check section formatting with various check states."""
    checks = [
        CheckRunInfo("Test1", "completed", "success"),
        CheckRunInfo("Test2", "completed", "failure"),
        CheckRunInfo("Test3", "in_progress", None),
        CheckRunInfo("Test4", "completed", "skipped"),
    ]

    result = format_checks_section(checks)

    assert "**Passed:** 1" in result
    assert "**Failed:** 1" in result
    assert "**Pending:** 1" in result
    assert "**Total:** 4" in result
    assert "**Failed Checks:**" in result
    assert "❌ Test2" in result


def test_generate_markdown():
    """Test complete markdown report generation."""
    status = PRStatus(
        number=42,
        title="Fix critical bug",
        author="developer",
        base_ref="main",
        head_ref="bugfix",
        is_draft=False,
        url="https://github.com/test/repo/pull/42",
        commit_count=3,
        file_count=5,
        additions=75,
        deletions=25,
        labels=["bug", "priority"],
        mergeable=True,
        mergeable_state="clean",
        review_stats={"approved": 2, "changes_requested": 0, "commented": 1, "total": 3},
        open_thread_count=4,
        check_runs=[CheckRunInfo("CI", "completed", "success")],
    )

    report = generate_markdown(status)

    assert "📊 **PR Status Report**" in report
    assert "Fix critical bug (#42)" in report
    assert "@developer" in report
    assert "`main` ← `bugfix`" in report
    assert "5 files (3 commits)" in report
    assert "+75 / -25" in report
    assert "`bug`, `priority`" in report
    assert "**Approved:** 2" in report
    assert "**Changes Requested:** 0" in report
    assert "**Commented:** 1" in report
    assert "**Comments/Threads:** 4" in report
    assert "**Mergeable:** ✅ Yes" in report
    assert "Generated by PR Copilot" in report


def test_generate_markdown_draft_pr():
    """Test markdown generation for draft PR."""
    status = PRStatus(
        number=1,
        title="WIP: New feature",
        author="dev",
        base_ref="main",
        head_ref="wip",
        is_draft=True,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=0,
        labels=[],
        mergeable=None,
        mergeable_state="unknown",
        review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
        open_thread_count=0,
        check_runs=[],
    )

    report = generate_markdown(status)

    assert "**Draft:** 📝 Yes" in report
    assert "**Mergeable:** ⏳ Checking..." in report


def test_write_output_to_stdout():
    """Test writing output to stdout when no GitHub summary is set."""
    test_content = "Test report content"

    with patch.dict(os.environ, {}, clear=True):
        with patch("builtins.print") as mock_print:
            write_output(test_content)

            mock_print.assert_any_call(test_content)


def test_write_output_with_github_summary():
    """Test writing output to GitHub step summary."""
    test_content = "Test report"

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": tmp_path}):
            write_output(test_content)

        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Test report" in content
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def test_format_checklist_unknown_mergeable():
    """Test checklist when mergeable state is unknown.

    When mergeable is None and state is 'unknown', the checklist should prompt
    the user to check for merge conflicts rather than asserting a definitive state.
    """
    status = PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=None,
        mergeable_state="unknown",
        review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
        open_thread_count=0,
        check_runs=[CheckRunInfo("Test", "completed", "success")],
    )

    checklist = format_checklist(status)
    assert "- [ ] Check for merge conflicts" in checklist


def test_format_checklist_mergeable_false_but_not_dirty():
    """Test checklist when mergeable is False but state is not dirty (e.g., blocked)."""
    status = PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=False,
        mergeable_state="blocked",
        review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
        open_thread_count=0,
        check_runs=[CheckRunInfo("Test", "completed", "success")],
    )

    checklist = format_checklist(status)
    assert "- [ ] Check for merge conflicts" in checklist
    assert "- [ ] Resolve merge conflicts" not in checklist


def test_generate_markdown_no_labels():
    """Test markdown generation when PR has no labels."""
    status = PRStatus(
        number=1,
        title="Test PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
        open_thread_count=0,
        check_runs=[],
    )

    report = generate_markdown(status)
    assert "**Labels:** None" in report


def test_format_checks_section_with_skipped_checks():
    """Test check section formatting with skipped checks."""
    checks = [
        CheckRunInfo("Test1", "completed", "success"),
        CheckRunInfo("Test2", "completed", "skipped"),
        CheckRunInfo("Test3", "completed", "skipped"),
    ]

    result = format_checks_section(checks)

    assert "**Passed:** 1" in result
    assert "**Skipped:** 2" in result
    assert "**Total:** 3" in result


def test_format_checklist_with_multiple_approvals():
    """Test checklist when PR has multiple approvals."""
    status = PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={"approved": 3, "changes_requested": 0, "commented": 0, "total": 3},
        open_thread_count=0,
        check_runs=[CheckRunInfo("Test", "completed", "success")],
    )

    checklist = format_checklist(status)
    assert "- [x] Get approval from reviewer" in checklist


def test_fetch_pr_status_with_no_reviews(mock_github_client, mock_pr):
    """Test fetching PR status when there are no reviews."""
    repo = Mock()
    mock_github_client.get_repo.return_value = repo
    repo.get_pull.return_value = mock_pr

    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)

    commit = Mock()
    commit.get_check_runs.return_value = []
    repo.get_commit.return_value = commit

    status = fetch_pr_status(mock_github_client, "test/repo", 123)

    assert status.review_stats["approved"] == 0
    assert status.review_stats["changes_requested"] == 0
    assert status.review_stats["commented"] == 0
    assert status.review_stats["total"] == 0
    assert status.open_thread_count == 0


def test_generate_markdown_with_unmergeable_pr():
    """Test markdown generation for unmergeable PR."""
    status = PRStatus(
        number=1,
        title="Test PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=False,
        mergeable_state="dirty",
        review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
        open_thread_count=0,
        check_runs=[],
    )

    report = generate_markdown(status)
    assert "**Mergeable:** ❌ No" in report
    assert "**State:** `dirty`" in report


def test_format_checks_section_all_skipped():
    """Test check section formatting when all checks are skipped."""
    checks = [
        CheckRunInfo("Test1", "completed", "skipped"),
        CheckRunInfo("Test2", "completed", "skipped"),
    ]

    result = format_checks_section(checks)

    assert "**Passed:** 0" in result
    assert "**Failed:** 0" in result
    assert "**Skipped:** 2" in result
    assert "**Total:** 2" in result


def test_format_checklist_with_pending_checks():
    """Test checklist when checks are still pending."""
    status = PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
        open_thread_count=0,
        check_runs=[
            CheckRunInfo("Test1", "completed", "success"),
            CheckRunInfo("Test2", "in_progress", None),
        ],
    )

    checklist = format_checklist(status)
    assert "- [ ] All CI checks passing (1/2 passed)" in checklist


def test_write_output_handles_io_error():
    """Test write_output handles IO errors gracefully."""
    test_content = "Test report"

    with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": "/invalid/path/file.txt"}):
        with patch("builtins.print") as mock_print:
            write_output(test_content)
            mock_print.assert_any_call(test_content)


def test_fetch_pr_status_with_null_mergeable_state(mock_github_client, mock_pr):
    """Test fetching PR status when mergeable_state is None.

    When GitHub is still calculating merge status, mergeable_state can be None.
    The implementation should convert this to 'unknown' for consistent handling.
    """

    repo = Mock()
    mock_github_client.get_repo.return_value = repo
    repo.get_pull.return_value = mock_pr

    mock_pr.mergeable_state = None
    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)

    commit = Mock()
    commit.get_check_runs.return_value = []
    repo.get_commit.return_value = commit

    status = fetch_pr_status(mock_github_client, "test/repo", 123)
    assert status.mergeable_state == "unknown"

    assert status.mergeable == mock_pr.mergeable
    assert status.number == 123


def test_fetch_pr_status_with_empty_mergeable_state(mock_github_client, mock_pr):
    """Test fetching PR status when mergeable_state is empty string."""
    repo = Mock()
    mock_github_client.get_repo.return_value = repo
    repo.get_pull.return_value = mock_pr

    mock_pr.mergeable_state = ""
    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)

    commit = Mock()
    commit.get_check_runs.return_value = []
    repo.get_commit.return_value = commit

    status = fetch_pr_status(mock_github_client, "test/repo", 123)

    assert status.mergeable_state == "unknown"
    assert status.mergeable is True
    assert status.number == 123


def test_generate_markdown_with_null_mergeable_state():
    """Test markdown generation when mergeable is None."""
    status = PRStatus(
        number=1,
        title="Test PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=None,
        mergeable_state="unknown",
        review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
        open_thread_count=0,
        check_runs=[],
    )

    report = generate_markdown(status)
    assert "**Mergeable:** ⏳ Checking..." in report


def test_generate_markdown_with_multiple_labels():
    """Test markdown generation with multiple labels."""
    status = PRStatus(
        number=1,
        title="Test PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="url",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=["bug", "enhancement", "documentation"],
        mergeable=True,
        mergeable_state="clean",
        review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
        open_thread_count=0,
        check_runs=[],
    )

    report = generate_markdown(status)
    assert "`bug`, `enhancement`, `documentation`" in report


def test_format_checks_section_with_multiple_failures():
    """Test check section formatting with multiple failed checks."""
    checks = [
        CheckRunInfo("Test1", "completed", "success"),
        CheckRunInfo("Test2", "completed", "failure"),
        CheckRunInfo("Test3", "completed", "failure"),
        CheckRunInfo("Test4", "completed", "failure"),
    ]

    result = format_checks_section(checks)

    assert "**Passed:** 1" in result
    assert "**Failed:** 3" in result
    assert "**Failed Checks:**" in result
    assert "❌ Test2" in result
    assert "❌ Test3" in result
    assert "❌ Test4" in result
