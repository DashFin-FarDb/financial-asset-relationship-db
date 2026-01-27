"""6. Security best practices in workflows"""

from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml


class TestPRAgentWorkflowChanges:
    """Tests for pr-agent.yml workflow changes."""

    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
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

        setup_python_step = next(
            (s for s in steps if s.get("name") == "Setup Python"), None
        )
        assert setup_python_step is not None
        assert "with" in setup_python_step
        assert "python-version" in setup_python_step["with"]
        assert setup_python_step["with"]["python-version"] == "3.11"

    def test_checkout_uses_fetch_depth_zero(self, pr_agent_workflow):
        """Verify checkout fetches full git history."""
        jobs = pr_agent_workflow.get("jobs", {})
        pr_agent_job = jobs.get("pr-agent-action", {})
        steps = pr_agent_job.get("steps", [])

        checkout_step = next(
            (s for s in steps if "actions/checkout" in s.get("uses", "")), None
        )
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

    def test_monitoring_check_interval_configured(self, pr_agent_config):
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

    def test_greetings_workflow_syntax_valid(self, greetings_workflow):
        """Verify workflow has valid YAML syntax."""
        assert greetings_workflow is not None
        assert isinstance(greetings_workflow, dict)

    def test_greetings_messages_simplified(self, greetings_workflow):
        """Verify greeting messages were simplified."""
        jobs = greetings_workflow.get("jobs", {})
        greeting_job = jobs.get("greeting", {})
        steps = greeting_job.get("steps", [])

        action_step = next(
            (s for s in steps if "actions/first-interaction" in s.get("uses", "")), None
        )

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

        action_step = next(
            (s for s in steps if "actions/first-interaction" in s.get("uses", "")), None
        )

        if action_step and "with" in action_step:
            issue_message = action_step["with"].get("issue-message", "")
            pr_message = action_step["with"].get("pr-message", "")

            # Should not contain resources section or checkmarks
            assert "**Resources:**" not in issue_message
            assert "**Resources:**" not in pr_message
            assert "✅" not in issue_message
            assert "✅" not in pr_message


class TestLabelWorkflowConfigChanges:
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
        config_check_steps = [
            s for s in steps if s.get("name") == "Check for labeler config"
        ]
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
    """Tests for apisec-scan.yml workflow changes."""

    @pytest.fixture
    def apisec_workflow(self) -> Dict[str, Any]:
        """
        Load and parse the .github/workflows/apisec-scan.yml GitHub Actions workflow.

        Returns:
            workflow (dict | None): Parsed YAML content of the workflow file as a dictionary, or `None` if the file is empty.
        """
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        with open(workflow_path, "r") as f:
            return yaml.safe_load(f)

    def test_workflow_syntax_valid(self, apisec_workflow):
        """Verify workflow has valid YAML syntax."""
        assert apisec_workflow is not None
        assert isinstance(apisec_workflow, dict)

    def test_no_job_level_conditional(self, apisec_workflow):
        """Verify job-level 'if' condition was removed."""
        jobs = apisec_workflow.get("jobs", {})
        scan_job = jobs.get("Trigger_APIsec_scan", {})

        # Should not have 'if' at job level
        assert "if" not in scan_job

    def test_no_credential_check_step(self, apisec_workflow):
        """
        Confirm the 'Trigger_APIsec_scan' job contains no step named 'Check for APIsec credentials'.

        Asserts that there are zero steps whose `name` equals 'Check for APIsec credentials' in that job's step list.
        """
        jobs = apisec_workflow.get("jobs", {})
        scan_job = jobs.get("Trigger_APIsec_scan", {})
        steps = scan_job.get("steps", [])

        credential_check_steps = [
            s for s in steps if s.get("name") == "Check for APIsec credentials"
        ]
        assert len(credential_check_steps) == 0

    def test_scan_step_is_first_step(self, apisec_workflow):
        """
        Assert that the Trigger_APIsec_scan job's first step is named "APIsec scan" and invokes the apisec-inc/apisec-run-scan action.

        Checks that the job exists, contains at least one step, and that the first step's name equals "APIsec scan" and its `uses` reference includes `apisec-inc/apisec-run-scan`.
        """
        jobs = apisec_workflow.get("jobs", {})
        scan_job = jobs.get("Trigger_APIsec_scan", {})
        steps = scan_job.get("steps", [])

        assert len(steps) >= 1
        first_step = steps[0]
        assert first_step.get("name") == "APIsec scan"
        assert "apisec-inc/apisec-run-scan" in first_step.get("uses", "")

    def test_workflow_assumes_credentials_configured(self, apisec_workflow):
        """Verify workflow now assumes credentials are configured."""
        # Since credential checks are removed, workflow should run unconditionally
        jobs = apisec_workflow.get("jobs", {})
        scan_job = jobs.get("Trigger_APIsec_scan", {})

        # No if condition means it always runs
        assert "if" not in scan_job


class TestWorkflowSecurityBestPractices:
    """Security-focused tests for workflow changes."""

    @staticmethod
    def test_no_hardcoded_secrets_in_workflows():
        """Verify no hardcoded secrets in any workflow file."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                content = f.read()

            # Check for common secret patterns
            dangerous_patterns = [
                "password:",
                "api_key:",
                "token:",
                "secret:",
            ]

            for pattern in dangerous_patterns:
                # Allow if it's using secrets context
                lines_with_pattern = [
                    line
                    for line in content.split("\n")
                    if pattern in line.lower() and "secrets." not in line
                ]

                assert len(lines_with_pattern) == 0, (
                    f"Potential hardcoded secret in {workflow_file}: {lines_with_pattern}"
                )

    @staticmethod
    def test_workflows_use_pinned_action_versions():
        """Verify workflows use pinned action versions."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for _, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step in steps:
                    if "uses" in step:
                        action = step["uses"]
                        # Should have @version or @sha
                        assert (
                            action.startswith("./")
                            or action.startswith("docker://")
                            or "@" in action
                        ), f"Action {action} in {workflow_file} should be pinned"

    @staticmethod
    def test_workflows_use_read_only_permissions_by_default():
        """
        Ensure workflow files in .github/workflows limit top-level write permissions to enforce least privilege.

        Iterates over each YAML workflow file in .github/workflows, and for workflows that define a top-level `permissions` mapping, counts entries explicitly set to `write`. The test fails if more than three permissions are set to `write` for a single workflow.
        """
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            # Check top-level permissions
            if "permissions" in workflow:
                perms = workflow["permissions"]
                if isinstance(perms, dict):
                    # If specific permissions are set, verify they're intentional
                    write_perms = [k for k, v in perms.items() if v == "write"]
                    # Write permissions should be justified by workflow purpose
                    assert len(write_perms) <= 3, (
                        f"Too many write permissions in {workflow_file}: {write_perms}"
                    )

# ... rest of code unchanged ...

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
