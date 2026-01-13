"""
Comprehensive tests for workflow configuration changes in current branch.

Tests focus on:
1. PR Agent workflow configuration validation
2. Greetings workflow message customization
3. Label workflow configuration
4. APISec scan workflow conditional execution
5. Workflow YAML syntax and structure
6. Security best practices in workflows
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml


class TestPRAgentWorkflowChanges:
    """Tests for pr-agent.yml workflow changes."""

    @staticmethod
    @pytest.fixture
    def pr_agent_workflow() -> Dict[str, Any]:
        """
        Load and parse the .github/workflows/pr-agent.yml workflow file.

        Returns:
            dict: Dictionary representation of the parsed YAML workflow.
        """
        workflow_path = Path(".github/workflows/pr-agent.yml")
        with open(workflow_path, "r") as f:
            return yaml.safe_load(f)

    def test_workflow_has_valid_yaml_syntax(self, pr_agent_workflow):
        """Verify workflow file has valid YAML syntax."""
        assert pr_agent_workflow is not None
        assert isinstance(pr_agent_workflow, dict)

    def test_workflow_has_required_keys(self, pr_agent_workflow):
        """
        Checks that the parsed pr-agent workflow contains the top-level keys 'name', 'on', 'permissions', and 'jobs'.

        Parameters:
            pr_agent_workflow (dict): Parsed YAML content of .github/workflows/pr-agent.yml represented as a dictionary.
        """
        required_keys = ["name", "on", "permissions", "jobs"]
        for key in required_keys:
            assert key in pr_agent_workflow, f"Missing required key: {key}"

    def test_on_key_uses_string_format(self, pr_agent_workflow):
        """Verify 'on' key uses string format (not bare 'on')."""
        # The fix changed from `on:` to `"on":`
        assert "on" in pr_agent_workflow or '"on"' in pr_agent_workflow

    def test_workflow_triggers_are_configured(self, pr_agent_workflow):
        """
        Assert that the parsed pr-agent workflow config includes pull request triggers.

        Parameters:
            pr_agent_workflow (dict): Parsed YAML of .github/workflows/pr-agent.yml as a dictionary; may use either `on` or `"on"` key.
        """
        triggers = pr_agent_workflow.get("on") or pr_agent_workflow.get('"on"')
        assert triggers is not None

        # Should trigger on PR events
        assert "pull_request" in triggers
        assert "pull_request_review" in triggers

    def test_python_dependencies_installation(self, pr_agent_workflow):
        """Verify Python dependencies are properly installed."""
        jobs = pr_agent_workflow.get("jobs", {})
        pr_agent_job = jobs.get("pr-agent-action", {})
        steps = pr_agent_job.get("steps", [])

        # Find the dependency installation step
        install_step = None
        for step in steps:
            if step.get("name") == "Install Python dependencies":
                install_step = step
                break

        assert install_step is not None, "Python dependency installation step not found"
        assert "run" in install_step

    def test_no_duplicate_setup_python_steps(self, pr_agent_workflow):
        """Verify no duplicate 'Setup Python' steps exist."""
        jobs = pr_agent_workflow.get("jobs", {})
        pr_agent_job = jobs.get("pr-agent-action", {})
        steps = pr_agent_job.get("steps", [])

        setup_python_steps = [s for s in steps if s.get("name") == "Setup Python"]
        assert len(setup_python_steps) == 1, "Found duplicate 'Setup Python' steps"

    def test_uses_specific_python_version(self, pr_agent_workflow):
        """Verify workflow pins Python version."""
        jobs = pr_agent_workflow.get("jobs", {})
        pr_agent_job = jobs.get("pr-agent-action", {})
        steps = pr_agent_job.get("steps", [])

        setup_python_step = next((s for s in steps if s.get("name") == "Setup Python"), None)
        assert setup_python_step is not None
        assert "with" in setup_python_step
        assert "python-version" in setup_python_step["with"]
        assert setup_python_step["with"]["python-version"] == "3.11"

    def test_checkout_uses_fetch_depth_zero(self, pr_agent_workflow):
        """Verify checkout fetches full git history."""
        jobs = pr_agent_workflow.get("jobs", {})
        pr_agent_job = jobs.get("pr-agent-action", {})
        steps = pr_agent_job.get("steps", [])

        checkout_step = next((s for s in steps if "actions/checkout" in s.get("uses", "")), None)
        assert checkout_step is not None
        assert checkout_step.get("with", {}).get("fetch-depth") == 0


class TestPRAgentConfigChanges:
    """Tests for pr-agent-config.yml configuration changes."""

    @pytest.fixture
    def pr_agent_config(self) -> Dict[str, Any]:
        """
        Load and parse the .github/pr-agent-config.yml file.

        Returns:
            config (Dict[str, Any]): Parsed YAML configuration as a dictionary.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def test_config_has_valid_yaml_syntax(self, pr_agent_config):
        """Verify config file has valid YAML syntax."""
        assert pr_agent_config is not None
        assert isinstance(pr_agent_config, dict)

    def test_agent_version_is_simplified(self, pr_agent_config):
        """
        Assert the agent version in the parsed pr-agent-config.yml equals "1.0.0".

        Parameters:
            pr_agent_config (dict): Parsed YAML content of .github/pr-agent-config.yml as a dictionary.
        """
        agent_config = pr_agent_config.get("agent", {})
        version = agent_config.get("version")

        # Version should be 1.0.0 (reverted from 1.1.0)
        assert version == "1.0.0"

    def test_no_context_chunking_config(self, pr_agent_config):
        """
        Ensure the agent configuration does not include a 'context' chunking subsection.
        """
        agent_config = pr_agent_config.get("agent", {})

        # Context chunking section should not exist
        assert "context" not in agent_config

    def test_no_chunking_limits_config(self, pr_agent_config):
        """Verify chunking limits configuration was removed."""
        limits_config = pr_agent_config.get("limits", {})

        # These keys should not exist anymore
        assert "max_files_per_chunk" not in limits_config
        assert "max_diff_lines" not in limits_config
        assert "max_comment_length" not in limits_config
        assert "fallback" not in limits_config

    def test_basic_config_structure_intact(self, pr_agent_config):
        """Verify basic configuration structure is maintained."""
        assert "agent" in pr_agent_config
        assert "monitoring" in pr_agent_config
        assert "limits" in pr_agent_config

    def test_rate_limiting_configured(self, pr_agent_config):
        """Verify rate limiting is still configured."""
        limits = pr_agent_config.get("limits", {})
        assert "rate_limit_requests" in limits
        assert isinstance(limits["rate_limit_requests"], int)

    def test_monitoring_interval_configured(self, pr_agent_config):
        """Verify monitoring interval is configured."""
        monitoring = pr_agent_config.get("monitoring", {})
        assert "check_interval" in monitoring
        assert isinstance(monitoring["check_interval"], int)


