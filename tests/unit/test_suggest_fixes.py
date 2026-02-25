"""Comprehensive unit tests for suggest_fixes.py.

This module tests all functions in the suggest_fixes.py script including:
- Configuration loading
- Code suggestion extraction from comments
- Comment categorization and priority assignment
- Actionable comment detection
- Review comment parsing
- Fix proposal generation
- Output writing
- Error handling and edge cases
"""

import os
import sys
import tempfile
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

# Add the script directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.github/pr-copilot/scripts"))

# Now we can import directly
import suggest_fixes
from github import GithubException


# --- Fixtures ---


@pytest.fixture
def sample_config():
    """Create a sample configuration."""
    return {
        "review_handling": {
            "actionable_keywords": [
                "please",
                "should",
                "could you",
                "nit",
                "typo",
                "fix",
                "refactor",
                "change",
                "update",
                "add",
                "remove",
            ]
        }
    }


@pytest.fixture
def mock_comment():
    """Create a mock review comment."""
    comment = Mock()
    comment.id = 1
    comment.user = Mock(login="reviewer1")
    comment.body = "Please fix the typo in line 10"
    comment.path = "src/file.py"
    comment.original_line = 10
    comment.html_url = "https://github.com/owner/repo/pull/123#comment-1"
    comment.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return comment


@pytest.fixture
def mock_review():
    """Create a mock review object."""
    review = Mock()
    review.id = 100
    review.user = Mock(login="reviewer2")
    review.body = "Please add more tests"
    review.state = "CHANGES_REQUESTED"
    review.submitted_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
    review.html_url = "https://github.com/owner/repo/pull/123#review-100"
    return review


@pytest.fixture
def mock_pr():
    """Create a mock PR object."""
    pr = Mock()
    pr.number = 123
    return pr


# --- Test load_config Function ---


def test_load_config_file_exists():
    """Test load_config when config file exists."""
    config_data = """
review_handling:
  actionable_keywords:
    - please
    - should
    - fix
"""
    with patch("builtins.open", mock_open(read_data=config_data)):
        with patch("os.path.exists", return_value=True):
            config = suggest_fixes.load_config()

    assert "review_handling" in config
    assert "actionable_keywords" in config["review_handling"]
    assert "please" in config["review_handling"]["actionable_keywords"]


def test_load_config_file_not_found():
    """Test load_config when config file doesn't exist."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        config = suggest_fixes.load_config()

    # Should return defaults
    assert "review_handling" in config
    assert "actionable_keywords" in config["review_handling"]
    assert "please" in config["review_handling"]["actionable_keywords"]


def test_load_config_default_keywords():
    """Test load_config returns expected default keywords."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        config = suggest_fixes.load_config()

    keywords = config["review_handling"]["actionable_keywords"]
    assert "please" in keywords
    assert "should" in keywords
    assert "fix" in keywords
    assert "refactor" in keywords
    assert "change" in keywords


# --- Test extract_code_suggestions Function ---


def test_extract_code_suggestions_with_suggestion_block():
    """Test extracting code from suggestion block."""
    comment = """
Please update the code:
```suggestion
def foo():
    return 42
```
"""
    suggestions = suggest_fixes.extract_code_suggestions(comment)

    assert len(suggestions) == 1
    assert suggestions[0]["type"] == "code_suggestion"
    assert "def foo():" in suggestions[0]["content"]


def test_extract_code_suggestions_with_inline_suggestion():
    """Test extracting inline code suggestions."""
    comment = "This should be `True` instead of False"
    suggestions = suggest_fixes.extract_code_suggestions(comment)

    assert len(suggestions) == 1
    assert suggestions[0]["type"] == "inline_suggestion"
    assert suggestions[0]["content"] == "True"


def test_extract_code_suggestions_multiple_patterns():
    """Test extracting multiple suggestions from same comment."""
    comment = """
Please change to `new_value` and also use `better_name`
```suggestion
def improved():
    pass
```
"""
    suggestions = suggest_fixes.extract_code_suggestions(comment)

    assert len(suggestions) == 3
    types = [s["type"] for s in suggestions]
    assert "code_suggestion" in types
    assert "inline_suggestion" in types


def test_extract_code_suggestions_no_suggestions():
    """Test extract_code_suggestions with no suggestions."""
    comment = "This looks good to me"
    suggestions = suggest_fixes.extract_code_suggestions(comment)

    assert len(suggestions) == 0


