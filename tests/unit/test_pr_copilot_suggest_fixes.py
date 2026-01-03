# pylint: disable=redefined-outer-name, unused-argument
"""
Unit tests for PR Copilot suggest_fixes.py script.

Tests review comment parsing, categorization, and fix proposal generation.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from suggest_fixes import (
    categorize_comment,
    extract_code_suggestions,
    generate_fix_proposals,
    is_actionable,
    load_config,
    parse_review_comments,
)

sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts"))


def test_extract_code_suggestions_with_suggestion_block():
    """Test extracting code suggestions from suggestion blocks."""
    comment = """
Please change this:
```suggestion
def new_function():
    return True
```
"""
    suggestions = extract_code_suggestions(comment)

    assert len(suggestions) == 1
    assert suggestions[0]["type"] == "code_suggestion"
    assert "def new_function()" in suggestions[0]["content"]


def test_extract_code_suggestions_inline():
    """Test extracting inline code suggestions."""
    comment = "You should use `const` instead of `var` here"
    suggestions = extract_code_suggestions(comment)

    assert len(suggestions) == 1
    assert suggestions[0]["type"] == "inline_suggestion"
    assert suggestions[0]["content"] == "const"


def test_extract_code_suggestions_multiple():
    """Test extracting multiple code suggestions."""
    comment = """
