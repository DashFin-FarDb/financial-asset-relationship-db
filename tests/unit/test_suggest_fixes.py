#!/usr/bin/env python3
"""
Unit tests for .github/pr-copilot/scripts/suggest_fixes.py

Tests cover configuration loading, comment parsing, categorization,
formatting, and report generation.
"""

from __future__ import annotations

import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add the script to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_ROOT / ".github" / "pr-copilot" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from suggest_fixes import (  # noqa: E402
    categorize_comment,
    extract_code_suggestions,
    generate_fix_proposals,
    is_actionable,
    load_config,
    parse_review_comments,
    write_output,
)


class TestLoadConfig:
    """Test load_config function."""

    def test_load_config_with_existing_file(self, tmp_path, monkeypatch):
        """load_config loads configuration from existing YAML file."""
        # Create a mock config file
        config_dir = tmp_path / ".github"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-copilot-config.yml"

        config_content = """
review_handling:
  actionable_keywords:
    - "fix"
    - "update"
    - "refactor"
"""
        config_file.write_text(config_content)

        # Change to tmp_path directory
        monkeypatch.chdir(tmp_path)

        config = load_config()

        assert "review_handling" in config
        assert "actionable_keywords" in config["review_handling"]
        assert "fix" in config["review_handling"]["actionable_keywords"]
        assert "update" in config["review_handling"]["actionable_keywords"]

    def test_load_config_with_missing_file(self, tmp_path, monkeypatch):
        """load_config returns defaults when config file is missing."""
        monkeypatch.chdir(tmp_path)

        config = load_config()

        # Should return defaults
        assert "review_handling" in config
        assert "actionable_keywords" in config["review_handling"]
        # Check some default keywords
        keywords = config["review_handling"]["actionable_keywords"]
        assert "please" in keywords
        assert "should" in keywords
        assert "fix" in keywords


class TestExtractCodeSuggestions:
    """Test extract_code_suggestions function."""

    def test_extract_code_suggestions_with_suggestion_blocks(self):
        """extract_code_suggestions extracts fenced suggestion blocks."""
        comment = """
Please update the code like this:

```suggestion
def new_function():
    return "fixed"
```

This is better.
"""
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "code_suggestion"
        assert 'def new_function()' in suggestions[0]["content"]
        assert 'return "fixed"' in suggestions[0]["content"]

    def test_extract_code_suggestions_with_inline_suggestions(self):
        """extract_code_suggestions extracts inline code suggestions."""
        comment = "This should be `new_value` instead."
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "inline_suggestion"
        assert suggestions[0]["content"] == "new_value"

    def test_extract_code_suggestions_change_to_pattern(self):
        """extract_code_suggestions recognizes 'change to' pattern."""
        comment = "Change to `updated_variable_name` for clarity."
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 1
        assert suggestions[0]["content"] == "updated_variable_name"

    def test_extract_code_suggestions_replace_with_pattern(self):
        """extract_code_suggestions recognizes 'replace with' pattern."""
        comment = "Replace with `better_implementation()` here."
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 1
        assert suggestions[0]["content"] == "better_implementation()"

    def test_extract_code_suggestions_use_pattern(self):
        """extract_code_suggestions recognizes 'use' pattern."""
        comment = "Use `const` instead of `let`."
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 1
        assert suggestions[0]["content"] == "const"

    def test_extract_code_suggestions_multiple(self):
        """extract_code_suggestions extracts multiple suggestions."""
        comment = """
```suggestion
line1
line2
```

Also, change to `value1` and use `value2`.
"""
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 3
        assert suggestions[0]["type"] == "code_suggestion"
        assert suggestions[1]["type"] == "inline_suggestion"
        assert suggestions[2]["type"] == "inline_suggestion"

    def test_extract_code_suggestions_no_matches(self):
        """extract_code_suggestions returns empty list when no suggestions."""
        comment = "This looks good to me."
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 0

    def test_extract_code_suggestions_case_insensitive(self):
        """extract_code_suggestions matches patterns case-insensitively."""
        comment = "SHOULD BE `UPPERCASE` here."
        suggestions = extract_code_suggestions(comment)

        assert len(suggestions) == 1
        assert suggestions[0]["content"] == "UPPERCASE"