def test_extract_code_suggestions_various_keywords():
    """Test inline suggestions with various keywords."""
    test_cases = [
        ("should be `value1`", "value1"),
        ("change to `value2`", "value2"),
        ("replace with `value3`", "value3"),
        ("use `value4` here", "value4"),
    ]

    for comment, expected in test_cases:
        suggestions = suggest_fixes.extract_code_suggestions(comment)
        assert len(suggestions) == 1
        assert suggestions[0]["content"] == expected


def test_extract_code_suggestions_multiline_suggestion():
    """Test extracting multiline code suggestion."""
    comment = """
```suggestion
def calculate(x, y):
    result = x + y
    return result
```
"""
    suggestions = suggest_fixes.extract_code_suggestions(comment)

    assert len(suggestions) == 1
    assert "def calculate" in suggestions[0]["content"]
    assert "result = x + y" in suggestions[0]["content"]


def test_extract_code_suggestions_case_insensitive():
    """Test that keyword matching is case insensitive."""
    comment = "Should Be `VALUE` instead"
    suggestions = suggest_fixes.extract_code_suggestions(comment)

    assert len(suggestions) == 1
    assert suggestions[0]["content"] == "VALUE"


# --- Test categorize_comment Function ---


def test_categorize_comment_security():
    """Test categorizing security-related comments."""
    comment = "This has a security vulnerability"
    category, priority = suggest_fixes.categorize_comment(comment)

    assert category == "critical"
    assert priority == 1


def test_categorize_comment_bug():
    """Test categorizing bug-related comments."""
    comment = "This code has a bug that causes errors"
    category, priority = suggest_fixes.categorize_comment(comment)

    assert category == "bug"
    assert priority == 1


def test_categorize_comment_question():
    """Test categorizing questions."""
    comment = "Why did you choose this approach?"
    category, priority = suggest_fixes.categorize_comment(comment)

    assert category == "question"
    assert priority == 3


def test_categorize_comment_style():
    """Test categorizing style comments."""
    comment = "Please follow the naming convention here"
    category, priority = suggest_fixes.categorize_comment(comment)

    assert category == "style"
    assert priority == 3


def test_categorize_comment_improvement():
    """Test categorizing improvement suggestions."""
    comment = "Consider refactoring this for better performance"
    category, priority = suggest_fixes.categorize_comment(comment)

    assert category == "improvement"
    assert priority == 2


def test_categorize_comment_default():
    """Test categorizing comment with no specific keywords."""
    comment = "Nice work on this feature"
    category, priority = suggest_fixes.categorize_comment(comment)

    assert category == "improvement"
    assert priority == 2


def test_categorize_comment_multiple_keywords():
    """Test categorizing comment with multiple keywords (first match wins)."""
    comment = "This is a critical bug that needs fixing"
    category, priority = suggest_fixes.categorize_comment(comment)

    # "critical" is checked before "bug"
    assert category == "critical"
    assert priority == 1


def test_categorize_comment_various_critical_keywords():
    """Test various critical keywords."""
    critical_comments = [
        "security issue here",
        "vulnerability found",
        "exploit possible",
        "this is critical",
        "breaking change",
    ]

    for comment in critical_comments:
        category, priority = suggest_fixes.categorize_comment(comment)
        assert category == "critical"
        assert priority == 1


def test_categorize_comment_various_bug_keywords():
    """Test various bug keywords."""
    bug_comments = [
        "there is a bug",
        "this causes an error",
        "the test fails",
        "this is broken",
        "incorrect behavior",
        "wrong output",
    ]

    for comment in bug_comments:
        category, priority = suggest_fixes.categorize_comment(comment)
        assert category == "bug"
        assert priority == 1


# --- Test is_actionable Function ---


def test_is_actionable_with_keyword():
    """Test is_actionable returns True for actionable comments."""
    comment = "Please fix this typo"
    keywords = ["please", "should", "fix"]

    assert suggest_fixes.is_actionable(comment, keywords) is True


def test_is_actionable_without_keyword():
    """Test is_actionable returns False for non-actionable comments."""
    comment = "Looks good to me"
    keywords = ["please", "should", "fix"]

    assert suggest_fixes.is_actionable(comment, keywords) is False


def test_is_actionable_case_insensitive():
    """Test is_actionable is case insensitive."""
    comment = "PLEASE fix this"
    keywords = ["please"]

    assert suggest_fixes.is_actionable(comment, keywords) is True


def test_is_actionable_multiple_keywords():
    """Test is_actionable with multiple keywords."""
    comment = "You should refactor this code"
    keywords = ["please", "should", "refactor"]

    assert suggest_fixes.is_actionable(comment, keywords) is True


def test_is_actionable_partial_match():
    """Test is_actionable with partial word match."""
    comment = "This code should be please reviewed"
    keywords = ["please"]

    # Should match because "please" is a complete word in the comment
    assert suggest_fixes.is_actionable(comment, keywords) is True


