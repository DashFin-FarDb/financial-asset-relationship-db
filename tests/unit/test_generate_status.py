"""
Comprehensive unit tests for .github/pr-copilot/scripts/generate_status.py

Tests cover:
- PR status fetching and data consolidation
- Checklist generation logic
- Check runs formatting
- Markdown report generation
- Output writing to files and GitHub summary
- Error handling and edge cases
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "pr-copilot" / "scripts"))

try:
    import generate_status
    from generate_status import (
        CheckRunInfo,
        PRStatus,
        fetch_pr_status,
        format_checklist,
        format_checks_section,
        generate_markdown,
        write_output,
    )
except ImportError:
    pytest.skip("Cannot import generate_status module", allow_module_level=True)


@dataclass
class MockUser:
    """Mock GitHub user object."""

    login: str


@dataclass
class MockLabel:
    """Mock GitHub label object."""

    name: str


@dataclass
class MockRef:
    """Mock GitHub ref object."""

    ref: str
    sha: str = "abc123"


class MockReview:
    """Mock GitHub review object."""

    def __init__(self, state: str):
        self.state = state


class MockCheckRun:
    """Mock GitHub check run object."""

    def __init__(self, name: str, status: str, conclusion: str | None = None):
        self.name = name
        self.status = status
        self.conclusion = conclusion


class MockCommit:
    """Mock GitHub commit object."""

    def __init__(self, check_runs: list[MockCheckRun] | None = None):
        self._check_runs = check_runs or []

    def get_check_runs(self):
        """Return mock check runs."""
        return iter(self._check_runs)


class MockPullRequest:
    """Mock GitHub pull request object."""

    def __init__(
        self,
        number: int = 1,
        title: str = "Test PR",
        author: str = "testuser",
        base_ref: str = "main",
        head_ref: str = "feature",
        head_sha: str = "abc123",
        is_draft: bool = False,
        commits: int = 5,
        changed_files: int = 3,
        additions: int = 100,
        deletions: int = 50,
        labels: list[str] | None = None,
        mergeable: bool | None = True,
        mergeable_state: str = "clean",
        reviews: list[MockReview] | None = None,
        review_comment_count: int = 0,
    ):
        self.number = number
        self.title = title
        self.user = MockUser(login=author)
        self.base = MockRef(ref=base_ref)
        self.head = MockRef(ref=head_ref, sha=head_sha)
        self.draft = is_draft
        self.html_url = f"https://github.com/owner/repo/pull/{number}"
        self.commits = commits
        self.changed_files = changed_files
        self.additions = additions
        self.deletions = deletions
        self.labels = [MockLabel(name=label) for label in (labels or [])]
        self.mergeable = mergeable
        self.mergeable_state = mergeable_state
        self._reviews = reviews or []
        self._review_comment_count = review_comment_count

    def get_reviews(self):
        """Return mock reviews."""
        return self._reviews

    def get_review_comments(self):
        """Return mock review comments count."""
        mock_comments = Mock()
        mock_comments.totalCount = self._review_comment_count
        return mock_comments


class MockRepo:
    """Mock GitHub repository object."""

    def __init__(self, pr: MockPullRequest, check_runs: list[MockCheckRun] | None = None):
        self._pr = pr
        self._check_runs = check_runs or []

    def get_pull(self, number: int) -> MockPullRequest:
        """Return mock pull request."""
        return self._pr

    def get_commit(self, sha: str) -> MockCommit:
        """Return mock commit with check runs."""
        return MockCommit(check_runs=self._check_runs)


class MockGithub:
    """Mock GitHub client."""

    def __init__(self, repo: MockRepo):
        self._repo = repo

    def get_repo(self, name: str) -> MockRepo:
        """Return mock repository."""
        return self._repo


# --- Tests for CheckRunInfo ---


class TestCheckRunInfo:
    """Tests for CheckRunInfo dataclass."""

    def test_check_run_info_creation(self):
        """CheckRunInfo should be created with correct fields."""
        check = CheckRunInfo(name="test-check", status="completed", conclusion="success")
        assert check.name == "test-check"
        assert check.status == "completed"
        assert check.conclusion == "success"

    def test_check_run_info_immutable(self):
        """CheckRunInfo should be frozen (immutable)."""
        check = CheckRunInfo(name="test", status="completed", conclusion="success")
        with pytest.raises(AttributeError):
            check.name = "new-name"


# --- Tests for PRStatus ---


class TestPRStatus:
    """Tests for PRStatus dataclass."""

    def test_pr_status_creation(self):
        """PRStatus should be created with all required fields."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://github.com/owner/repo/pull/1",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=["bug", "enhancement"],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=2,
            check_runs=[CheckRunInfo("test", "completed", "success")],
        )

        assert status.number == 1
        assert status.title == "Test"
        assert len(status.labels) == 2
        assert status.review_stats["approved"] == 1


