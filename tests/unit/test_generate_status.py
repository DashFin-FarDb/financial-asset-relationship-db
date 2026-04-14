"""Comprehensive unit tests for generate_status.py.

This module tests all functions in the generate_status.py script including:
- PRStatus dataclass creation
- PR data fetching and consolidation
- Checklist generation with various PR states
- Check runs formatting
- Markdown report generation
- Output writing to files and stdout
- Error handling and edge cases
"""

import os
import sys
import tempfile
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import MagicMock, Mock, mock_open, patch

import generate_status
import pytest
from github import GithubException

# Add the script directory to path so generate_status can be resolved
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.github/pr-copilot/scripts"))


# --- Fixtures ---


@pytest.fixture
def mock_pr():
    """Create a mock PR object with common attributes."""
    pr = Mock()
    pr.number = 123
    pr.title = "Test PR Title"
    pr.user = Mock(login="testuser")
    pr.base = Mock(ref="main")
    pr.head = Mock(ref="feature-branch", sha="abc123")
    pr.draft = False
    pr.html_url = "https://github.com/owner/repo/pull/123"
    pr.commits = 5
    pr.changed_files = 10
    pr.additions = 100
    pr.deletions = 50
    pr.labels = []
    pr.mergeable = True
    pr.mergeable_state = "clean"
    return pr


@pytest.fixture
def mock_review_approved():
    """Create a mock approved review."""
    review = Mock()
    review.state = "APPROVED"
    review.user = Mock(login="reviewer1")
    review.submitted_at = datetime.now(timezone.utc)
    review.body = "LGTM!"
    review.id = 1
    review.html_url = "https://github.com/owner/repo/pull/123#review-1"
    return review


@pytest.fixture
def mock_review_changes_requested():
    """Create a mock changes requested review."""
    review = Mock()
    review.state = "CHANGES_REQUESTED"
    review.user = Mock(login="reviewer2")
    review.submitted_at = datetime.now(timezone.utc)
    review.body = "Please fix the typo"
    review.id = 2
    review.html_url = "https://github.com/owner/repo/pull/123#review-2"
    return review


@pytest.fixture
def mock_review_commented():
    """Create a mock commented review."""
    review = Mock()
    review.state = "COMMENTED"
    review.user = Mock(login="reviewer3")
    review.submitted_at = datetime.now(timezone.utc)
    review.body = "Nice work!"
    review.id = 3
    review.html_url = "https://github.com/owner/repo/pull/123#review-3"
    return review


@pytest.fixture
def mock_check_run_success():
    """Create a mock successful check run."""
    check = Mock()
    check.name = "test-check"
    check.status = "completed"
    check.conclusion = "success"
    return check


@pytest.fixture
def mock_check_run_failure():
    """Create a mock failed check run."""
    check = Mock()
    check.name = "lint-check"
    check.status = "completed"
    check.conclusion = "failure"
    return check


@pytest.fixture
def mock_check_run_pending():
    """Create a mock pending check run."""
    check = Mock()
    check.name = "build-check"
    check.status = "in_progress"
    check.conclusion = None
    return check


@pytest.fixture
def sample_pr_status():
    """Create a sample PRStatus object for testing."""
    return generate_status.PRStatus(
        number=123,
        title="Test PR",
        author="testuser",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://github.com/owner/repo/pull/123",
        commit_count=5,
        file_count=10,
        additions=100,
        deletions=50,
        labels=["bug", "enhancement"],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 1,
            "changes_requested": 0,
            "commented": 1,
            "total": 2,
        },
        open_thread_count=3,
        check_runs=[
            generate_status.CheckRunInfo("test", "completed", "success"),
            generate_status.CheckRunInfo("lint", "completed", "success"),
        ],
    )


# --- Test CheckRunInfo Dataclass ---


