# pylint: disable=redefined-outer-name, unused-argument
"""
Unit tests for PR Copilot analyze_pr.py script.

Tests PR complexity analysis, scope validation, and risk assessment functionality.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from analyze_pr import (
    AnalysisData,
    analyze_pr_files,
    assess_complexity,
    calculate_score,
    categorize_filename,
    find_related_issues,
    find_scope_issues,
    generate_markdown,
    load_config,
)

# Add the scripts directory to the path before importing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts"))


@pytest.fixture
def mock_config_file_missing():
    """Mock configuration file that doesn't exist."""
    with patch("os.path.exists", return_value=False):
        yield


@pytest.fixture
def mock_config_file_valid():
    """Mock valid configuration file."""
    mock_config = {"scope": {"warn_on_long_title": 80}}

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", create=True):
            with patch("yaml.safe_load", return_value=mock_config):
                yield mock_config


def test_categorize_filename_python():
    """Test Python file categorization."""
    assert categorize_filename("main.py") == "python"
    assert categorize_filename("src/utils.py") == "python"


def test_categorize_filename_javascript():
    """Test JavaScript/TypeScript file categorization."""
    assert categorize_filename("app.js") == "javascript"
    assert categorize_filename("component.jsx") == "javascript"
    assert categorize_filename("module.ts") == "javascript"
    assert categorize_filename("Component.tsx") == "javascript"


def test_categorize_filename_test():
    """Test test file categorization."""
    assert categorize_filename("test_main.py") == "test"
    assert categorize_filename("main.test.js") == "test"
    assert categorize_filename("spec/user_spec.rb") == "test"


def test_categorize_filename_workflow():
    """Test workflow file categorization (should take precedence over test)."""
    assert categorize_filename(".github/workflows/ci.yml") == "workflow"
    assert categorize_filename(".github/workflows/test.yml") == "workflow"


def test_categorize_filename_config():
    """Test configuration file categorization."""
    assert categorize_filename("config.json") == "config"
    assert categorize_filename("settings.yaml") == "config"
    assert categorize_filename("pyproject.toml") == "config"


def test_categorize_filename_documentation():
    """Test documentation file categorization."""
    assert categorize_filename("README.md") == "documentation"
    assert categorize_filename("docs/guide.rst") == "documentation"


def test_categorize_filename_other():
    """Test unknown file type categorization."""
    assert categorize_filename("binary.exe") == "other"
    assert categorize_filename("data.dat") == "other"


def test_analyze_pr_files_empty():
    """Test analyzing PR with no files."""
    result = analyze_pr_files([])

    assert result["file_count"] == 0
    assert result["total_additions"] == 0
    assert result["total_deletions"] == 0
    assert result["total_changes"] == 0
    assert result["has_large_files"] is False
    assert len(result["large_files"]) == 0


def test_analyze_pr_files_small_changes():
    """Test analyzing PR with small changes."""
    mock_file1 = Mock(filename="main.py", additions=10, deletions=5)
    mock_file2 = Mock(filename="test.py", additions=20, deletions=10)

    result = analyze_pr_files([mock_file1, mock_file2])

    assert result["file_count"] == 2
    assert result["total_additions"] == 30
    assert result["total_deletions"] == 15
    assert result["total_changes"] == 45
    assert result["has_large_files"] is False
    assert "python" in result["file_categories"]
    assert "test" in result["file_categories"]


def test_analyze_pr_files_large_file():
    """Test analyzing PR with large file changes."""
    mock_file = Mock(filename="large.py", additions=600, deletions=100)

    result = analyze_pr_files([mock_file])

    assert result["has_large_files"] is True
    assert len(result["large_files"]) == 1
    assert result["large_files"][0]["filename"] == "large.py"
    assert result["large_files"][0]["changes"] == 700


def test_calculate_score_thresholds():
    """Test score calculation with different thresholds."""
    thresholds = [(100, 30), (50, 20), (10, 10)]

    assert calculate_score(150, thresholds, 5) == 30
    assert calculate_score(75, thresholds, 5) == 20
    assert calculate_score(25, thresholds, 5) == 10
    assert calculate_score(5, thresholds, 5) == 5


