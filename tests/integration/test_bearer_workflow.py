"""
Comprehensive integration tests for the Bearer security scanning GitHub Actions workflow.

This test suite validates:
- YAML syntax and structure
- Required workflow configuration
- Trigger conditions (push, pull_request, schedule)
- Job permissions and security settings
- Step configuration and action versions
- SARIF upload integration
- Environment variable usage
- Security best practices
"""

import os
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def bearer_workflow_path():
    """Provide the path to the bearer workflow file."""
    return Path(__file__).parent.parent.parent / ".github" / "workflows" / "bearer.yml"


@pytest.fixture
def bearer_workflow_content(bearer_workflow_path):
    """Load and parse the bearer workflow YAML content."""
    with open(bearer_workflow_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def bearer_workflow_raw(bearer_workflow_path):
    """Load the raw bearer workflow content."""
    with open(bearer_workflow_path, "r") as f:
        return f.read()


class TestBearerWorkflowStructure:
    """Test the basic structure and syntax of the Bearer workflow."""

    def test_workflow_file_exists(self, bearer_workflow_path):
        """Verify the bearer workflow file exists."""
        assert bearer_workflow_path.exists(), "Bearer workflow file should exist"
        assert bearer_workflow_path.is_file(), "Bearer workflow path should be a file"

    def test_yaml_is_valid(self, bearer_workflow_content):
        """Verify the YAML is valid and parseable."""
        assert bearer_workflow_content is not None, "YAML content should be parseable"
        assert isinstance(bearer_workflow_content, dict), (
            "YAML should parse to a dictionary"
        )

    def test_workflow_has_name(self, bearer_workflow_content):
        """Verify the workflow has a name."""
        assert "name" in bearer_workflow_content, "Workflow should have a name"
        assert bearer_workflow_content["name"] == "Bearer", (
            "Workflow name should be 'Bearer'"
        )

    def test_workflow_has_on_triggers(self, bearer_workflow_content):
        """Verify the workflow has trigger configuration."""
        assert "on" in bearer_workflow_content, (
            "Workflow should have 'on' trigger configuration"
        )
        assert isinstance(bearer_workflow_content["on"], dict), (
            "'on' should be a dictionary"
        )

    def test_workflow_has_jobs(self, bearer_workflow_content):
        """Verify the workflow has jobs defined."""
        assert "jobs" in bearer_workflow_content, "Workflow should have jobs"
        assert isinstance(bearer_workflow_content["jobs"], dict), (
            "jobs should be a dictionary"
        )
        assert len(bearer_workflow_content["jobs"]) > 0, (
            "Workflow should have at least one job"
        )


class TestBearerWorkflowTriggers:
    """Test the trigger configuration for the Bearer workflow."""

    def test_push_trigger_configured(self, bearer_workflow_content):
        """Verify push trigger is configured."""
        triggers = bearer_workflow_content["on"]
        assert "push" in triggers, "Workflow should have push trigger"
        assert "branches" in triggers["push"], "Push trigger should specify branches"

    def test_push_trigger_main_branch(self, bearer_workflow_content):
        """Verify push trigger targets main branch."""
        push_config = bearer_workflow_content["on"]["push"]
        assert "main" in push_config["branches"], (
            "Push trigger should include main branch"
        )

    def test_pull_request_trigger_configured(self, bearer_workflow_content):
        """Verify pull_request trigger is configured."""
        triggers = bearer_workflow_content["on"]
        assert "pull_request" in triggers, "Workflow should have pull_request trigger"
        assert "branches" in triggers["pull_request"], (
            "PR trigger should specify branches"
        )

    def test_pull_request_trigger_main_branch(self, bearer_workflow_content):
        """Verify PR trigger targets main branch."""
        pr_config = bearer_workflow_content["on"]["pull_request"]
        assert "main" in pr_config["branches"], "PR trigger should include main branch"

    def test_schedule_trigger_configured(self, bearer_workflow_content):
        """Verify scheduled trigger is configured."""
        triggers = bearer_workflow_content["on"]
        assert "schedule" in triggers, "Workflow should have schedule trigger"
        assert isinstance(triggers["schedule"], list), "Schedule should be a list"
        assert len(triggers["schedule"]) > 0, "Schedule should have at least one entry"

    def test_schedule_cron_format(self, bearer_workflow_content):
        """Verify schedule uses valid cron format."""
        schedule = bearer_workflow_content["on"]["schedule"][0]
        assert "cron" in schedule, "Schedule entry should have cron"
        cron_value = schedule["cron"]
        assert isinstance(cron_value, str), "Cron should be a string"
        # Cron format: minute hour day month weekday
        cron_parts = cron_value.split()
        assert len(cron_parts) == 5, "Cron should have 5 parts"
        assert cron_value == "16 8 * * 1", (
            "Cron should match expected schedule (Mondays at 8:16)"
        )


class TestBearerJobConfiguration:
    """Test the Bearer job configuration."""

    def test_bearer_job_exists(self, bearer_workflow_content):
        """Verify the bearer job is defined."""
        jobs = bearer_workflow_content["jobs"]
        assert "bearer" in jobs, "Workflow should have a 'bearer' job"

    def test_job_runs_on_ubuntu(self, bearer_workflow_content):
        """Verify the job runs on Ubuntu."""
        bearer_job = bearer_workflow_content["jobs"]["bearer"]
        assert "runs-on" in bearer_job, "Job should specify runs-on"
        assert bearer_job["runs-on"] == "ubuntu-latest", (
            "Job should run on ubuntu-latest"
        )

    def test_job_has_permissions(self, bearer_workflow_content):
        """Verify the job has permissions configured."""
        bearer_job = bearer_workflow_content["jobs"]["bearer"]
        assert "permissions" in bearer_job, "Job should have permissions"
        assert isinstance(bearer_job["permissions"], dict), (
            "Permissions should be a dictionary"
        )

    def test_job_has_steps(self, bearer_workflow_content):
        """Verify the job has steps defined."""
        bearer_job = bearer_workflow_content["jobs"]["bearer"]
        assert "steps" in bearer_job, "Job should have steps"
        assert isinstance(bearer_job["steps"], list), "Steps should be a list"
        assert len(bearer_job["steps"]) >= 3, "Job should have at least 3 steps"


class TestBearerPermissions:
    """Test the permissions configuration for security."""

    def test_contents_read_permission(self, bearer_workflow_content):
        """Verify contents read permission is set."""
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        assert "contents" in permissions, "Permissions should include 'contents'"
        assert permissions["contents"] == "read", "Contents permission should be 'read'"

    def test_security_events_write_permission(self, bearer_workflow_content):
        """Verify security-events write permission is set."""
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        assert "security-events" in permissions, (
            "Permissions should include 'security-events'"
        )
        assert permissions["security-events"] == "write", (
            "Security-events permission should be 'write'"
        )

    def test_minimal_permissions_principle(self, bearer_workflow_content):
        """Verify the workflow follows minimal permissions principle."""
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        # Should only have the necessary permissions
        expected_permissions = {"contents", "security-events"}
        actual_permissions = set(permissions.keys())
        assert actual_permissions == expected_permissions, (
            f"Workflow should only have minimal required permissions: {expected_permissions}"
        )


class TestBearerSteps:
    """Test the individual steps in the Bearer workflow."""

    def test_checkout_step_exists(self, bearer_workflow_content):
        """Verify checkout step is present."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        checkout_step = next(
            (s for s in steps if "actions/checkout" in s.get("uses", "")), None
        )
        assert checkout_step is not None, "Workflow should have a checkout step"

    def test_checkout_uses_v4(self, bearer_workflow_content):
        """Verify checkout action uses v4."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        checkout_step = next(
            (s for s in steps if "actions/checkout" in s.get("uses", "")), None
        )
        assert "actions/checkout@v4" in checkout_step["uses"], "Checkout should use v4"

    def test_bearer_report_step_exists(self, bearer_workflow_content):
        """Verify Bearer report step is present."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "name" in s and "Report" in s["name"]), None
        )
        assert bearer_step is not None, "Workflow should have a Bearer report step"

    def test_bearer_step_has_id(self, bearer_workflow_content):
        """Verify Bearer report step has an ID."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "name" in s and "Report" in s["name"]), None
        )
        assert "id" in bearer_step, "Bearer report step should have an ID"
        assert bearer_step["id"] == "report", "Bearer report step ID should be 'report'"

    def test_bearer_action_configured(self, bearer_workflow_content):
        """Verify Bearer action is configured."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        assert bearer_step is not None, "Workflow should use bearer-action"

    def test_bearer_action_pinned_to_commit(self, bearer_workflow_content):
        """Verify Bearer action is pinned to a specific commit SHA."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        uses_value = bearer_step["uses"]
        # Should be format: bearer/bearer-action@<sha>
        assert "@" in uses_value, "Bearer action should be pinned to a version"
        sha = uses_value.split("@")[1]
        assert len(sha) == 40, (
            "Bearer action should be pinned to full commit SHA (40 chars)"
        )
        assert sha == "828eeb928ce2f4a7ca5ed57fb8b59508cb8c79bc", (
            "Bearer action SHA should match expected value"
        )

    def test_upload_sarif_step_exists(self, bearer_workflow_content):
        """Verify SARIF upload step is present."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        upload_step = next(
            (s for s in steps if "codeql-action/upload-sarif" in s.get("uses", "")),
            None,
        )
        assert upload_step is not None, "Workflow should have a SARIF upload step"

    def test_upload_sarif_uses_v3(self, bearer_workflow_content):
        """Verify SARIF upload uses CodeQL action v3."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        upload_step = next(
            (s for s in steps if "codeql-action/upload-sarif" in s.get("uses", "")),
            None,
        )
        assert "github/codeql-action/upload-sarif@v3" in upload_step["uses"], (
            "SARIF upload should use CodeQL action v3"
        )


