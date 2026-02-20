"""Comprehensive tests for .github/pr-copilot/scripts/generate_status.py"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add the scripts directory to path for imports
import sys
from pathlib import Path

scripts_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts"
sys.path.insert(0, str(scripts_path))

from generate_status import (
    CheckRunInfo,
    PRStatus,
    fetch_pr_status,
    format_checklist,
    format_checks_section,
    generate_markdown,
    main,
    write_output,
)


class TestCheckRunInfo:
    """Test CheckRunInfo dataclass."""

    def test_check_run_info_creation(self):
        """Test creating CheckRunInfo instances."""
        check = CheckRunInfo(name="Test", status="completed", conclusion="success")
        assert check.name == "Test"
        assert check.status == "completed"
        assert check.conclusion == "success"

    def test_check_run_info_frozen(self):
        """Test that CheckRunInfo is frozen."""
        check = CheckRunInfo(name="Test", status="completed", conclusion="success")
        with pytest.raises(Exception):  # dataclass frozen error
            check.name = "Modified"


class TestPRStatus:
    """Test PRStatus dataclass."""

    def test_pr_status_creation(self):
        """Test creating PRStatus with all fields."""
        status = PRStatus(
            number=123,
            title="Test PR",
            author="testuser",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://github.com/test/repo/pull/123",
            commit_count=5,
            file_count=10,
            additions=100,
            deletions=50,
            labels=["bug", "enhancement"],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 2, "total": 3},
            open_thread_count=3,
            check_runs=[CheckRunInfo("ci", "completed", "success")],
        )
        assert status.number == 123
        assert status.title == "Test PR"
        assert len(status.labels) == 2
        assert status.review_stats["approved"] == 1


class TestFetchPRStatus:
    """Test fetch_pr_status function."""

    @patch("generate_status.Github")
    def test_fetch_pr_status_success(self, mock_github_class):
        """Test successfully fetching PR status."""
        # Setup mocks
        mock_github = mock_github_class.return_value
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_commit = MagicMock()

        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_repo.get_commit.return_value = mock_commit

        # Configure PR mock
        mock_pr.number = 123
        mock_pr.title = "Test PR"
        mock_pr.user.login = "testuser"
        mock_pr.base.ref = "main"
        mock_pr.head.ref = "feature"
        mock_pr.head.sha = "abc123"
        mock_pr.draft = False
        mock_pr.html_url = "https://github.com/test/repo/pull/123"
        mock_pr.commits = 5
        mock_pr.changed_files = 10
        mock_pr.additions = 100
        mock_pr.deletions = 50
        mock_pr.labels = [MagicMock(name="bug")]
        mock_pr.mergeable = True
        mock_pr.mergeable_state = "clean"

        # Configure reviews
        mock_review1 = MagicMock(state="APPROVED")
        mock_review2 = MagicMock(state="COMMENTED")
        mock_pr.get_reviews.return_value = [mock_review1, mock_review2]

        # Configure review comments
        mock_pr.get_review_comments.return_value = MagicMock(totalCount=3)

        # Configure check runs
        mock_check = MagicMock(name="CI", status="completed", conclusion="success")
        mock_commit.get_check_runs.return_value = [mock_check]

        # Execute
        result = fetch_pr_status(mock_github, "owner/repo", 123)

        # Verify
        assert result.number == 123
        assert result.title == "Test PR"
        assert result.review_stats["approved"] == 1
        assert result.review_stats["commented"] == 1
        assert result.open_thread_count == 3
        assert len(result.check_runs) == 1


class TestFormatChecklist:
    """Test format_checklist function."""

    def test_format_checklist_all_complete(self):
        """Test checklist when all items are complete."""
        status = PRStatus(
            number=123,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://example.com",
            commit_count=5,
            file_count=10,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[CheckRunInfo("test", "completed", "success")],
        )

        result = format_checklist(status)

        assert "- [x] Mark PR as ready for review" in result
        assert "- [x] Get approval from reviewer" in result
        assert "- [x] All CI checks passing" in result
        assert "- [x] No merge conflicts" in result
        assert "- [x] No pending change requests" in result

    def test_format_checklist_all_incomplete(self):
        """Test checklist when all items are incomplete."""
        status = PRStatus(
            number=123,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=True,
            url="https://example.com",
            commit_count=5,
            file_count=10,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=None,
            mergeable_state="unknown",
            review_stats={"approved": 0, "changes_requested": 1, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[],
        )

        result = format_checklist(status)

        assert "- [ ] Mark PR as ready for review" in result
        assert "- [ ] Get approval from reviewer" in result
        assert "- [ ] CI checks pending/not configured" in result

    def test_format_checklist_partial_checks_passing(self):
        """Test checklist with partial CI checks passing."""
        status = PRStatus(
            number=123,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://example.com",
            commit_count=5,
            file_count=10,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[
                CheckRunInfo("test1", "completed", "success"),
                CheckRunInfo("test2", "completed", "failure"),
            ],
        )

        result = format_checklist(status)

        assert "- [ ] All CI checks passing (1/2 passed)" in result


class TestFormatChecksSection:
    """Test format_checks_section function."""

    def test_format_checks_no_checks(self):
        """Test formatting with no checks configured."""
        result = format_checks_section([])
        assert "No checks configured or pending" in result

    def test_format_checks_all_passed(self):
        """Test formatting with all checks passed."""
        checks = [
            CheckRunInfo("test1", "completed", "success"),
            CheckRunInfo("test2", "completed", "success"),
        ]
        result = format_checks_section(checks)

        assert "Passed:** 2" in result
        assert "Failed:** 0" in result

    def test_format_checks_with_failures(self):
        """Test formatting with some failed checks."""
        checks = [
            CheckRunInfo("test1", "completed", "success"),
            CheckRunInfo("test2", "completed", "failure"),
            CheckRunInfo("test3", "in_progress", None),
        ]
        result = format_checks_section(checks)

        assert "Passed:** 1" in result
        assert "Failed:** 1" in result
        assert "Pending:** 1" in result
        assert "Failed Checks:" in result
        assert "test2" in result


class TestGenerateMarkdown:
    """Test generate_markdown function."""

    @patch("generate_status.datetime")
    def test_generate_markdown_complete(self, mock_datetime):
        """Test generating complete markdown report."""
        mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        status = PRStatus(
            number=123,
            title="Test PR",
            author="testuser",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://github.com/test/repo/pull/123",
            commit_count=5,
            file_count=10,
            additions=100,
            deletions=50,
            labels=["bug", "enhancement"],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 2, "total": 3},
            open_thread_count=5,
            check_runs=[CheckRunInfo("ci", "completed", "success")],
        )

        result = generate_markdown(status)

        # Verify key sections present
        assert "PR Status Report" in result
        assert "Test PR (#123)" in result
        assert "@testuser" in result
        assert "`main` ← `feature`" in result
        assert "10 files (5 commits)" in result
        assert "+100 / -50" in result
        assert "`bug`" in result
        assert "Approved:** 1" in result
        assert "Comments/Threads:** 5" in result
        assert "2024-01-01 12:00:00 UTC" in result


class TestWriteOutput:
    """Test write_output function."""

    @patch("builtins.open", create=True)
    @patch("generate_status.os.environ.get")
    @patch("builtins.print")
    def test_write_output_with_github_summary(self, mock_print, mock_env_get, mock_open):
        """Test writing output with GitHub summary."""
        mock_env_get.return_value = "/tmp/github_summary"
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        write_output("Test content")

        # Verify file write
        assert mock_file.write.called
        mock_file.write.assert_called_with("Test content")

        # Verify stdout
        mock_print.assert_called()

    @patch("builtins.open", create=True)
    @patch("generate_status.os.environ.get")
    @patch("builtins.print")
    def test_write_output_without_github_summary(self, mock_print, mock_env_get, mock_open):
        """Test writing output without GitHub summary."""
        mock_env_get.return_value = None
        write_output("Test content")

        # Should still print to stdout
        mock_print.assert_called()


class TestMain:
    """Test main function."""

    @patch("generate_status.Github")
    @patch("generate_status.os.environ.get")
    @patch("generate_status.write_output")
    @patch("generate_status.sys.exit")
    def test_main_success(self, mock_exit, mock_write, mock_env, mock_github_class):
        """Test successful main execution."""
        # Setup environment
        env_values = {
            "GITHUB_TOKEN": "token123",
            "PR_NUMBER": "123",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repo",
        }
        mock_env.side_effect = lambda key: env_values.get(key)

        # Setup mocks (simplified)
        mock_github = mock_github_class.return_value
        mock_repo = MagicMock()
        mock_pr = MagicMock()

        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        # Configure minimal PR
        mock_pr.number = 123
        mock_pr.title = "Test"
        mock_pr.user.login = "user"
        mock_pr.base.ref = "main"
        mock_pr.head.ref = "feature"
        mock_pr.head.sha = "abc"
        mock_pr.draft = False
        mock_pr.html_url = "url"
        mock_pr.commits = 1
        mock_pr.changed_files = 1
        mock_pr.additions = 1
        mock_pr.deletions = 1
        mock_pr.labels = []
        mock_pr.mergeable = True
        mock_pr.mergeable_state = "clean"
        mock_pr.get_reviews.return_value = []
        mock_pr.get_review_comments.return_value = MagicMock(totalCount=0)

        mock_commit = MagicMock()
        mock_commit.get_check_runs.return_value = []
        mock_repo.get_commit.return_value = mock_commit

        main()

        mock_exit.assert_called_with(0)
        assert mock_write.called

    @patch("generate_status.os.environ.get")
    @patch("generate_status.sys.exit")
    @patch("builtins.print")
    def test_main_missing_env_vars(self, mock_print, mock_exit, mock_env):
        """Test main with missing environment variables."""
        mock_env.return_value = None

        main()

        mock_exit.assert_called_with(1)

    @patch("generate_status.os.environ.get")
    @patch("generate_status.sys.exit")
    @patch("builtins.print")
    def test_main_invalid_pr_number(self, mock_print, mock_exit, mock_env):
        """Test main with invalid PR number."""
        env_values = {
            "GITHUB_TOKEN": "token",
            "PR_NUMBER": "not_a_number",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repo",
        }
        mock_env.side_effect = lambda key: env_values.get(key)

        main()

        mock_exit.assert_called_with(1)


# Additional edge case tests
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_format_checklist_dirty_merge_state(self):
        """Test checklist with dirty merge state."""
        status = PRStatus(
            number=123,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=False,
            mergeable_state="dirty",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        result = format_checklist(status)
        assert "- [ ] Resolve merge conflicts" in result

    def test_generate_markdown_draft_pr(self):
        """Test markdown generation for draft PR."""
        status = PRStatus(
            number=123,
            title="Draft PR",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=True,
            url="url",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=None,
            mergeable_state="unknown",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        result = generate_markdown(status)
        assert "Draft:** 📝 Yes" in result
        assert "Mergeable:** ⏳ Checking..." in result

    def test_format_checks_mixed_states(self):
        """Test formatting checks with various states."""
        checks = [
            CheckRunInfo("success", "completed", "success"),
            CheckRunInfo("failure", "completed", "failure"),
            CheckRunInfo("pending", "in_progress", None),
            CheckRunInfo("skipped", "completed", "skipped"),
        ]

        result = format_checks_section(checks)
        assert "Total:** 4" in result
        assert "Passed:** 1" in result
        assert "Failed:** 1" in result
        assert "Pending:** 1" in result
        assert "Skipped:** 1" in result