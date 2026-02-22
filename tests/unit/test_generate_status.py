#!/usr/bin/env python3
"""
Unit tests for .github/pr-copilot/scripts/generate_status.py

Tests cover all functions, dataclasses, API interactions, and output formatting.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add the script to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_ROOT / ".github" / "pr-copilot" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from generate_status import (  # noqa: E402
    CheckRunInfo,
    PRStatus,
    fetch_pr_status,
    format_checklist,
    format_checks_section,
    generate_markdown,
    write_output,
)


class TestCheckRunInfo:
    """Test CheckRunInfo dataclass."""

    def test_check_run_info_creation(self):
        """CheckRunInfo can be created with valid fields."""
        check = CheckRunInfo(name="test-check", status="completed", conclusion="success")
        assert check.name == "test-check"
        assert check.status == "completed"
        assert check.conclusion == "success"

    def test_check_run_info_immutable(self):
        """CheckRunInfo is frozen and immutable."""
        check = CheckRunInfo(name="test", status="completed", conclusion="success")
        with pytest.raises(AttributeError):
            check.name = "modified"  # type: ignore

    def test_check_run_info_none_conclusion(self):
        """CheckRunInfo can have None conclusion for pending checks."""
        check = CheckRunInfo(name="pending-check", status="in_progress", conclusion=None)
        assert check.conclusion is None


class TestPRStatus:
    """Test PRStatus dataclass."""

    def test_pr_status_creation(self):
        """PRStatus can be created with all required fields."""
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
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=2,
            check_runs=[CheckRunInfo("test", "completed", "success")],
        )
        assert status.number == 123
        assert status.title == "Test PR"
        assert len(status.labels) == 2
        assert len(status.check_runs) == 1

    def test_pr_status_immutable(self):
        """PRStatus is frozen and immutable."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={},
            open_thread_count=0,
            check_runs=[],
        )
        with pytest.raises(AttributeError):
            status.number = 2  # type: ignore