def test_check_run_info_creation():
    """Test CheckRunInfo dataclass creation."""
    check = generate_status.CheckRunInfo(name="test-check", status="completed", conclusion="success")
    assert check.name == "test-check"
    assert check.status == "completed"
    assert check.conclusion == "success"


def test_check_run_info_frozen():
    """Test that CheckRunInfo is immutable (frozen)."""
    check = generate_status.CheckRunInfo("test", "completed", "success")
    with pytest.raises(AttributeError):
        check.name = "new-name"


def test_check_run_info_with_none_conclusion():
    """Test CheckRunInfo with None conclusion (pending check)."""
    check = generate_status.CheckRunInfo("pending-check", "in_progress", None)
    assert check.conclusion is None


# --- Test PRStatus Dataclass ---


def test_pr_status_creation(sample_pr_status):
    """Test PRStatus dataclass creation."""
    assert sample_pr_status.number == 123
    assert sample_pr_status.title == "Test PR"
    assert sample_pr_status.author == "testuser"
    assert len(sample_pr_status.labels) == 2
    assert sample_pr_status.review_stats["approved"] == 1


def test_pr_status_frozen():
    """Test that PRStatus is immutable (frozen)."""
    status = generate_status.PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={},
        open_thread_count=0,
        check_runs=[],
    )
    with pytest.raises(AttributeError):
        status.number = 999


# --- Test fetch_pr_status Function ---


def test_fetch_pr_status_basic(mock_pr, mock_review_approved, mock_check_run_success):
    """Test fetch_pr_status with basic PR data."""
    # Setup mocks
    mock_github = Mock()
    mock_repo = Mock()
    mock_commit = Mock()

    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_commit.return_value = mock_commit

    # Mock reviews
    mock_pr.get_reviews.return_value = [mock_review_approved]

    # Mock review comments
    mock_review_comments = Mock()
    mock_review_comments.totalCount = 2
    mock_pr.get_review_comments.return_value = mock_review_comments

    # Mock check runs
    mock_commit.get_check_runs.return_value = [mock_check_run_success]

    # Execute
    status = generate_status.fetch_pr_status(mock_github, "owner/repo", 123)

    # Verify
    assert status.number == 123
    assert status.title == "Test PR Title"
    assert status.author == "testuser"
    assert status.base_ref == "main"
    assert status.head_ref == "feature-branch"
    assert status.commit_count == 5
    assert status.file_count == 10
    assert status.review_stats["approved"] == 1
    assert status.open_thread_count == 2
    assert len(status.check_runs) == 1


def test_fetch_pr_status_with_multiple_reviews(
    mock_pr, mock_review_approved, mock_review_changes_requested, mock_review_commented
):
    """Test fetch_pr_status with multiple review types."""
    mock_github = Mock()
    mock_repo = Mock()
    mock_commit = Mock()

    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_commit.return_value = mock_commit

    # Multiple reviews
    mock_pr.get_reviews.return_value = [
        mock_review_approved,
        mock_review_changes_requested,
        mock_review_commented,
    ]

    mock_review_comments = Mock()
    mock_review_comments.totalCount = 5
    mock_pr.get_review_comments.return_value = mock_review_comments

    mock_commit.get_check_runs.return_value = []

    status = generate_status.fetch_pr_status(mock_github, "owner/repo", 123)

    assert status.review_stats["approved"] == 1
    assert status.review_stats["changes_requested"] == 1
    assert status.review_stats["commented"] == 1
    assert status.review_stats["total"] == 3


def test_fetch_pr_status_with_labels(mock_pr):
    """Test fetch_pr_status with PR labels."""
    mock_github = Mock()
    mock_repo = Mock()
    mock_commit = Mock()

    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_commit.return_value = mock_commit

    # Add labels with proper .name attribute
    label1 = Mock()
    label1.name = "bug"
    label2 = Mock()
    label2.name = "enhancement"
    mock_pr.labels = [label1, label2]

    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)
    mock_commit.get_check_runs.return_value = []

    status = generate_status.fetch_pr_status(mock_github, "owner/repo", 123)

    assert len(status.labels) == 2
    assert "bug" in status.labels
    assert "enhancement" in status.labels