# --- Tests for fetch_pr_status ---


class TestFetchPRStatus:
    """Tests for fetch_pr_status function."""

    def test_fetch_pr_status_basic(self):
        """fetch_pr_status should return PRStatus with correct data."""
        pr = MockPullRequest(number=1, title="Test PR")
        repo = MockRepo(pr=pr)
        github = MockGithub(repo=repo)

        status = fetch_pr_status(github, "owner/repo", 1)

        assert status.number == 1
        assert status.title == "Test PR"
        assert status.author == "testuser"
        assert status.base_ref == "main"
        assert status.head_ref == "feature"

    def test_fetch_pr_status_with_reviews(self):
        """fetch_pr_status should correctly count review states."""
        reviews = [
            MockReview("APPROVED"),
            MockReview("APPROVED"),
            MockReview("CHANGES_REQUESTED"),
            MockReview("COMMENTED"),
        ]
        pr = MockPullRequest(reviews=reviews)
        repo = MockRepo(pr=pr)
        github = MockGithub(repo=repo)

        status = fetch_pr_status(github, "owner/repo", 1)

        assert status.review_stats["approved"] == 2
        assert status.review_stats["changes_requested"] == 1
        assert status.review_stats["commented"] == 1
        assert status.review_stats["total"] == 4

    def test_fetch_pr_status_with_check_runs(self):
        """fetch_pr_status should collect check runs from commit."""
        check_runs = [
            MockCheckRun("test1", "completed", "success"),
            MockCheckRun("test2", "completed", "failure"),
            MockCheckRun("test3", "in_progress", None),
        ]
        pr = MockPullRequest()
        repo = MockRepo(pr=pr, check_runs=check_runs)
        github = MockGithub(repo=repo)

        status = fetch_pr_status(github, "owner/repo", 1)

        assert len(status.check_runs) == 3
        assert status.check_runs[0].name == "test1"
        assert status.check_runs[0].conclusion == "success"
        assert status.check_runs[1].conclusion == "failure"
        assert status.check_runs[2].status == "in_progress"

    def test_fetch_pr_status_with_labels(self):
        """fetch_pr_status should extract label names."""
        pr = MockPullRequest(labels=["bug", "enhancement", "priority-high"])
        repo = MockRepo(pr=pr)
        github = MockGithub(repo=repo)

        status = fetch_pr_status(github, "owner/repo", 1)

        assert len(status.labels) == 3
        assert "bug" in status.labels
        assert "enhancement" in status.labels
        assert "priority-high" in status.labels

    def test_fetch_pr_status_draft_pr(self):
        """fetch_pr_status should correctly identify draft PRs."""
        pr = MockPullRequest(is_draft=True)
        repo = MockRepo(pr=pr)
        github = MockGithub(repo=repo)

        status = fetch_pr_status(github, "owner/repo", 1)

        assert status.is_draft is True

    def test_fetch_pr_status_with_review_comments(self):
        """fetch_pr_status should count review comments."""
        pr = MockPullRequest(review_comment_count=15)
        repo = MockRepo(pr=pr)
        github = MockGithub(repo=repo)

        status = fetch_pr_status(github, "owner/repo", 1)

        assert status.open_thread_count == 15


# --- Tests for format_checklist ---