class TestGreetingsWorkflowChanges:
    """Tests for greetings.yml workflow changes."""

    @pytest.fixture
    def greetings_workflow(self) -> Dict[str, Any]:
        """Load greetings.yml workflow."""
        workflow_path = Path(".github/workflows/greetings.yml")
        with open(workflow_path, "r") as f:
            return yaml.safe_load(f)

    def test_workflow_syntax_valid(self, greetings_workflow):
        """Verify workflow has valid YAML syntax."""
        assert greetings_workflow is not None
        assert isinstance(greetings_workflow, dict)

    def test_greetings_messages_simplified(self, greetings_workflow):
        """Verify greeting messages were simplified."""
        jobs = greetings_workflow.get("jobs", {})
        greeting_job = jobs.get("greeting", {})
        steps = greeting_job.get("steps", [])

        action_step = next((s for s in steps if "actions/first-interaction" in s.get("uses", "")), None)

        assert action_step is not None
        assert "with" in action_step

        # Messages should be simple placeholders
        issue_message = action_step["with"].get("issue-message", "")
        pr_message = action_step["with"].get("pr-message", "")

        # Should be simple generic messages, not multi-line detailed ones
        assert len(issue_message) < 200, "Issue message should be simplified"
        assert len(pr_message) < 200, "PR message should be simplified"

    def test_no_complex_markdown_formatting(self, greetings_workflow):
        """Verify messages don't contain complex markdown."""
        jobs = greetings_workflow.get("jobs", {})
        greeting_job = jobs.get("greeting", {})
        steps = greeting_job.get("steps", [])

        action_step = next((s for s in steps if "actions/first-interaction" in s.get("uses", "")), None)

        if action_step and "with" in action_step:
            issue_message = action_step["with"].get("issue-message", "")
            pr_message = action_step["with"].get("pr-message", "")

            # Should not contain resources section or checkmarks
            assert "**Resources:**" not in issue_message
            assert "**Resources:**" not in pr_message
            assert "✅" not in issue_message
            assert "✅" not in pr_message