class TestFetchPRStatus:
    """Test fetch_pr_status function."""

    def test_fetch_pr_status_success(self):
        """fetch_pr_status fetches and aggregates PR data correctly."""
        # Mock GitHub API objects
        mock_github = Mock()
        mock_repo = Mock()
        mock_pr = Mock()

        # Configure PR mock
        mock_pr.number = 42
        mock_pr.title = "Add new feature"
        mock_pr.user = Mock(login="contributor")
        mock_pr.base = Mock(ref="main")
        mock_pr.head = Mock(ref="feature-branch", sha="abc123")
        mock_pr.draft = False
        mock_pr.html_url = "https://github.com/owner/repo/pull/42"
        mock_pr.commits = 3
        mock_pr.changed_files = 5
        mock_pr.additions = 150
        mock_pr.deletions = 50
        # Create label mocks with proper name attribute
        label1 = Mock()
        label1.name = "enhancement"
        label2 = Mock()
        label2.name = "documentation"
        mock_pr.labels = [label1, label2]
        mock_pr.mergeable = True
        mock_pr.mergeable_state = "clean"

        # Mock reviews
        review1 = Mock(state="APPROVED")
        review2 = Mock(state="COMMENTED")
        mock_pr.get_reviews.return_value = [review1, review2]
        mock_pr.get_review_comments.return_value = Mock(totalCount=3)

        # Mock check runs
        check_run = Mock()
        check_run.name = "CI Test"
        check_run.status = "completed"
        check_run.conclusion = "success"
        mock_commit = Mock()
        mock_commit.get_check_runs.return_value = [check_run]

        # Setup mock chain
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_repo.get_commit.return_value = mock_commit

        # Execute
        result = fetch_pr_status(mock_github, "owner/repo", 42)

        # Verify
        assert result.number == 42
        assert result.title == "Add new feature"
        assert result.author == "contributor"
        assert result.base_ref == "main"
        assert result.head_ref == "feature-branch"
        assert result.is_draft is False
        assert result.commit_count == 3
        assert result.file_count == 5
        assert result.additions == 150
        assert result.deletions == 50
        assert result.labels == ["enhancement", "documentation"]
        assert result.mergeable is True
        assert result.mergeable_state == "clean"
        assert result.review_stats["approved"] == 1
        assert result.review_stats["commented"] == 1
        assert result.review_stats["total"] == 2
        assert result.open_thread_count == 3
        assert len(result.check_runs) == 1
        assert result.check_runs[0].name == "CI Test"

    def test_fetch_pr_status_with_changes_requested(self):
        """fetch_pr_status correctly counts changes_requested reviews."""
        mock_github = Mock()
        mock_repo = Mock()
        mock_pr = Mock()

        # Minimal PR setup
        mock_pr.number = 1
        mock_pr.title = "Test"
        mock_pr.user = Mock(login="user")
        mock_pr.base = Mock(ref="main")
        mock_pr.head = Mock(ref="feature", sha="abc")
        mock_pr.draft = False
        mock_pr.html_url = "https://test.com"
        mock_pr.commits = 1
        mock_pr.changed_files = 1
        mock_pr.additions = 10
        mock_pr.deletions = 5
        mock_pr.labels = []
        mock_pr.mergeable = True
        mock_pr.mergeable_state = "clean"

        # Reviews with changes requested
        review1 = Mock(state="CHANGES_REQUESTED")
        review2 = Mock(state="CHANGES_REQUESTED")
        review3 = Mock(state="APPROVED")
        mock_pr.get_reviews.return_value = [review1, review2, review3]
        mock_pr.get_review_comments.return_value = Mock(totalCount=0)

        mock_commit = Mock()
        mock_commit.get_check_runs.return_value = []

        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_repo.get_commit.return_value = mock_commit

        result = fetch_pr_status(mock_github, "owner/repo", 1)

        assert result.review_stats["changes_requested"] == 2
        assert result.review_stats["approved"] == 1
        assert result.review_stats["total"] == 3

    def test_fetch_pr_status_unknown_mergeable_state(self):
        """fetch_pr_status defaults to 'unknown' if mergeable_state is None."""
        mock_github = Mock()
        mock_repo = Mock()
        mock_pr = Mock()

        # Setup with None mergeable_state
        mock_pr.number = 1
        mock_pr.title = "Test"
        mock_pr.user = Mock(login="user")
        mock_pr.base = Mock(ref="main")
        mock_pr.head = Mock(ref="feature", sha="abc")
        mock_pr.draft = False
        mock_pr.html_url = "https://test.com"
        mock_pr.commits = 1
        mock_pr.changed_files = 1
        mock_pr.additions = 1
        mock_pr.deletions = 1
        mock_pr.labels = []
        mock_pr.mergeable = None
        mock_pr.mergeable_state = None
        mock_pr.get_reviews.return_value = []
        mock_pr.get_review_comments.return_value = Mock(totalCount=0)

        mock_commit = Mock()
        mock_commit.get_check_runs.return_value = []

        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_repo.get_commit.return_value = mock_commit

        result = fetch_pr_status(mock_github, "owner/repo", 1)

        assert result.mergeable_state == "unknown"