def test_assess_complexity_low():
    """Test complexity assessment for low-risk PR."""
    file_data = {
        "file_count": 3,
        "total_changes": 50,
        "has_large_files": False,
        "large_files": [],
    }

    score, risk = assess_complexity(file_data, commit_count=2)

    assert risk == "Low"
    assert score < 40


def test_assess_complexity_medium():
    """Test complexity assessment for medium-risk PR."""
    file_data = {
        "file_count": 15,
        "total_changes": 600,
        "has_large_files": False,
        "large_files": [],
    }

    score, risk = assess_complexity(file_data, commit_count=12)

    assert risk == "Medium"
    assert 40 <= score < 70


def test_assess_complexity_high():
    """Test complexity assessment for high-risk PR."""
    file_data = {
        "file_count": 60,
        "total_changes": 2500,
        "has_large_files": True,
        "large_files": [{"filename": "big.py", "changes": 1000}],
    }

    score, risk = assess_complexity(file_data, commit_count=55)

    assert risk == "High"
    assert score >= 70


def test_assess_complexity_with_large_files():
    """Test complexity penalty for large files."""
    file_data_no_large = {
        "file_count": 10,
        "total_changes": 500,
        "has_large_files": False,
        "large_files": [],
    }

    file_data_with_large = {
        "file_count": 10,
        "total_changes": 500,
        "has_large_files": True,
        "large_files": [{"filename": "big1.py"}, {"filename": "big2.py"}],
    }

    score_no_large, _ = assess_complexity(file_data_no_large, commit_count=10)
    score_with_large, _ = assess_complexity(file_data_with_large, commit_count=10)

    assert score_with_large > score_no_large


def test_find_scope_issues_long_title():
    """Test scope issue detection for long titles."""
    config = {"scope": {"warn_on_long_title": 72}}
    file_data = {"file_count": 5, "total_changes": 100, "file_categories": {"python": 5}}

    long_title = "A" * 100
    issues = find_scope_issues(long_title, file_data, config)

    assert any("Title too long" in issue for issue in issues)


def test_find_scope_issues_multiple_responsibilities():
    """Test scope issue detection for multi-purpose PRs."""
    config = {"scope": {"warn_on_long_title": 72}}
    file_data = {"file_count": 5, "total_changes": 100, "file_categories": {"python": 5}}

    title = "Add feature and fix bug"
    issues = find_scope_issues(title, file_data, config)

    assert any("multiple responsibilities" in issue for issue in issues)


def test_find_scope_issues_too_many_files():
    """Test scope issue detection for too many files changed."""
    config = {"scope": {"warn_on_long_title": 72, "max_files_changed": 20}}
    file_data = {"file_count": 35, "total_changes": 500, "file_categories": {"python": 35}}

    issues = find_scope_issues("Normal title", file_data, config)

    assert any("Too many files" in issue for issue in issues)


def test_find_scope_issues_large_changeset():
    """Test scope issue detection for large changesets."""
    config = {"scope": {"warn_on_long_title": 72, "max_total_changes": 1000}}
    file_data = {"file_count": 10, "total_changes": 2000, "file_categories": {"python": 10}}

    issues = find_scope_issues("Normal title", file_data, config)

    assert any("Large changeset" in issue for issue in issues)


def test_find_scope_issues_context_switching():
    """Test scope issue detection for high context switching."""
    config = {"scope": {"warn_on_long_title": 72, "max_file_types_changed": 3}}
    file_data = {
        "file_count": 10,
        "total_changes": 500,
        "file_categories": {"python": 3, "javascript": 2, "css": 2, "html": 2, "config": 1},
    }

    issues = find_scope_issues("Normal title", file_data, config)

    # Assert exactly one context switching issue is found
    context_switching_issues = [issue for issue in issues if "context switching" in issue]
    assert len(context_switching_issues) == 1
    # Verify the exact content: should report 5 file types changed (exceeds max of 3)
    assert context_switching_issues[0] == "High context switching (5 file types changed)"