class TestBearerActionConfiguration:
    """Test Bearer action configuration parameters."""

    def test_bearer_api_key_configured(self, bearer_workflow_content):
        """Verify Bearer API key is configured from secrets."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        assert "with" in bearer_step, "Bearer step should have 'with' configuration"
        assert "api-key" in bearer_step["with"], "Bearer config should include api-key"
        assert "${{ secrets.BEARER_TOKEN }}" in bearer_step["with"]["api-key"], (
            "API key should reference BEARER_TOKEN secret"
        )

    def test_bearer_format_is_sarif(self, bearer_workflow_content):
        """Verify Bearer output format is SARIF."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        assert "format" in bearer_step["with"], "Bearer config should specify format"
        assert bearer_step["with"]["format"] == "sarif", (
            "Bearer format should be 'sarif'"
        )

    def test_bearer_output_configured(self, bearer_workflow_content):
        """Verify Bearer output file is configured."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        assert "output" in bearer_step["with"], (
            "Bearer config should specify output file"
        )
        assert bearer_step["with"]["output"] == "results.sarif", (
            "Bearer output should be 'results.sarif'"
        )

    def test_bearer_exit_code_configured(self, bearer_workflow_content):
        """Verify Bearer exit-code is configured to not fail the workflow."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        assert "exit-code" in bearer_step["with"], (
            "Bearer config should specify exit-code"
        )
        assert bearer_step["with"]["exit-code"] == 0, (
            "Bearer exit-code should be 0 to prevent workflow failure"
        )

    def test_sarif_file_reference_matches(self, bearer_workflow_content):
        """Verify SARIF file reference is consistent across steps."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        upload_step = next(
            (s for s in steps if "codeql-action/upload-sarif" in s.get("uses", "")),
            None,
        )

        bearer_output = bearer_step["with"]["output"]
        upload_file = upload_step["with"]["sarif_file"]

        assert bearer_output == upload_file, (
            f"Bearer output ({bearer_output}) should match upload sarif_file ({upload_file})"
        )


class TestBearerWorkflowComments:
    """Test that the workflow has appropriate documentation."""

    def test_has_header_comment(self, bearer_workflow_raw):
        """Verify the workflow has a header comment explaining its purpose."""
        assert bearer_workflow_raw.startswith("#"), (
            "Workflow should start with a comment"
        )
        assert "not certified by GitHub" in bearer_workflow_raw, (
            "Header should mention third-party action disclaimer"
        )

    def test_has_bearer_documentation_link(self, bearer_workflow_raw):
        """Verify the workflow references Bearer documentation."""
        assert (
            "bearer.com" in bearer_workflow_raw.lower()
            or "docs.bearer" in bearer_workflow_raw.lower()
        ), "Workflow should reference Bearer documentation"

    def test_has_inline_comments(self, bearer_workflow_raw):
        """Verify the workflow has inline comments for steps."""
        lines = bearer_workflow_raw.split("\n")
        comment_lines = [line for line in lines if line.strip().startswith("#")]
        # Should have header comments plus inline comments for steps
        assert len(comment_lines) >= 5, (
            "Workflow should have multiple comment lines for documentation"
        )


class TestBearerWorkflowSecurity:
    """Test security best practices in the Bearer workflow."""

    def test_no_hardcoded_secrets(self, bearer_workflow_raw):
        """Verify no secrets are hardcoded in the workflow."""
        # Common patterns for secrets
        secret_patterns = ["password", "api_key", "token", "secret"]
        lines = bearer_workflow_raw.lower().split("\n")

        for line in lines:
            # Skip comment lines and lines referencing secrets properly
            if line.strip().startswith("#") or "secrets." in line:
                continue
            for pattern in secret_patterns:
                if f"{pattern}:" in line or f"{pattern} =" in line:
                    # Make sure it's not a proper secret reference
                    assert "secrets." in line or "${{" in line, (
                        f"Line may contain hardcoded secret: {line}"
                    )

    def test_uses_github_secrets(self, bearer_workflow_content):
        """Verify the workflow uses GitHub secrets for sensitive data."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )

        api_key = bearer_step["with"]["api-key"]
        assert "secrets." in api_key, "API key should reference GitHub secrets"
        assert "BEARER_TOKEN" in api_key, "Should use BEARER_TOKEN secret"

    def test_actions_pinned_to_versions(self, bearer_workflow_content):
        """Verify all actions are pinned to specific versions."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]

        for step in steps:
            if "uses" in step:
                uses = step["uses"]
                assert "@" in uses, f"Action should be pinned to version: {uses}"
                version = uses.split("@")[1]
                assert version != "main" and version != "master", (
                    f"Action should not use branch references: {uses}"
                )

    def test_read_only_checkout(self, bearer_workflow_content):
        """Verify the workflow uses read-only permissions for checkout."""
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        assert permissions.get("contents") == "read", (
            "Checkout should only have read permissions"
        )


class TestBearerWorkflowIntegration:
    """Test integration aspects of the Bearer workflow."""

    def test_sarif_upload_depends_on_report(self, bearer_workflow_content):
        """Verify SARIF upload happens after Bearer report."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]

        report_index = next(
            (
                i
                for i, s in enumerate(steps)
                if "bearer/bearer-action" in s.get("uses", "")
            ),
            None,
        )
        upload_index = next(
            (
                i
                for i, s in enumerate(steps)
                if "codeql-action/upload-sarif" in s.get("uses", "")
            ),
            None,
        )

        assert report_index is not None, "Bearer report step should exist"
        assert upload_index is not None, "SARIF upload step should exist"
        assert report_index < upload_index, (
            "Bearer report should run before SARIF upload"
        )

    def test_checkout_happens_first(self, bearer_workflow_content):
        """Verify checkout happens before other steps."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]

        checkout_index = next(
            (i for i, s in enumerate(steps) if "actions/checkout" in s.get("uses", "")),
            None,
        )

        assert checkout_index == 0, "Checkout should be the first step"

    def test_step_order_is_logical(self, bearer_workflow_content):
        """Verify the steps follow a logical order."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]

        # Expected order: checkout -> bearer scan -> upload results
        step_names = []
        for step in steps:
            if "uses" in step:
                if "checkout" in step["uses"]:
                    step_names.append("checkout")
                elif "bearer-action" in step["uses"]:
                    step_names.append("bearer")
                elif "upload-sarif" in step["uses"]:
                    step_names.append("upload")

        assert step_names == [
            "checkout",
            "bearer",
            "upload",
        ], f"Steps should be in order: checkout, bearer, upload. Got: {step_names}"


