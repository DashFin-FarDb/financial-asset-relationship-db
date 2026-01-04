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

from analyze_pr import (AnalysisData, analyze_pr_files,  # noqa: E402
                        assess_complexity, categorize_filename,
                        find_related_issues, find_scope_issues,
                        generate_markdown, load_config)

import pytest  # noqa: E402


@pytest.fixture
def mock_config():
    """Provide a mock configuration for tests."""
    return {
        "scope": {
            "warn_on_long_title": 80,
            "max_files_changed": 20,
            "max_total_changes": 500,
            "max_file_types_changed": 5,
        },
    }


@pytest.fixture
def mock_pr():
    """Create a mock PR object."""
    pr = Mock()
    pr.number = 1
    pr.user = Mock(login="testuser")
    pr.title = "Add new feature"
    pr.body = "This PR implements a new feature. Fixes #123"
    pr.commits = 3
    pr.html_url = "https://github.com/test/repo"
    return pr


@pytest.fixture
def mock_pr_files():
    """Create mock PR file objects."""
    file1 = Mock()
    file1.filename = "src/auth.py"
    file1.additions = 50
    file1.deletions = 10

    file2 = Mock()
    file2.filename = "tests/test_auth.py"
    file2.additions = 30
    file2.deletions = 5

    file3 = Mock()
    file3.filename = "README.md"
    file3.additions = 10
    file3.deletions = 2

    return [file1, file2, file3]


# --- File Categorization Tests ---


def test_categorize_filename_python():
    """Test categorization of Python files."""
    assert categorize_filename("src/main.py") == "python"
    assert categorize_filename("lib/utils.py") == "python"


def test_categorize_filename_test():
    """Test categorization of test files."""
    assert categorize_filename("tests/test_main.py") == "test"
    assert categorize_filename("src/test_utils.py") == "test"
    assert categorize_filename("spec/feature_spec.js") == "test"


def test_categorize_filename_workflow():
    """Test categorization of workflow files."""
    assert categorize_filename(".github/workflows/ci.yml") == "workflow"
    assert categorize_filename(".github/workflows/deploy.yaml") == "workflow"


def test_categorize_filename_documentation():
    """Test categorization of documentation files."""
    assert categorize_filename("README.md") == "documentation"
    assert categorize_filename("docs/guide.rst") == "documentation"
    assert categorize_filename("CHANGELOG.txt") == "documentation"


def test_categorize_filename_config():
    """Test categorization of config files."""
    assert categorize_filename("package.json") == "config"
    assert categorize_filename("config.yaml") == "config"
    assert categorize_filename("settings.toml") == "config"


def test_categorize_filename_javascript():
    """Test categorization of JavaScript files."""
    assert categorize_filename("src/app.js") == "javascript"
    assert categorize_filename("components/Button.jsx") == "javascript"
    assert categorize_filename("utils.ts") == "javascript"


def test_categorize_filename_other():
    """Test categorization of unknown file types."""
    assert categorize_filename("data.bin") == "other"
    assert categorize_filename("image.png") == "other"


# --- File Analysis Tests ---


def test_analyze_pr_files(mock_pr_files):
    """Test PR file analysis."""
    result = analyze_pr_files(mock_pr_files)

    assert result["file_count"] == 3
    assert result["total_additions"] == 90
    assert result["total_deletions"] == 17
    assert result["total_changes"] == 107
    assert "python" in result["file_categories"]
    assert "test" in result["file_categories"]
    assert "documentation" in result["file_categories"]
    assert result["has_large_files"] is False


def test_analyze_pr_files_with_large_file():
    """Test file analysis with large files."""
    large_file = Mock()
    large_file.filename = "src/large.py"
    large_file.additions = 600
    large_file.deletions = 100

    result = analyze_pr_files([large_file])

    assert result["file_count"] == 1
    assert result["has_large_files"] is True
    assert len(result["large_files"]) == 1
    assert result["large_files"][0]["filename"] == "src/large.py"
    assert result["large_files"][0]["changes"] == 700