def test_fetch_pr_status_draft_pr(mock_pr):
    """Test fetch_pr_status with draft PR."""
    mock_pr.draft = True

    mock_github = Mock()
    mock_repo = Mock()
    mock_commit = Mock()

    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_commit.return_value = mock_commit

    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)
    mock_commit.get_check_runs.return_value = []

    status = generate_status.fetch_pr_status(mock_github, "owner/repo", 123)

    assert status.is_draft is True


def test_fetch_pr_status_mergeable_none(mock_pr):
    """Test fetch_pr_status when mergeable status is unknown."""
    mock_pr.mergeable = None
    mock_pr.mergeable_state = None

    mock_github = Mock()
    mock_repo = Mock()
    mock_commit = Mock()

    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_commit.return_value = mock_commit

    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)
    mock_commit.get_check_runs.return_value = []

    status = generate_status.fetch_pr_status(mock_github, "owner/repo", 123)

    assert status.mergeable is None
    assert status.mergeable_state == "unknown"


def test_fetch_pr_status_with_multiple_check_runs(
    mock_pr, mock_check_run_success, mock_check_run_failure, mock_check_run_pending
):
    """Test fetch_pr_status with multiple check runs."""
    mock_github = Mock()
    mock_repo = Mock()
    mock_commit = Mock()

    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_commit.return_value = mock_commit

    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)
    mock_commit.get_check_runs.return_value = [
        mock_check_run_success,
        mock_check_run_failure,
        mock_check_run_pending,
    ]

    status = generate_status.fetch_pr_status(mock_github, "owner/repo", 123)

    assert len(status.check_runs) == 3
    assert status.check_runs[0].conclusion == "success"
    assert status.check_runs[1].conclusion == "failure"
    assert status.check_runs[2].conclusion is None


# --- Test format_checklist Function ---


def test_format_checklist_all_tasks_complete():
    """Test format_checklist when all tasks are complete."""
    status = generate_status.PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 1,
            "changes_requested": 0,
            "commented": 0,
            "total": 1,
        },
        open_thread_count=0,
        check_runs=[generate_status.CheckRunInfo("test", "completed", "success")],
    )

    checklist = generate_status.format_checklist(status)

    assert "- [x] Mark PR as ready for review" in checklist
    assert "- [x] Get approval from reviewer" in checklist
    assert "- [x] All CI checks passing" in checklist
    assert "- [x] No merge conflicts" in checklist
    assert "- [x] No pending change requests" in checklist


def test_format_checklist_draft_pr():
    """Test format_checklist with draft PR."""
    status = generate_status.PRStatus(
        number=1,
        title="Draft",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=True,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    checklist = generate_status.format_checklist(status)

    assert "- [ ] Mark PR as ready for review" in checklist


def test_format_checklist_no_approval():
    """Test format_checklist without approval."""
    status = generate_status.PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 1,
            "total": 1,
        },
        open_thread_count=0,
        check_runs=[],
    )

    checklist = generate_status.format_checklist(status)

    assert "- [ ] Get approval from reviewer" in checklist


def test_format_checklist_partial_checks():
    """Test format_checklist with some checks failing."""
    status = generate_status.PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[
            generate_status.CheckRunInfo("test1", "completed", "success"),
            generate_status.CheckRunInfo("test2", "completed", "failure"),
        ],
    )

    checklist = generate_status.format_checklist(status)

    assert "- [ ] All CI checks passing (1/2 passed)" in checklist


def test_format_checklist_no_checks():
    """Test format_checklist with no checks configured."""
    status = generate_status.PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    checklist = generate_status.format_checklist(status)

    assert "- [ ] CI checks pending/not configured" in checklist


