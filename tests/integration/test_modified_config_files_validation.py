"""
Validation tests for configuration files modified in the current branch.

Tests cover:
- .github/pr-agent-config.yml
- .github/workflows/*.yml
- requirements-dev.txt
- Deletion validation for removed files
"""

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


class TestPRAgentConfigChanges:
    """Validate changes to PR Agent configuration file."""

    @pytest.fixture
    @staticmethod
    def config_path() -> Path:
        """
        Return the Path to the PR Agent YAML configuration file relative to the test module.

        Returns:
            path (Path): Path to the .github/pr-agent-config.yml file.
        """
        return Path(__file__).parent.parent.parent / ".github" / "pr-agent-config.yml"

    @pytest.fixture
    @staticmethod
    def config_data(config_path: Path) -> Dict[str, Any]:
        """
        Load and parse the PR Agent YAML configuration file.

        Parameters:
            config_path (Path): Path to the `.github/pr-agent-config.yml` file to read.

        Returns:
            config (Dict[str, Any]): Mapping representing the parsed YAML configuration.
        """
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    @staticmethod
    def test_version_is_correct(config_data: Dict[str, Any]):
        """
        Verify the PR agent configuration declares agent.version equal to "1.0.0".

        Parameters:
            config_data (dict): Parsed YAML content of .github/pr-agent-config.yml.
        """
        assert "agent" in config_data
        assert "version" in config_data["agent"]
        assert config_data["agent"]["version"] == "1.0.0"

    @staticmethod
    def test_no_context_chunking_config(config_data: Dict[str, Any]):
        """Verify context chunking configuration has been removed."""
        # Should not have context configuration
        if "agent" in config_data:
            assert "context" not in config_data["agent"], (
                "Context chunking config should be removed in v1.0.0"
            )

    @staticmethod
    def test_no_fallback_strategies(config_data: Dict[str, Any]):
        """
        Verify the PR Agent configuration does not define a 'fallback' key under the top-level 'limits' mapping.

        Parameters:
            config_data (Dict[str, Any]): Parsed contents of `.github/pr-agent-config.yml`. If a 'limits' mapping exists, this test asserts it does not contain a 'fallback' key.
        """
        limits = config_data.get("limits")
        if isinstance(limits, dict):
            assert "fallback" not in limits, "Fallback strategies should be removed"

    @staticmethod
    def test_basic_sections_present(config_data: Dict[str, Any]):
        """
        Check that the PR agent YAML configuration includes the essential top-level sections.

        Parameters:
            config_data (dict): Parsed YAML configuration mapping (from .github/pr-agent-config.yml).
        """
        required_sections = ["agent", "monitoring", "actions", "quality"]

        for section in required_sections:
            assert section in config_data, (
                f"Required section '{section}' missing from config"
            )

    @staticmethod
    def test_no_complex_token_management(config_data: Dict[str, Any]):
        """
        Check that the PR agent configuration does not contain complex token-chunking or explicit token-limit settings.

        Asserts that the configuration text does not include 'chunk_size', and that 'max_tokens' is absent unless a `limits.max_execution_time` value is present in the config.

        Parameters:
            config_data (Dict[str, Any]): Parsed PR agent configuration data.
        """
        config_str = str(config_data)

        # Should not contain references to chunking or token limits
        assert "chunk_size" not in config_str.lower()
        assert "max_tokens" not in config_str.lower() or config_data.get(
            "limits", {}
        ).get("max_execution_time"), "Token management should be simplified"

    @staticmethod
    def test_quality_standards_preserved(config_data: Dict[str, Any]):
        """
        Validate that the configuration preserves required quality settings for supported languages and Python tooling.

        Parameters:
            config_data (Dict[str, Any]): Parsed YAML configuration for the PR agent.

        Details:
            Asserts that the top-level `quality` section contains `python` and `typescript`, and that the Python quality configuration includes a `linter` and a `test_runner` set to `pytest`.
        """
        assert "quality" in config_data
        assert "python" in config_data["quality"]
        assert "typescript" in config_data["quality"]

        # Check Python quality settings
        py_quality = config_data["quality"]["python"]
        assert "linter" in py_quality
        assert "test_runner" in py_quality
        assert py_quality["test_runner"] == "pytest"


class TestWorkflowSimplifications:
    """Validate simplifications made to GitHub workflows."""

    @pytest.fixture
    @staticmethod
    def workflows_dir() -> Path:
        """Get workflows directory."""
        return Path(__file__).parent.parent.parent / ".github" / "workflows"


@staticmethod
def test_pr_agent_workflow_simplified(workflows_dir: Path):
    """
    Validate that the PR Agent GitHub Actions workflow has been simplified.

    Checks that .github/workflows/pr-agent.yml exists, does not reference `context_chunker` or inline `tiktoken` usage with nearby `pip install`, and includes a simplified Python dependency installation that references `requirements.txt`.
    """
    workflow_file = workflows_dir / "pr-agent.yml"
    assert workflow_file.exists()

    with open(workflow_file, "r") as f:
        content = f.read()

    # Should not contain context chunking references
    assert "context_chunker" not in content
    assert (
        "tiktoken" not in content
        or "pip install" not in content.split("tiktoken")[0][-200:]
    )

    # Should have simplified Python dependency installation
    assert "pip install" in content
    assert "requirements.txt" in content


@staticmethod
def test_apisec_workflow_no_conditional_skip(workflows_dir: Path):
    """
    Ensure the APIsec workflow file exists and does not use conditional skips based on APIsec credentials.

    Asserts that .github/workflows/apisec-scan.yml is present and that its contents do not contain conditional checks for `apisec_username` or `apisec_password` (for example, `secrets.apisec_username != ''`).
    """
    workflow_file = workflows_dir / "apisec-scan.yml"
    assert workflow_file.exists()

    with open(workflow_file, "r") as f:
        content = f.read()

    # Should not have "if: secrets.apisec_username != ''" type conditions
    assert "apisec_username != ''" not in content
    assert "apisec_password != ''" not in content


@staticmethod
def test_label_workflow_simplified(workflows_dir: Path):
    """
    Validate that the label workflow uses a simplified configuration.

    Asserts that .github/workflows/label.yml exists and does not contain the substring 'check-config' (case-insensitive) nor the exact text 'labeler.yml not found'.
    """
    workflow_file = workflows_dir / "label.yml"
    assert workflow_file.exists()

    with open(workflow_file, "r") as f:
        content = f.read()

    # Should be simple and not check for config existence
    assert "check-config" not in content.lower()
    assert "labeler.yml not found" not in content


@staticmethod
def test_greetings_workflow_simple_messages(workflows_dir: Path):
    """Verify greetings workflow has simple placeholder messages."""
    workflow_file = workflows_dir / "greetings.yml"
    assert workflow_file.exists()

    with open(workflow_file, "r") as f:
        workflow_data = yaml.safe_load(f)

    # Check for simple messages (not elaborate multi-line messages)
    steps = workflow_data["jobs"]["greeting"]["steps"]
    first_interaction_step = next(
        (s for s in steps if "first-interaction" in str(s)), None
    )

    assert first_interaction_step is not None
    issue_msg = first_interaction_step["with"].get("issue-message", "")
    pr_msg = first_interaction_step["with"].get("pr-message", "")

    # Messages should be short placeholders
    assert len(issue_msg) < 200, "Issue message should be a simple placeholder"
    assert len(pr_msg) < 200, "PR message should be a simple placeholder"