class TestBearerWorkflowEdgeCases:
    """Test edge cases and error handling."""

    def test_workflow_handles_schedule_trigger_independently(
        self, bearer_workflow_content
    ):
        """Verify schedule trigger works independently of push/PR."""
        triggers = bearer_workflow_content["on"]
        # Schedule should be able to run independently
        assert "schedule" in triggers, "Schedule should be independent trigger"

    def test_exit_code_zero_prevents_false_failures(self, bearer_workflow_content):
        """Verify exit-code: 0 prevents Bearer findings from failing workflow."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )

        exit_code = bearer_step["with"]["exit-code"]
        assert exit_code == 0, (
            "Exit code 0 allows workflow to continue even with findings"
        )

    def test_all_required_with_parameters_present(self, bearer_workflow_content):
        """Verify all required Bearer action parameters are present."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )

        required_params = {"api-key", "format", "output", "exit-code"}
        actual_params = set(bearer_step["with"].keys())

        assert required_params.issubset(actual_params), (
            f"Bearer action missing required parameters. Expected: {required_params}, Got: {actual_params}"
        )


class TestBearerWorkflowMaintainability:
    """Test maintainability and future-proofing."""

    def test_workflow_name_is_descriptive(self, bearer_workflow_content):
        """Verify workflow has a clear, descriptive name."""
        name = bearer_workflow_content["name"]
        assert len(name) > 0, "Workflow should have a non-empty name"
        assert name.isalnum() or " " in name, "Workflow name should be readable"

    def test_step_names_are_descriptive(self, bearer_workflow_content):
        """Verify steps have descriptive names where provided."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]

        for step in steps:
            if "name" in step:
                name = step["name"]
                assert len(name) > 0, "Step name should not be empty"
                assert len(name.split()) >= 1, "Step name should be descriptive"

    def test_bearer_action_version_is_documented(self, bearer_workflow_raw):
        """Verify Bearer action version/SHA is clear for future updates."""
        steps_section = bearer_workflow_raw[bearer_workflow_raw.find("steps:") :]
        bearer_section = steps_section[steps_section.find("bearer/bearer-action") :]

        # Should have the SHA visible for easy reference
        assert "828eeb928ce2f4a7ca5ed57fb8b59508cb8c79bc" in bearer_section, (
            "Bearer action commit SHA should be clearly visible"
        )


class TestBearerWorkflowCompliance:
    """Test compliance with GitHub Actions and security tool standards."""

    def test_sarif_format_for_security_tab(self, bearer_workflow_content):
        """Verify SARIF format is used for GitHub Security tab integration."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )

        assert bearer_step["with"]["format"] == "sarif", (
            "SARIF format required for GitHub Security tab"
        )

    def test_codeql_upload_for_security_integration(self, bearer_workflow_content):
        """Verify CodeQL action is used for proper Security tab integration."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        upload_step = next(
            (s for s in steps if "upload-sarif" in s.get("uses", "")), None
        )

        assert "codeql-action" in upload_step["uses"], (
            "CodeQL action required for Security tab integration"
        )

    def test_security_events_permission_for_upload(self, bearer_workflow_content):
        """Verify security-events write permission for SARIF upload."""
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]

        assert permissions.get("security-events") == "write", (
            "security-events: write required for SARIF upload"
        )


# Additional parameterized tests for robustness
class TestBearerWorkflowParameterized:
    """Parameterized tests for comprehensive coverage."""

    @pytest.mark.parametrize("trigger", ["push", "pull_request", "schedule"])
    def test_all_triggers_present(self, bearer_workflow_content, trigger):
        """Verify all expected triggers are configured."""
        assert trigger in bearer_workflow_content["on"], (
            f"Workflow should have {trigger} trigger"
        )

    @pytest.mark.parametrize(
        "permission,value", [("contents", "read"), ("security-events", "write")]
    )
    def test_required_permissions(self, bearer_workflow_content, permission, value):
        """Verify required permissions are set correctly."""
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        assert permissions.get(permission) == value, (
            f"Permission '{permission}' should be '{value}'"
        )

    @pytest.mark.parametrize(
        "action",
        [
            "actions/checkout@v4",
            "bearer/bearer-action@828eeb928ce2f4a7ca5ed57fb8b59508cb8c79bc",
            "github/codeql-action/upload-sarif@v3",
        ],
    )
    def test_required_actions_present(self, bearer_workflow_content, action):
        """Verify all required actions are present in workflow."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        action_found = any(action in step.get("uses", "") for step in steps)
        assert action_found, f"Action '{action}' should be present in workflow"
