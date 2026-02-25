"""Comprehensive tests for .github/pr-copilot/scripts/suggest_fixes.py"""

from __future__ import annotations

# Add the scripts directory to path for imports
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from suggest_fixes import (
    categorize_comment,
    extract_code_suggestions,
    generate_fix_proposals,
    is_actionable,
    load_config,
    main,
    parse_review_comments,
    write_output,
)

scripts_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts"
sys.path.insert(0, str(scripts_path))


class TestLoadConfig:
    """Test load_config function."""

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="review_handling:\n  actionable_keywords:\n    - custom\n",
    )
    @patch("suggest_fixes.yaml.safe_load")
    def test_load_config_exists(self, mock_yaml_load, mock_file):
        """Test loading config when file exists."""
        mock_yaml_load.return_value = {"review_handling": {"actionable_keywords": ["custom"]}}

        result = load_config()

        assert "review_handling" in result
        assert result["review_handling"]["actionable_keywords"] == ["custom"]

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_load_config_missing(self, mock_file):
        """Test loading config when file is missing."""
        result = load_config()

        assert "review_handling" in result
        assert "actionable_keywords" in result["review_handling"]
        assert "please" in result["review_handling"]["actionable_keywords"]


class TestExtractCodeSuggestions:
    """Test extract_code_suggestions function."""

    def test_extract_code_block_suggestion(self):
        """Test extracting code from suggestion block."""
        comment = "```suggestion\nconst foo = bar;\n```"
        result = extract_code_suggestions(comment)

        assert len(result) == 1
        assert result[0]["type"] == "code_suggestion"
        assert result[0]["content"] == "const foo = bar;"

    def test_extract_inline_suggestion(self):
        """Test extracting inline code suggestion."""
        comment = "You should change to `newVariable`"
        result = extract_code_suggestions(comment)

        assert len(result) == 1
        assert result[0]["type"] == "inline_suggestion"
        assert result[0]["content"] == "newVariable"

    def test_extract_multiple_suggestions(self):
        """Test extracting multiple suggestions."""
        comment = """
        ```suggestion
        const foo = bar;
        ```
        Also, please use `betterName` instead.
        """
        result = extract_code_suggestions(comment)

        assert len(result) == 2

    def test_extract_no_suggestions(self):
        """Test comment with no code suggestions."""
        comment = "This looks good to me!"
        result = extract_code_suggestions(comment)

        assert len(result) == 0

    def test_extract_multiple_patterns(self):
        """Test various suggestion patterns."""
        patterns = [
            ("should be `value1`", "value1"),
            ("replace with `value2`", "value2"),
            ("use `value3` instead", "value3"),
        ]

        for comment, expected in patterns:
            result = extract_code_suggestions(comment)
            assert len(result) == 1
            assert result[0]["content"] == expected


class TestCategorizeComment:
    """Test categorize_comment function."""

    def test_categorize_critical(self):
        """Test categorizing critical issues."""
        category, priority = categorize_comment("This is a critical security vulnerability")
        assert category == "critical"
        assert priority == 1

    def test_categorize_bug(self):
        """Test categorizing bugs."""
        category, priority = categorize_comment("This code is broken and fails")
        assert category == "bug"
        assert priority == 1

    def test_categorize_question(self):
        """Test categorizing questions."""
        category, priority = categorize_comment("Why did you choose this approach?")
        assert category == "question"
        assert priority == 3

    def test_categorize_style(self):
        """Test categorizing style issues."""
        category, priority = categorize_comment("Please follow naming conventions")
        assert category == "style"
        assert priority == 3

    def test_categorize_improvement(self):
        """Test categorizing improvements."""
        category, priority = categorize_comment("Consider refactoring this for better performance")
        assert category == "improvement"
        assert priority == 2

    def test_categorize_default(self):
        """Test default categorization."""
        category, priority = categorize_comment("Some generic comment")
        assert category == "improvement"
        assert priority == 2


class TestIsActionable:
    """Test is_actionable function."""

    def test_is_actionable_true(self):
        """Test comment that is actionable."""
        keywords = ["please", "should", "fix"]

        assert is_actionable("Please fix this bug", keywords) is True
        assert is_actionable("You should refactor", keywords) is True
        assert is_actionable("Fix the typo", keywords) is True

    def test_is_actionable_false(self):
        """Test comment that is not actionable."""
        keywords = ["please", "should", "fix"]

        assert is_actionable("Looks good!", keywords) is False
        assert is_actionable("LGTM", keywords) is False

    def test_is_actionable_case_insensitive(self):
        """Test case insensitivity."""
        keywords = ["please"]

        assert is_actionable("PLEASE update", keywords) is True
        assert is_actionable("Please update", keywords) is True


