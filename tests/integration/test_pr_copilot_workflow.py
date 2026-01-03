# pylint: disable=redefined-outer-name, unused-argument
"""
Integration tests for PR Copilot workflow.

Tests the complete PR Copilot workflow including configuration loading,
script execution, and output generation.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts"))


@pytest.fixture
def mock_env_vars():
    """Provide mock environment variables for testing."""
    return {
        "GITHUB_TOKEN": "test_token_12345",
        "PR_NUMBER": "42",
        "REPO_OWNER": "test-owner",
        "REPO_NAME": "test-repo",
    }


@pytest.fixture
def mock_pr_complete():
    """Create a complete mock PR with all data."""
    pr = Mock()
    pr.number = 42
    pr.title = "Add new feature for user authentication"
    pr.user.login = "contributor"
    pr.base.ref = "main"
    pr.head.ref = "feature/auth"
    pr.head.sha = "abc123def456"
    pr.draft = False
    pr.html_url = "https://github.com/test-owner/test-repo/pull/42"
    pr.commits = 8
    pr.changed_files = 12
    pr.additions = 250
    pr.deletions = 75
    pr.labels = [Mock(name="enhancement"), Mock(name="security")]
    pr.mergeable = True
    pr.mergeable_state = "clean"
    pr.body = "This PR fixes #123 and resolves #456"

    approved_review = Mock(state="APPROVED", user=Mock(login="reviewer1"))
    commented_review = Mock(state="COMMENTED", user=Mock(login="reviewer2"))
    pr.get_reviews.return_value = [approved_review, commented_review]

    pr.get_review_comments.return_value = Mock(totalCount=3)

    mock_file1 = Mock(filename="src/auth.py", additions=100, deletions=30)
    mock_file2 = Mock(filename="tests/test_auth.py", additions=80, deletions=20)
    mock_file3 = Mock(filename="README.md", additions=70, deletions=25)
    pr.get_files.return_value = [mock_file1, mock_file2, mock_file3]

    check1 = Mock(name="CI Tests", status="completed", conclusion="success")
    check2 = Mock(name="Linting", status="completed", conclusion="success")
    check3 = Mock(name="Security Scan", status="completed", conclusion="success")

    commit = Mock()
    commit.get_check_runs.return_value = [check1, check2, check3]

    return pr, commit


def test_config_file_exists():
    """Test that PR Copilot config file exists and is valid."""
    config_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot-config.yml"
    assert config_path.exists(), "PR Copilot config file should exist"

    import yaml

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert config is not None
    assert "agent" in config
    assert "triggers" in config
    assert "scope" in config
    assert "auto_merge" in config


def test_workflow_file_exists():
    """Test that PR Copilot workflow file exists and is valid."""
    workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "pr-copilot.yml"
    assert workflow_path.exists(), "PR Copilot workflow file should exist"

    import yaml

    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    assert workflow is not None
    assert "name" in workflow
    assert "on" in workflow
    assert "jobs" in workflow


def test_scripts_exist():
    """Test that all required PR Copilot scripts exist."""
    scripts_dir = Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts"

    assert (scripts_dir / "generate_status.py").exists()
    assert (scripts_dir / "analyze_pr.py").exists()
    assert (scripts_dir / "suggest_fixes.py").exists()
    assert (scripts_dir / "requirements.txt").exists()


def test_requirements_file_valid():
    """Test that requirements.txt is valid and contains necessary packages."""
    req_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "scripts" / "requirements.txt"

    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PyGithub" in content
    assert "pyyaml" in content
    assert "requests" in content


def test_generate_status_integration(mock_env_vars, mock_pr_complete):
    """Test generate_status.py script integration."""
    from generate_status import fetch_pr_status, generate_markdown

    pr, commit = mock_pr_complete

    mock_github = Mock()
    mock_repo = Mock()
    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value = pr
    mock_repo.get_commit.return_value = commit

    with patch.dict(os.environ, mock_env_vars):
        status = fetch_pr_status(mock_github, "test-owner/test-repo", 42)

        assert status.number == 42
        assert status.title == "Add new feature for user authentication"
        assert status.author == "contributor"
        assert status.commit_count == 8
        assert status.file_count == 12

        report = generate_markdown(status)

        assert "📊 **PR Status Report**" in report
        assert "contributor" in report
        assert "enhancement" in report
        assert "security" in report


def test_analyze_pr_integration(mock_env_vars, mock_pr_complete):
    """Test analyze_pr.py script integration."""
    from analyze_pr import analyze_pr_files, assess_complexity, find_scope_issues, generate_markdown

    pr, _ = mock_pr_complete

    file_data = analyze_pr_files(pr.get_files())

    assert file_data["file_count"] == 3
    assert file_data["total_additions"] == 250
    assert file_data["total_deletions"] == 75
    assert "python" in file_data["file_categories"]
    assert "test" in file_data["file_categories"]
    assert "documentation" in file_data["file_categories"]

    score, risk = assess_complexity(file_data, pr.commits)

    assert isinstance(score, int)
    assert risk in ["Low", "Medium", "High"]


def test_suggest_fixes_integration(mock_env_vars):
    """Test suggest_fixes.py script integration."""
    from suggest_fixes import categorize_comment, extract_code_suggestions, is_actionable

    comment1 = "Please fix this security vulnerability"
    category1, priority1 = categorize_comment(comment1)
    assert category1 == "critical"
    assert priority1 == 1

    comment2 = "Consider refactoring this function"
    category2, priority2 = categorize_comment(comment2)
    assert category2 == "improvement"
    assert priority2 == 2

    comment3 = "You should use `const` instead of `var`"
    suggestions = extract_code_suggestions(comment3)
    assert len(suggestions) > 0

    keywords = ["please", "fix", "should"]
    assert is_actionable(comment1, keywords) is True
    assert is_actionable("Looks good!", keywords) is False


def test_config_loading_integration():
    """Test configuration loading from actual config file."""
    from analyze_pr import load_config as load_analyze_config

    config = load_analyze_config()

    if config:
        assert isinstance(config, dict)


def test_workflow_triggers_configuration():
    """Test that workflow has all required triggers configured."""
    import yaml

    workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "pr-copilot.yml"

    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    triggers = workflow.get("on", {})

    assert "pull_request" in triggers
    assert "pull_request_review" in triggers
    assert "pull_request_review_comment" in triggers
    assert "issue_comment" in triggers
    assert "check_suite" in triggers


def test_workflow_jobs_configuration():
    """Test that workflow has all required jobs."""
    import yaml

    workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "pr-copilot.yml"

    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    jobs = workflow.get("jobs", {})

    assert "detect-trigger" in jobs
    assert "welcome" in jobs
    assert "scope-check" in jobs
    assert "status-update" in jobs
    assert "review-handler" in jobs
    assert "auto-merge-check" in jobs
    assert "merge-conflict-check" in jobs


def test_workflow_permissions():
    """Test that workflow has correct permissions configured."""
    import yaml

    workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "pr-copilot.yml"

    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    permissions = workflow.get("permissions", {})

    assert permissions.get("contents") == "read"
    assert permissions.get("pull-requests") == "write"
    assert permissions.get("issues") == "write"
    assert permissions.get("checks") == "read"
    assert permissions.get("statuses") == "read"


def test_config_agent_settings():
    """Test agent configuration settings."""
    import yaml

    config_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot-config.yml"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    agent = config.get("agent", {})

    assert agent.get("name") == "pr-copilot"
    assert agent.get("enabled") is True
    assert "version" in agent


def test_config_triggers_settings():
    """Test trigger configuration settings."""
    import yaml

    config_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot-config.yml"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    triggers = config.get("triggers", {})

    assert triggers.get("mention") is True
    assert triggers.get("pr_opened") is True
    assert "status_keywords" in triggers
    assert "mention_patterns" in triggers


def test_config_scope_settings():
    """Test scope validation configuration settings."""
    import yaml

    config_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot-config.yml"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    scope = config.get("scope", {})

    assert scope.get("enabled") is True
    assert isinstance(scope.get("warn_on_long_title"), int)
    assert scope.get("warn_on_multiple_changes") is True


def test_config_auto_merge_settings():
    """Test auto-merge configuration settings."""
    import yaml

    config_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot-config.yml"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    auto_merge = config.get("auto_merge", {})

    assert auto_merge.get("enabled") is True
    assert isinstance(auto_merge.get("require_reviews"), int)
    assert auto_merge.get("merge_method") in ["squash", "merge", "rebase"]


def test_documentation_exists():
    """Test that PR Copilot documentation exists."""
    docs_dir = Path(__file__).parent.parent.parent / ".github" / "pr-copilot"

    assert (docs_dir / "README.md").exists()
    assert (docs_dir / "SETUP.md").exists()


def test_readme_content():
    """Test that README contains essential information."""
    readme_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "README.md"

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PR Copilot" in content
    assert "Commands" in content or "commands" in content
    assert "@pr-copilot" in content
    assert "status update" in content


def test_setup_guide_content():
    """Test that SETUP.md contains essential setup information."""
    setup_path = Path(__file__).parent.parent.parent / ".github" / "pr-copilot" / "SETUP.md"

    with open(setup_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Setup" in content or "setup" in content
    assert "GitHub Actions" in content
    assert "permissions" in content.lower()
