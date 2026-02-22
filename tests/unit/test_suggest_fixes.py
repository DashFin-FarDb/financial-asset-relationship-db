"""
Comprehensive unit tests for .github/pr-copilot/scripts/suggest_fixes.py

Tests cover:
- Configuration loading from YAML
- Code suggestion extraction from comments
- Comment categorization and prioritization
- Actionable keyword detection
- Review comment parsing
- Fix proposal generation
- Output writing to files and GitHub summary
- Error handling and edge cases
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "pr-copilot" / "scripts"))

try:
    import suggest_fixes
    from suggest_fixes import (
        categorize_comment,
        extract_code_suggestions,
        generate_fix_proposals,
        is_actionable,
        load_config,
        parse_review_comments,
        write_output,
    )
except ImportError:
    pytest.skip("Cannot import suggest_fixes module", allow_module_level=True)


# --- Test Fixtures ---


class MockUser:
    """Mock GitHub user object."""

    def __init__(self, login: str = "testuser"):
        self.login = login


class MockComment:
    """Mock GitHub comment object."""

    def __init__(
        self,
        comment_id: int,
        body: str,
        author: str = "testuser",
        path: str | None = None,
        line: int | None = None,
        url: str | None = None,
        created_at: Any = None,
    ):
        self.id = comment_id
        self.body = body
        self.user = MockUser(login=author)
        self.path = path
        self.original_line = line
        self.html_url = url or f"https://github.com/owner/repo/pull/1#comment-{comment_id}"
        self.created_at = created_at or "2024-01-01T00:00:00Z"


class MockReview:
    """Mock GitHub review object."""

    def __init__(
        self,
        review_id: int,
        body: str,
        state: str = "COMMENTED",
        author: str = "reviewer",
        submitted_at: Any = None,
    ):
        self.id = review_id
        self.body = body
        self.state = state
        self.user = MockUser(login=author)
        self.html_url = f"https://github.com/owner/repo/pull/1#review-{review_id}"
        self.submitted_at = submitted_at or "2024-01-01T00:00:00Z"


class MockPullRequest:
    """Mock GitHub pull request object."""

    def __init__(
        self,
        comments: list[MockComment] | None = None,
        reviews: list[MockReview] | None = None,
    ):
        self._comments = comments or []
        self._reviews = reviews or []

    def get_review_comments(self):
        """Return mock review comments."""
        return iter(self._comments)

    def get_reviews(self):
        """Return mock reviews."""
        return iter(self._reviews)


# --- Tests for load_config ---


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_file_not_found(self, monkeypatch):
        """Should return default config when file not found."""
        # Change to a directory without config file
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.chdir(tmpdir)
            config = load_config()

            assert "review_handling" in config
            assert "actionable_keywords" in config["review_handling"]
            assert "please" in config["review_handling"]["actionable_keywords"]

    def test_load_config_valid_yaml(self, tmp_path, monkeypatch):
        """Should load config from valid YAML file."""
        config_dir = tmp_path / ".github"
        config_dir.mkdir()
        config_file = config_dir / "pr-copilot-config.yml"

        config_content = """
review_handling:
  actionable_keywords:
    - custom_keyword
    - another_keyword
"""
        config_file.write_text(config_content)
        monkeypatch.chdir(tmp_path)

        config = load_config()

        assert "review_handling" in config
        assert "custom_keyword" in config["review_handling"]["actionable_keywords"]
        assert "another_keyword" in config["review_handling"]["actionable_keywords"]

    def test_load_config_default_keywords(self):
        """Default config should contain expected keywords."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            config = load_config()

            keywords = config["review_handling"]["actionable_keywords"]
            assert "please" in keywords
            assert "should" in keywords
            assert "fix" in keywords
            assert "refactor" in keywords


# --- Tests for extract_code_suggestions ---