class TestCategorizeComment:
    """Test categorize_comment function."""

    def test_categorize_comment_critical(self):
        """categorize_comment identifies critical security issues."""
        comment = "This is a critical security vulnerability!"
        category, priority = categorize_comment(comment)

        assert category == "critical"
        assert priority == 1

    def test_categorize_comment_bug(self):
        """categorize_comment identifies bugs."""
        comment = "This code has a bug that causes incorrect results."
        category, priority = categorize_comment(comment)

        assert category == "bug"
        assert priority == 1

    def test_categorize_comment_question(self):
        """categorize_comment identifies questions."""
        comment = "Why did you choose this approach?"
        category, priority = categorize_comment(comment)

        assert category == "question"
        assert priority == 3

    def test_categorize_comment_style(self):
        """categorize_comment identifies style issues."""
        comment = "This doesn't follow our naming convention."
        category, priority = categorize_comment(comment)

        assert category == "style"
        assert priority == 3

    def test_categorize_comment_improvement(self):
        """categorize_comment identifies improvements."""
        comment = "Consider refactoring this for better performance."
        category, priority = categorize_comment(comment)

        assert category == "improvement"
        assert priority == 2

    def test_categorize_comment_default(self):
        """categorize_comment defaults to improvement for generic comments."""
        comment = "This is a comment without specific keywords."
        category, priority = categorize_comment(comment)

        assert category == "improvement"
        assert priority == 2

    def test_categorize_comment_priority_order(self):
        """categorize_comment respects priority order of categories."""
        # Security should win over bug
        comment = "This security issue causes bugs."
        category, priority = categorize_comment(comment)

        assert category == "critical"
        assert priority == 1


class TestIsActionable:
    """Test is_actionable function."""

    def test_is_actionable_with_keyword(self):
        """is_actionable returns True when keyword is present."""
        keywords = ["please", "fix", "update"]
        comment = "Please fix this issue."

        assert is_actionable(comment, keywords) is True

    def test_is_actionable_without_keyword(self):
        """is_actionable returns False when no keyword is present."""
        keywords = ["please", "fix", "update"]
        comment = "This looks good!"

        assert is_actionable(comment, keywords) is False

    def test_is_actionable_case_insensitive(self):
        """is_actionable is case-insensitive."""
        keywords = ["fix"]
        comment = "FIX this bug."

        assert is_actionable(comment, keywords) is True

    def test_is_actionable_partial_match(self):
        """is_actionable matches keywords as substrings."""
        keywords = ["nit"]
        comment = "Just a nitpick, but consider changing this."

        assert is_actionable(comment, keywords) is True

    def test_is_actionable_multiple_keywords(self):
        """is_actionable returns True if any keyword matches."""
        keywords = ["fix", "update", "change"]
        comment = "You should update this."

        assert is_actionable(comment, keywords) is True