# --- Test parse_review_comments Function ---


def test_parse_review_comments_single_comment(mock_pr, mock_comment):
    """Test parsing single review comment."""
    mock_pr.get_review_comments.return_value = [mock_comment]
    mock_pr.get_reviews.return_value = []

    keywords = ["please", "fix"]
    items = suggest_fixes.parse_review_comments(mock_pr, keywords)

    assert len(items) == 1
    assert items[0]["author"] == "reviewer1"
    assert items[0]["body"] == "Please fix the typo in line 10"
    assert items[0]["file"] == "src/file.py"
    assert items[0]["line"] == 10


def test_parse_review_comments_multiple_comments(mock_pr):
    """Test parsing multiple review comments."""
    comment1 = Mock()
    comment1.id = 1
    comment1.user = Mock(login="user1")
    comment1.body = "Please fix this"
    comment1.path = "file1.py"
    comment1.original_line = 10
    comment1.html_url = "url1"
    comment1.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    comment2 = Mock()
    comment2.id = 2
    comment2.user = Mock(login="user2")
    comment2.body = "Should update that"
    comment2.path = "file2.py"
    comment2.original_line = 20
    comment2.html_url = "url2"
    comment2.created_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)

    mock_pr.get_review_comments.return_value = [comment1, comment2]
    mock_pr.get_reviews.return_value = []

    keywords = ["please", "should"]
    items = suggest_fixes.parse_review_comments(mock_pr, keywords)

    assert len(items) == 2


def test_parse_review_comments_filters_non_actionable(mock_pr):
    """Test that non-actionable comments are filtered out."""
    actionable = Mock()
    actionable.id = 1
    actionable.user = Mock(login="user1")
    actionable.body = "Please fix this"
    actionable.path = "file.py"
    actionable.original_line = 10
    actionable.html_url = "url"
    actionable.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    non_actionable = Mock()
    non_actionable.id = 2
    non_actionable.user = Mock(login="user2")
    non_actionable.body = "Looks good"
    non_actionable.path = "file.py"
    non_actionable.original_line = 20
    non_actionable.html_url = "url2"
    non_actionable.created_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)

    mock_pr.get_review_comments.return_value = [actionable, non_actionable]
    mock_pr.get_reviews.return_value = []

    keywords = ["please"]
    items = suggest_fixes.parse_review_comments(mock_pr, keywords)

    assert len(items) == 1
    assert items[0]["body"] == "Please fix this"


def test_parse_review_comments_includes_reviews(mock_pr, mock_review):
    """Test parsing includes review-level comments."""
    mock_pr.get_review_comments.return_value = []
    mock_pr.get_reviews.return_value = [mock_review]

    keywords = ["please"]
    items = suggest_fixes.parse_review_comments(mock_pr, keywords)

    assert len(items) == 1
    assert items[0]["author"] == "reviewer2"
    assert items[0]["body"] == "Please add more tests"


def test_parse_review_comments_only_changes_requested_reviews(mock_pr):
    """Test that only CHANGES_REQUESTED reviews are included."""
    review_approved = Mock()
    review_approved.id = 1
    review_approved.user = Mock(login="user1")
    review_approved.body = "Please fix something"
    review_approved.state = "APPROVED"
    review_approved.submitted_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    review_approved.html_url = "url1"

    review_changes = Mock()
    review_changes.id = 2
    review_changes.user = Mock(login="user2")
    review_changes.body = "Please fix this issue"
    review_changes.state = "CHANGES_REQUESTED"
    review_changes.submitted_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
    review_changes.html_url = "url2"

    mock_pr.get_review_comments.return_value = []
    mock_pr.get_reviews.return_value = [review_approved, review_changes]

    keywords = ["please"]
    items = suggest_fixes.parse_review_comments(mock_pr, keywords)

    assert len(items) == 1
    assert items[0]["body"] == "Please fix this issue"