class TestFormatChecklist:
    """Tests for format_checklist function."""

    def test_format_checklist_all_complete(self):
        """Checklist should show all items checked when conditions are met."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[CheckRunInfo("test", "completed", "success")],
        )

        checklist = format_checklist(status)

        assert "- [x] Mark PR as ready for review" in checklist
        assert "- [x] Get approval from reviewer" in checklist
        assert "- [x] All CI checks passing" in checklist
        assert "- [x] No merge conflicts" in checklist
        assert "- [x] No pending change requests" in checklist

    def test_format_checklist_draft_pr(self):
        """Checklist should show PR not ready when draft."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=True,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        checklist = format_checklist(status)

        assert "- [ ] Mark PR as ready for review" in checklist

    def test_format_checklist_no_approval(self):
        """Checklist should show approval needed when no approvals."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 1, "total": 1},
            open_thread_count=0,
            check_runs=[],
        )

        checklist = format_checklist(status)

        assert "- [ ] Get approval from reviewer" in checklist

    def test_format_checklist_ci_checks_partial(self):
        """Checklist should show partial CI status when some checks fail."""
        check_runs = [
            CheckRunInfo("test1", "completed", "success"),
            CheckRunInfo("test2", "completed", "failure"),
            CheckRunInfo("test3", "completed", "success"),
        ]
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=check_runs,
        )

        checklist = format_checklist(status)

        assert "- [ ] All CI checks passing (2/3 passed)" in checklist

    def test_format_checklist_no_checks(self):
        """Checklist should handle no CI checks configured."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[],
        )

        checklist = format_checklist(status)

        assert "- [ ] CI checks pending/not configured" in checklist

    def test_format_checklist_merge_conflicts(self):
        """Checklist should show merge conflicts when state is dirty."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=False,
            mergeable_state="dirty",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[],
        )

        checklist = format_checklist(status)

        assert "- [ ] Resolve merge conflicts" in checklist

    def test_format_checklist_changes_requested(self):
        """Checklist should show changes requested when reviews request changes."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 2, "commented": 0, "total": 3},
            open_thread_count=0,
            check_runs=[],
        )

        checklist = format_checklist(status)

        assert "- [ ] No pending change requests" in checklist


# --- Tests for format_checks_section ---


class TestFormatChecksSection:
    """Tests for format_checks_section function."""

    def test_format_checks_section_no_checks(self):
        """Should return info message when no checks configured."""
        result = format_checks_section([])

        assert "No checks configured or pending" in result

    def test_format_checks_section_all_passed(self):
        """Should show correct counts when all checks pass."""
        checks = [
            CheckRunInfo("test1", "completed", "success"),
            CheckRunInfo("test2", "completed", "success"),
        ]

        result = format_checks_section(checks)

        assert "**Passed:** 2" in result
        assert "**Failed:** 0" in result
        assert "**Total:** 2" in result

    def test_format_checks_section_with_failures(self):
        """Should list failed checks with details."""
        checks = [
            CheckRunInfo("test1", "completed", "success"),
            CheckRunInfo("test2", "completed", "failure"),
            CheckRunInfo("test3", "completed", "failure"),
        ]

        result = format_checks_section(checks)

        assert "**Failed:** 2" in result
        assert "**Failed Checks:**" in result
        assert "test2" in result
        assert "test3" in result

    def test_format_checks_section_with_pending(self):
        """Should count pending checks correctly."""
        checks = [
            CheckRunInfo("test1", "completed", "success"),
            CheckRunInfo("test2", "in_progress", None),
            CheckRunInfo("test3", "queued", None),
        ]

        result = format_checks_section(checks)

        assert "**Pending:** 2" in result

    def test_format_checks_section_with_skipped(self):
        """Should count skipped checks (not completed, not pending, not failed)."""
        checks = [
            CheckRunInfo("test1", "completed", "success"),
            CheckRunInfo("test2", "completed", "skipped"),
            CheckRunInfo("test3", "completed", "neutral"),
        ]

        result = format_checks_section(checks)

        # Skipped count = total - passed - failed - pending
        # 3 - 1 - 0 - 0 = 2
        assert "**Skipped:** 2" in result


# --- Tests for generate_markdown ---