def test_format_checklist_merge_conflicts():
    """Test format_checklist with merge conflicts."""
    status = generate_status.PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=False,
        mergeable_state="dirty",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    checklist = generate_status.format_checklist(status)

    assert "- [ ] Resolve merge conflicts" in checklist


def test_format_checklist_mergeable_unknown():
    """Test format_checklist when merge status is unknown."""
    status = generate_status.PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=None,
        mergeable_state="unknown",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    checklist = generate_status.format_checklist(status)

    assert "- [ ] Check for merge conflicts" in checklist


def test_format_checklist_with_change_requests():
    """Test format_checklist with pending change requests."""
    status = generate_status.PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 2,
            "commented": 0,
            "total": 2,
        },
        open_thread_count=0,
        check_runs=[],
    )

    checklist = generate_status.format_checklist(status)

    assert "- [ ] No pending change requests" in checklist


# --- Test format_checks_section Function ---


def test_format_checks_section_no_checks():
    """Test format_checks_section with no checks."""
    result = generate_status.format_checks_section([])

    assert "No checks configured or pending" in result


def test_format_checks_section_all_passed():
    """Test format_checks_section with all checks passing."""
    checks = [
        generate_status.CheckRunInfo("test1", "completed", "success"),
        generate_status.CheckRunInfo("test2", "completed", "success"),
    ]

    result = generate_status.format_checks_section(checks)

    assert "**Passed:** 2" in result
    assert "**Failed:** 0" in result
    assert "**Pending:** 0" in result
    assert "**Total:** 2" in result
    assert "Failed Checks:" not in result


def test_format_checks_section_with_failures():
    """Test format_checks_section with failed checks."""
    checks = [
        generate_status.CheckRunInfo("test1", "completed", "success"),
        generate_status.CheckRunInfo("lint", "completed", "failure"),
        generate_status.CheckRunInfo("build", "completed", "failure"),
    ]

    result = generate_status.format_checks_section(checks)

    assert "**Passed:** 1" in result
    assert "**Failed:** 2" in result
    assert "**Failed Checks:**" in result
    assert "❌ lint" in result
    assert "❌ build" in result


def test_format_checks_section_with_pending():
    """Test format_checks_section with pending checks."""
    checks = [
        generate_status.CheckRunInfo("test1", "completed", "success"),
        generate_status.CheckRunInfo("test2", "in_progress", None),
        generate_status.CheckRunInfo("test3", "queued", None),
    ]

    result = generate_status.format_checks_section(checks)

    assert "**Passed:** 1" in result
    assert "**Pending:** 2" in result


def test_format_checks_section_with_skipped():
    """Test format_checks_section with skipped checks."""
    checks = [
        generate_status.CheckRunInfo("test1", "completed", "success"),
        generate_status.CheckRunInfo("test2", "completed", "skipped"),
        generate_status.CheckRunInfo("test3", "completed", "cancelled"),
    ]

    result = generate_status.format_checks_section(checks)

    assert "**Passed:** 1" in result
    assert "**Failed:** 0" in result
    assert "**Pending:** 0" in result
    # Skipped = total - passed - failed - pending
    assert "**Skipped:** 2" in result


def test_format_checks_section_mixed_states():
    """Test format_checks_section with mixed check states."""
    checks = [
        generate_status.CheckRunInfo("unit-tests", "completed", "success"),
        generate_status.CheckRunInfo("integration-tests", "completed", "success"),
        generate_status.CheckRunInfo("lint", "completed", "failure"),
        generate_status.CheckRunInfo("build", "in_progress", None),
        generate_status.CheckRunInfo("deploy", "completed", "skipped"),
    ]

    result = generate_status.format_checks_section(checks)

    assert "**Passed:** 2" in result
    assert "**Failed:** 1" in result
    assert "**Pending:** 1" in result
    assert "**Skipped:** 1" in result
    assert "**Total:** 5" in result
    assert "❌ lint" in result


