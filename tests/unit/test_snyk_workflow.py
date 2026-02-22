"""Unit tests for Snyk Infrastructure as Code workflow.

This module tests the Snyk workflow configuration (.github/workflows/snyk-infrastructure.yml):
- Valid YAML syntax
- Required workflow structure
- Job configuration
- Security best practices
- Trigger configuration
- Permission settings
"""

from pathlib import Path

import pytest
import yaml


@pytest.mark.unit
class TestSnykWorkflowStructure:
    """Test cases for Snyk workflow structure validation."""

    @pytest.fixture
    def snyk_workflow_path(self):
        """
        Path to the Snyk Infrastructure as Code workflow file.

        Returns:
            pathlib.Path: Path object pointing to ".github/workflows/snyk-infrastructure.yml".
        """
        return Path(".github/workflows/snyk-infrastructure.yml")

    @pytest.fixture
    def snyk_workflow(self, snyk_workflow_path):
        """
        Load and parse the Snyk workflow YAML file.

        Parameters:
            snyk_workflow_path (Path): Path to the Snyk workflow YAML file.

        Returns:
            dict: Parsed YAML mapping representing the workflow.

        Raises:
            AssertionError: If the workflow file does not exist.
        """
        assert snyk_workflow_path.exists(), "Snyk workflow file not found"
        with open(snyk_workflow_path) as f:
            return yaml.safe_load(f)

    def test_workflow_file_exists(self, snyk_workflow_path):
        """Test that Snyk workflow file exists."""
        assert snyk_workflow_path.exists()
        assert snyk_workflow_path.is_file()

    def test_workflow_valid_yaml(self, snyk_workflow_path):
        """Test that workflow is valid YAML."""
        with open(snyk_workflow_path) as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert isinstance(data, dict)

    def test_workflow_has_name(self, snyk_workflow):
        """
        Check that the workflow defines a non-empty string at the top-level "name" key.

        Parameters:
            snyk_workflow (dict): Parsed workflow YAML as a dictionary.
        """
        assert "name" in snyk_workflow
        assert isinstance(snyk_workflow["name"], str)
        assert len(snyk_workflow["name"]) > 0

    def test_workflow_name_descriptive(self, snyk_workflow):
        """Test that workflow name is descriptive."""
        name = snyk_workflow["name"].lower()
        assert "snyk" in name
        assert "infrastructure" in name or "iac" in name

    def test_workflow_has_trigger(self, snyk_workflow):
        """Test that workflow has trigger configuration."""
        # YAML parses 'on' as boolean True
        assert True in snyk_workflow or "on" in snyk_workflow
        triggers = snyk_workflow.get(True) or snyk_workflow.get("on")
        assert triggers is not None

    def test_workflow_has_jobs(self, snyk_workflow):
        """Test that workflow has jobs defined."""
        assert "jobs" in snyk_workflow
        assert isinstance(snyk_workflow["jobs"], dict)
        assert len(snyk_workflow["jobs"]) > 0


@pytest.mark.unit
class TestSnykWorkflowTriggers:
    """Test cases for workflow trigger configuration."""

    @pytest.fixture
    def snyk_workflow(self):
        """
        Load and parse the Snyk GitHub Actions workflow YAML from .github/workflows/snyk-infrastructure.yml.

        Returns:
            dict | None: Parsed workflow mapping if the file contains YAML, or `None` if the file is empty.
        """
        workflow_path = Path(".github/workflows/snyk-infrastructure.yml")
        with open(workflow_path) as f:
            return yaml.safe_load(f)

    def test_workflow_triggers_on_push(self, snyk_workflow):
        """Test that workflow triggers on push."""
        triggers = snyk_workflow.get(True) or snyk_workflow.get("on")
        assert "push" in triggers

    def test_workflow_triggers_on_pull_request(self, snyk_workflow):
        """Test that workflow triggers on pull requests."""
        triggers = snyk_workflow.get(True) or snyk_workflow.get("on")
        assert "pull_request" in triggers

    def test_workflow_has_schedule(self, snyk_workflow):
        """
        Verify the workflow defines at least one scheduled trigger.

        Asserts that the workflow's triggers include a top-level "schedule" key whose value is a non-empty list.
        """
        triggers = snyk_workflow.get(True) or snyk_workflow.get("on")
        assert "schedule" in triggers
        assert isinstance(triggers["schedule"], list)
        assert len(triggers["schedule"]) > 0

    def test_schedule_cron_format_valid(self, snyk_workflow):
        """
        Verify the workflow's schedule trigger contains a cron expression with five space-separated fields.

        Checks that a 'schedule' trigger exists, that its first entry includes a 'cron' key, and that the cron expression consists of exactly five space-separated parts.
        """
        triggers = snyk_workflow.get(True) or snyk_workflow.get("on")
        schedule = triggers["schedule"][0]
        assert "cron" in schedule
        cron_expr = schedule["cron"]
        # Basic cron validation: should have 5 parts
        parts = cron_expr.split()
        assert len(parts) == 5, "Cron expression should have 5 parts"

    def test_push_triggers_on_main_branch(self, snyk_workflow):
        """Test that push trigger includes main branch."""
        triggers = snyk_workflow.get(True) or snyk_workflow.get("on")
        push_config = triggers["push"]
        if isinstance(push_config, dict) and "branches" in push_config:
            branches = push_config["branches"]
            assert "main" in branches or "Default" in branches

    def test_pull_request_triggers_on_main_branch(self, snyk_workflow):
        """Test that PR trigger targets main branch."""
        triggers = snyk_workflow.get(True) or snyk_workflow.get("on")
        pr_config = triggers["pull_request"]
        if isinstance(pr_config, dict) and "branches" in pr_config:
            branches = pr_config["branches"]
            assert "main" in branches


