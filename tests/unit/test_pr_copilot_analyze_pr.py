"""
Unit tests for PR Copilot analyze_pr.py script.

Tests PR analysis functionality including complexity scoring,
scope validation, and risk assessment.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts"))

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


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "scope": {
            "warn_on_long_title": 72,
            "max_files_changed": 30,
            "max_total_changes": 1500,
            "max_file_types_changed": 5,
        }
    }


def test_categorize_filename_python():
    """Test categorization of Python files."""
    assert categorize_filename("src/main.py") == "python"
    assert categorize_filename("tests/test_main.py") == "test"


def test_categorize_filename_javascript():
    """Test categorization of JavaScript/TypeScript files."""
    assert categorize_filename("src/app.js") == "javascript"
    assert categorize_filename("src/component.jsx") == "javascript"
    assert categorize_filename("src/types.ts") == "javascript"
    assert categorize_filename("src/component.tsx") == "javascript"


def test_categorize_filename_workflow():
    """Test categorization of workflow files."""
    assert categorize_filename(".github/workflows/ci.yml") == "workflow"
    assert categorize_filename(".github/workflows/test.yaml") == "workflow"


def test_categorize_filename_config():
    """Test categorization of config files."""
    assert categorize_filename("package.json") == "config"
    assert categorize_filename("config.yaml") == "config"
    assert categorize_filename("settings.toml") == "config"


def test_categorize_filename_documentation():
    """Test categorization of documentation files."""
    assert categorize_filename("README.md") == "documentation"
    assert categorize_filename("docs/guide.rst") == "documentation"


def test_categorize_filename_test():
    """Test categorization of test files."""
    assert categorize_filename("test_module.py") == "test"
    assert categorize_filename("module.spec.js") == "test"


def test_categorize_filename_other():
    """Test categorization of unknown file types."""
    assert categorize_filename("file.xyz") == "other"
    assert categorize_filename("binary.exe") == "other"


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
    mock_file1 = Mock(filename="src/main.py", additions=10, deletions=5)
    mock_file2 = Mock(filename="tests/test_main.py", additions=20, deletions=10)

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
    mock_file = Mock(filename="src/large.py", additions=600, deletions=100)

    result = analyze_pr_files([mock_file])

    assert result["file_count"] == 1
    assert result["total_changes"] == 700
    assert result["has_large_files"] is True
    assert len(result["large_files"]) == 1
    assert result["large_files"][0]["filename"] == "src/large.py"
    assert result["large_files"][0]["changes"] == 700


def test_analyze_pr_files_multiple_categories():
    """Test analyzing PR with multiple file types."""
    files = [
        Mock(filename="src/app.py", additions=50, deletions=20),
        Mock(filename="src/app.js", additions=30, deletions=10),
        Mock(filename="README.md", additions=10, deletions=5),
        Mock(filename="config.yml", additions=5, deletions=2),
    ]

    result = analyze_pr_files(files)

    assert result["file_count"] == 4
    assert len(result["file_categories"]) == 4
    assert result["file_categories"]["python"] == 1
    assert result["file_categories"]["javascript"] == 1
    assert result["file_categories"]["documentation"] == 1
    assert result["file_categories"]["config"] == 1


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
        "total_changes": 100,
        "has_large_files": False,
        "large_files": [],
    }

    score, risk = assess_complexity(file_data, commit_count=2)

    assert score < 40
    assert risk == "Low"


def test_assess_complexity_medium():
    """Test complexity assessment for medium-risk PR."""
    file_data = {
        "file_count": 15,
        "total_changes": 600,
        "has_large_files": False,
        "large_files": [],
    }

    score, risk = assess_complexity(file_data, commit_count=12)

    assert 40 <= score < 70
    assert risk == "Medium"


def test_assess_complexity_high():
    """Test complexity assessment for high-risk PR."""
    file_data = {
        "file_count": 60,
        "total_changes": 2500,
        "has_large_files": True,
        "large_files": [{"filename": "large.py", "changes": 800}],
    }

    score, risk = assess_complexity(file_data, commit_count=55)

    assert score >= 70
    assert risk == "High"


def test_assess_complexity_with_large_files():
    """Test complexity assessment with multiple large files."""
    file_data = {
        "file_count": 10,
        "total_changes": 500,
        "has_large_files": True,
        "large_files": [
            {"filename": "file1.py", "changes": 600},
            {"filename": "file2.py", "changes": 700},
            {"filename": "file3.py", "changes": 800},
        ],
    }

    score, risk = assess_complexity(file_data, commit_count=5)

    assert score > 30


def test_find_scope_issues_clean_pr(sample_config):
    """Test scope validation for clean PR."""
    file_data = {
        "file_count": 5,
        "total_changes": 200,
        "file_categories": {"python": 3, "test": 2},
    }

    issues = find_scope_issues("Fix bug in authentication", file_data, sample_config)

    assert len(issues) == 0


def test_find_scope_issues_long_title(sample_config):
    """Test scope validation with long title."""
    file_data = {
        "file_count": 5,
        "total_changes": 200,
        "file_categories": {"python": 3},
    }

    long_title = "A" * 80
    issues = find_scope_issues(long_title, file_data, sample_config)

    assert any("Title too long" in issue for issue in issues)


def test_find_scope_issues_multiple_responsibilities(sample_config):
    """Test scope validation with multi-purpose title."""
    file_data = {
        "file_count": 5,
        "total_changes": 200,
        "file_categories": {"python": 3},
    }

    issues = find_scope_issues("Add feature and fix bug", file_data, sample_config)

    assert any("multiple responsibilities" in issue for issue in issues)


def test_find_scope_issues_too_many_files(sample_config):
    """Test scope validation with too many files."""
    file_data = {
        "file_count": 50,
        "total_changes": 500,
        "file_categories": {"python": 30, "test": 20},
    }

    issues = find_scope_issues("Update module", file_data, sample_config)

    assert any("Too many files" in issue for issue in issues)


def test_find_scope_issues_large_changeset(sample_config):
    """Test scope validation with large changeset."""
    file_data = {
        "file_count": 10,
        "total_changes": 2000,
        "file_categories": {"python": 10},
    }

    issues = find_scope_issues("Refactor module", file_data, sample_config)

    assert any("Large changeset" in issue for issue in issues)


def test_find_scope_issues_high_context_switching(sample_config):
    """Test scope validation with many file types."""
    file_data = {
        "file_count": 20,
        "total_changes": 500,
        "file_categories": {
            "python": 5,
            "javascript": 5,
            "css": 3,
            "html": 3,
            "config": 2,
            "documentation": 2,
        },
    }

    issues = find_scope_issues("Update application", file_data, sample_config)

    assert any("context switching" in issue for issue in issues)


def test_find_related_issues_no_body():
    """Test finding related issues with no PR body."""
    issues = find_related_issues(None, "https://github.com/test/repo")
    assert len(issues) == 0


def test_find_related_issues_simple_reference():
    """Test finding related issues with simple reference."""
    body = "This PR addresses #123"
    issues = find_related_issues(body, "https://github.com/test/repo")

    assert len(issues) == 1
    assert issues[0]["number"] == "123"
    assert "issues/123" in issues[0]["url"]


def test_find_related_issues_fix_keywords():
    """Test finding related issues with fix keywords."""
    body = "Fixes #456 and closes #789"
    issues = find_related_issues(body, "https://github.com/test/repo")

    assert len(issues) == 2
    numbers = [issue["number"] for issue in issues]
    assert "456" in numbers
    assert "789" in numbers


def test_find_related_issues_duplicate_references():
    """Test finding related issues with duplicate references."""
    body = "Fixes #123 and resolves #123"
    issues = find_related_issues(body, "https://github.com/test/repo")

    assert len(issues) == 1
    assert issues[0]["number"] == "123"


def test_generate_markdown_complete():
    """Test markdown generation with complete analysis data."""
    mock_pr = Mock(number=42, user=Mock(login="developer"))

    data = AnalysisData(
        file_analysis={
            "file_count": 10,
            "total_changes": 500,
            "file_categories": {"python": 6, "test": 4},
            "large_files": [],
            "has_large_files": False,
        },
        complexity_score=35,
        risk_level="Medium",
        scope_issues=["Title too long (80 > 72)"],
        related_issues=[{"number": "123", "url": "https://github.com/test/repo/issues/123"}],
        commit_count=8,
    )

    report = generate_markdown(mock_pr, data)

    assert "🔍 **PR Analysis Report**" in report
    assert "#42" in report
    assert "@developer" in report
    assert "35/100" in report
    assert "🟡 Medium" in report
    assert "10 files, 500 lines" in report
    assert "Title too long" in report
    assert "#123" in report