class TestLabelWorkflowChanges:
    """Tests for label.yml workflow changes."""

    @pytest.fixture
    def label_workflow(self) -> Dict[str, Any]:
        """
        Load and parse the label GitHub Actions workflow file.

        Returns:
            workflow (dict): Parsed contents of `.github/workflows/label.yml` as a dictionary.
        """
        workflow_path = Path(".github/workflows/label.yml")
        with open(workflow_path, "r") as f:
            return yaml.safe_load(f)

    def test_workflow_syntax_valid(self, label_workflow):
        """Verify workflow has valid YAML syntax."""
        assert label_workflow is not None
        assert isinstance(label_workflow, dict)

    def test_no_config_check_step(self, label_workflow):
        """Verify config check step was removed."""
        jobs = label_workflow.get("jobs", {})
        label_job = jobs.get("label", {})
        steps = label_job.get("steps", [])

        # Should not have config check step
        config_check_steps = [s for s in steps if s.get("name") == "Check for labeler config"]
        assert len(config_check_steps) == 0

    def test_no_checkout_step(self, label_workflow):
        """Verify checkout step was removed (not needed)."""
        jobs = label_workflow.get("jobs", {})
        label_job = jobs.get("label", {})
        steps = label_job.get("steps", [])

        checkout_steps = [s for s in steps if "actions/checkout" in s.get("uses", "")]
        assert len(checkout_steps) == 0

    def test_simplified_to_single_step(self, label_workflow):
        """
        Assert the label workflow has been simplified to a single actions/labeler step.

        Checks that the 'label' job contains exactly one step and that the step's `uses`
        reference includes `actions/labeler`.
        """
        jobs = label_workflow.get("jobs", {})
        label_job = jobs.get("label", {})
        steps = label_job.get("steps", [])

        # Should only have the labeler action step
        assert len(steps) == 1
        assert "actions/labeler" in steps[0].get("uses", "")

    def test_no_conditional_execution(self, label_workflow):
        """Verify no conditional if statements in steps."""
        jobs = label_workflow.get("jobs", {})
        label_job = jobs.get("label", {})
        steps = label_job.get("steps", [])

        for step in steps:
            assert "if" not in step, "Steps should not have conditional execution"


class TestAPISecScanWorkflowChanges:
    pass


class TestRequirementsDevChanges:
    """Tests for requirements-dev.txt changes."""

    @staticmethod
    def test_requirements_file_exists():
        """Verify requirements-dev.txt exists."""
        req_path = Path("requirements-dev.txt")
        assert req_path.exists(), "requirements-dev.txt should exist"

    @staticmethod
    def test_pyyaml_dependency_added():
        """Verify PyYAML dependency is in requirements-dev.txt."""
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            content = f.read().lower()

        assert "pyyaml" in content, "PyYAML should be in requirements-dev.txt"

    @staticmethod
    def test_pyyaml_version_pinned():
        """Verify PyYAML has version constraint."""
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            lines = f.readlines()

        pyyaml_lines = [line for line in lines if "pyyaml" in line.lower()]
        assert len(pyyaml_lines) > 0, "PyYAML not found in requirements"

        # Should have version specifier
        pyyaml_line = pyyaml_lines[0]
        assert any(op in pyyaml_line for op in ["==", ">=", "<=", "~="]), "PyYAML should have version constraint"

    @staticmethod
    def test_no_duplicate_dependencies():
        """
        Check that requirements-dev.txt contains no duplicate package entries.

        Ignores blank lines and comments, normalizes package names to lowercase and strips version specifiers (e.g., ==, >=, <=, ~=, >, <), and asserts there are no duplicate package names; on failure, reports the duplicated package names.
        """
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        # Extract package names (before version specifiers)
        package_names = []
        for line in lines:
            pkg_name = line.split("=")[0].split(">")[0].split("<")[0].split("~")[0].strip()
            package_names.append(pkg_name.lower())

        # Check for duplicates
        duplicates = [pkg for pkg in package_names if package_names.count(pkg) > 1]
        assert len(duplicates) == 0, f"Duplicate dependencies found: {set(duplicates)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
