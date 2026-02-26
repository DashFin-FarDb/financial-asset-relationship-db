"""Unit tests for Snyk Infrastructure as Code workflow.

This module tests the Snyk workflow configuration (.github/workflows/snyk-infrastructure.yml):
- Valid YAML syntax
- Required workflow structure
- Job configuration
- Security best practices
- Trigger configuration
- Permission settings
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOW_PATH = Path(".github/workflows/snyk-infrastructure.yml")


@pytest.fixture
def snyk_workflow_path():
    """Path to the Snyk Infrastructure workflow file.

    Returns:
        Path: Path object for ".github/workflows/snyk-infrastructure.yml".
    """
    return WORKFLOW_PATH


@pytest.fixture
def snyk_workflow(snyk_workflow_path):
    """Load and parse the Snyk workflow YAML file.

    Parameters:
        snyk_workflow_path (Path): Path to the Snyk workflow YAML file.

    Returns:
        dict: Parsed YAML content as a Python dictionary.

    Raises:
        AssertionError: If the provided path does not exist.
    """
    assert snyk_workflow_path.exists(), "Snyk workflow file not found"
    return yaml.safe_load(snyk_workflow_path.read_text())


@pytest.fixture
def snyk_workflow_content(snyk_workflow_path):
    """Return the raw text content of the Snyk workflow file.

    Returns:
        str: Contents of the Snyk workflow file as a string.
    """
    return snyk_workflow_path.read_text()


@pytest.fixture
def snyk_triggers(snyk_workflow):
    """Extract trigger configuration from the Snyk workflow.

    Handles the YAML quirk where 'on' is parsed as boolean True.

    Returns:
        dict: Trigger configuration from the workflow.
    """
    return snyk_workflow.get(True) or snyk_workflow.get("on")


@pytest.fixture
def snyk_job(snyk_workflow):
    """Return the 'snyk' job configuration from the workflow.

    Returns:
        dict: Parsed job configuration for the 'snyk' job.
    """
    return snyk_workflow["jobs"]["snyk"]


@pytest.fixture
def snyk_job_steps(snyk_job):
    """Return the steps list from the snyk job.

    Returns:
        list: Steps from the snyk job configuration.
    """
    return snyk_job["steps"]


@pytest.fixture
def snyk_action_steps(snyk_job_steps):
    """Filter steps that use the Snyk action.

    Returns:
        list: Steps whose 'uses' value contains 'snyk'.
    """
    return [s for s in snyk_job_steps if "uses" in s and "snyk" in s["uses"].lower()]


@pytest.fixture
def sarif_upload_steps(snyk_job_steps):
    """Filter steps that upload SARIF results.

    Returns:
        list: Steps using codeql-action/upload-sarif.
    """
    return [
        s
        for s in snyk_job_steps
        if "uses" in s and "codeql-action/upload-sarif" in s["uses"]
    ]


@pytest.mark.unit
class TestSnykWorkflowStructure:
    """Test cases for Snyk workflow structure validation."""

    @staticmethod
    def test_workflow_file_exists(snyk_workflow_path):
        """Test that Snyk workflow file exists."""
        assert snyk_workflow_path.exists()
        assert snyk_workflow_path.is_file()

    @staticmethod
    def test_workflow_valid_yaml(snyk_workflow):
        """Test that workflow is valid YAML."""
        assert snyk_workflow is not None
        assert isinstance(snyk_workflow, dict)

    @staticmethod
    def test_workflow_has_name(snyk_workflow):
        """Test that workflow has a name."""
        assert "name" in snyk_workflow
        assert isinstance(snyk_workflow["name"], str)
        assert len(snyk_workflow["name"]) > 0

    @staticmethod
    def test_workflow_name_descriptive(snyk_workflow):
        """Test that workflow name is descriptive."""
        name = snyk_workflow["name"].lower()
        assert "snyk" in name
        assert "infrastructure" in name or "iac" in name

    @staticmethod
    def test_workflow_has_trigger(snyk_workflow):
        """Test that workflow has trigger configuration."""
        # YAML parses 'on' as boolean True
        assert True in snyk_workflow or "on" in snyk_workflow
        triggers = snyk_workflow.get(True) or snyk_workflow.get("on")
        assert triggers is not None

    @staticmethod
    def test_workflow_has_jobs(snyk_workflow):
        """Test that workflow has jobs defined."""
        assert "jobs" in snyk_workflow
        assert isinstance(snyk_workflow["jobs"], dict)
        assert len(snyk_workflow["jobs"]) > 0


@pytest.mark.unit
class TestSnykWorkflowTriggers:
    """Test cases for workflow trigger configuration."""

    @staticmethod
    def test_workflow_triggers_on_push(snyk_triggers):
        """Test that workflow triggers on push."""
        assert "push" in snyk_triggers

    @staticmethod
    def test_workflow_triggers_on_pull_request(snyk_triggers):
        """Test that workflow triggers on pull requests."""
        assert "pull_request" in snyk_triggers

    @staticmethod
    def test_workflow_has_schedule(snyk_triggers):
        """Test that workflow has scheduled execution."""
        assert "schedule" in snyk_triggers
        assert isinstance(snyk_triggers["schedule"], list)
        assert len(snyk_triggers["schedule"]) > 0

    @staticmethod
    def test_schedule_cron_format_valid(snyk_triggers):
        """Test that schedule uses valid cron format."""
        schedule = snyk_triggers["schedule"][0]
        assert "cron" in schedule
        cron_expr = schedule["cron"]
        # Basic cron validation: should have 5 parts
        parts = cron_expr.split()
        assert len(parts) == 5, "Cron expression should have 5 parts"

    @staticmethod
    def test_push_triggers_on_main_branch(snyk_triggers):
        """Test that push trigger includes main branch."""
        push_config = snyk_triggers["push"]
        if isinstance(push_config, dict) and "branches" in push_config:
            branches = push_config["branches"]
            assert "main" in branches or "Default" in branches

    @staticmethod
    def test_pull_request_triggers_on_main_branch(snyk_triggers):
        """Test that PR trigger targets main branch."""
        pr_config = snyk_triggers["pull_request"]
        if isinstance(pr_config, dict) and "branches" in pr_config:
            branches = pr_config["branches"]
            assert "main" in branches


@pytest.mark.unit
class TestSnykWorkflowPermissions:
    """Test cases for workflow permissions configuration."""

    @staticmethod
    def test_workflow_has_top_level_permissions(snyk_workflow):
        """Test that workflow declares top-level permissions."""
        assert "permissions" in snyk_workflow

    @staticmethod
    def test_workflow_permissions_minimal(snyk_workflow):
        """Assert top-level permissions use least privilege for repository contents.

        If a top-level 'contents' permission is present, it must be 'read' or 'none'.
        """
        permissions = snyk_workflow["permissions"]
        if "contents" in permissions:
            assert permissions["contents"] in ["read", "none"]

    @staticmethod
    def test_job_has_specific_permissions(snyk_job):
        """Test that Snyk job declares specific permissions."""
        assert "permissions" in snyk_job
        job_permissions = snyk_job["permissions"]

        # Should have contents read for checkout
        assert "contents" in job_permissions
        assert job_permissions["contents"] == "read"

        # Should have security-events write for SARIF upload
        assert "security-events" in job_permissions
        assert job_permissions["security-events"] == "write"

    @staticmethod
    def test_job_permissions_include_actions_read(snyk_job):
        """Test that job has actions read permission for SARIF upload."""
        job_permissions = snyk_job["permissions"]

        # Required for github/codeql-action/upload-sarif in private repos
        assert "actions" in job_permissions
        assert job_permissions["actions"] == "read"


@pytest.mark.unit
class TestSnykJobConfiguration:
    """Test cases for Snyk job configuration."""

    @staticmethod
    def test_job_runs_on_ubuntu(snyk_job):
        """Test that job runs on Ubuntu."""
        assert "runs-on" in snyk_job
        assert "ubuntu" in snyk_job["runs-on"].lower()

    @staticmethod
    def test_job_has_steps(snyk_job_steps):
        """Test that job has defined steps."""
        assert isinstance(snyk_job_steps, list)
        assert len(snyk_job_steps) > 0

    @staticmethod
    def test_job_checks_out_code(snyk_job_steps):
        """Test that job checks out repository code."""
        checkout_steps = [
            s for s in snyk_job_steps if "uses" in s and "checkout" in s["uses"]
        ]
        assert len(checkout_steps) > 0

    @staticmethod
    def test_checkout_uses_v4(snyk_job_steps):
        """Test that checkout action uses v4."""
        checkout_steps = [
            s for s in snyk_job_steps if "uses" in s and "checkout" in s["uses"]
        ]
        assert len(checkout_steps) > 0
        assert "@v4" in checkout_steps[0]["uses"]

    @staticmethod
    def test_job_runs_snyk_action(snyk_action_steps):
        """Test that job runs Snyk IaC action."""
        assert len(snyk_action_steps) > 0

    @staticmethod
    def test_snyk_action_is_iac(snyk_action_steps):
        """Test that Snyk action is IaC scan."""
        assert snyk_action_steps, "No Snyk action steps found in workflow"
        assert "/iac@" in snyk_action_steps[0]["uses"]

    @staticmethod
    def test_snyk_action_has_pinned_sha(snyk_action_steps):
        """Test that Snyk action uses pinned SHA for security."""
        assert snyk_action_steps, "No Snyk action steps found in workflow"
        snyk_action = snyk_action_steps[0]["uses"]
        assert "@" in snyk_action
        sha_part = snyk_action.split("@")[1]
        # Full 40-character lowercase hex SHA
        assert re.fullmatch(r"[0-9a-f]{40}", sha_part), (
            f"Action does not appear to be pinned to a full SHA: {sha_part!r}"
        )

    @staticmethod
    def test_snyk_step_continues_on_error(snyk_action_steps):
        """Test that Snyk step is configured to continue on error."""
        assert snyk_action_steps, "No Snyk action steps found in workflow"
        snyk_step = snyk_action_steps[0]
        # Should continue on error to allow SARIF upload
        assert "continue-on-error" in snyk_step
        assert snyk_step["continue-on-error"] is True

    @staticmethod
    def test_snyk_step_has_env_token(snyk_action_steps):
        """Test that Snyk step has SNYK_TOKEN environment variable."""
        assert snyk_action_steps, "No Snyk action steps found in workflow"
        snyk_step = snyk_action_steps[0]
        assert "env" in snyk_step
        assert "SNYK_TOKEN" in snyk_step["env"]

    @staticmethod
    def test_snyk_token_uses_secret(snyk_action_steps):
        """Test that SNYK_TOKEN references GitHub secret."""
        assert snyk_action_steps, "No Snyk action steps found in workflow"
        snyk_step = snyk_action_steps[0]
        assert snyk_step["env"]["SNYK_TOKEN"] == "${{ secrets.SNYK_TOKEN }}"

    @staticmethod
    def test_snyk_step_has_file_input(snyk_action_steps):
        """Test that Snyk step specifies file to test."""
        assert snyk_action_steps, "No Snyk action steps found in workflow"
        snyk_step = snyk_action_steps[0]
        assert "with" in snyk_step
        assert "file" in snyk_step["with"]

    @staticmethod
    def test_job_uploads_sarif(sarif_upload_steps):
        """Assert that the job includes a SARIF upload step using codeql-action/upload-sarif."""
        assert snyk_action_steps, "No Snyk action steps found in workflow"
        assert len(sarif_upload_steps) > 0

    @staticmethod
    def test_sarif_upload_uses_v4(sarif_upload_steps):
        """Test that SARIF upload uses CodeQL action v4."""
        assert snyk_action_steps, "No Snyk action steps found in workflow"
        assert "@v4" in sarif_upload_steps[0]["uses"]

    @staticmethod
    def test_sarif_upload_has_file_input(sarif_upload_steps):
        """Assert the SARIF upload step includes a sarif_file input set to 'snyk.sarif'."""
        sarif_step = sarif_upload_steps[0]
        assert "with" in sarif_step
        assert "sarif_file" in sarif_step["with"]
        assert sarif_step["with"]["sarif_file"] == "snyk.sarif"


@pytest.mark.unit
class TestSnykWorkflowSecurity:
    """Test security best practices in Snyk workflow."""

    @staticmethod
    def test_no_hardcoded_secrets(snyk_workflow):
        """Test that workflow contains no hardcoded secrets."""
        workflow_str = str(snyk_workflow).lower()
        forbidden_patterns = [
            "password=",
            "api_key=",
            "access_token=",
            "private_key",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in workflow_str

    @staticmethod
    def test_uses_github_secrets(snyk_action_steps):
        """Test that sensitive data uses GitHub secrets."""
        assert "${{ secrets." in str(snyk_action_steps[0]["env"])

    @staticmethod
    def test_actions_use_specific_versions(snyk_job):
        """Test that actions use specific versions or SHAs."""
        for step in snyk_job["steps"]:
            if "uses" in step:
                action = step["uses"]
                # Should have @ with version or SHA
                assert "@" in action
                # Should not use @main or @master
                assert "@main" not in action.lower()
                assert "@master" not in action.lower()


@pytest.mark.unit
class TestSnykWorkflowEdgeCases:
    """Test edge cases and potential issues."""

    @staticmethod
    def test_workflow_file_not_empty(snyk_workflow_content: str) -> None:
        """Test that workflow file is not empty."""
        assert len(snyk_workflow_content.strip()) > 0

    @staticmethod
    def test_workflow_has_no_syntax_errors(snyk_workflow):
        """Test that YAML has no syntax errors."""
        assert snyk_workflow is not None

    @staticmethod
    def test_workflow_not_disabled(snyk_workflow_content: str) -> None:
        """Test that workflow is not commented out or disabled."""
        lines = [
            line
            for line in snyk_workflow_content.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 0

    @staticmethod
    def test_workflow_job_names_valid(snyk_workflow):
        """Ensure workflow job names contain only ASCII letters, digits, hyphens, or underscores."""
        for job_name in snyk_workflow["jobs"]:
            assert job_name.replace("-", "").replace("_", "").isalnum()


@pytest.mark.unit
class TestSnykWorkflowComments:
    """Test workflow documentation and comments."""

    @staticmethod
    def test_workflow_has_comments(snyk_workflow_content):
        """Test that workflow includes helpful comments."""
        assert "#" in snyk_workflow_content

    @staticmethod
    def test_workflow_documents_third_party_actions(snyk_workflow_content):
        """Test that third-party action usage is documented."""
        lines = snyk_workflow_content.split("\n")
        comment_lines = [line for line in lines if line.strip().startswith("#")]
        assert len(comment_lines) > 0

    @staticmethod
    def test_workflow_provides_context(snyk_workflow_content):
        """Test that workflow provides context about its purpose."""
        comments = " ".join(
            line.strip("# ").lower()
            for line in snyk_workflow_content.split("\n")
            if line.strip().startswith("#")
        )
        # Should mention scanning or security
        assert "scan" in comments or "security" in comments