def test_find_scope_issues_clean_pr():
    """Test scope issue detection for clean PR."""
    config = {"scope": {"warn_on_long_title": 72, "max_files_changed": 30, "max_total_changes": 1500}}
    file_data = {"file_count": 5, "total_changes": 100, "file_categories": {"python": 5}}

    issues = find_scope_issues("Fix bug in user module", file_data, config)

    assert len(issues) == 0


def test_find_related_issues_simple():
    """Test finding related issues with simple references."""
    pr_body = "This PR fixes #123 and addresses #456"
    repo_url = "https://github.com/test/repo"

    issues = find_related_issues(pr_body, repo_url)

    assert len(issues) == 2
    assert any(i["number"] == "123" for i in issues)
    assert any(i["number"] == "456" for i in issues)


def test_find_related_issues_keywords():
    """Test finding related issues with closing keywords."""
    pr_body = "Closes #100\nResolves #200\nFixes #300"
    repo_url = "https://github.com/test/repo"

    issues = find_related_issues(pr_body, repo_url)

    assert len(issues) == 3


def test_find_related_issues_no_body():
    """Test finding related issues with no PR body."""
    issues = find_related_issues(None, "https://github.com/test/repo")
    assert len(issues) == 0


def test_find_related_issues_no_references():
    """Test finding related issues with no issue references."""
    pr_body = "This is a PR with no issue references"
    issues = find_related_issues(pr_body, "https://github.com/test/repo")
    assert len(issues) == 0


def test_generate_markdown_low_risk():
    """Test markdown generation for low-risk PR."""
    mock_pr = Mock(number=1, user=Mock(login="testuser"))

    data = AnalysisData(
        file_analysis={
            "file_count": 3,
            "total_changes": 50,
            "file_categories": {"python": 3},
            "large_files": [],
        },
        complexity_score=25,
        risk_level="Low",
        scope_issues=[],
        related_issues=[],
        commit_count=2,
    )

    report = generate_markdown(mock_pr, data)

    assert "🔍 **PR Analysis Report**" in report
    assert "🟢 Low" in report
    assert "✅ Low complexity" in report
    assert "🚀 Fast merge candidate" in report


def test_generate_markdown_high_risk():
    """Test markdown generation for high-risk PR."""
    mock_pr = Mock(number=2, user=Mock(login="developer"))

    data = AnalysisData(
        file_analysis={
            "file_count": 50,
            "total_changes": 2000,
            "file_categories": {"python": 30, "javascript": 20},
            "large_files": [{"filename": "big.py", "changes": 1000, "additions": 800, "deletions": 200}],
        },
        complexity_score=85,
        risk_level="High",
        scope_issues=["Title too long (100 > 72)", "Too many files changed (50 > 30)"],
        related_issues=[{"number": "123", "url": "https://github.com/test/repo/issues/123"}],
        commit_count=40,
    )

    report = generate_markdown(mock_pr, data)

    assert "🔴 High" in report
    assert "⚠️ Split into smaller changes" in report
    assert "📋 Comprehensive testing required" in report
    assert "**Large Files (>500 lines):**" in report
    assert "**⚠️ Potential Scope Issues**" in report
    assert "**Related Issues:**" in report


def test_load_config_missing_file(mock_config_file_missing):
    """Test loading config when file doesn't exist."""
    config = load_config()
    assert config == {}


def test_load_config_valid_file(mock_config_file_valid):
    """Test loading valid config file."""
    config = load_config()
    assert config == {"scope": {"warn_on_long_title": 80}}


def test_analysis_data_immutable():
    """Test that AnalysisData is immutable (frozen dataclass)."""
    data = AnalysisData(
        file_analysis={},
        complexity_score=50,
        risk_level="Medium",
        scope_issues=[],
        related_issues=[],
        commit_count=5,
    )

    with pytest.raises(AttributeError):
        data.complexity_score = 60