Change to `async/await` and replace with `Promise.all()`
```suggestion
await Promise.all(tasks)
```
"""
    suggestions = extract_code_suggestions(comment)

    assert len(suggestions) == 3


def test_extract_code_suggestions_none():
    """Test extracting code suggestions when none exist."""
    comment = "This looks good to me"
    suggestions = extract_code_suggestions(comment)

    assert len(suggestions) == 0


def test_categorize_comment_critical():
    """Test categorizing critical security comments."""
    comment = "This has a security vulnerability that could be exploited"
    category, priority = categorize_comment(comment)

    assert category == "critical"
    assert priority == 1


def test_categorize_comment_bug():
    """Test categorizing bug-related comments."""
    comment = "This code has a bug that causes the test to fail"
    category, priority = categorize_comment(comment)

    assert category == "bug"
    assert priority == 1


def test_categorize_comment_question():
    """Test categorizing question comments."""
    comment = "Why did you choose this approach? Can you explain?"
    category, priority = categorize_comment(comment)

    assert category == "question"
    assert priority == 3


def test_categorize_comment_style():
    """Test categorizing style-related comments."""
    comment = "Please follow the naming convention for this variable"
    category, priority = categorize_comment(comment)

    assert category == "style"
    assert priority == 3


def test_categorize_comment_improvement():
    """Test categorizing improvement suggestions."""
    comment = "Consider refactoring this to improve performance"
    category, priority = categorize_comment(comment)

    assert category == "improvement"
    assert priority == 2


def test_categorize_comment_default():
    """Test default categorization for generic comments."""
    comment = "This is a general comment"
    category, priority = categorize_comment(comment)

    assert category == "improvement"
    assert priority == 2


def test_is_actionable_with_keywords():
    """Test actionable detection with configured keywords."""
    keywords = ["please", "fix", "change", "update"]

    assert is_actionable("Please fix this typo", keywords) is True
    assert is_actionable("You should change this", keywords) is True
    assert is_actionable("Update the documentation", keywords) is True


def test_is_actionable_without_keywords():
    """Test non-actionable comments."""
    keywords = ["please", "fix", "change", "update"]

    assert is_actionable("Looks good to me", keywords) is False
    assert is_actionable("Nice work!", keywords) is False


def test_parse_review_comments_empty():
    """Test parsing review comments when none exist."""
    mock_pr = Mock()
    mock_pr.get_review_comments.return_value = []
    mock_pr.get_reviews.return_value = []

    items = parse_review_comments(mock_pr, ["please", "fix"])

    assert len(items) == 0


def test_parse_review_comments_with_actionable():
    """Test parsing review comments with actionable items."""
    mock_comment = Mock()
    mock_comment.id = 1
    mock_comment.user.login = "reviewer"
    mock_comment.body = "Please fix this typo in the function name"
    mock_comment.created_at = "2024-01-01T00:00:00Z"
    mock_comment.path = "main.py"
    mock_comment.original_line = 42
    mock_comment.html_url = "https://github.com/test/repo/pull/1#discussion_r1"

    mock_pr = Mock()
    mock_pr.get_review_comments.return_value = [mock_comment]
    mock_pr.get_reviews.return_value = []

    items = parse_review_comments(mock_pr, ["please", "fix"])

    assert len(items) == 1
    assert items[0]["author"] == "reviewer"
    assert items[0]["category"] == "style"
    assert items[0]["file"] == "main.py"
    assert items[0]["line"] == 42


def test_parse_review_comments_changes_requested():
    """Test parsing review with changes requested."""
    mock_review = Mock()
    mock_review.id = 2
    mock_review.user.login = "maintainer"
    mock_review.body = "Please refactor this function to improve readability"
    mock_review.state = "CHANGES_REQUESTED"
    mock_review.submitted_at = "2024-01-01T00:00:00Z"
    mock_review.html_url = "https://github.com/test/repo/pull/1#pullrequestreview-2"

    mock_pr = Mock()
    mock_pr.get_review_comments.return_value = []
    mock_pr.get_reviews.return_value = [mock_review]

    items = parse_review_comments(mock_pr, ["please", "refactor"])

    assert len(items) == 1
    assert items[0]["author"] == "maintainer"
    assert items[0]["category"] == "improvement"


def test_parse_review_comments_sorting():
    """Test that comments are sorted by priority and date."""
    mock_comment1 = Mock()
    mock_comment1.id = 1
    mock_comment1.user.login = "user1"
    mock_comment1.body = "This is a critical security issue"
    mock_comment1.created_at = "2024-01-02T00:00:00Z"
    mock_comment1.path = None
    mock_comment1.original_line = None
    mock_comment1.html_url = "url1"

    mock_comment2 = Mock()
    mock_comment2.id = 2
    mock_comment2.user.login = "user2"
    mock_comment2.body = "Please fix this style issue"
    mock_comment2.created_at = "2024-01-01T00:00:00Z"
    mock_comment2.path = None
    mock_comment2.original_line = None
    mock_comment2.html_url = "url2"

    mock_pr = Mock()
    mock_pr.get_review_comments.return_value = [mock_comment2, mock_comment1]
    mock_pr.get_reviews.return_value = []

    items = parse_review_comments(mock_pr, ["please", "fix", "critical", "security"])

    assert len(items) == 2
    assert items[0]["category"] == "critical"
    assert items[1]["category"] == "style"


def test_generate_fix_proposals_empty():
    """Test generating fix proposals with no actionable items."""
    result = generate_fix_proposals([])

    assert "No actionable items found" in result


def test_generate_fix_proposals_single_item():
    """Test generating fix proposals with single item."""
    items = [
        {
            "id": 1,
            "author": "reviewer",
            "body": "Please fix this bug",
            "category": "bug",
            "priority": 1,
            "file": "main.py",
            "line": 10,
            "code_suggestions": [],
            "url": "https://github.com/test/repo/pull/1#discussion_r1",
            "created_at": "2024-01-01T00:00:00Z",
        }
    ]

    result = generate_fix_proposals(items)

    assert "🔧 **Fix Proposals from Review Comments**" in result
    assert "### 🐛 Bug (1)" in result
    assert "**1. Comment by @reviewer**" in result
    assert "Please fix this bug" in result
    assert "**Total Actionable Items:** 1" in result


def test_generate_fix_proposals_multiple_categories():
    """Test generating fix proposals with multiple categories."""
    items = [
        {
            "id": 1,
            "author": "user1",
            "body": "Critical security vulnerability",
            "category": "critical",
            "priority": 1,
            "file": None,
            "line": None,
            "code_suggestions": [],
            "url": "url1",
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 2,
            "author": "user2",
            "body": "Please fix this bug",
            "category": "bug",
            "priority": 1,
            "file": None,
            "line": None,
            "code_suggestions": [],
            "url": "url2",
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 3,
            "author": "user3",
            "body": "Consider refactoring",
            "category": "improvement",
            "priority": 2,
            "file": None,
            "line": None,
            "code_suggestions": [],
            "url": "url3",
            "created_at": "2024-01-01T00:00:00Z",
        },
    ]

    result = generate_fix_proposals(items)

    assert "### 🚨 Critical (1)" in result
    assert "### 🐛 Bug (1)" in result
    assert "### 💡 Improvement (1)" in result
    assert "**Total Actionable Items:** 3" in result
    assert "⚠️ **Priority:** Address critical issues and bugs first." in result


def test_generate_fix_proposals_with_code_suggestions():
    """Test generating fix proposals with code suggestions."""
    items = [
        {
            "id": 1,
            "author": "reviewer",
            "body": "Please update this code",
            "category": "improvement",
            "priority": 2,
            "file": "app.js",
            "line": 25,
            "code_suggestions": [{"type": "inline_suggestion", "content": "const newValue = 42"}],
            "url": "url",
            "created_at": "2024-01-01T00:00:00Z",
        }
    ]

    result = generate_fix_proposals(items)

    assert "**Suggested Code:**" in result
    assert "`const newValue = 42`" in result


def test_generate_fix_proposals_long_body_truncation():
    """Test that long comment bodies are truncated."""
    long_body = "A" * 250

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
            "url": "url",
            "created_at": "2024-01-01T00:00:00Z",
        }
    ]

    result = generate_fix_proposals(items)

    assert "..." in result
    assert len(long_body) > 200


def test_load_config_with_defaults():
    """Test loading config with default values when file not found."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        config = load_config()

        assert "review_handling" in config
        assert "actionable_keywords" in config["review_handling"]
        assert "please" in config["review_handling"]["actionable_keywords"]


def test_load_config_valid_file():
    """Test loading valid config file."""
    mock_config = {"review_handling": {"actionable_keywords": ["custom", "keywords"]}}

    with patch("builtins.open", create=True):
        with patch("yaml.safe_load", return_value=mock_config):
            config = load_config()
            assert config == mock_config