def test_analyze_pr_files_empty():
    """Test file analysis with no files."""
    result = analyze_pr_files([])

    assert result["file_count"] == 0
    assert result["total_additions"] == 0
    assert result["total_deletions"] == 0
    assert result["has_large_files"] is False


# --- Complexity Assessment Tests ---


def test_assess_complexity_low():
    """Test complexity assessment for simple changes."""
    file_data = {
        "file_count": 3,
        "total_changes": 100,
        "has_large_files": False,
        "large_files": [],
    }
    score, risk = assess_complexity(file_data, 2)

    assert risk == "Low"
    assert score < 40


def test_assess_complexity_medium():
    """Test complexity assessment for moderate changes."""
    file_data = {
        "file_count": 15,
        "total_changes": 600,
        "has_large_files": False,
        "large_files": [],
    }
    score, risk = assess_complexity(file_data, 12)

    assert risk == "Medium"
    assert 40 <= score < 70


def test_assess_complexity_high():
    """Test complexity assessment for complex changes."""
    file_data = {
        "file_count": 30,
        "total_changes": 1500,
        "has_large_files": True,
        "large_files": [{"filename": "large.py", "changes": 800}],
    }
    score, risk = assess_complexity(file_data, 25)

    assert risk == "High"
    assert score >= 70


def test_assess_complexity_with_large_files():
    """Test complexity with large file penalty."""
    file_data = {
        "file_count": 5,
        "total_changes": 300,
        "has_large_files": True,
        "large_files": [
            {"filename": "file1.py", "changes": 600},
            {"filename": "file2.py", "changes": 700},
        ],
    }
    score, risk = assess_complexity(file_data, 5)

    assert score > 20  # Should have large file penalty


# --- Scope Issue Detection Tests ---


def test_find_scope_issues_long_title(mock_config):
    """Test detection of overly long PR titles."""
    long_title = "A" * 100
    file_data = {"file_count": 5, "total_changes": 100, "file_categories": {"python": 2}}

    issues = find_scope_issues(long_title, file_data, mock_config)

    assert len(issues) > 0
    assert any("Title too long" in issue for issue in issues)


def test_find_scope_issues_multiple_responsibilities(mock_config):
    """Test detection of titles suggesting multiple responsibilities."""
    title = "Add feature and fix bug"
    file_data = {"file_count": 5, "total_changes": 100, "file_categories": {"python": 2}}

    issues = find_scope_issues(title, file_data, mock_config)

    assert any("multiple responsibilities" in issue for issue in issues)


def test_find_scope_issues_too_many_files(mock_config):
    """Test detection of PRs with too many files."""
    title = "Short title"
    file_data = {"file_count": 25, "total_changes": 100, "file_categories": {"python": 10}}

    issues = find_scope_issues(title, file_data, mock_config)

    assert any("Too many files" in issue for issue in issues)


def test_find_scope_issues_large_changeset(mock_config):
    """Test detection of PRs with too many line changes."""
    title = "Short title"
    file_data = {"file_count": 5, "total_changes": 600, "file_categories": {"python": 2}}

    issues = find_scope_issues(title, file_data, mock_config)

    assert any("Large changeset" in issue for issue in issues)


def test_find_scope_issues_high_context_switching(mock_config):
    """Test detection of high context switching."""
    title = "Short title"
    file_data = {
        "file_count": 10,
        "total_changes": 200,
        "file_categories": {
            "python": 2,
            "javascript": 2,
            "config": 2,
            "documentation": 2,
            "test": 2,
            "style": 2,
        },
    }

    issues = find_scope_issues(title, file_data, mock_config)

    assert any("context switching" in issue for issue in issues)


def test_find_scope_issues_clean_pr(mock_config):
    """Test that clean PRs have no scope issues."""
    title = "Add authentication"
    file_data = {"file_count": 5, "total_changes": 100, "file_categories": {"python": 3, "test": 2}}

    issues = find_scope_issues(title, file_data, mock_config)

    assert len(issues) == 0