def test_parse_review_comments_sorts_by_priority_then_date(mock_pr):
    """Test that comments are sorted by priority then date."""
    # Critical (priority 1), later date - but needs actionable keyword
    comment1 = Mock()
    comment1.id = 1
    comment1.user = Mock(login="user1")
    comment1.body = "Please fix this critical security issue"  # Added "please fix"
    comment1.path = "file.py"
    comment1.original_line = 10
    comment1.html_url = "url1"
    comment1.created_at = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

    # Bug (priority 1), earlier date
    comment2 = Mock()
    comment2.id = 2
    comment2.user = Mock(login="user2")
    comment2.body = "Please fix this bug"
    comment2.path = "file.py"
    comment2.original_line = 20
    comment2.html_url = "url2"
    comment2.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Improvement (priority 2)
    comment3 = Mock()
    comment3.id = 3
    comment3.user = Mock(login="user3")
    comment3.body = "Please refactor this"
    comment3.path = "file.py"
    comment3.original_line = 30
    comment3.html_url = "url3"
    comment3.created_at = datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc)

    mock_pr.get_review_comments.return_value = [comment1, comment2, comment3]
    mock_pr.get_reviews.return_value = []

    keywords = ["please", "fix", "refactor"]
    items = suggest_fixes.parse_review_comments(mock_pr, keywords)

    assert len(items) == 3
    # Should be sorted: priority 1 (bug first by date, then critical), then priority 2
    assert items[0]["body"] == "Please fix this bug"  # Priority 1, earliest
    assert items[1]["body"] == "Please fix this critical security issue"  # Priority 1, later
    assert items[2]["body"] == "Please refactor this"  # Priority 2


def test_parse_review_comments_includes_code_suggestions(mock_pr):
    """Test that code suggestions are extracted and included."""
    comment = Mock()
    comment.id = 1
    comment.user = Mock(login="user1")
    comment.body = "Please change to `new_value`"
    comment.path = "file.py"
    comment.original_line = 10
    comment.html_url = "url"
    comment.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    mock_pr.get_review_comments.return_value = [comment]
    mock_pr.get_reviews.return_value = []

    keywords = ["please"]
    items = suggest_fixes.parse_review_comments(mock_pr, keywords)

    assert len(items) == 1
    assert len(items[0]["code_suggestions"]) == 1
    assert items[0]["code_suggestions"][0]["content"] == "new_value"


def test_parse_review_comments_no_file_or_line(mock_pr, mock_review):
    """Test parsing review-level comments without file/line info."""
    # Review objects don't have path or original_line attributes
    # Remove these attributes if they exist on the mock
    if hasattr(mock_review, 'path'):
        delattr(mock_review, 'path')
    if hasattr(mock_review, 'original_line'):
        delattr(mock_review, 'original_line')

    mock_pr.get_review_comments.return_value = []
    mock_pr.get_reviews.return_value = [mock_review]

    keywords = ["please"]
    items = suggest_fixes.parse_review_comments(mock_pr, keywords)

    assert len(items) == 1
    assert items[0]["file"] is None
    assert items[0]["line"] is None


# --- Test formatting helper functions ---


def test_format_code_suggestions_with_code_block():
    """Test _format_code_suggestions with code block."""
    suggestions = [{"type": "code_suggestion", "content": "def foo():\n    pass"}]

    result = suggest_fixes._format_code_suggestions(suggestions)

    assert "**Suggested Code:**" in result
    assert "```" in result
    assert "def foo():" in result


def test_format_code_suggestions_with_inline():
    """Test _format_code_suggestions with inline suggestion."""
    suggestions = [{"type": "inline_suggestion", "content": "new_value"}]

    result = suggest_fixes._format_code_suggestions(suggestions)

    assert "**Suggested Code:**" in result
    assert "`new_value`" in result


def test_format_code_suggestions_mixed():
    """Test _format_code_suggestions with mixed types."""
    suggestions = [
        {"type": "code_suggestion", "content": "def foo():\n    pass"},
        {"type": "inline_suggestion", "content": "bar"},
    ]

    result = suggest_fixes._format_code_suggestions(suggestions)

    assert "def foo():" in result
    assert "`bar`" in result


def test_format_item_basic():
    """Test _format_item with basic item."""
    item = {
        "author": "reviewer1",
        "body": "Please fix this issue",
        "priority": 1,
        "file": "src/file.py",
        "line": 10,
        "code_suggestions": [],
        "url": "https://github.com/owner/repo/pull/123#comment-1",
        "category": "bug",
    }

    result = suggest_fixes._format_item(1, item)

    assert "**1. Comment by @reviewer1**" in result
    assert "**Location:** `src/file.py:10`" in result
    assert "**Priority:** 🔴 High" in result
    assert "**Feedback:** Please fix this issue" in result
    assert "[View Comment](https://github.com/owner/repo/pull/123#comment-1)" in result


def test_format_item_long_body_truncation():
    """Test _format_item truncates long comment bodies."""
    item = {
        "author": "reviewer1",
        "body": "A" * 250,  # 250 characters
        "priority": 2,
        "file": None,
        "line": None,
        "code_suggestions": [],
        "url": "url",
        "category": "improvement",
    }

    result = suggest_fixes._format_item(1, item)

    # Should truncate to 200 chars + "..."
    assert "A" * 200 in result
    assert "..." in result
    assert len(result.split("**Feedback:**")[1].split("\n")[0].strip()) <= 204  # 200 + "..."


