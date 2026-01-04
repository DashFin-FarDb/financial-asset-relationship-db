# pylint: disable=redefined-outer-name, unused-argument
"""
Unit tests for PR Copilot analyze_pr.py script.

Tests PR complexity analysis, scope validation, and risk assessment functionality.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Add the scripts directory to the path before importing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts"))

from analyze_pr import (AnalysisData, analyze_pr_files, assess_complexity,
                        calculate_score, categorize_filename,
                        find_related_issues, find_scope_issues,
                        generate_markdown, load_config)

import pytest


@pytest.fixture
def mock_config():
    """Provide a mock configuration for tests."""
    return {
        "thresholds": {
            "title_length": 80,
            "files_changed": 20,
            "lines_changed": 500,
        },
        "scope_keywords": {
            "feature": ["add", "new", "implement"],
            "bugfix": ["fix", "bug", "issue"],
            "refactor": ["refactor", "cleanup", "improve"],
        },
    }


@pytest.fixture
def mock_pr_data():
    """Provide mock PR data for tests."""
    return {
        "title": "Add new feature for user authentication",
        "body": "This PR implements user authentication. Fixes #123",
        "files": [
            {"filename": "src/auth.py", "additions": 50, "deletions": 10, "changes": 60},
            {"filename": "tests/test_auth.py", "additions": 30, "deletions": 5, "changes": 35},
        ],
        "commits": 3,
    }


def test_categorize_filename():
    """Test file categorization logic."""
    assert categorize_filename("src/main.py") == "source"
    assert categorize_filename("tests/test_main.py") == "test"
    assert categorize_filename("README.md") == "docs"
    assert categorize_filename(".github/workflows/ci.yml") == "config"
    assert categorize_filename("package.json") == "config"


def test_assess_complexity_low():
    """Test complexity assessment for simple changes."""
    result = assess_complexity(5, 100, 2)
    assert result["level"] == "low"
    assert result["score"] < 30


def test_assess_complexity_medium():
    """Test complexity assessment for moderate changes."""
    result = assess_complexity(10, 300, 5)
    assert result["level"] == "medium"
    assert 30 <= result["score"] < 70


def test_assess_complexity_high():
    """Test complexity assessment for complex changes."""
    result = assess_complexity(25, 800, 15)
    assert result["level"] == "high"
    assert result["score"] >= 70


def test_find_scope_issues_long_title(mock_config):
    """Test detection of overly long PR titles."""
    long_title = "A" * 100
    issues = find_scope_issues(long_title, "", 5, 100, mock_config)
    assert any("title is too long" in issue.lower() for issue in issues)


def test_find_scope_issues_many_files(mock_config):
    """Test detection of PRs with too many files."""
    issues = find_scope_issues("Short title", "", 25, 100, mock_config)
    assert any("many files" in issue.lower() for issue in issues)


def test_find_scope_issues_many_lines(mock_config):
    """Test detection of PRs with too many line changes."""
    issues = find_scope_issues("Short title", "", 5, 600, mock_config)
    assert any("many lines" in issue.lower() for issue in issues)


def test_find_related_issues():
    """Test extraction of related issue numbers from PR body."""
    body = "This PR fixes #123 and resolves #456. Closes #789"
    issues = find_related_issues(body)
    assert "123" in issues
    assert "456" in issues
    assert "789" in issues


def test_calculate_score():
    """Test overall PR score calculation."""
    score = calculate_score(10, 300, 5, 2)
    assert 0 <= score <= 100
    assert isinstance(score, (int, float))


def test_analyze_pr_files(mock_pr_data):
    """Test PR file analysis."""
    result = analyze_pr_files(mock_pr_data["files"])
    assert result["total_files"] == 2
    assert result["total_additions"] == 80
    assert result["total_deletions"] == 15
    assert result["total_changes"] == 95
    assert "source" in result["by_category"]
    assert "test" in result["by_category"]


def test_load_config_with_file():
    """Test loading configuration from a file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("thresholds:\n  title_length: 100\n")
        config_path = f.name

    try:
        config = load_config(config_path)
        assert "thresholds" in config
        assert config["thresholds"]["title_length"] == 100
    finally:
        os.unlink(config_path)


def test_load_config_default():
    """Test loading default configuration when file doesn't exist."""
    config = load_config("nonexistent_file.yml")
    assert "thresholds" in config
    assert isinstance(config["thresholds"], dict)


def test_generate_markdown(mock_pr_data, mock_config):
    """Test markdown report generation."""
    analysis = AnalysisData(
        complexity=assess_complexity(2, 95, 3),
        file_analysis=analyze_pr_files(mock_pr_data["files"]),
        scope_issues=find_scope_issues(
            mock_pr_data["title"],
            mock_pr_data["body"],
            2,
            95,
            mock_config
        ),
        related_issues=find_related_issues(mock_pr_data["body"]),
        score=calculate_score(2, 95, 3, 1)
    )

    markdown = generate_markdown(analysis, mock_pr_data)
    assert "## PR Analysis" in markdown
    assert "Complexity" in markdown
    assert "Files Changed" in markdown
    assert isinstance(markdown, str)
    assert len(markdown) > 0