class TestFormatChecklist:
    """Test format_checklist function."""

    def test_format_checklist_all_ready(self):
        """format_checklist shows all tasks complete when PR is ready."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,  # Ready
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,  # No conflicts
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[CheckRunInfo("test", "completed", "success")],  # All pass
        )

        result = format_checklist(status)

        assert "- [x] Mark PR as ready for review" in result
        assert "- [x] Get approval from reviewer" in result
        assert "- [x] All CI checks passing" in result
        assert "- [x] No merge conflicts" in result
        assert "- [x] No pending change requests" in result

    def test_format_checklist_draft_pr(self):
        """format_checklist marks PR as not ready when draft."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=True,  # Draft
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        result = format_checklist(status)

        assert "- [ ] Mark PR as ready for review" in result

    def test_format_checklist_no_approval(self):
        """format_checklist shows approval needed when not approved."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 1, "total": 1},
            open_thread_count=0,
            check_runs=[],
        )

        result = format_checklist(status)

        assert "- [ ] Get approval from reviewer" in result

    def test_format_checklist_failing_checks(self):
        """format_checklist shows check progress when some fail."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[
                CheckRunInfo("test1", "completed", "success"),
                CheckRunInfo("test2", "completed", "failure"),
                CheckRunInfo("test3", "completed", "success"),
            ],
        )

        result = format_checklist(status)

        assert "- [ ] All CI checks passing (2/3 passed)" in result

    def test_format_checklist_no_checks(self):
        """format_checklist indicates when no checks are configured."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[],
        )

        result = format_checklist(status)

        assert "- [ ] CI checks pending/not configured" in result

    def test_format_checklist_merge_conflicts(self):
        """format_checklist shows conflicts when mergeable_state is dirty."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=False,
            mergeable_state="dirty",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[],
        )

        result = format_checklist(status)

        assert "- [ ] Resolve merge conflicts" in result

    def test_format_checklist_unknown_mergeable_state(self):
        """format_checklist shows 'Check for merge conflicts' when mergeable state is unknown."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
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

        result = format_checklist(status)

        assert "- [ ] Check for merge conflicts" in result

    def test_format_checklist_changes_requested(self):
        """format_checklist shows pending change requests."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 2, "commented": 1, "total": 3},
            open_thread_count=0,
            check_runs=[],
        )

        result = format_checklist(status)

        assert "- [ ] No pending change requests" in result


class TestFormatChecksSection:
    """Test format_checks_section function."""

    def test_format_checks_section_no_checks(self):
        """format_checks_section returns info message when no checks."""
        result = format_checks_section([])
        assert "No checks configured or pending" in result

    def test_format_checks_section_all_passed(self):
        """format_checks_section formats all passed checks correctly."""
        checks = [
            CheckRunInfo("test1", "completed", "success"),
            CheckRunInfo("test2", "completed", "success"),
            CheckRunInfo("test3", "completed", "success"),
        ]
        result = format_checks_section(checks)

        assert "✅ **Passed:** 3" in result
        assert "❌ **Failed:** 0" in result
        assert "⏳ **Pending:** 0" in result
        assert "📊 **Total:** 3" in result

    def test_format_checks_section_with_failures(self):
        """format_checks_section lists failed checks."""
        checks = [
            CheckRunInfo("passing-test", "completed", "success"),
            CheckRunInfo("failing-test-1", "completed", "failure"),
            CheckRunInfo("failing-test-2", "completed", "failure"),
        ]
        result = format_checks_section(checks)

        assert "✅ **Passed:** 1" in result
        assert "❌ **Failed:** 2" in result
        assert "**Failed Checks:**" in result
        assert "❌ failing-test-1" in result
        assert "❌ failing-test-2" in result

    def test_format_checks_section_with_pending(self):
        """format_checks_section counts pending checks."""
        checks = [
            CheckRunInfo("completed-test", "completed", "success"),
            CheckRunInfo("pending-test-1", "in_progress", None),
            CheckRunInfo("pending-test-2", "queued", None),
        ]
        result = format_checks_section(checks)

        assert "✅ **Passed:** 1" in result
        assert "⏳ **Pending:** 2" in result

    def test_format_checks_section_with_skipped(self):
        """format_checks_section counts skipped checks."""
        checks = [
            CheckRunInfo("success", "completed", "success"),
            CheckRunInfo("failure", "completed", "failure"),
            CheckRunInfo("skipped", "completed", "skipped"),
            CheckRunInfo("cancelled", "completed", "cancelled"),
        ]
        result = format_checks_section(checks)

        assert "✅ **Passed:** 1" in result
        assert "❌ **Failed:** 1" in result
        assert "⏭️ **Skipped:** 2" in result