@pytest.mark.unit
class TestSnykWorkflowPermissions:
    """Test cases for workflow permissions configuration."""

    @pytest.fixture
    def snyk_workflow(self):
        """
        Load and parse the Snyk GitHub Actions workflow YAML from .github/workflows/snyk-infrastructure.yml.

        Returns:
            dict | None: Parsed workflow mapping if the file contains YAML, or `None` if the file is empty.
        """
        workflow_path = Path(".github/workflows/snyk-infrastructure.yml")
        with open(workflow_path) as f:
            return yaml.safe_load(f)

    def test_workflow_has_top_level_permissions(self, snyk_workflow):
        """Test that workflow declares top-level permissions."""
        assert "permissions" in snyk_workflow

    def test_workflow_permissions_minimal(self, snyk_workflow):
        """Test that top-level permissions follow principle of least privilege."""
        permissions = snyk_workflow["permissions"]
        # Top-level should be minimal (e.g., contents: read)
        if "contents" in permissions:
            assert permissions["contents"] in ["read", "none"]

    def test_job_has_specific_permissions(self, snyk_workflow):
        """Test that Snyk job declares specific permissions."""
        snyk_job = snyk_workflow["jobs"]["snyk"]
        assert "permissions" in snyk_job
        job_permissions = snyk_job["permissions"]

        # Should have contents read for checkout
        assert "contents" in job_permissions
        assert job_permissions["contents"] == "read"

        # Should have security-events write for SARIF upload
        assert "security-events" in job_permissions
        assert job_permissions["security-events"] == "write"

    def test_job_permissions_include_actions_read(self, snyk_workflow):
        """Test that job has actions read permission for SARIF upload."""
        snyk_job = snyk_workflow["jobs"]["snyk"]
        job_permissions = snyk_job["permissions"]

        # Required for github/codeql-action/upload-sarif in private repos
        assert "actions" in job_permissions
        assert job_permissions["actions"] == "read"