def test_format_item_no_file_or_line():
    """Test _format_item without file/line information."""
    item = {
        "author": "reviewer1",
        "body": "General comment",
        "priority": 3,
        "file": None,
        "line": None,
        "code_suggestions": [],
        "url": "url",
        "category": "question",
    }

    result = suggest_fixes._format_item(1, item)

    assert "**Location:**" not in result
    assert "**Priority:** 🟢 Low" in result


def test_format_item_with_code_suggestions():
    """Test _format_item with code suggestions."""
    item = {
        "author": "reviewer1",
        "body": "Please update",
        "priority": 2,
        "file": "file.py",
        "line": 10,
        "code_suggestions": [{"type": "inline_suggestion", "content": "new_value"}],
        "url": "url",
        "category": "improvement",
    }

    result = suggest_fixes._format_item(1, item)

    assert "**Suggested Code:**" in result
    assert "`new_value`" in result


def test_generate_summary_basic():
    """Test _generate_summary with basic items."""
    items = [
        {"category": "bug", "priority": 1},
        {"category": "improvement", "priority": 2},
        {"category": "style", "priority": 3},
    ]

    result = suggest_fixes._generate_summary(items)

    assert "**Total Actionable Items:** 3" in result
    assert "**Bugs:** 1" in result
    assert "**Improvements:** 1" in result
    assert "**Style:** 1" in result


def test_generate_summary_with_critical():
    """Test _generate_summary with critical items."""
    items = [{"category": "critical", "priority": 1}, {"category": "bug", "priority": 1}]

    result = suggest_fixes._generate_summary(items)

    assert "**Critical Issues:** 1" in result
    assert "**Bugs:** 1" in result
    assert "⚠️ **Priority:** Address critical issues and bugs first." in result


def test_generate_summary_no_critical_or_bugs():
    """Test _generate_summary without critical issues or bugs."""
    items = [{"category": "improvement", "priority": 2}, {"category": "style", "priority": 3}]

    result = suggest_fixes._generate_summary(items)

    assert "Critical Issues:" not in result
    assert "Bugs:" not in result
    assert "Address critical issues and bugs first" not in result


def test_generate_summary_counts_categories():
    """Test _generate_summary correctly counts categories."""
    items = [
        {"category": "bug", "priority": 1},
        {"category": "bug", "priority": 1},
        {"category": "improvement", "priority": 2},
        {"category": "improvement", "priority": 2},
        {"category": "improvement", "priority": 2},
    ]

    result = suggest_fixes._generate_summary(items)

    assert "**Bugs:** 2" in result
    assert "**Improvements:** 3" in result


# --- Test generate_fix_proposals Function ---


def test_generate_fix_proposals_no_items():
    """Test generate_fix_proposals with no actionable items."""
    result = suggest_fixes.generate_fix_proposals([])

    assert "No actionable items found" in result


def test_generate_fix_proposals_single_item():
    """Test generate_fix_proposals with single item."""
    items = [
        {
            "category": "bug",
            "priority": 1,
            "author": "reviewer1",
            "body": "Please fix this bug",
            "file": "file.py",
            "line": 10,
            "code_suggestions": [],
            "url": "url",
        }
    ]

    result = suggest_fixes.generate_fix_proposals(items)

    assert "🔧 **Fix Proposals from Review Comments**" in result
    assert "### 🐛 Bug (1)" in result
    assert "Comment by @reviewer1" in result


def test_generate_fix_proposals_multiple_categories():
    """Test generate_fix_proposals with multiple categories."""
    items = [
        {
            "category": "critical",
            "priority": 1,
            "author": "user1",
            "body": "Security issue",
            "file": None,
            "line": None,
            "code_suggestions": [],
            "url": "url1",
        },
        {
            "category": "bug",
            "priority": 1,
            "author": "user2",
            "body": "Bug found",
            "file": None,
            "line": None,
            "code_suggestions": [],
            "url": "url2",
        },
        {
            "category": "improvement",
            "priority": 2,
            "author": "user3",
            "body": "Refactor suggestion",
            "file": None,
            "line": None,
            "code_suggestions": [],
            "url": "url3",
        },
    ]

    result = suggest_fixes.generate_fix_proposals(items)

    assert "### 🚨 Critical (1)" in result
    assert "### 🐛 Bug (1)" in result
    assert "### 💡 Improvement (1)" in result