class TestParseReviewComments:
    """Test parse_review_comments function."""

    def test_parse_review_comments_file_level(self):
        """parse_review_comments extracts actionable file-level comments."""
        mock_pr = Mock()

        # Mock file-level comment
        comment1 = Mock()
        comment1.id = 1
        comment1.user = Mock(login="reviewer1")
        comment1.body = "Please fix this typo."
        comment1.path = "src/file.py"
        comment1.original_line = 42
        comment1.html_url = "https://github.com/repo/pull/1#comment-1"
        comment1.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        mock_pr.get_review_comments.return_value = [comment1]
        mock_pr.get_reviews.return_value = []

        keywords = ["please", "fix"]
        items = parse_review_comments(mock_pr, keywords)

        assert len(items) == 1
        assert items[0]["id"] == 1
        assert items[0]["author"] == "reviewer1"
        assert items[0]["body"] == "Please fix this typo."
        assert items[0]["file"] == "src/file.py"
        assert items[0]["line"] == 42
        assert items[0]["priority"] == 2

    def test_parse_review_comments_changes_requested(self):
        """parse_review_comments includes CHANGES_REQUESTED reviews."""
        mock_pr = Mock()

        mock_pr.get_review_comments.return_value = []

        # Mock review with changes requested
        review = Mock()
        review.id = 2
        review.user = Mock(login="reviewer2")
        review.body = "Please refactor this code."
        review.state = "CHANGES_REQUESTED"
        review.html_url = "https://github.com/repo/pull/1#review-2"
        review.submitted_at = datetime(2024, 1, 2, tzinfo=timezone.utc)

        mock_pr.get_reviews.return_value = [review]

        keywords = ["please", "refactor"]
        items = parse_review_comments(mock_pr, keywords)

        assert len(items) == 1
        assert items[0]["id"] == 2
        assert items[0]["author"] == "reviewer2"
        assert items[0]["category"] == "improvement"

    def test_parse_review_comments_ignores_approved(self):
        """parse_review_comments ignores APPROVED reviews without actionable content."""
        mock_pr = Mock()

        mock_pr.get_review_comments.return_value = []

        # Approved review without actionable keywords
        review = Mock()
        review.user = Mock(login="reviewer")
        review.body = "Looks good to me!"
        review.state = "APPROVED"

        mock_pr.get_reviews.return_value = [review]

        keywords = ["please", "fix"]
        items = parse_review_comments(mock_pr, keywords)

        # Should be empty because "Looks good to me!" has no actionable keywords
        assert len(items) == 0

    def test_parse_review_comments_with_code_suggestions(self):
        """parse_review_comments extracts code suggestions."""
        mock_pr = Mock()

        comment = Mock()
        comment.id = 1
        comment.user = Mock(login="reviewer")
        comment.body = """
Please update:
```suggestion
new_code()
```
"""
        comment.path = "file.py"
        comment.original_line = 10
        comment.html_url = "https://test.com"
        comment.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        mock_pr.get_review_comments.return_value = [comment]
        mock_pr.get_reviews.return_value = []

        keywords = ["please"]
        items = parse_review_comments(mock_pr, keywords)

        assert len(items) == 1
        assert len(items[0]["code_suggestions"]) == 1
        assert "new_code()" in items[0]["code_suggestions"][0]["content"]

    def test_parse_review_comments_sorted_by_priority(self):
        """parse_review_comments sorts by priority then date."""
        mock_pr = Mock()

        # Create comments with different priorities
        comment1 = Mock()
        comment1.id = 1
        comment1.user = Mock(login="reviewer")
        comment1.body = "This is a style issue."  # Priority 3
        comment1.path = "file.py"
        comment1.original_line = 1
        comment1.html_url = "https://test.com/1"
        comment1.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        comment2 = Mock()
        comment2.id = 2
        comment2.user = Mock(login="reviewer")
        comment2.body = "This is a critical bug!"  # Priority 1
        comment2.path = "file.py"
        comment2.original_line = 2
        comment2.html_url = "https://test.com/2"
        comment2.created_at = datetime(2024, 1, 2, tzinfo=timezone.utc)

        comment3 = Mock()
        comment3.id = 3
        comment3.user = Mock(login="reviewer")
        comment3.body = "Please refactor this."  # Priority 2
        comment3.path = "file.py"
        comment3.original_line = 3
        comment3.html_url = "https://test.com/3"
        comment3.created_at = datetime(2024, 1, 3, tzinfo=timezone.utc)

        mock_pr.get_review_comments.return_value = [comment1, comment2, comment3]
        mock_pr.get_reviews.return_value = []

        keywords = ["style", "critical", "bug", "please", "refactor"]
        items = parse_review_comments(mock_pr, keywords)

        # Should be sorted by priority (1, 2, 3)
        assert len(items) == 3
        assert items[0]["priority"] == 1  # Critical bug
        assert items[1]["priority"] == 2  # Refactor
        assert items[2]["priority"] == 3  # Style

    def test_parse_review_comments_filters_non_actionable(self):
        """parse_review_comments filters out non-actionable comments."""
        mock_pr = Mock()

        comment1 = Mock()
        comment1.user = Mock(login="reviewer")
        comment1.body = "Please fix this."
        comment1.path = "file.py"
        comment1.original_line = 1
        comment1.html_url = "https://test.com"
        comment1.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        comment2 = Mock()
        comment2.user = Mock(login="reviewer")
        comment2.body = "Looks good!"  # Not actionable
        comment2.path = "file.py"
        comment2.original_line = 2
        comment2.html_url = "https://test.com"
        comment2.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        mock_pr.get_review_comments.return_value = [comment1, comment2]
        mock_pr.get_reviews.return_value = []

        keywords = ["please", "fix"]
        items = parse_review_comments(mock_pr, keywords)

        # Only comment1 should be included
        assert len(items) == 1
        assert items[0]["body"] == "Please fix this."