class TestExtractCodeSuggestions:
    """Tests for extract_code_suggestions function."""

    def test_extract_suggestion_block(self):
        """Should extract code from ```suggestion blocks."""
        comment = """
Please fix this:
```suggestion
def fixed_function():
    return True
```
"""
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "code_suggestion"
        assert "def fixed_function():" in suggestions[0]["content"]

    def test_extract_multiple_suggestion_blocks(self):
        """Should extract multiple suggestion blocks."""
        comment = """
First fix:
```suggestion
x = 1
```

Second fix:
```suggestion
y = 2
```
"""
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 2
        assert suggestions[0]["content"].strip() == "x = 1"
        assert suggestions[1]["content"].strip() == "y = 2"

    def test_extract_inline_suggestions(self):
        """Should extract inline code suggestions."""
        comment = "This should be `fixed_value` instead"
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "inline_suggestion"
        assert suggestions[0]["content"] == "fixed_value"

    def test_extract_inline_with_different_phrases(self):
        """Should extract inline suggestions with various trigger phrases."""
        test_cases = [
            ("should be `value1`", "value1"),
            ("change to `value2`", "value2"),
            ("replace with `value3`", "value3"),
            ("use `value4`", "value4"),
        ]

        for comment, expected in test_cases:
            suggestions = extract_code_suggestions(comment)
            assert len(suggestions) >= 1
            assert any(s["content"] == expected for s in suggestions)

    def test_extract_no_suggestions(self):
        """Should return empty list when no suggestions present."""
        comment = "This is just a comment without suggestions."
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 0

    def test_extract_mixed_suggestions(self):
        """Should extract both block and inline suggestions."""
        comment = """
You should use `inline_fix` here.

Also:
```suggestion
block_fix()
```
"""
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 2
        # Check both types are present
        types = {s["type"] for s in suggestions}
        assert "inline_suggestion" in types
        assert "code_suggestion" in types


# --- Tests for categorize_comment ---


class TestCategorizeComment:
    """Tests for categorize_comment function."""

    def test_categorize_critical_security(self):
        """Should categorize security issues as critical priority 1."""
        comment = "This has a security vulnerability that needs fixing."
        category, priority = categorize_comment(comment)

        assert category == "critical"
        assert priority == 1

    def test_categorize_bug(self):
        """Should categorize bugs as priority 1."""
        comment = "This is a bug that causes errors."
        category, priority = categorize_comment(comment)

        assert category == "bug"
        assert priority == 1

    def test_categorize_question(self):
        """Should categorize questions as priority 3."""
        comment = "Why did you implement it this way?"
        category, priority = categorize_comment(comment)

        assert category == "question"
        assert priority == 3

    def test_categorize_style(self):
        """Should categorize style issues as priority 3."""
        comment = "Please fix the formatting and naming conventions."
        category, priority = categorize_comment(comment)

        assert category == "style"
        assert priority == 3

    def test_categorize_improvement(self):
        """Should categorize improvements as priority 2."""
        comment = "Consider refactoring this for better performance."
        category, priority = categorize_comment(comment)

        assert category == "improvement"
        assert priority == 2

    def test_categorize_default(self):
        """Should default to improvement priority 2 for unclear comments."""
        comment = "Some generic comment."
        category, priority = categorize_comment(comment)

        assert category == "improvement"
        assert priority == 2

    def test_categorize_critical_keywords(self):
        """Should detect critical keywords."""
        critical_keywords = ["exploit", "breaking", "vulnerability"]
        for keyword in critical_keywords:
            comment = f"This has a {keyword} issue."
            category, priority = categorize_comment(comment)
            assert category == "critical"
            assert priority == 1

    def test_categorize_case_insensitive(self):
        """Should be case insensitive when categorizing."""
        comment = "THIS IS A BUG"
        category, priority = categorize_comment(comment)

        assert category == "bug"


# --- Tests for is_actionable ---