# --- Test generate_markdown Function ---


def test_generate_markdown_basic(sample_pr_status):
    """Test generate_markdown with basic PR status."""
    markdown = generate_status.generate_markdown(sample_pr_status)

    assert "📊 **PR Status Report**" in markdown
    assert "**Title:** Test PR (#123)" in markdown
    assert "**Author:** @testuser" in markdown
    assert "**Branch:** `main` ← `feature`" in markdown
    assert "**Size:** 10 files (5 commits)" in markdown
    assert "**Diff:** +100 / -50" in markdown
    assert "**Labels:** `bug`, `enhancement`" in markdown


def test_generate_markdown_draft_pr():
    """Test generate_markdown with draft PR."""
    status = generate_status.PRStatus(
        number=1,
        title="Draft PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=True,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "**Draft:** 📝 Yes" in markdown


def test_generate_markdown_no_draft():
    """Test generate_markdown with non-draft PR."""
    status = generate_status.PRStatus(
        number=1,
        title="Regular PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "**Draft:** ✅ No" in markdown


def test_generate_markdown_no_labels():
    """Test generate_markdown with no labels."""
    status = generate_status.PRStatus(
        number=1,
        title="PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "**Labels:** None" in markdown


def test_generate_markdown_review_section():
    """Test generate_markdown review section."""
    status = generate_status.PRStatus(
        number=1,
        title="PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 2,
            "changes_requested": 1,
            "commented": 3,
            "total": 6,
        },
        open_thread_count=5,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "**Review Status**" in markdown
    assert "**Approved:** 2" in markdown
    assert "**Changes Requested:** 1" in markdown
    assert "**Commented:** 3" in markdown
    assert "**Total Reviews:** 6" in markdown
    assert "**Comments/Threads:** 5" in markdown


def test_generate_markdown_mergeable_yes():
    """Test generate_markdown with mergeable PR."""
    status = generate_status.PRStatus(
        number=1,
        title="PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "**Mergeable:** ✅ Yes" in markdown


def test_generate_markdown_mergeable_no():
    """Test generate_markdown with non-mergeable PR."""
    status = generate_status.PRStatus(
        number=1,
        title="PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=False,
        mergeable_state="dirty",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "**Mergeable:** ❌ No" in markdown


def test_generate_markdown_mergeable_unknown():
    """Test generate_markdown with unknown merge status."""
    status = generate_status.PRStatus(
        number=1,
        title="PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=None,
        mergeable_state="unknown",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "**Mergeable:** ⏳ Checking..." in markdown


def test_generate_markdown_includes_timestamp():
    """Test generate_markdown includes timestamp."""
    status = generate_status.PRStatus(
        number=1,
        title="PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "Last updated:" in markdown
    assert "UTC" in markdown
    assert "Generated by PR Copilot" in markdown


def test_generate_markdown_includes_checklist():
    """Test generate_markdown includes task checklist."""
    status = generate_status.PRStatus(
        number=1,
        title="PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "**Task Checklist**" in markdown
    assert "Mark PR as ready for review" in markdown


# --- Test write_output Function ---


def test_write_output_to_stdout(capsys):
    """Test write_output writes to stdout."""
    content = "Test report content"

    with patch.dict(os.environ, {}, clear=True):
        with patch("tempfile.gettempdir", return_value="/tmp"):
            with patch("builtins.open", mock_open()) as mock_file:
                generate_status.write_output(content)

    captured = capsys.readouterr()
    assert content in captured.out


def test_write_output_to_temp_file():
    """Test write_output writes to temp file."""
    content = "Test report content"

    with patch.dict(os.environ, {}, clear=True):
        with patch("tempfile.gettempdir", return_value="/tmp"):
            m = mock_open()
            with patch("builtins.open", m):
                generate_status.write_output(content)

            # Verify file was written
            m.assert_called_once()
            handle = m()
            handle.write.assert_called_once_with(content)


def test_write_output_to_github_step_summary():
    """Test write_output writes to GITHUB_STEP_SUMMARY."""
    content = "Test report"
    summary_file = "/tmp/github_summary.md"

    with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": summary_file}):
        m = mock_open()
        with patch("builtins.open", m):
            generate_status.write_output(content)

        # Check that summary file was opened in append mode
        calls = m.call_args_list
        assert any(summary_file in str(call) for call in calls)


def test_write_output_handles_io_error_temp_file(capsys):
    """Test write_output handles IOError for temp file."""
    content = "Test content"

    with patch.dict(os.environ, {}, clear=True):
        with patch("tempfile.gettempdir", return_value="/tmp"):
            with patch("builtins.open", side_effect=IOError("Disk full")):
                generate_status.write_output(content)

    captured = capsys.readouterr()
    assert "Error writing to temp file" in captured.err


def test_write_output_handles_io_error_github_summary(capsys):
    """Test write_output handles IOError for GitHub summary."""
    content = "Test content"
    summary_file = "/tmp/summary.md"

    with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": summary_file}):
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            generate_status.write_output(content)

    captured = capsys.readouterr()
    assert "Warning: Could not write to GITHUB_STEP_SUMMARY" in captured.err


# --- Test main Function ---


def test_main_missing_env_vars(capsys):
    """Test main exits with error when env vars are missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            generate_status.main()

        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Missing environment variables" in captured.err


def test_main_invalid_pr_number(capsys):
    """Test main exits with error when PR_NUMBER is not an integer."""
    env = {
        "GITHUB_TOKEN": "token",
        "PR_NUMBER": "not-a-number",
        "REPO_OWNER": "owner",
        "REPO_NAME": "repo",
    }

    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            generate_status.main()

        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "PR_NUMBER must be an integer" in captured.err


def test_main_github_api_error(capsys):
    """Test main handles GitHub API errors."""
    env = {
        "GITHUB_TOKEN": "token",
        "PR_NUMBER": "123",
        "REPO_OWNER": "owner",
        "REPO_NAME": "repo",
    }

    with patch.dict(os.environ, env, clear=True):
        with patch("generate_status.Github") as mock_github_class:
            mock_github = Mock()
            mock_github_class.return_value = mock_github
            mock_github.get_repo.side_effect = GithubException(status=404, data={"message": "Not Found"}, headers={})

            with pytest.raises(SystemExit) as exc_info:
                generate_status.main()

            assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "GitHub API Error" in captured.err


def test_main_success_flow(mock_pr, mock_review_approved, mock_check_run_success, capsys):
    """Test main executes successfully."""
    env = {
        "GITHUB_TOKEN": "token",
        "PR_NUMBER": "123",
        "REPO_OWNER": "owner",
        "REPO_NAME": "repo",
    }

    with patch.dict(os.environ, env, clear=True):
        with patch("generate_status.Github") as mock_github_class:
            with patch("tempfile.gettempdir", return_value="/tmp"):
                with patch("builtins.open", mock_open()):
                    # Setup mocks
                    mock_github = Mock()
                    mock_repo = Mock()
                    mock_commit = Mock()

                    mock_github_class.return_value = mock_github
                    mock_github.get_repo.return_value = mock_repo
                    mock_repo.get_pull.return_value = mock_pr
                    mock_repo.get_commit.return_value = mock_commit

                    mock_pr.get_reviews.return_value = [mock_review_approved]
                    mock_pr.get_review_comments.return_value = Mock(totalCount=0)
                    mock_commit.get_check_runs.return_value = [mock_check_run_success]

                    with pytest.raises(SystemExit) as exc_info:
                        generate_status.main()

                    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "Fetching status for PR #123" in captured.err
    assert "📊 **PR Status Report**" in captured.out


def test_main_generic_exception(capsys):
    """Test main handles generic exceptions."""
    env = {
        "GITHUB_TOKEN": "token",
        "PR_NUMBER": "123",
        "REPO_OWNER": "owner",
        "REPO_NAME": "repo",
    }

    with patch.dict(os.environ, env, clear=True):
        with patch("generate_status.Github", side_effect=Exception("Unexpected error")):
            with pytest.raises(SystemExit) as exc_info:
                generate_status.main()

            assert exc_info.value.code == 1

    captured = capsys.readouterr()
    # Should print traceback
    assert len(captured.err) > 0


# --- Edge Cases and Boundary Tests ---


def test_format_checklist_edge_case_all_checks_passed_zero_total():
    """Test edge case where check logic might divide by zero."""
    status = generate_status.PRStatus(
        number=1,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    # Should not raise exception
    checklist = generate_status.format_checklist(status)
    assert "CI checks pending/not configured" in checklist


def test_generate_markdown_with_special_characters():
    """Test generate_markdown handles special characters in title."""
    status = generate_status.PRStatus(
        number=1,
        title='PR with "quotes" and <tags>',
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)
    assert 'PR with "quotes" and <tags>' in markdown


def test_format_checks_section_all_pending():
    """Test format_checks_section with all checks pending."""
    checks = [
        generate_status.CheckRunInfo("test1", "queued", None),
        generate_status.CheckRunInfo("test2", "in_progress", None),
    ]

    result = generate_status.format_checks_section(checks)

    assert "**Passed:** 0" in result
    assert "**Failed:** 0" in result
    assert "**Pending:** 2" in result
    assert "Failed Checks:" not in result


def test_fetch_pr_status_empty_reviews():
    """Test fetch_pr_status with no reviews."""
    mock_pr = Mock()
    mock_pr.number = 1
    mock_pr.title = "Test"
    mock_pr.user = Mock(login="user")
    mock_pr.base = Mock(ref="main")
    mock_pr.head = Mock(ref="feature", sha="abc")
    mock_pr.draft = False
    mock_pr.html_url = "https://example.com"
    mock_pr.commits = 1
    mock_pr.changed_files = 1
    mock_pr.additions = 10
    mock_pr.deletions = 5
    mock_pr.labels = []
    mock_pr.mergeable = True
    mock_pr.mergeable_state = "clean"

    mock_github = Mock()
    mock_repo = Mock()
    mock_commit = Mock()

    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_commit.return_value = mock_commit

    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)
    mock_commit.get_check_runs.return_value = []

    status = generate_status.fetch_pr_status(mock_github, "owner/repo", 1)

    assert status.review_stats["approved"] == 0
    assert status.review_stats["changes_requested"] == 0
    assert status.review_stats["commented"] == 0
    assert status.review_stats["total"] == 0


def test_large_diff_numbers():
    """Test with very large diff numbers."""
    status = generate_status.PRStatus(
        number=1,
        title="Large PR",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="https://example.com",
        commit_count=100,
        file_count=1000,
        additions=999999,
        deletions=888888,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 0,
            "changes_requested": 0,
            "commented": 0,
            "total": 0,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    assert "**Size:** 1000 files (100 commits)" in markdown
    assert "**Diff:** +999999 / -888888" in markdown


# --- Tests for PR changes: PullRequest import and label extraction ---


def test_pull_request_type_accessible_in_module():
    """Verify that PullRequest type from github.PullRequest is importable.

    This is a regression test for the import added in this PR:
        from github.PullRequest import PullRequest
    The import must not break module loading.
    """
    # If the module imported successfully (it was imported at the top of this
    # test file), PullRequest should be accessible in the module's globals.
    assert hasattr(generate_status, "PullRequest"), (
        "generate_status module should expose PullRequest after importing it from github.PullRequest"
    )

    # Also verify we can independently import the same symbol
    from github.PullRequest import PullRequest as PR

    assert PR is not None


def test_fetch_pr_status_label_extraction_uses_name_attribute():
    """Regression test: label names are correctly extracted with short loop variable.

    The PR changed the label comprehension from:
        labels=[label.name for label in pr.labels]
    to:
        labels=[l.name for l in pr.labels]

    Both forms must produce identical output. This test verifies the .name
    attribute is accessed on each label object regardless of variable name.
    """
    mock_github = Mock()
    mock_repo = Mock()
    mock_commit = Mock()
    mock_pr = Mock()

    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_commit.return_value = mock_commit

    # Create label mocks with .name attributes
    label_a = Mock()
    label_a.name = "bug"
    label_b = Mock()
    label_b.name = "enhancement"
    label_c = Mock()
    label_c.name = "help wanted"

    mock_pr.number = 42
    mock_pr.title = "Fix issue"
    mock_pr.user = Mock(login="dev")
    mock_pr.base = Mock(ref="main")
    mock_pr.head = Mock(ref="fix-branch", sha="deadbeef")
    mock_pr.draft = False
    mock_pr.html_url = "https://github.com/owner/repo/pull/42"
    mock_pr.commits = 1
    mock_pr.changed_files = 2
    mock_pr.additions = 10
    mock_pr.deletions = 5
    mock_pr.labels = [label_a, label_b, label_c]
    mock_pr.mergeable = True
    mock_pr.mergeable_state = "clean"
    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)
    mock_commit.get_check_runs.return_value = []

    status = generate_status.fetch_pr_status(mock_github, "owner/repo", 42)

    # All three label names must be present and in the correct order
    assert status.labels == ["bug", "enhancement", "help wanted"]
    assert len(status.labels) == 3


def test_fetch_pr_status_empty_labels_list():
    """Regression test: empty label list produces empty list in PRStatus."""
    mock_github = Mock()
    mock_repo = Mock()
    mock_commit = Mock()
    mock_pr = Mock()

    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_commit.return_value = mock_commit

    mock_pr.number = 1
    mock_pr.title = "No labels PR"
    mock_pr.user = Mock(login="user")
    mock_pr.base = Mock(ref="main")
    mock_pr.head = Mock(ref="branch", sha="abc")
    mock_pr.draft = False
    mock_pr.html_url = "https://github.com/owner/repo/pull/1"
    mock_pr.commits = 1
    mock_pr.changed_files = 1
    mock_pr.additions = 5
    mock_pr.deletions = 2
    mock_pr.labels = []
    mock_pr.mergeable = True
    mock_pr.mergeable_state = "clean"
    mock_pr.get_reviews.return_value = []
    mock_pr.get_review_comments.return_value = Mock(totalCount=0)
    mock_commit.get_check_runs.return_value = []

    status = generate_status.fetch_pr_status(mock_github, "owner/repo", 1)

    assert status.labels == []


def test_generate_markdown_multiple_labels_formatted_with_backticks():
    """Test that multiple labels in the markdown report are wrapped in backticks.

    Regression for the label comprehension change: labels must appear as
    comma-separated backtick-wrapped strings in the generated report.
    """
    status = generate_status.PRStatus(
        number=7,
        title="Feature PR",
        author="contributor",
        base_ref="main",
        head_ref="feature-x",
        is_draft=False,
        url="https://github.com/owner/repo/pull/7",
        commit_count=3,
        file_count=5,
        additions=80,
        deletions=20,
        labels=["bug", "priority:high", "v2.0"],
        mergeable=True,
        mergeable_state="clean",
        review_stats={
            "approved": 1,
            "changes_requested": 0,
            "commented": 0,
            "total": 1,
        },
        open_thread_count=0,
        check_runs=[],
    )

    markdown = generate_status.generate_markdown(status)

    # Labels must appear as comma-separated backtick-wrapped strings
    assert "**Labels:** `bug`, `priority:high`, `v2.0`" in markdown