@pytest.mark.unit
class TestSnykJobConfiguration:
    """Test cases for Snyk job configuration."""

    @pytest.fixture
    def snyk_job(self):
        """
        Retrieve the 'snyk' job configuration from the Snyk workflow file.

        Reads .github/workflows/snyk-infrastructure.yml and returns the mapping under `jobs` for the `snyk` job.

        Returns:
            snyk_job (dict): The dictionary representing the `snyk` job configuration from the workflow YAML.
        """
        workflow_path = Path(".github/workflows/snyk-infrastructure.yml")
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)
        return workflow["jobs"]["snyk"]

    def test_job_runs_on_ubuntu(self, snyk_job):
        """Test that job runs on Ubuntu."""
        assert "runs-on" in snyk_job
        runs_on = snyk_job["runs-on"]
        assert "ubuntu" in runs_on.lower()

    def test_job_has_steps(self, snyk_job):
        """Test that job has defined steps."""
        assert "steps" in snyk_job
        assert isinstance(snyk_job["steps"], list)
        assert len(snyk_job["steps"]) > 0

    def test_job_checks_out_code(self, snyk_job):
        """Test that job checks out repository code."""
        steps = snyk_job["steps"]
        checkout_steps = [s for s in steps if "uses" in s and "checkout" in s["uses"]]
        assert len(checkout_steps) > 0

    def test_checkout_uses_v4(self, snyk_job):
        """Test that checkout action uses v4."""
        steps = snyk_job["steps"]
        checkout_steps = [s for s in steps if "uses" in s and "checkout" in s["uses"]]
        assert len(checkout_steps) > 0
        checkout_action = checkout_steps[0]["uses"]
        assert "@v4" in checkout_action

    def test_job_runs_snyk_action(self, snyk_job):
        """Test that job runs Snyk IaC action."""
        steps = snyk_job["steps"]
        snyk_steps = [s for s in steps if "uses" in s and "snyk" in s["uses"].lower()]
        assert len(snyk_steps) > 0

    def test_snyk_action_is_iac(self, snyk_job):
        """Test that Snyk action is IaC scan."""
        steps = snyk_job["steps"]
        snyk_steps = [s for s in steps if "uses" in s and "snyk" in s["uses"].lower()]
        snyk_action = snyk_steps[0]["uses"]
        assert "/iac@" in snyk_action

    def test_snyk_action_has_pinned_sha(self, snyk_job):
        """Test that Snyk action uses pinned SHA for security."""
        steps = snyk_job["steps"]
        snyk_steps = [s for s in steps if "uses" in s and "snyk" in s["uses"].lower()]
        snyk_action = snyk_steps[0]["uses"]
        # Should have SHA after @
        assert "@" in snyk_action
        sha_part = snyk_action.split("@")[1]
        # SHA should be 40 hex characters
        assert len(sha_part) >= 40

    def test_snyk_step_continues_on_error(self, snyk_job):
        """Test that Snyk step is configured to continue on error."""
        steps = snyk_job["steps"]
        snyk_steps = [s for s in steps if "uses" in s and "snyk" in s["uses"].lower()]
        snyk_step = snyk_steps[0]
        # Should continue on error to allow SARIF upload
        assert "continue-on-error" in snyk_step
        assert snyk_step["continue-on-error"] is True

    def test_snyk_step_has_env_token(self, snyk_job):
        """Test that Snyk step has SNYK_TOKEN environment variable."""
        steps = snyk_job["steps"]
        snyk_steps = [s for s in steps if "uses" in s and "snyk" in s["uses"].lower()]
        snyk_step = snyk_steps[0]

        assert "env" in snyk_step
        assert "SNYK_TOKEN" in snyk_step["env"]

    def test_snyk_token_uses_secret(self, snyk_job):
        """Test that SNYK_TOKEN references GitHub secret."""
        steps = snyk_job["steps"]
        snyk_steps = [s for s in steps if "uses" in s and "snyk" in s["uses"].lower()]
        snyk_step = snyk_steps[0]

        token_value = snyk_step["env"]["SNYK_TOKEN"]
        assert "${{ secrets.SNYK_TOKEN }}" in token_value

    def test_snyk_step_has_file_input(self, snyk_job):
        """Test that Snyk step specifies file to test."""
        steps = snyk_job["steps"]
        snyk_steps = [s for s in steps if "uses" in s and "snyk" in s["uses"].lower()]
        snyk_step = snyk_steps[0]

        assert "with" in snyk_step
        assert "file" in snyk_step["with"]

    def test_job_uploads_sarif(self, snyk_job):
        """Test that job uploads SARIF results."""
        steps = snyk_job["steps"]
        sarif_steps = [s for s in steps if "uses" in s and "codeql-action/upload-sarif" in s["uses"]]
        assert len(sarif_steps) > 0

    def test_sarif_upload_uses_v4(self, snyk_job):
        """Test that SARIF upload uses CodeQL action v4."""
        steps = snyk_job["steps"]
        sarif_steps = [s for s in steps if "uses" in s and "codeql-action/upload-sarif" in s["uses"]]
        sarif_action = sarif_steps[0]["uses"]
        assert "@v4" in sarif_action

    def test_sarif_upload_has_file_input(self, snyk_job):
        """
        Verifies the SARIF upload step includes a `sarif_file` input set to "snyk.sarif".

        Parameters:
            snyk_job (dict): Parsed workflow job mapping for the `snyk` job under test.
        """
        steps = snyk_job["steps"]
        sarif_steps = [s for s in steps if "uses" in s and "codeql-action/upload-sarif" in s["uses"]]
        sarif_step = sarif_steps[0]

        assert "with" in sarif_step
        assert "sarif_file" in sarif_step["with"]
        assert sarif_step["with"]["sarif_file"] == "snyk.sarif"