class TestIsActionable:
    """Tests for is_actionable function."""

    def test_is_actionable_with_keyword(self):
        """Should return True when actionable keyword present."""
        keywords = ["please", "should", "fix"]
        comment = "Please fix this issue."

        assert is_actionable(comment, keywords) is True

    def test_is_actionable_without_keyword(self):
        """Should return False when no actionable keyword present."""
        keywords = ["please", "should", "fix"]
        comment = "This looks fine to me."

        assert is_actionable(comment, keywords) is False

    def test_is_actionable_case_insensitive(self):
        """Should be case insensitive."""
        keywords = ["please"]
        comment = "PLEASE update this."

        assert is_actionable(comment, keywords) is True

    def test_is_actionable_multiple_keywords(self):
        """Should detect any keyword from the list."""
        keywords = ["please", "should", "fix"]

        assert is_actionable("Should change this", keywords) is True
        assert is_actionable("Please update", keywords) is True
        assert is_actionable("Fix this bug", keywords) is True

    def test_is_actionable_empty_keywords(self):
        """Should return False with empty keyword list."""
        assert is_actionable("Please fix this", []) is False


# --- Tests for parse_review_comments ---


class TestParseReviewComments:
    """Tests for parse_review_comments function."""

    def test_parse_review_comments_file_comments(self):
        """Should parse file-level review comments."""
        comments = [
            MockComment(1, "Please fix this bug", path="file.py", line=10),
            MockComment(2, "Should refactor this", path="file.py", line=20),
        ]
        pr = MockPullRequest(comments=comments)
        keywords = ["please", "should"]

        items = parse_review_comments(pr, keywords)

        assert len(items) == 2
        assert items[0]["body"] == "Please fix this bug"
        assert items[0]["file"] == "file.py"
        assert items[0]["line"] == 10

    def test_parse_review_comments_changes_requested(self):
        """Should include reviews with CHANGES_REQUESTED state."""
        reviews = [
            MockReview(1, "Please fix these issues", state="CHANGES_REQUESTED"),
            MockReview(2, "Looks good", state="APPROVED"),  # Should be excluded
        ]
        pr = MockPullRequest(reviews=reviews)
        keywords = ["please"]

        items = parse_review_comments(pr, keywords)

        assert len(items) == 1
        assert items[0]["body"] == "Please fix these issues"

    def test_parse_review_comments_filters_non_actionable(self):
        """Should filter out comments without actionable keywords."""
        comments = [
            MockComment(1, "Please fix this", path="file.py", line=10),
            MockComment(2, "Looks good to me", path="file.py", line=20),
        ]
        pr = MockPullRequest(comments=comments)
        keywords = ["please", "fix"]

        items = parse_review_comments(pr, keywords)

        assert len(items) == 1
        assert "Please fix this" in items[0]["body"]

    def test_parse_review_comments_sorted_by_priority_and_date(self):
        """Should sort items by priority first, then date."""
        comments = [
            MockComment(
                1, "Please improve this", created_at="2024-01-03T00:00:00Z"
            ),  # improvement, priority 2
            MockComment(2, "Fix this bug", created_at="2024-01-02T00:00:00Z"),  # bug, priority 1
            MockComment(
                3, "Security issue here", created_at="2024-01-01T00:00:00Z"
            ),  # critical, priority 1
        ]
        pr = MockPullRequest(comments=comments)
        keywords = ["please", "fix", "issue"]

        items = parse_review_comments(pr, keywords)

        # Should be sorted: critical (oldest first), bug, then improvement
        assert "Security" in items[0]["body"]
        assert "bug" in items[1]["body"]
        assert "improve" in items[2]["body"]

    def test_parse_review_comments_extracts_code_suggestions(self):
        """Should extract code suggestions from comments."""
        comments = [
            MockComment(
                1,
                "Please fix:\n```suggestion\nfixed_code\n```",
                path="file.py",
                line=10,
            )
        ]
        pr = MockPullRequest(comments=comments)
        keywords = ["please"]

        items = parse_review_comments(pr, keywords)

        assert len(items) == 1
        assert len(items[0]["code_suggestions"]) > 0

    def test_parse_review_comments_includes_metadata(self):
        """Should include all expected metadata fields."""
        comment = MockComment(
            123,
            "Please fix this",
            author="reviewer",
            path="src/file.py",
            line=42,
            url="https://github.com/test",
            created_at="2024-01-01T12:00:00Z",
        )
        pr = MockPullRequest(comments=[comment])
        keywords = ["please"]

        items = parse_review_comments(pr, keywords)

        assert len(items) == 1
        item = items[0]
        assert item["id"] == 123
        assert item["author"] == "reviewer"
        assert item["file"] == "src/file.py"
        assert item["line"] == 42
        assert item["url"] == "https://github.com/test"
        assert "category" in item
        assert "priority" in item


