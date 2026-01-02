"""Tests for PR Copilot status generation script."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_github_client():
    """Mock GitHub client with PR data."""
    mock_g = Mock()
    mock_repo = Mock()
    mock_pr = Mock()

    mock_pr.number = 123
    mock_pr.title = "Test PR Title"
    mock_pr.user.login = "testuser"
    mock_pr.base.ref = "main"
    mock_pr.head.ref = "feature-branch"
    mock_pr.head.sha = "abc123"
    mock_pr.draft = False
    mock_pr.html_url = "https://github.com/test/repo/pull/123"
    mock_pr.commits = 5
    mock_pr.changed_files = 10
    mock_pr.additions = 100
    mock_pr.deletions = 50
    mock_pr.labels = []
    mock_pr.mergeable = True
    mock_pr.mergeable_state = "clean"

    mock_repo.get_pull.return_value = mock_pr
    mock_g.get_repo.return_value = mock_repo

    return mock_g, mock_repo, mock_pr


@pytest.fixture
def mock_reviews():
    """Mock review data."""
    approved_review = Mock()
    approved_review.state = "APPROVED"

    changes_review = Mock()
    changes_review.state = "CHANGES_REQUESTED"

    comment_review = Mock()
    comment_review.state = "COMMENTED"

    return [approved_review, changes_review, comment_review]


@pytest.fixture
def mock_check_runs():
    """Mock check run data."""
    success_check = Mock()
    success_check.name = "CI Test"
    success_check.status = "completed"
    success_check.conclusion = "success"

    failure_check = Mock()
    failure_check.name = "Lint Check"
    failure_check.status = "completed"
    failure_check.conclusion = "failure"

    pending_check = Mock()
    pending_check.name = "Build"
    pending_check.status = "in_progress"
    pending_check.conclusion = None

    return [success_check, failure_check, pending_check]


@pytest.fixture
def env_vars():
    """Set up required environment variables."""
    env = {
        "GITHUB_TOKEN": "test_token",
        "PR_NUMBER": "123",
        "REPO_OWNER": "testowner",
        "REPO_NAME": "testrepo",
    }
    with patch.dict(os.environ, env, clear=False):
        yield env


def test_fetch_pr_status_returns_complete_data(mock_github_client, mock_reviews, mock_check_runs):
    """Test that fetch_pr_status returns all required PR data."""
    from .github.pr_copilot.scripts.generate_status import fetch_pr_status

    mock_g, mock_repo, mock_pr = mock_github_client

    mock_pr.get_reviews.return_value = mock_reviews
    mock_pr.get_review_comments.return_value.totalCount = 5

    mock_commit = Mock()
    mock_commit.get_check_runs.return_value = mock_check_runs
    mock_repo.get_commit.return_value = mock_commit

    status = fetch_pr_status(mock_g, "testowner/testrepo", 123)

    assert status.number == 123
    assert status.title == "Test PR Title"
    assert status.author == "testuser"
    assert status.commit_count == 5
    assert status.file_count == 10
    assert status.review_stats["approved"] == 1
    assert status.review_stats["changes_requested"] == 1
    assert status.review_stats["commented"] == 1
    assert len(status.check_runs) == 3


def test_format_checklist_all_complete():
    """Test checklist formatting when all tasks are complete."""
    from .github.pr_copilot.scripts.generate_status import CheckRunInfo, PRStatus, format_checklist

    success_check = CheckRunInfo(name="Test", status="completed", conclusion="success")

    status = PRStatus(
        number=123,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="http://test",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=True,
        mergeable_state="clean",
        review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
        open_thread_count=0,
        check_runs=[success_check],
    )

    checklist = format_checklist(status)

    assert "- [x] Mark PR as ready for review" in checklist
    assert "- [x] Get approval from reviewer" in checklist
    assert "- [x] All CI checks passing" in checklist
    assert "- [x] No merge conflicts" in checklist
    assert "- [x] No pending change requests" in checklist


def test_format_checklist_with_blockers():
    """Test checklist formatting when tasks are incomplete."""
    from .github.pr_copilot.scripts.generate_status import CheckRunInfo, PRStatus, format_checklist

    failed_check = CheckRunInfo(name="Test", status="completed", conclusion="failure")

    status = PRStatus(
        number=123,
        title="Test",
        author="user",
        base_ref="main",
        head_ref="feature",
        is_draft=True,
        url="http://test",
        commit_count=1,
        file_count=1,
        additions=10,
        deletions=5,
        labels=[],
        mergeable=False,
        mergeable_state="dirty",
        review_stats={"approved": 0, "changes_requested": 1, "commented": 0, "total": 1},
        open_thread_count=3,
        check_runs=[failed_check],
    )

    checklist = format_checklist(status)

    assert "- [ ] Mark PR as ready for review" in checklist
    assert "- [ ] Get approval from reviewer" in checklist
    assert "- [ ] All CI checks passing" in checklist
    assert "- [ ] Resolve merge conflicts" in checklist
    assert "- [ ] No pending change requests" in checklist


def test_format_checks_section_with_failures():
    """Test check status formatting with failed checks."""
    from .github.pr_copilot.scripts.generate_status import CheckRunInfo, format_checks_section

    checks = [
        CheckRunInfo(name="Test 1", status="completed", conclusion="success"),
        CheckRunInfo(name="Test 2", status="completed", conclusion="failure"),
        CheckRunInfo(name="Test 3", status="in_progress", conclusion=None),
    ]

    result = format_checks_section(checks)

    assert "✅ **Passed:** 1" in result
    assert "❌ **Failed:** 1" in result
    assert "⏳ **Pending:** 1" in result
    assert "**Failed Checks:**" in result
    assert "❌ Test 2" in result


def test_format_checks_section_no_checks():
    """Test check status formatting when no checks are configured."""
    from .github.pr_copilot.scripts.generate_status import format_checks_section

    result = format_checks_section([])

    assert "ℹ️ No checks configured or pending" in result


def test_generate_markdown_includes_all_sections():
    """Test that generated markdown includes all required sections."""
    from .github.pr_copilot.scripts.generate_status import CheckRunInfo, PRStatus, generate_markdown

    status = PRStatus(
        number=123,
        title="Test PR",
        author="testuser",
        base_ref="main",
        head_ref="feature",
        is_draft=False,
        url="http://test",
        commit_count=5,
        file_count=10,
        additions=100,
        deletions=50,
        labels=["bug", "enhancement"],
        mergeable=True,
        mergeable_state="clean",
        review_stats={"approved": 1, "changes_requested": 0, "commented": 1, "total": 2},
        open_thread_count=2,
        check_runs=[CheckRunInfo(name="CI", status="completed", conclusion="success")],
    )

    markdown = generate_markdown(status)

    assert "📊 **PR Status Report**" in markdown
    assert "**PR Information**" in markdown
    assert "**Review Status**" in markdown
    assert "**CI/Check Status**" in markdown
    assert "**Merge Status**" in markdown
    assert "**Task Checklist**" in markdown
    assert "testuser" in markdown
    assert "`bug`" in markdown
    assert "`enhancement`" in markdown