class TestParseReviewComments:
    """Test parse_review_comments function."""

    def test_parse_file_level_comments(self):
        """Test parsing file-level review comments."""
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 1
        mock_comment.user.login = "reviewer"
        mock_comment.body = "Please fix this issue"
        mock_comment.created_at = "2024-01-01"
        mock_comment.path = "file.py"
        mock_comment.original_line = 10
        mock_comment.html_url = "http://example.com"

        mock_pr.get_review_comments.return_value = [mock_comment]
        mock_pr.get_reviews.return_value = []

        result = parse_review_comments(mock_pr, ["please", "fix"])

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["author"] == "reviewer"
        assert result[0]["body"] == "Please fix this issue"
        assert result[0]["file"] == "file.py"
        assert result[0]["line"] == 10

    def test_parse_changes_requested_reviews(self):
        """Test parsing CHANGES_REQUESTED reviews."""
        mock_pr = MagicMock()
        mock_pr.get_review_comments.return_value = []

        mock_review = MagicMock()
        mock_review.id = 2
        mock_review.state = "CHANGES_REQUESTED"
        mock_review.user.login = "reviewer"
        mock_review.body = "Please update the logic"
        mock_review.submitted_at = "2024-01-01"
        mock_review.html_url = "http://example.com"

        mock_pr.get_reviews.return_value = [mock_review]

        result = parse_review_comments(mock_pr, ["please", "update"])

        assert len(result) == 1
        assert result[0]["author"] == "reviewer"
        assert result[0]["body"] == "Please update the logic"

    def test_parse_skips_non_actionable(self):
        """Test that non-actionable comments are skipped."""
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.body = "Looks good to me"

        mock_pr.get_review_comments.return_value = [mock_comment]
        mock_pr.get_reviews.return_value = []

        result = parse_review_comments(mock_pr, ["please", "fix"])

        assert len(result) == 0

    def test_parse_sorts_by_priority_and_date(self):
        """Test that results are sorted by priority then date."""
        mock_pr = MagicMock()

        # Create comments with different priorities
        comment1 = MagicMock()
        comment1.id = 1
        comment1.user.login = "user1"
        comment1.body = "This is a critical bug"  # Priority 1
        comment1.created_at = "2024-01-02"
        comment1.path = None
        comment1.original_line = None
        comment1.html_url = "url1"

        comment2 = MagicMock()
        comment2.id = 2
        comment2.user.login = "user2"
        comment2.body = "Consider refactoring"  # Priority 2
        comment2.created_at = "2024-01-01"
        comment2.path = None
        comment2.original_line = None
        comment2.html_url = "url2"

        mock_pr.get_review_comments.return_value = [comment2, comment1]
        mock_pr.get_reviews.return_value = []

        result = parse_review_comments(mock_pr, ["critical", "consider", "refactoring"])

        # Critical (priority 1) should come first
        assert "critical" in result[0]["body"].lower()
        assert "refactoring" in result[1]["body"].lower()


class TestGenerateFixProposals:
    """Test generate_fix_proposals function."""

    def test_generate_no_items(self):
        """Test generating proposals with no actionable items."""
        result = generate_fix_proposals([])
        assert "No actionable items found" in result

    def test_generate_with_items(self):
        """Test generating proposals with actionable items."""
        items = [
            {
                "id": 1,
                "author": "reviewer",
                "body": "Please fix this bug",
                "category": "bug",
                "priority": 1,
                "file": "test.py",
                "line": 10,
                "code_suggestions": [],
                "url": "http://example.com",
                "created_at": "2024-01-01",
            }
        ]

        result = generate_fix_proposals(items)

        assert "Fix Proposals" in result
        assert "🐛" in result  # Bug emoji
        assert "reviewer" in result
        assert "test.py:10" in result

    def test_generate_groups_by_category(self):
        """Test that items are grouped by category."""
        items = [
            {
                "id": 1,
                "author": "user1",
                "body": "Critical issue",
                "category": "critical",
                "priority": 1,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "url1",
                "created_at": "2024-01-01",
            },
            {
                "id": 2,
                "author": "user2",
                "body": "Fix bug",
                "category": "bug",
                "priority": 1,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "url2",
                "created_at": "2024-01-01",
            },
        ]

        result = generate_fix_proposals(items)

        assert "🚨 Critical" in result
        assert "🐛 Bug" in result

    def test_generate_includes_summary(self):
        """Test that summary is included."""
        items = [
            {
                "id": 1,
                "author": "user",
                "body": "Critical issue",
                "category": "critical",
                "priority": 1,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "url",
                "created_at": "2024-01-01",
            }
        ]

        result = generate_fix_proposals(items)

        assert "Summary:" in result
        assert "Total Actionable Items:** 1" in result
        assert "Critical Issues:** 1" in result

    def test_generate_truncates_long_body(self):
        """Test that long comment bodies are truncated."""
        long_body = "a" * 300
        items = [
            {
                "id": 1,
                "author": "user",
                "body": long_body,
                "category": "improvement",
                "priority": 2,
                "file": None,
                "line": None,
                "code_suggestions": [],
                "url": "url",
                "created_at": "2024-01-01",
            }
        ]

        result = generate_fix_proposals(items)

        assert "..." in result  # Truncation indicator