# --- Tests for formatting helpers ---


class TestFormatCodeSuggestions:
    """Tests for _format_code_suggestions helper."""

    def test_format_code_suggestions_block(self):
        """Should format code suggestion blocks."""
        suggestions = [{"type": "code_suggestion", "content": "def foo():\n    pass"}]

        result = suggest_fixes._format_code_suggestions(suggestions)

        assert "**Suggested Code:**" in result
        assert "def foo():" in result

    def test_format_code_suggestions_inline(self):
        """Should format inline suggestions."""
        suggestions = [{"type": "inline_suggestion", "content": "value"}]

        result = suggest_fixes._format_code_suggestions(suggestions)

        assert "`value`" in result

    def test_format_code_suggestions_mixed(self):
        """Should format both block and inline suggestions."""
        suggestions = [
            {"type": "code_suggestion", "content": "block"},
            {"type": "inline_suggestion", "content": "inline"},
        ]

        result = suggest_fixes._format_code_suggestions(suggestions)

        assert "block" in result
        assert "`inline`" in result


class TestFormatItem:
    """Tests for _format_item helper."""

    def test_format_item_basic(self):
        """Should format basic item information."""
        item = {
            "author": "reviewer",
            "body": "Please fix this issue.",
            "file": "src/file.py",
            "line": 42,
            "priority": 1,
            "category": "bug",
            "code_suggestions": [],
            "url": "https://github.com/test",
        }

        result = suggest_fixes._format_item(1, item)

        assert "**1. Comment by @reviewer**" in result
        assert "`src/file.py:42`" in result
        assert "🔴 High" in result
        assert "Please fix this issue." in result

    def test_format_item_truncates_long_body(self):
        """Should truncate body text longer than 200 characters."""
        long_body = "a" * 250
        item = {
            "author": "reviewer",
            "body": long_body,
            "file": None,
            "line": None,
            "priority": 2,
            "category": "improvement",
            "code_suggestions": [],
            "url": "https://github.com/test",
        }

        result = suggest_fixes._format_item(1, item)

        assert "..." in result
        # The body is truncated to 200 chars + "..." = 203, plus formatting
        feedback_lines = [line for line in result.split("\n") if "**Feedback:**" in line]
        assert len(feedback_lines) > 0
        # Check that the content after "**Feedback:** " is truncated
        assert "aaaaaa..." in result

    def test_format_item_with_code_suggestions(self):
        """Should include code suggestions when present."""
        item = {
            "author": "reviewer",
            "body": "Fix this",
            "file": "file.py",
            "line": 10,
            "priority": 1,
            "category": "bug",
            "code_suggestions": [{"type": "inline_suggestion", "content": "fixed"}],
            "url": "https://github.com/test",
        }

        result = suggest_fixes._format_item(1, item)

        assert "**Suggested Code:**" in result
        assert "`fixed`" in result

    def test_format_item_priority_icons(self):
        """Should use correct priority icons."""
        priorities = [
            (1, "🔴 High"),
            (2, "🟡 Medium"),
            (3, "🟢 Low"),
        ]

        for priority, expected_icon in priorities:
            item = {
                "author": "reviewer",
                "body": "Test",
                "file": None,
                "line": None,
                "priority": priority,
                "category": "improvement",
                "code_suggestions": [],
                "url": "url",
            }
            result = suggest_fixes._format_item(1, item)
            assert expected_icon in result