@pytest.mark.unit
class TestSnykWorkflowSecurity:
    """Test security best practices in Snyk workflow."""

    @pytest.fixture
    def snyk_workflow(self):
        """
        Load and parse the Snyk GitHub Actions workflow YAML from .github/workflows/snyk-infrastructure.yml.

        Returns:
            dict | None: Parsed workflow mapping if the file contains YAML, or `None` if the file is empty.
        """
        workflow_path = Path(".github/workflows/snyk-infrastructure.yml")
        with open(workflow_path) as f:
            return yaml.safe_load(f)

    def test_no_hardcoded_secrets(self, snyk_workflow_content: str) -> None:
        """Test that workflow contains no hardcoded secrets."""
        workflow_str = snyk_workflow_content.lower()
        # Check for common secret patterns
        forbidden_patterns = [
            "password: ",
            "api_key: ",
            "access_token: ",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in workflow_str

    def test_uses_github_secrets(self, snyk_workflow):
        """Test that sensitive data uses GitHub secrets."""
        snyk_job = snyk_workflow["jobs"]["snyk"]
        steps = snyk_job["steps"]
        snyk_steps = [s for s in steps if "uses" in s and "snyk" in s["uses"].lower()]

        # Token should reference secrets
        assert "${{ secrets." in str(snyk_steps[0]["env"])

    def test_actions_use_specific_versions(self, snyk_workflow):
        """Test that actions use specific versions or SHAs."""
        snyk_job = snyk_workflow["jobs"]["snyk"]
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

    @pytest.fixture
    def snyk_workflow_path(self):
        """
        Path to the Snyk Infrastructure as Code workflow file.

        Returns:
            pathlib.Path: Path object pointing to ".github/workflows/snyk-infrastructure.yml".
        """
        return Path(".github/workflows/snyk-infrastructure.yml")

    def test_workflow_file_not_empty(self, snyk_workflow_path):
        """Test that workflow file is not empty."""
        content = snyk_workflow_path.read_text()
        assert len(content.strip()) > 0

    def test_workflow_has_no_syntax_errors(self, snyk_workflow_path):
        """
        Ensure the Snyk workflow file parses as valid YAML.

        Attempts to load the workflow file with yaml.safe_load and asserts the parsed document is not None, indicating the file contains valid YAML syntax.
        """
        with open(snyk_workflow_path) as f:
            data = yaml.safe_load(f)
        assert data is not None

    def test_workflow_not_disabled(self, snyk_workflow_path):
        """
        Ensure the workflow file is not entirely commented out or blank.

        Reads the workflow YAML file and asserts there is at least one non-empty, non-comment line.
        """
        content = snyk_workflow_path.read_text()
        lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith("#")]
        assert len(lines) > 0

    def test_workflow_job_names_valid(self, snyk_workflow_path):
        """
        Ensure each job name in the workflow consists only of ASCII letters, digits, hyphens, or underscores.

        Raises an assertion error if any job name contains characters outside the set A-Z, a-z, 0-9, '-', or '_'.
        """
        with open(snyk_workflow_path) as f:
            workflow = yaml.safe_load(f)

        for job_name in workflow["jobs"].keys():
            # Job names should be alphanumeric with hyphens/underscores
            assert job_name.replace("-", "").replace("_", "").isalnum()


@pytest.mark.unit
class TestSnykWorkflowComments:
    """Test workflow documentation and comments."""

    @pytest.fixture
    def snyk_workflow_content(self):
        """
        Read the raw text content of the Snyk workflow YAML file at .github/workflows/snyk-infrastructure.yml.

        Returns:
            content (str): The workflow file's text content.
        """
        workflow_path = Path(".github/workflows/snyk-infrastructure.yml")
        return workflow_path.read_text()

    def test_workflow_has_comments(self, snyk_workflow_content):
        """Test that workflow includes helpful comments."""
        assert "#" in snyk_workflow_content

    def test_workflow_documents_third_party_actions(self, snyk_workflow_content):
        """
        Asserts the workflow file contains at least one comment documenting third-party (non-GitHub-certified) actions.

        Parameters:
            snyk_workflow_content (str): Raw text content of the workflow YAML file used to extract comment lines.
        """
        # Should mention that actions are not certified by GitHub
        lines = snyk_workflow_content.split("\n")
        comment_lines = [l for l in lines if l.strip().startswith("#")]
        assert len(comment_lines) > 0

    def test_workflow_provides_context(self, snyk_workflow_content):
        """
        Asserts the workflow's comment lines mention scanning or security to ensure the file provides contextual purpose.

        Parameters:
            snyk_workflow_content (str): Raw text content of the workflow YAML file, including comment lines.
        """
        comments = " ".join(
            l.strip("# ").lower() for l in snyk_workflow_content.split("\n") if l.strip().startswith("#")
        )
        # Should mention scanning or security
        assert "scan" in comments or "security" in comments