class TestWriteOutput:
    """Test write_output function."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("suggest_fixes.os.environ.get")
    @patch("builtins.print")
    @patch("suggest_fixes.tempfile.NamedTemporaryFile")
    def test_write_output_with_github_summary(self, mock_temp, mock_print, mock_env, mock_file_open):
        """Test writing output with GitHub summary."""
        mock_env.return_value = "/tmp/summary"
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/report.md"
        mock_temp.__enter__.return_value = mock_temp_file

        write_output("Test report")

        assert mock_print.called

    @patch("suggest_fixes.os.environ.get")
    @patch("builtins.print")
    @patch("suggest_fixes.tempfile.NamedTemporaryFile")
    def test_write_output_without_github_summary(self, mock_temp, mock_print, mock_env):
        """Test writing output without GitHub summary."""
        mock_env.return_value = None
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/report.md"
        mock_temp.__enter__.return_value = mock_temp_file

        write_output("Test report")

        assert mock_print.called


class TestMain:
    """Test main function."""

    @patch("suggest_fixes.Github")
    @patch("suggest_fixes.os.environ.get")
    @patch("suggest_fixes.write_output")
    @patch("suggest_fixes.sys.exit")
    @patch("suggest_fixes.load_config")
    def test_main_success(self, mock_config, mock_exit, mock_write, mock_env, mock_github_class):
        """Test successful main execution."""
        env_values = {
            "GITHUB_TOKEN": "token",
            "PR_NUMBER": "123",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repo",
        }
        mock_env.side_effect = lambda key: env_values.get(key)
        mock_config.return_value = {"review_handling": {"actionable_keywords": ["please"]}}

        # Setup mocks
        mock_github = mock_github_class.return_value
        mock_repo = MagicMock()
        mock_pr = MagicMock()

        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        mock_pr.get_review_comments.return_value = []
        mock_pr.get_reviews.return_value = []

        main()

        assert mock_write.called

    @patch("suggest_fixes.os.environ.get")
    @patch("suggest_fixes.sys.exit")
    @patch("builtins.print")
    def test_main_missing_env_vars(self, mock_print, mock_exit, mock_env):
        """Test main with missing environment variables."""
        mock_env.return_value = None

        main()

        mock_exit.assert_called_with(1)

    @patch("suggest_fixes.os.environ.get")
    @patch("suggest_fixes.sys.exit")
    @patch("builtins.print")
    def test_main_invalid_pr_number(self, mock_print, mock_exit, mock_env):
        """Test main with invalid PR number."""
        env_values = {
            "GITHUB_TOKEN": "token",
            "PR_NUMBER": "invalid",
            "REPO_OWNER": "owner",
            "REPO_NAME": "repo",
        }
        mock_env.side_effect = lambda key: env_values.get(key)

        main()

        mock_exit.assert_called_with(1)


# Additional edge case tests
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_extract_code_suggestions_malformed(self):
        """Test extracting from malformed code blocks."""
        comment = "```suggestion\nincomplete"
        result = extract_code_suggestions(comment)
        # Should handle gracefully
        assert isinstance(result, list)

    def test_categorize_comment_multiple_keywords(self):
        """Test categorizing with multiple matching keywords."""
        # Should return first match (critical)
        category, _ = categorize_comment("This is a critical bug")
        assert category == "critical"

    def test_parse_review_comments_with_code_suggestions(self):
        """Test parsing comments with code suggestions."""
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 1
        mock_comment.user.login = "reviewer"
        mock_comment.body = "Please use `newValue`"
        mock_comment.created_at = "2024-01-01"
        mock_comment.path = "file.py"
        mock_comment.original_line = 10
        mock_comment.html_url = "url"

        mock_pr.get_review_comments.return_value = [mock_comment]
        mock_pr.get_reviews.return_value = []

        result = parse_review_comments(mock_pr, ["please"])

        assert len(result) == 1
        assert len(result[0]["code_suggestions"]) > 0
        assert result[0]["code_suggestions"][0]["content"] == "newValue"

    def test_generate_fix_proposals_with_code_suggestions(self):
        """Test generating proposals with code suggestions."""
        items = [
            {
                "id": 1,
                "author": "user",
                "body": "Please fix",
                "category": "bug",
                "priority": 1,
                "file": "test.py",
                "line": 10,
                "code_suggestions": [{"type": "code_suggestion", "content": "const x = 1;"}],
                "url": "url",
                "created_at": "2024-01-01",
            }
        ]

        result = generate_fix_proposals(items)

        assert "Suggested Code:" in result
        assert "const x = 1;" in result