def test_generate_fix_proposals_maintains_order():
    """Test generate_fix_proposals maintains priority order."""
    items = [
        {"category": "style", "priority": 3, "author": "u1", "body": "Style", "file": None, "line": None, "code_suggestions": [], "url": "url1"},
        {"category": "critical", "priority": 1, "author": "u2", "body": "Critical", "file": None, "line": None, "code_suggestions": [], "url": "url2"},
        {"category": "improvement", "priority": 2, "author": "u3", "body": "Improve", "file": None, "line": None, "code_suggestions": [], "url": "url3"},
    ]

    result = suggest_fixes.generate_fix_proposals(items)

    # Check order: critical, bug, improvement, style, question
    critical_pos = result.find("### 🚨 Critical")
    improvement_pos = result.find("### 💡 Improvement")
    style_pos = result.find("### 🎨 Style")

    assert critical_pos < improvement_pos < style_pos


def test_generate_fix_proposals_includes_summary():
    """Test generate_fix_proposals includes summary."""
    items = [
        {"category": "bug", "priority": 1, "author": "u1", "body": "Bug", "file": None, "line": None, "code_suggestions": [], "url": "url1"},
    ]

    result = suggest_fixes.generate_fix_proposals(items)

    assert "**Summary:**" in result
    assert "**Total Actionable Items:** 1" in result
    assert "Generated by PR Copilot Fix Suggestion Tool" in result


def test_generate_fix_proposals_skips_empty_categories():
    """Test generate_fix_proposals skips categories with no items."""
    items = [
        {"category": "bug", "priority": 1, "author": "u1", "body": "Bug", "file": None, "line": None, "code_suggestions": [], "url": "url1"},
    ]

    result = suggest_fixes.generate_fix_proposals(items)

    # Should not include headers for empty categories
    assert "### 🚨 Critical" not in result
    assert "### 💡 Improvement" not in result
    assert "### 🎨 Style" not in result
    assert "### ❓ Question" not in result


# --- Test write_output Function ---


def test_write_output_to_stdout(capsys):
    """Test write_output writes to stdout."""
    report = "Test fix proposals"

    with patch.dict(os.environ, {}, clear=True):
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_file = mock_open()
            mock_temp.return_value.__enter__ = lambda self: mock_file()
            mock_temp.return_value.__exit__ = lambda self, *args: None
            mock_file.return_value.name = "/tmp/fix_proposals_test.md"

            suggest_fixes.write_output(report)

    captured = capsys.readouterr()
    assert report in captured.out


def test_write_output_to_temp_file():
    """Test write_output writes to temp file."""
    report = "Test report"

    with patch.dict(os.environ, {}, clear=True):
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_file = Mock()
            mock_file.name = "/tmp/test.md"
            mock_temp.return_value.__enter__ = lambda self: mock_file
            mock_temp.return_value.__exit__ = lambda self, *args: None

            suggest_fixes.write_output(report)

            # Verify NamedTemporaryFile was called with correct parameters
            mock_temp.assert_called_once()
            kwargs = mock_temp.call_args[1]
            assert kwargs["mode"] == "w"
            assert kwargs["delete"] is False
            assert kwargs["suffix"] == ".md"
            assert kwargs["prefix"] == "fix_proposals_"


def test_write_output_to_github_step_summary():
    """Test write_output writes to GITHUB_STEP_SUMMARY."""
    report = "Test report"
    summary_file = "/tmp/github_summary.md"

    with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": summary_file}):
        m = mock_open()
        with patch("builtins.open", m):
            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_file = Mock()
                mock_file.name = "/tmp/test.md"
                mock_temp.return_value.__enter__ = lambda self: mock_file
                mock_temp.return_value.__exit__ = lambda self, *args: None

                suggest_fixes.write_output(report)

        # Check that summary file was opened in append mode
        calls = [str(call) for call in m.call_args_list]
        assert any(summary_file in call for call in calls)


def test_write_output_handles_io_error_temp_file(capsys):
    """Test write_output handles IOError for temp file."""
    report = "Test content"

    with patch.dict(os.environ, {}, clear=True):
        with patch("tempfile.NamedTemporaryFile", side_effect=IOError("Disk full")):
            suggest_fixes.write_output(report)

    captured = capsys.readouterr()
    assert "Error writing temp file" in captured.err


def test_write_output_handles_io_error_github_summary(capsys):
    """Test write_output handles IOError for GitHub summary."""
    report = "Test content"
    summary_file = "/tmp/summary.md"

    with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": summary_file}):
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_file = Mock()
                mock_file.name = "/tmp/test.md"
                mock_temp.return_value.__enter__ = lambda self: mock_file
                mock_temp.return_value.__exit__ = lambda self, *args: None

                suggest_fixes.write_output(report)

    captured = capsys.readouterr()
    assert "Failed to write to GITHUB_STEP_SUMMARY" in captured.err