class TestGenerateMarkdown:
    """Test generate_markdown function."""

    def test_generate_markdown_structure(self):
        """generate_markdown produces properly structured markdown report."""
        status = PRStatus(
            number=123,
            title="Add authentication feature",
            author="developer",
            base_ref="main",
            head_ref="auth-feature",
            is_draft=False,
            url="https://github.com/test/repo/pull/123",
            commit_count=5,
            file_count=10,
            additions=200,
            deletions=50,
            labels=["feature", "security"],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 2, "changes_requested": 0, "commented": 1, "total": 3},
            open_thread_count=4,
            check_runs=[CheckRunInfo("CI", "completed", "success")],
        )

        result = generate_markdown(status)

        # Check main sections
        assert "📊 **PR Status Report**" in result
        assert "**PR Information**" in result
        assert "**Review Status**" in result
        assert "**CI/Check Status**" in result
        assert "**Merge Status**" in result
        assert "**Task Checklist**" in result

        # Check specific content
        assert "Add authentication feature (#123)" in result
        assert "@developer" in result
        assert "`main` ← `auth-feature`" in result
        assert "10 files (5 commits)" in result
        assert "+200 / -50" in result
        assert "`feature`, `security`" in result
        assert "✅ **Approved:** 2" in result
        assert "**Comments/Threads:** 4" in result
        assert "Generated by PR Copilot" in result

    def test_generate_markdown_draft_status(self):
        """generate_markdown shows draft status correctly."""
        status = PRStatus(
            number=1,
            title="Draft PR",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=True,
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        result = generate_markdown(status)
        assert "📝 Yes" in result

    def test_generate_markdown_no_labels(self):
        """generate_markdown handles PR with no labels."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        result = generate_markdown(status)
        assert "**Labels:** None" in result

    def test_generate_markdown_mergeable_states(self):
        """generate_markdown displays different mergeable states correctly."""
        # Test mergeable=True
        status_clean = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
            commit_count=1,
            file_count=1,
            additions=1,
            deletions=1,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )
        result = generate_markdown(status_clean)
        assert "✅ Yes" in result

        # Test mergeable=False
        status_dirty = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
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
        result = generate_markdown(status_dirty)
        assert "❌ No" in result

        # Test mergeable=None
        status_checking = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://test.com",
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
        result = generate_markdown(status_checking)
        assert "⏳ Checking..." in result


class TestWriteOutput:
    """Test write_output function."""

    def test_write_output_to_stdout(self, capsys):
        """write_output prints content to stdout."""
        content = "Test report content"
        write_output(content)

        captured = capsys.readouterr()
        assert content in captured.out

    def test_write_output_to_github_summary(self, monkeypatch, tmp_path):
        """write_output writes to GITHUB_STEP_SUMMARY when set."""
        summary_file = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        content = "Test summary content"
        write_output(content)

        assert summary_file.exists()
        assert summary_file.read_text() == content

    def test_write_output_to_temp_file(self, monkeypatch):
        """write_output writes to standard temp file location."""
        # Unset GITHUB_STEP_SUMMARY to test temp file path
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

        content = "Test temp content"
        write_output(content)

        temp_file = Path(tempfile.gettempdir()) / "pr_status_report.md"
        assert temp_file.exists()
        assert content in temp_file.read_text()

    def test_write_output_handles_github_summary_error(self, monkeypatch, capsys, tmp_path):
        """write_output handles errors writing to GITHUB_STEP_SUMMARY gracefully."""
        bad_path = tmp_path / "nonexistent_dir" / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(bad_path))

        content = "Test content"
        write_output(content)  # Should not raise

        captured = capsys.readouterr()

        warned = "Warning" in captured.err
        fell_back = content in captured.out

        assert warned or fell_back, "write_output should either warn on stderr or fall back to stdout on error"


class TestMainFunction:
    """Test main() entry point."""

    def test_main_missing_env_vars(self, monkeypatch, capsys):
        """main exits with error when required env vars are missing."""
        # Clear all required env vars
        for var in ["GITHUB_TOKEN", "PR_NUMBER", "REPO_OWNER", "REPO_NAME"]:
            monkeypatch.delenv(var, raising=False)

        # Import and run main
        from generate_status import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Missing environment variables" in captured.err

    def test_main_invalid_pr_number(self, monkeypatch, capsys):
        """main exits with error when PR_NUMBER is not an integer."""
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monkeypatch.setenv("PR_NUMBER", "not-a-number")
        monkeypatch.setenv("REPO_OWNER", "owner")
        monkeypatch.setenv("REPO_NAME", "repo")

        from generate_status import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "PR_NUMBER must be an integer" in captured.err

    @patch("generate_status.Github")
    def test_main_success(self, mock_github_class, monkeypatch, capsys):
        """main successfully generates report when all inputs are valid."""
        # Setup environment
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monkeypatch.setenv("PR_NUMBER", "42")
        monkeypatch.setenv("REPO_OWNER", "test-owner")
        monkeypatch.setenv("REPO_NAME", "test-repo")

        # Mock GitHub API
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()

        mock_pr.number = 42
        mock_pr.title = "Test PR"
        mock_pr.user = MagicMock(login="testuser")
        mock_pr.base = MagicMock(ref="main")
        mock_pr.head = MagicMock(ref="feature", sha="abc123")
        mock_pr.draft = False
        mock_pr.html_url = "https://github.com/test-owner/test-repo/pull/42"
        mock_pr.commits = 1
        mock_pr.changed_files = 1
        mock_pr.additions = 10
        mock_pr.deletions = 5
        mock_pr.labels = []
        mock_pr.mergeable = True
        mock_pr.mergeable_state = "clean"
        mock_pr.get_reviews.return_value = []
        mock_pr.get_review_comments.return_value = MagicMock(totalCount=0)

        mock_commit = MagicMock()
        mock_commit.get_check_runs.return_value = []

        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_repo.get_commit.return_value = mock_commit
        mock_github_class.return_value = mock_github

        from generate_status import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Test PR" in captured.out


# Integration-style tests
class TestEndToEndScenarios:
    """Test realistic end-to-end scenarios."""

    def test_complete_pr_workflow(self):
        """Test complete PR status flow from fetch to markdown generation."""
        # Create mock GitHub objects
        mock_github = Mock()
        mock_repo = Mock()
        mock_pr = Mock()

        # Setup complete PR scenario
        mock_pr.number = 456
        mock_pr.title = "Refactor database layer"
        mock_pr.user = Mock(login="dbexpert")
        mock_pr.base = Mock(ref="main")
        mock_pr.head = Mock(ref="refactor-db", sha="def456")
        mock_pr.draft = False
        mock_pr.html_url = "https://github.com/company/project/pull/456"
        mock_pr.commits = 12
        mock_pr.changed_files = 25
        mock_pr.additions = 500
        mock_pr.deletions = 300
        # Create label mocks with proper name attribute
        label1 = Mock()
        label1.name = "refactoring"
        label2 = Mock()
        label2.name = "database"
        mock_pr.labels = [label1, label2]
        mock_pr.mergeable = True
        mock_pr.mergeable_state = "clean"

        # Multiple reviews
        mock_pr.get_reviews.return_value = [
            Mock(state="APPROVED"),
            Mock(state="APPROVED"),
            Mock(state="COMMENTED"),
        ]
        mock_pr.get_review_comments.return_value = Mock(totalCount=8)

        # Multiple check runs
        check1 = Mock()
        check1.name = "Unit Tests"
        check1.status = "completed"
        check1.conclusion = "success"
        check2 = Mock()
        check2.name = "Integration Tests"
        check2.status = "completed"
        check2.conclusion = "success"
        check3 = Mock()
        check3.name = "Linting"
        check3.status = "completed"
        check3.conclusion = "success"
        check4 = Mock()
        check4.name = "Security Scan"
        check4.status = "completed"
        check4.conclusion = "success"
        mock_commit = Mock()
        mock_commit.get_check_runs.return_value = [check1, check2, check3, check4]

        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_repo.get_commit.return_value = mock_commit

        # Fetch status
        status = fetch_pr_status(mock_github, "company/project", 456)

        # Generate markdown
        markdown = generate_markdown(status)

        # Verify complete report
        assert "Refactor database layer" in markdown
        assert "dbexpert" in markdown
        assert "25 files" in markdown
        assert "12 commits" in markdown
        assert "+500 / -300" in markdown
        assert "`refactoring`, `database`" in markdown
        assert "✅ **Approved:** 2" in markdown
        assert "**Comments/Threads:** 8" in markdown
        assert "Unit Tests" in markdown or "✅ **Passed:** 4" in markdown
        assert "[x] All CI checks passing" in markdown
        assert "[x] Get approval from reviewer" in markdown