class TestGenerateSummary:
    """Tests for _generate_summary helper."""

    def test_generate_summary_counts_categories(self):
        """Should count items by category."""
        items = [
            {"category": "bug", "priority": 1},
            {"category": "bug", "priority": 1},
            {"category": "improvement", "priority": 2},
            {"category": "style", "priority": 3},
        ]

        result = suggest_fixes._generate_summary(items)

        assert "**Total Actionable Items:** 4" in result
        assert "**Bugs:** 2" in result
        assert "**Improvements:** 1" in result
        assert "**Style:** 1" in result

    def test_generate_summary_highlights_critical(self):
        """Should highlight critical issues."""
        items = [{"category": "critical", "priority": 1}]

        result = suggest_fixes._generate_summary(items)

        assert "**Critical Issues:** 1" in result
        assert "Address critical issues" in result

    def test_generate_summary_no_critical_or_bugs(self):
        """Should not show warning when no critical issues or bugs."""
        items = [{"category": "improvement", "priority": 2}]

        result = suggest_fixes._generate_summary(items)

        assert "Critical Issues" not in result
        assert "Bugs" not in result
        assert "Address critical" not in result


# --- Tests for generate_fix_proposals ---


class TestGenerateFixProposals:
    """Tests for generate_fix_proposals function."""

    def test_generate_fix_proposals_empty_list(self):
        """Should return success message when no actionable items."""
        result = generate_fix_proposals([])

        assert "No actionable items found" in result

    def test_generate_fix_proposals_groups_by_category(self):
        """Should group items by category."""
        items = [
            {
                "id": 1,
                "author": "user1",
                "body": "Fix bug",
                "category": "bug",
                "priority": 1,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "url1",
            },
            {
                "id": 2,
                "author": "user2",
                "body": "Improve code",
                "category": "improvement",
                "priority": 2,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "url2",
            },
        ]

        result = generate_fix_proposals(items)

        assert "🐛 Bug (1)" in result
        assert "💡 Improvement (1)" in result

    def test_generate_fix_proposals_priority_order(self):
        """Should present categories in priority order."""
        items = [
            {
                "id": 1,
                "author": "user",
                "body": "style",
                "category": "style",
                "priority": 3,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "url",
            },
            {
                "id": 2,
                "author": "user",
                "body": "critical",
                "category": "critical",
                "priority": 1,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "url",
            },
        ]

        result = generate_fix_proposals(items)

        # Critical should appear before style in the output
        critical_pos = result.find("🚨 Critical")
        style_pos = result.find("🎨 Style")
        assert critical_pos < style_pos

    def test_generate_fix_proposals_includes_summary(self):
        """Should include summary section."""
        items = [
            {
                "id": 1,
                "author": "user",
                "body": "test",
                "category": "bug",
                "priority": 1,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "url",
            }
        ]

        result = generate_fix_proposals(items)

        assert "**Summary:**" in result
        assert "Generated by PR Copilot" in result


# --- Tests for write_output ---