# --- Test main Function ---


def test_main_missing_env_vars(capsys):
    """Test main exits with error when env vars are missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            suggest_fixes.main()

        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Missing required environment variables" in captured.err


def test_main_invalid_pr_number(capsys):
    """Test main exits with error when PR_NUMBER is not an integer."""
    env = {"GITHUB_TOKEN": "token", "PR_NUMBER": "not-a-number", "REPO_OWNER": "owner", "REPO_NAME": "repo"}

    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            suggest_fixes.main()

        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "PR_NUMBER must be an integer" in captured.err


def test_main_github_api_error(capsys):
    """Test main handles GitHub API errors."""
    env = {"GITHUB_TOKEN": "token", "PR_NUMBER": "123", "REPO_OWNER": "owner", "REPO_NAME": "repo"}

    with patch.dict(os.environ, env, clear=True):
        with patch("suggest_fixes.load_config", return_value={"review_handling": {"actionable_keywords": ["please"]}}):
            with patch("suggest_fixes.Github") as mock_github_class:
                mock_github = Mock()
                mock_github_class.return_value = mock_github
                mock_github.get_repo.side_effect = GithubException(
                    status=404, data={"message": "Not Found"}, headers={}
                )

                with pytest.raises(SystemExit) as exc_info:
                    suggest_fixes.main()

                assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "GitHub API Error" in captured.err


def test_main_success_flow(mock_pr, mock_comment, capsys):
    """Test main executes successfully."""
    env = {"GITHUB_TOKEN": "token", "PR_NUMBER": "123", "REPO_OWNER": "owner", "REPO_NAME": "repo"}

    with patch.dict(os.environ, env, clear=True):
        with patch("suggest_fixes.load_config") as mock_config:
            mock_config.return_value = {"review_handling": {"actionable_keywords": ["please"]}}

            with patch("suggest_fixes.Github") as mock_github_class:
                with patch("tempfile.NamedTemporaryFile") as mock_temp:
                    mock_file = Mock()
                    mock_file.name = "/tmp/test.md"
                    mock_temp.return_value.__enter__ = lambda self: mock_file
                    mock_temp.return_value.__exit__ = lambda self, *args: None

                    # Setup mocks
                    mock_github = Mock()
                    mock_repo = Mock()

                    mock_github_class.return_value = mock_github
                    mock_github.get_repo.return_value = mock_repo
                    mock_repo.get_pull.return_value = mock_pr

                    mock_pr.get_review_comments.return_value = [mock_comment]
                    mock_pr.get_reviews.return_value = []

                    suggest_fixes.main()

    captured = capsys.readouterr()
    assert "Parsing review comments for PR #123" in captured.err


def test_main_generic_exception(capsys):
    """Test main handles generic exceptions."""
    env = {"GITHUB_TOKEN": "token", "PR_NUMBER": "123", "REPO_OWNER": "owner", "REPO_NAME": "repo"}

    with patch.dict(os.environ, env, clear=True):
        # Patch load_config to return valid config, then patch Github to raise exception
        with patch("suggest_fixes.load_config") as mock_config:
            mock_config.return_value = {"review_handling": {"actionable_keywords": ["please"]}}

            with patch("suggest_fixes.Github", side_effect=Exception("Unexpected error")):
                with pytest.raises(SystemExit) as exc_info:
                    suggest_fixes.main()

                assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Unexpected Error" in captured.err


def test_main_with_no_actionable_items(mock_pr, capsys):
    """Test main when no actionable items are found."""
    env = {"GITHUB_TOKEN": "token", "PR_NUMBER": "123", "REPO_OWNER": "owner", "REPO_NAME": "repo"}

    # Comment without actionable keywords
    non_actionable = Mock()
    non_actionable.id = 1
    non_actionable.user = Mock(login="user")
    non_actionable.body = "Looks good"
    non_actionable.created_at = datetime.now(timezone.utc)

    with patch.dict(os.environ, env, clear=True):
        with patch("suggest_fixes.load_config") as mock_config:
            mock_config.return_value = {"review_handling": {"actionable_keywords": ["please"]}}

            with patch("suggest_fixes.Github") as mock_github_class:
                with patch("tempfile.NamedTemporaryFile") as mock_temp:
                    mock_file = Mock()
                    mock_file.name = "/tmp/test.md"
                    mock_temp.return_value.__enter__ = lambda self: mock_file
                    mock_temp.return_value.__exit__ = lambda self, *args: None

                    mock_github = Mock()
                    mock_repo = Mock()

                    mock_github_class.return_value = mock_github
                    mock_github.get_repo.return_value = mock_repo
                    mock_repo.get_pull.return_value = mock_pr

                    mock_pr.get_review_comments.return_value = [non_actionable]
                    mock_pr.get_reviews.return_value = []

                    suggest_fixes.main()

    captured = capsys.readouterr()
    assert "No actionable items found" in captured.out


# --- Edge Cases and Integration Tests ---


def test_extract_code_suggestions_empty_string():
    """Test extract_code_suggestions with empty string."""
    suggestions = suggest_fixes.extract_code_suggestions("")
    assert len(suggestions) == 0


def test_categorize_comment_empty_string():
    """Test categorize_comment with empty string."""
    category, priority = suggest_fixes.categorize_comment("")
    assert category == "improvement"
    assert priority == 2


def test_is_actionable_empty_keywords():
    """Test is_actionable with empty keyword list."""
    result = suggest_fixes.is_actionable("Please fix this", [])
    assert result is False


def test_parse_review_comments_empty_pr(mock_pr):
    """Test parse_review_comments with PR having no comments."""
    mock_pr.get_review_comments.return_value = []
    mock_pr.get_reviews.return_value = []

    items = suggest_fixes.parse_review_comments(mock_pr, ["please"])
    assert len(items) == 0


def test_format_item_all_priority_levels():
    """Test _format_item displays correct emoji for all priority levels."""
    priorities = [(1, "🔴 High"), (2, "🟡 Medium"), (3, "🟢 Low"), (999, "Medium")]

    for priority, expected in priorities:
        item = {
            "author": "user",
            "body": "test",
            "priority": priority,
            "file": None,
            "line": None,
            "code_suggestions": [],
            "url": "url",
            "category": "improvement",
        }
        result = suggest_fixes._format_item(1, item)
        assert expected in result


def test_generate_fix_proposals_with_all_categories():
    """Test generate_fix_proposals with all category types."""
    items = [
        {"category": "critical", "priority": 1, "author": "u1", "body": "Critical", "file": None, "line": None, "code_suggestions": [], "url": "u1"},
        {"category": "bug", "priority": 1, "author": "u2", "body": "Bug", "file": None, "line": None, "code_suggestions": [], "url": "u2"},
        {"category": "improvement", "priority": 2, "author": "u3", "body": "Improve", "file": None, "line": None, "code_suggestions": [], "url": "u3"},
        {"category": "style", "priority": 3, "author": "u4", "body": "Style", "file": None, "line": None, "code_suggestions": [], "url": "u4"},
        {"category": "question", "priority": 3, "author": "u5", "body": "Question", "file": None, "line": None, "code_suggestions": [], "url": "u5"},
    ]

    result = suggest_fixes.generate_fix_proposals(items)

    assert "### 🚨 Critical (1)" in result
    assert "### 🐛 Bug (1)" in result
    assert "### 💡 Improvement (1)" in result
    assert "### 🎨 Style (1)" in result
    assert "### ❓ Question (1)" in result


def test_extract_code_suggestions_multiple_suggestion_blocks():
    """Test extracting multiple suggestion blocks from same comment."""
    comment = """