class TestGenerateMarkdown:
    """Tests for generate_markdown function."""

    def test_generate_markdown_structure(self):
        """Generated markdown should have all expected sections."""
        status = PRStatus(
            number=1,
            title="Test PR",
            author="testuser",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="https://github.com/owner/repo/pull/1",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=["bug"],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=2,
            check_runs=[CheckRunInfo("test", "completed", "success")],
        )

        markdown = generate_markdown(status)

        assert "**PR Status Report**" in markdown
        assert "**PR Information**" in markdown
        assert "**Review Status**" in markdown
        assert "**CI/Check Status**" in markdown
        assert "**Merge Status**" in markdown
        assert "**Task Checklist**" in markdown
        assert "Test PR (#1)" in markdown
        assert "@testuser" in markdown
        assert "`bug`" in markdown

    def test_generate_markdown_no_labels(self):
        """Should show 'None' when no labels present."""
        status = PRStatus(
            number=1,
            title="Test PR",
            author="testuser",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        markdown = generate_markdown(status)

        assert "**Labels:** None" in markdown

    def test_generate_markdown_draft_status(self):
        """Should show draft status correctly."""
        status_draft = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=True,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        markdown = generate_markdown(status_draft)
        assert "**Draft:** 📝 Yes" in markdown

        status_ready = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        markdown = generate_markdown(status_ready)
        assert "**Draft:** ✅ No" in markdown

    def test_generate_markdown_mergeable_status(self):
        """Should show correct mergeable status icon."""
        # Mergeable
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )
        markdown = generate_markdown(status)
        assert "**Mergeable:** ✅ Yes" in markdown

        # Not mergeable
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=False,
            mergeable_state="dirty",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )
        markdown = generate_markdown(status)
        assert "**Mergeable:** ❌ No" in markdown

        # Checking
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=None,
            mergeable_state="unknown",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )
        markdown = generate_markdown(status)
        assert "**Mergeable:** ⏳ Checking..." in markdown

    def test_generate_markdown_includes_timestamp(self):
        """Should include UTC timestamp."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        markdown = generate_markdown(status)

        assert "Last updated:" in markdown
        assert "UTC" in markdown
        assert "Generated by PR Copilot" in markdown


# --- Tests for write_output ---


class TestWriteOutput:
    """Tests for write_output function."""

    def test_write_output_to_github_summary(self, monkeypatch, tmp_path):
        """Should write to GITHUB_STEP_SUMMARY when env var set."""
        summary_file = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        content = "# Test Report\nContent here"
        write_output(content)

        assert summary_file.exists()
        assert summary_file.read_text(encoding="utf-8") == content

    def test_write_output_to_temp_file(self, monkeypatch, capsys):
        """Should write to temp file with standard name."""
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

        content = "# Test Report"
        write_output(content)

        # Check temp file was created
        temp_path = Path(tempfile.gettempdir()) / "pr_status_report.md"
        assert temp_path.exists()
        assert temp_path.read_text(encoding="utf-8") == content

        # Check stderr message
        captured = capsys.readouterr()
        assert "Report written to:" in captured.err

    def test_write_output_to_stdout(self, capsys):
        """Should always write to stdout."""
        content = "# Test Report\nContent"
        write_output(content)

        captured = capsys.readouterr()
        assert content in captured.out

    def test_write_output_handles_io_error_gracefully(self, monkeypatch, capsys):
        """Should handle IO errors and print warning."""
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", "/nonexistent/path/summary.md")

        content = "# Test"
        write_output(content)  # Should not raise exception

        captured = capsys.readouterr()
        assert "Warning:" in captured.err or "Error:" in captured.err


# --- Tests for main function ---


class TestMain:
    """Tests for main function."""

    def test_main_missing_env_vars(self, monkeypatch, capsys):
        """Should exit with error when required env vars missing."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("PR_NUMBER", raising=False)
        monkeypatch.delenv("REPO_OWNER", raising=False)
        monkeypatch.delenv("REPO_NAME", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            generate_status.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Missing environment variables" in captured.err

    def test_main_invalid_pr_number(self, monkeypatch, capsys):
        """Should exit with error when PR_NUMBER is not an integer."""
        monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
        monkeypatch.setenv("PR_NUMBER", "not-a-number")
        monkeypatch.setenv("REPO_OWNER", "owner")
        monkeypatch.setenv("REPO_NAME", "repo")

        with pytest.raises(SystemExit) as exc_info:
            generate_status.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "must be an integer" in captured.err

    @patch("generate_status.Github")
    def test_main_github_api_error(self, mock_github_class, monkeypatch, capsys):
        """Should handle GitHub API errors gracefully."""
        from github import GithubException

        monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
        monkeypatch.setenv("PR_NUMBER", "1")
        monkeypatch.setenv("REPO_OWNER", "owner")
        monkeypatch.setenv("REPO_NAME", "repo")

        # Mock Github to raise exception
        mock_github = MagicMock()
        mock_github_class.return_value = mock_github
        mock_github.get_repo.side_effect = GithubException(
            404, {"message": "Not Found"}, None
        )

        with pytest.raises(SystemExit) as exc_info:
            generate_status.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "GitHub API Error" in captured.err

    @patch("generate_status.write_output")
    @patch("generate_status.fetch_pr_status")
    @patch("generate_status.Github")
    def test_main_success(
        self, mock_github_class, mock_fetch, mock_write, monkeypatch
    ):
        """Should successfully generate report when all conditions met."""
        monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
        monkeypatch.setenv("PR_NUMBER", "1")
        monkeypatch.setenv("REPO_OWNER", "owner")
        monkeypatch.setenv("REPO_NAME", "repo")

        # Mock successful execution
        mock_status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 1, "changes_requested": 0, "commented": 0, "total": 1},
            open_thread_count=0,
            check_runs=[],
        )
        mock_fetch.return_value = mock_status

        with pytest.raises(SystemExit) as exc_info:
            generate_status.main()

        assert exc_info.value.code == 0
        mock_write.assert_called_once()