# --- Related Issues Tests ---


def test_find_related_issues():
    """Test extraction of related issue numbers from PR body."""
    body = "This PR fixes #123 and resolves #456. Closes #789"
    repo_url = "https://github.com/test/repo"

    issues = find_related_issues(body, repo_url)

    assert len(issues) == 3
    issue_numbers = [i["number"] for i in issues]
    assert "123" in issue_numbers
    assert "456" in issue_numbers
    assert "789" in issue_numbers


def test_find_related_issues_no_body():
    """Test with no PR body."""
    issues = find_related_issues(None, "https://github.com/test/repo")
    assert len(issues) == 0


def test_find_related_issues_no_references():
    """Test with body but no issue references."""
    body = "This is a simple PR with no issue references"
    issues = find_related_issues(body, "https://github.com/test/repo")
    assert len(issues) == 0


# --- Configuration Tests ---


def test_load_config_missing_file():
    """Test loading configuration when file doesn't exist."""
    with patch("os.path.exists", return_value=False):
        config = load_config()
        assert isinstance(config, dict)
        assert len(config) == 0


def test_load_config_valid_file():
    """Test loading valid configuration file."""
    mock_config = {"scope": {"warn_on_long_title": 100}}

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", create=True):
            with patch("yaml.safe_load", return_value=mock_config):
                config = load_config()
                assert config == mock_config


# --- Markdown Generation Tests ---


def test_generate_markdown(mock_pr):
    """Test markdown report generation."""
    file_data = {
        "file_count": 3,
        "total_changes": 100,
        "total_additions": 80,
        "total_deletions": 20,
        "file_categories": {"python": 2, "test": 1},
        "large_files": [],
        "has_large_files": False,
    }

    analysis = AnalysisData(
        file_analysis=file_data,
        complexity_score=35,
        risk_level="Low",
        scope_issues=[],
        related_issues=[{"number": "123", "url": "https://github.com/test/repo/issues/123"}],
        commit_count=3,
    )

    markdown = generate_markdown(mock_pr, analysis)

    assert "🔍 **PR Analysis Report**" in markdown
    assert "testuser" in markdown
    assert "Low" in markdown
    assert "3 files" in markdown
    assert "100 lines" in markdown


def test_generate_markdown_with_scope_issues(mock_pr):
    """Test markdown generation with scope issues."""
    file_data = {
        "file_count": 25,
        "total_changes": 800,
        "total_additions": 600,
        "total_deletions": 200,
        "file_categories": {"python": 15, "test": 10},
        "large_files": [{"filename": "large.py", "changes": 600, "additions": 500, "deletions": 100}],
        "has_large_files": True,
    }

    analysis = AnalysisData(
        file_analysis=file_data,
        complexity_score=75,
        risk_level="High",
        scope_issues=["Too many files changed (25 > 20)", "Large changeset (800 lines > 500)"],
        related_issues=[],
        commit_count=15,
    )

    markdown = generate_markdown(mock_pr, analysis)

    assert "High" in markdown
    assert "⚠️ Potential Scope Issues" in markdown
    assert "Too many files" in markdown
    assert "Large changeset" in markdown
    assert "Large Files" in markdown


def test_generate_markdown_medium_risk(mock_pr):
    """Test markdown generation for medium risk PR."""
    file_data = {
        "file_count": 12,
        "total_changes": 400,
        "total_additions": 300,
        "total_deletions": 100,
        "file_categories": {"python": 8, "test": 4},
        "large_files": [],
        "has_large_files": False,
    }

    analysis = AnalysisData(
        file_analysis=file_data,
        complexity_score=50,
        risk_level="Medium",
        scope_issues=[],
        related_issues=[],
        commit_count=8,
    )

    markdown = generate_markdown(mock_pr, analysis)

    assert "Medium" in markdown
    assert "🟡" in markdown