First suggestion:
```suggestion
code1
```

Second suggestion:
```suggestion
code2
```
"""
    suggestions = suggest_fixes.extract_code_suggestions(comment)

    assert len(suggestions) == 2
    assert all(s["type"] == "code_suggestion" for s in suggestions)


def test_comment_with_very_long_body():
    """Test handling of very long comment bodies."""
    long_body = "A" * 1000
    item = {
        "author": "user",
        "body": long_body,
        "priority": 1,
        "file": None,
        "line": None,
        "code_suggestions": [],
        "url": "url",
        "category": "bug",
    }

    result = suggest_fixes._format_item(1, item)
    # Should be truncated to 200 chars
    assert len(item["body"]) == 1000
    feedback_line = [line for line in result.split("\n") if "**Feedback:**" in line][0]
    # Feedback should be truncated
    assert "..." in feedback_line


def test_unicode_characters_in_comments():
    """Test handling of unicode characters in comments."""
    comment = "Please fix this 🐛 bug with émojis and spëcial çhars"

    suggestions = suggest_fixes.extract_code_suggestions(comment)
    category, priority = suggest_fixes.categorize_comment(comment)
    is_act = suggest_fixes.is_actionable(comment, ["please"])

    # Should handle unicode without errors
    assert is_act is True
    assert category == "bug"