class TestGenerateFixProposals:
    """Test generate_fix_proposals function."""

    def test_generate_fix_proposals_no_items(self):
        """generate_fix_proposals returns success message when no items."""
        result = generate_fix_proposals([])

        assert "No actionable items found" in result

    def test_generate_fix_proposals_with_items(self):
        """generate_fix_proposals generates structured report."""
        items = [
            {
                "id": 1,
                "author": "reviewer1",
                "body": "This is a bug that needs fixing.",
                "category": "bug",
                "priority": 1,
                "file": "src/app.py",
                "line": 42,
                "code_suggestions": [],
                "url": "https://github.com/repo/pull/1#comment-1",
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
            {
                "id": 2,
                "author": "reviewer2",
                "body": "Consider refactoring this for better readability.",
                "category": "improvement",
                "priority": 2,
                "file": "src/utils.py",
                "line": 10,
                "code_suggestions": [],
                "url": "https://github.com/repo/pull/1#comment-2",
                "created_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
            },
        ]

        result = generate_fix_proposals(items)

        # Check main sections
        assert "🔧 **Fix Proposals from Review Comments**" in result
        assert "🐛 Bug" in result
        assert "💡 Improvement" in result

        # Check content
        assert "reviewer1" in result
        assert "reviewer2" in result
        assert "src/app.py:42" in result
        assert "src/utils.py:10" in result

        # Check summary
        assert "**Summary:**" in result
        assert "**Total Actionable Items:** 2" in result
        assert "🐛 **Bugs:** 1" in result
        assert "💡 **Improvements:** 1" in result

    def test_generate_fix_proposals_with_code_suggestions(self):
        """generate_fix_proposals includes code suggestions."""
        items = [
            {
                "id": 1,
                "author": "reviewer",
                "body": "Please update this code.",
                "category": "improvement",
                "priority": 2,
                "file": "file.py",
                "line": 1,
                "code_suggestions": [
                    {"type": "code_suggestion", "content": "new_function()"},
                    {"type": "inline_suggestion", "content": "value"},
                ],
                "url": "https://test.com",
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            }
        ]

        result = generate_fix_proposals(items)

        assert "**Suggested Code:**" in result
        assert "new_function()" in result
        assert "`value`" in result

    def test_generate_fix_proposals_long_body_truncated(self):
        """generate_fix_proposals truncates long comment bodies."""
        long_body = "a" * 250  # Longer than 200 chars
        items = [
            {
                "id": 1,
                "author": "reviewer",
                "body": long_body,
                "category": "improvement",
                "priority": 2,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "https://test.com",
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            }
        ]

        result = generate_fix_proposals(items)

        # Should be truncated with "..."
        assert "..." in result
        # Should not contain the full 250 chars
        assert long_body not in result

    def test_generate_fix_proposals_priority_warning(self):
        """generate_fix_proposals shows priority warning for critical/bugs."""
        items = [
            {
                "id": 1,
                "author": "reviewer",
                "body": "Critical security issue!",
                "category": "critical",
                "priority": 1,
                "file": "file.py",
                "line": 1,
                "code_suggestions": [],
                "url": "https://test.com",
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            }
        ]

        result = generate_fix_proposals(items)

        assert "⚠️ **Priority:**" in result
        assert "Address critical issues and bugs first" in result

    def test_generate_fix_proposals_category_order(self):
        """generate_fix_proposals displays categories in priority order."""
        items = [
            {
                "id": 1,
                "author": "reviewer",
                "body": "Style issue.",
                "category": "style",
                "priority": 3,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "https://test.com/1",
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
            {
                "id": 2,
                "author": "reviewer",
                "body": "Critical bug!",
                "category": "critical",
                "priority": 1,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "https://test.com/2",
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
        ]

        result = generate_fix_proposals(items)

        # Critical should appear before style in the output
        critical_pos = result.find("🚨 Critical")
        style_pos = result.find("🎨 Style")
        assert critical_pos < style_pos


class TestWriteOutput:
    """Test write_output function."""

    def test_write_output_to_stdout(self, capsys):
        """write_output prints to stdout."""
        report = "Test report content"
        write_output(report)

        captured = capsys.readouterr()
        assert report in captured.out

    def test_write_output_to_github_summary(self, monkeypatch, tmp_path):
        """write_output writes to GITHUB_STEP_SUMMARY when set."""
        summary_file = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        report = "Test summary"
        write_output(report)

        assert summary_file.exists()
        assert summary_file.read_text() == report

    def test_write_output_to_temp_file(self, capsys):
        """write_output creates temporary file."""
        report = "Test temp report"
        write_output(report)

        # Check stderr for file path message
        captured = capsys.readouterr()
        assert "Fix proposals generated:" in captured.err

    def test_write_output_handles_github_summary_error(self, monkeypatch, capsys):
        """write_output handles errors writing to GITHUB_STEP_SUMMARY."""
        bad_path = "/nonexistent/dir/summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", bad_path)

        report = "Test content"
        write_output(report)  # Should not raise

        captured = capsys.readouterr()
        # Should show warning or still output to stdout
        assert "Warning" in captured.err or report in captured.out


class TestMainFunction:
    """Test main() entry point."""

    def test_main_missing_env_vars(self, monkeypatch, capsys):
        """main exits with error when required env vars are missing."""
        for var in ["GITHUB_TOKEN", "PR_NUMBER", "REPO_OWNER", "REPO_NAME"]:
            monkeypatch.delenv(var, raising=False)

        from suggest_fixes import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Missing required environment variables" in captured.err

    def test_main_invalid_pr_number(self, monkeypatch, capsys):
        """main exits with error when PR_NUMBER is not an integer."""
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monkeypatch.setenv("PR_NUMBER", "not-a-number")
        monkeypatch.setenv("REPO_OWNER", "owner")
        monkeypatch.setenv("REPO_NAME", "repo")

        from suggest_fixes import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "PR_NUMBER must be an integer" in captured.err

    @patch("suggest_fixes.Github")
    def test_main_success(self, mock_github_class, monkeypatch, capsys, tmp_path):
        """main successfully generates fix proposals."""
        # Setup environment
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monkeypatch.setenv("PR_NUMBER", "42")
        monkeypatch.setenv("REPO_OWNER", "test-owner")
        monkeypatch.setenv("REPO_NAME", "test-repo")

        # Create mock config
        config_dir = tmp_path / ".github"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-copilot-config.yml"
        config_file.write_text("review_handling:\n  actionable_keywords:\n    - please\n")
        monkeypatch.chdir(tmp_path)

        # Mock GitHub API
        mock_github = Mock()
        mock_repo = Mock()
        mock_pr = Mock()

        # No comments for simplicity
        mock_pr.get_review_comments.return_value = []
        mock_pr.get_reviews.return_value = []

        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_github_class.return_value = mock_github

        from suggest_fixes import main

        # main() may not raise SystemExit on success, just return normally
        try:
            result = main()
            # If it returns normally, that's success (no exception)
            captured = capsys.readouterr()
            # Should show "no actionable items" message
            assert "No actionable items" in captured.out or "Parsing review comments" in captured.err
        except SystemExit as exc:
            # If it does exit, should be 0
            assert exc.code == 0


# Regression tests
class TestRegressionTests:
    """Test edge cases and regressions."""

    def test_extract_code_suggestions_empty_string(self):
        """extract_code_suggestions handles empty comment."""
        result = extract_code_suggestions("")
        assert result == []

    def test_categorize_comment_empty_string(self):
        """categorize_comment handles empty comment."""
        category, priority = categorize_comment("")
        assert category == "improvement"
        assert priority == 2

    def test_is_actionable_empty_keywords(self):
        """is_actionable returns False when keyword list is empty."""
        result = is_actionable("Please fix this.", [])
        assert result is False

    def test_parse_review_comments_empty_body(self):
        """parse_review_comments handles comments with None or empty body."""
        mock_pr = Mock()

        comment = Mock()
        comment.id = 1
        comment.user = Mock(login="reviewer")
        comment.body = None  # Empty body
        comment.path = "file.py"
        comment.original_line = 1
        comment.html_url = "https://test.com"
        comment.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        mock_pr.get_review_comments.return_value = [comment]
        mock_pr.get_reviews.return_value = []

        keywords = ["please"]
        items = parse_review_comments(mock_pr, keywords)

        # Should handle None body gracefully
        assert len(items) == 0

    def test_generate_fix_proposals_empty_category_counts(self):
        """generate_fix_proposals handles categories with zero counts."""
        items = [
            {
                "id": 1,
                "author": "reviewer",
                "body": "Question?",
                "category": "question",
                "priority": 3,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "https://test.com",
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            }
        ]

        result = generate_fix_proposals(items)

        # Should show question count but not critical/bug counts
        assert "❓ **Questions:** 1" in result
        # Should not show priority warning (no critical/bugs)
        assert "Address critical issues and bugs first" not in result