# --- Edge Cases and Regression Tests ---


class TestEdgeCases:
    """Additional edge case and regression tests."""

    def test_empty_reviews_list(self):
        """Should handle PRs with no reviews."""
        pr = MockPullRequest(reviews=[])
        repo = MockRepo(pr=pr)
        github = MockGithub(repo=repo)

        status = fetch_pr_status(github, "owner/repo", 1)

        assert status.review_stats["total"] == 0
        assert status.review_stats["approved"] == 0

    def test_multiple_labels_formatting(self):
        """Should format multiple labels with backticks."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=5,
            file_count=3,
            additions=100,
            deletions=50,
            labels=["bug", "enhancement", "priority-high"],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        markdown = generate_markdown(status)

        assert "`bug`" in markdown
        assert "`enhancement`" in markdown
        assert "`priority-high`" in markdown

    def test_large_diff_stats(self):
        """Should handle large addition/deletion counts."""
        status = PRStatus(
            number=1,
            title="Test",
            author="user",
            base_ref="main",
            head_ref="feature",
            is_draft=False,
            url="url",
            commit_count=50,
            file_count=100,
            additions=5000,
            deletions=3000,
            labels=[],
            mergeable=True,
            mergeable_state="clean",
            review_stats={"approved": 0, "changes_requested": 0, "commented": 0, "total": 0},
            open_thread_count=0,
            check_runs=[],
        )

        markdown = generate_markdown(status)

        assert "+5000" in markdown
        assert "-3000" in markdown
        assert "100 files" in markdown

    def test_mixed_check_run_states(self):
        """Should correctly categorize mixed check run states."""
        checks = [
            CheckRunInfo("test1", "completed", "success"),
            CheckRunInfo("test2", "completed", "failure"),
            CheckRunInfo("test3", "in_progress", None),
            CheckRunInfo("test4", "queued", None),
            CheckRunInfo("test5", "completed", "skipped"),
            CheckRunInfo("test6", "completed", "cancelled"),
        ]

        result = format_checks_section(checks)

        assert "**Total:** 6" in result
        assert "**Passed:** 1" in result
        assert "**Failed:** 1" in result
        assert "**Pending:** 2" in result