class TestWriteOutput:
    """Tests for write_output function."""

    def test_write_output_to_github_summary(self, monkeypatch, tmp_path):
        """Should write to GITHUB_STEP_SUMMARY when env var set."""
        summary_file = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        report = "# Test Report"
        write_output(report)

        assert summary_file.exists()
        assert summary_file.read_text(encoding="utf-8") == report

    def test_write_output_to_temp_file(self, capsys):
        """Should write to temp file with unique name."""
        report = "# Test Report"
        write_output(report)

        captured = capsys.readouterr()
        assert "Fix proposals generated:" in captured.err

    def test_write_output_to_stdout(self, capsys):
        """Should write to stdout."""
        report = "# Test Report"
        write_output(report)

        captured = capsys.readouterr()
        assert report in captured.out

    def test_write_output_handles_io_error(self, monkeypatch, capsys):
        """Should handle IO errors gracefully."""
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", "/nonexistent/path/file.md")

        report = "# Test"
        write_output(report)  # Should not raise

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
            suggest_fixes.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Missing required environment variables" in captured.err

    def test_main_invalid_pr_number(self, monkeypatch, capsys):
        """Should exit with error when PR_NUMBER is not an integer."""
        monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
        monkeypatch.setenv("PR_NUMBER", "not-a-number")
        monkeypatch.setenv("REPO_OWNER", "owner")
        monkeypatch.setenv("REPO_NAME", "repo")

        with pytest.raises(SystemExit) as exc_info:
            suggest_fixes.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "must be an integer" in captured.err

    @patch("suggest_fixes.Github")
    def test_main_github_api_error(self, mock_github_class, monkeypatch, capsys):
        """Should handle GitHub API errors gracefully."""
        from github import GithubException

        monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
        monkeypatch.setenv("PR_NUMBER", "1")
        monkeypatch.setenv("REPO_OWNER", "owner")
        monkeypatch.setenv("REPO_NAME", "repo")

        mock_github = MagicMock()
        mock_github_class.return_value = mock_github
        mock_github.get_repo.side_effect = GithubException(404, {"message": "Not Found"}, None)

        with pytest.raises(SystemExit) as exc_info:
            suggest_fixes.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "GitHub API Error" in captured.err

    @patch("suggest_fixes.write_output")
    @patch("suggest_fixes.parse_review_comments")
    @patch("suggest_fixes.Github")
    @patch("suggest_fixes.load_config")
    def test_main_success(
        self, mock_config, mock_github_class, mock_parse, mock_write, monkeypatch
    ):
        """Should successfully generate fix proposals when all conditions met."""
        monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
        monkeypatch.setenv("PR_NUMBER", "1")
        monkeypatch.setenv("REPO_OWNER", "owner")
        monkeypatch.setenv("REPO_NAME", "repo")

        mock_config.return_value = {
            "review_handling": {"actionable_keywords": ["please", "fix"]}
        }

        mock_items = [
            {
                "id": 1,
                "author": "user",
                "body": "Please fix this",
                "category": "bug",
                "priority": 1,
                "file": "file.py",
                "line": 10,
                "code_suggestions": [],
                "url": "url",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]
        mock_parse.return_value = mock_items

        # The script doesn't explicitly sys.exit(0) on success, it just returns None
        result = suggest_fixes.main()

        # Should return None on success (no exception raised)
        assert result is None
        # Verify the functions were called
        mock_write.assert_called_once()
        mock_parse.assert_called_once()


# --- Edge Cases and Integration Tests ---


class TestEdgeCases:
    """Additional edge case tests."""

    def test_empty_comment_body(self):
        """Should handle comments with empty body."""
        comment = MockComment(1, "", path="file.py", line=10)
        pr = MockPullRequest(comments=[comment])
        keywords = ["please"]

        items = parse_review_comments(pr, keywords)

        # Empty body is not actionable
        assert len(items) == 0

    def test_very_long_comment_body(self):
        """Should handle very long comment bodies."""
        long_body = "Please fix this. " + ("a" * 1000)
        comment = MockComment(1, long_body, path="file.py", line=10)
        pr = MockPullRequest(comments=[comment])
        keywords = ["please"]

        items = parse_review_comments(pr, keywords)

        assert len(items) == 1
        # Body should be present in full (truncation happens in formatting)
        assert len(items[0]["body"]) > 200

    def test_special_characters_in_suggestions(self):
        """Should handle special characters in code suggestions."""
        comment = 'Should be `"special\'chars"`'
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) > 0

    def test_multiple_reviews_same_issue(self):
        """Should handle multiple reviews mentioning same issue."""
        reviews = [
            MockReview(1, "Please fix the bug", state="CHANGES_REQUESTED"),
            MockReview(2, "Please fix the bug", state="CHANGES_REQUESTED"),
        ]
        pr = MockPullRequest(reviews=reviews)
        keywords = ["please"]

        items = parse_review_comments(pr, keywords)

        # Should include both (no deduplication)
        assert len(items) == 2

    def test_unicode_in_comments(self):
        """Should handle unicode characters in comments."""
        comment = MockComment(1, "Please fix this 🐛 bug", path="file.py", line=10)
        pr = MockPullRequest(comments=[comment])
        keywords = ["please"]

        items = parse_review_comments(pr, keywords)

        assert len(items) == 1
        assert "🐛" in items[0]["body"]

    def test_nested_code_blocks(self):
        """Should handle nested markdown structures."""
        comment = """
```suggestion
# Comment inside code
def foo():
    '''docstring'''
    pass
```
"""
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 1
        assert "def foo():" in suggestions[0]["content"]