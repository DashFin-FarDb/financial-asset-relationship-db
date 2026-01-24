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
    with open(bearer_workflow_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def bearer_workflow_raw(bearer_workflow_path):
    """Load the raw bearer workflow content."""
    with open(bearer_workflow_path, "r") as f:
        return f.read()


class TestBearerWorkflowStructure:
    """Test the basic structure and syntax of the Bearer workflow."""

    @staticmethod
    def test_workflow_file_exists(bearer_workflow_path):
        """Verify the bearer workflow file exists."""
        assert bearer_workflow_path.exists(), "Bearer workflow file should exist"
        assert bearer_workflow_path.is_file(), "Bearer workflow path should be a file"

    @staticmethod
    def test_yaml_is_valid(bearer_workflow_content):
        """Verify the YAML is valid and parseable."""
        assert bearer_workflow_content is not None, "YAML content should be parseable"
        assert isinstance(bearer_workflow_content, dict), (
            "YAML should parse to a dictionary"
        )

    @staticmethod
    def test_workflow_has_name(bearer_workflow_content):
        """Verify the workflow has a name."""
        assert "name" in bearer_workflow_content, "Workflow should have a name"
        assert bearer_workflow_content["name"] == "Bearer", (
            "Workflow name should be 'Bearer'"
        )

    @staticmethod
    def test_workflow_has_on_triggers(bearer_workflow_content):
        """Verify the workflow has trigger configuration."""
        assert "on" in bearer_workflow_content, (
            "Workflow should have 'on' trigger configuration"
        )
        assert isinstance(bearer_workflow_content["on"], dict), (
            "'on' should be a dictionary"
        )

    @staticmethod
    def test_workflow_has_jobs(bearer_workflow_content):
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

    @staticmethod
    def test_push_trigger_configured(bearer_workflow_content):
        """Verify push trigger is configured."""
        triggers = bearer_workflow_content["on"]
        assert "push" in triggers, "Workflow should have push trigger"
        assert "branches" in triggers["push"], "Push trigger should specify branches"

    @staticmethod
    def test_push_trigger_main_branch(bearer_workflow_content):
        """Verify push trigger targets main branch."""
        push_config = bearer_workflow_content["on"]["push"]
        assert "main" in push_config["branches"], (
            "Push trigger should include main branch"
        )

    @staticmethod
    def test_pull_request_trigger_configured(bearer_workflow_content):
        """Verify pull_request trigger is configured."""
        triggers = bearer_workflow_content["on"]
        assert "pull_request" in triggers, "Workflow should have pull_request trigger"
        assert "branches" in triggers["pull_request"], (
            "PR trigger should specify branches"
        )

    @staticmethod
    def test_pull_request_trigger_main_branch(bearer_workflow_content):
        """Verify PR trigger targets main branch."""
        pr_config = bearer_workflow_content["on"]["pull_request"]
        assert "main" in pr_config["branches"], "PR trigger should include main branch"

    @staticmethod
    def test_schedule_trigger_configured(bearer_workflow_content):
        """Verify scheduled trigger is configured."""
        triggers = bearer_workflow_content["on"]
        assert "schedule" in triggers, "Workflow should have schedule trigger"
        assert isinstance(triggers["schedule"], list), "Schedule should be a list"
        assert len(triggers["schedule"]) > 0, "Schedule should have at least one entry"

    @staticmethod
    def test_schedule_cron_format(bearer_workflow_content):
        """
        Assert that the workflow schedule is a five-field cron string and equals "16 8 * * 1" (Mondays at 08:16).

        Checks that the first schedule entry contains a `cron` key, that its value is a string composed of five space-separated fields, and that it exactly matches the expected cron expression "16 8 * * 1".
        """
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

    @staticmethod
    def test_bearer_job_exists(bearer_workflow_content):
        """Verify the bearer job is defined."""
        jobs = bearer_workflow_content["jobs"]
        assert "bearer" in jobs, "Workflow should have a 'bearer' job"

    @staticmethod
    def test_job_runs_on_ubuntu(bearer_workflow_content):
        """Verify the job runs on Ubuntu."""
        bearer_job = bearer_workflow_content["jobs"]["bearer"]
        assert "runs-on" in bearer_job, "Job should specify runs-on"
        assert bearer_job["runs-on"] == "ubuntu-latest", (
            "Job should run on ubuntu-latest"
        )

    @staticmethod
    def test_job_has_permissions(bearer_workflow_content):
        """
        Assert that the 'bearer' job defines a permissions mapping.

        Checks that the workflow's 'bearer' job contains a 'permissions' key and that its value is a dictionary.
        """
        bearer_job = bearer_workflow_content["jobs"]["bearer"]
        assert "permissions" in bearer_job, "Job should have permissions"
        assert isinstance(bearer_job["permissions"], dict), (
            "Permissions should be a dictionary"
        )

    @staticmethod
    def test_job_has_steps(bearer_workflow_content):
        """Verify the job has steps defined."""
        bearer_job = bearer_workflow_content["jobs"]["bearer"]
        assert "steps" in bearer_job, "Job should have steps"
        assert isinstance(bearer_job["steps"], list), "Steps should be a list"
        assert len(bearer_job["steps"]) >= 3, "Job should have at least 3 steps"


class TestBearerPermissions:
    """Test the permissions configuration for security."""

    @staticmethod
    def test_contents_read_permission(bearer_workflow_content):
        """Verify contents read permission is set."""
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        assert "contents" in permissions, "Permissions should include 'contents'"
        assert permissions["contents"] == "read", "Contents permission should be 'read'"

    @staticmethod
    def test_security_events_write_permission(bearer_workflow_content):
        """Verify security-events write permission is set."""
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        assert "security-events" in permissions, (
            "Permissions should include 'security-events'"
        )
        assert permissions["security-events"] == "write", (
            "Security-events permission should be 'write'"
        )

    @staticmethod
    def test_minimal_permissions_principle(bearer_workflow_content):
        """
        Assert that the Bearer job's permissions are limited to the minimal required set.

        Checks that the 'bearer' job in the workflow defines exactly the permissions 'contents' and 'security-events'.
        """
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        # Should only have the necessary permissions
        expected_permissions = {"contents", "security-events"}
        actual_permissions = set(permissions.keys())
        assert actual_permissions == expected_permissions, (
            f"Workflow should only have minimal required permissions: {expected_permissions}"
        )


class TestBearerSteps:
    """Test the individual steps in the Bearer workflow."""

    @staticmethod
    def test_checkout_step_exists(bearer_workflow_content):
        """Verify checkout step is present."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        checkout_step = next(
            (s for s in steps if "actions/checkout" in s.get("uses", "")), None
        )
        assert checkout_step is not None, "Workflow should have a checkout step"

    @staticmethod
    def test_checkout_uses_v4(bearer_workflow_content):
        """Verify checkout action uses v4."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        checkout_step = next(
            (s for s in steps if "actions/checkout" in s.get("uses", "")), None
        )
        assert "actions/checkout@v4" in checkout_step["uses"], "Checkout should use v4"

    @staticmethod
    def test_bearer_report_step_exists(bearer_workflow_content):
        """Verify Bearer report step is present."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "name" in s and "Report" in s["name"]), None
        )
        assert bearer_step is not None, "Workflow should have a Bearer report step"

    @staticmethod
    def test_bearer_step_has_id(bearer_workflow_content):
        """Verify Bearer report step has an ID."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "name" in s and "Report" in s["name"]), None
        )
        assert "id" in bearer_step, "Bearer report step should have an ID"
        assert bearer_step["id"] == "report", "Bearer report step ID should be 'report'"

    @staticmethod
    def test_bearer_action_configured(bearer_workflow_content):
        """Verify Bearer action is configured."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        assert bearer_step is not None, "Workflow should use bearer-action"

    @staticmethod
    def test_bearer_action_pinned_to_commit(bearer_workflow_content):
        """
        Ensure the Bearer GitHub Action is pinned to the exact commit SHA expected.

        Asserts the action's `uses` reference contains an `@` suffix with a 40-character commit SHA and that the SHA equals "828eeb928ce2f4a7ca5ed57fb8b59508cb8c79bc".
        """
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

    @staticmethod
    def test_upload_sarif_step_exists(bearer_workflow_content):
        """Verify SARIF upload step is present."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        upload_step = next(
            (s for s in steps if "codeql-action/upload-sarif" in s.get("uses", "")),
            None,
        )
        assert upload_step is not None, "Workflow should have a SARIF upload step"

    @staticmethod
    def test_upload_sarif_uses_v3(bearer_workflow_content):
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

    @staticmethod
    def test_bearer_api_key_configured(bearer_workflow_content):
        """
        Assert the Bearer action's `api-key` is sourced from the `secrets.BEARER_TOKEN` GitHub secret.

        Checks that the Bearer step in the workflow includes a `with.api-key` field referencing `${{ secrets.BEARER_TOKEN }}`.
        """
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        assert "with" in bearer_step, "Bearer step should have 'with' configuration"
        assert "api-key" in bearer_step["with"], "Bearer config should include api-key"
        assert "${{ secrets.BEARER_TOKEN }}" in bearer_step["with"]["api-key"], (
            "API key should reference BEARER_TOKEN secret"
        )

    @staticmethod
    def test_bearer_format_is_sarif(bearer_workflow_content):
        """Verify Bearer output format is SARIF."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )
        assert "format" in bearer_step["with"], "Bearer config should specify format"
        assert bearer_step["with"]["format"] == "sarif", (
            "Bearer format should be 'sarif'"
        )

    @staticmethod
    def test_bearer_output_configured(bearer_workflow_content):
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

    @staticmethod
    def test_bearer_exit_code_configured(bearer_workflow_content):
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

    @staticmethod
    def test_sarif_file_reference_matches(bearer_workflow_content):
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

    @staticmethod
    def test_has_header_comment(bearer_workflow_raw):
        """Verify the workflow has a header comment explaining its purpose."""
        assert bearer_workflow_raw.startswith("#"), (
            "Workflow should start with a comment"
        )
        assert "not certified by GitHub" in bearer_workflow_raw, (
            "Header should mention third-party action disclaimer"
        )

    @staticmethod
    def test_has_bearer_documentation_link(bearer_workflow_raw):
        """Verify the workflow references Bearer documentation."""
        content = bearer_workflow_raw.lower()
        allowed_hosts = [
            "docs.bearer.com",
            "www.bearer.com",
            "bearer.com",
        ]
        assert any(host in content for host in allowed_hosts), (
            "Workflow should reference Bearer documentation"
        )

    @staticmethod
    def test_has_inline_comments(bearer_workflow_raw):
        """Verify the workflow has inline comments for steps."""
        lines = bearer_workflow_raw.split("\n")
        comment_lines = [line for line in lines if line.strip().startswith("#")]
        # Should have header comments plus inline comments for steps
        assert len(comment_lines) >= 5, (
            "Workflow should have multiple comment lines for documentation"
        )


class TestBearerWorkflowSecurity:
    """Test security best practices in the Bearer workflow."""

    @staticmethod
    def test_no_hardcoded_secrets(bearer_workflow_raw):
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

    @staticmethod
    def test_uses_github_secrets(bearer_workflow_content):
        """Verify the workflow uses GitHub secrets for sensitive data."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )

        api_key = bearer_step["with"]["api-key"]
        assert "secrets." in api_key, "API key should reference GitHub secrets"
        assert "BEARER_TOKEN" in api_key, "Should use BEARER_TOKEN secret"

    @staticmethod
    def test_actions_pinned_to_versions(bearer_workflow_content):
        """Verify all actions are pinned to specific versions."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]

        for step in steps:
            if "uses" in step:
                uses = step["uses"]
                assert "@" in uses, f"Action should be pinned to version: {uses}"
                version = uses.split("@")[1]
                assert version not in (
                    "main",
                    "master",
                ), f"Action should not use branch references: {uses}"

    @staticmethod
    def test_read_only_checkout(bearer_workflow_content):
        """Verify the workflow uses read-only permissions for checkout."""
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        assert permissions.get("contents") == "read", (
            "Checkout should only have read permissions"
        )


class TestBearerWorkflowIntegration:
    """Test integration aspects of the Bearer workflow."""

    @staticmethod
    def test_sarif_upload_depends_on_report(bearer_workflow_content):
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

    @staticmethod
    def test_checkout_happens_first(bearer_workflow_content):
        """Verify checkout happens before other steps."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]

        checkout_index = next(
            (i for i, s in enumerate(steps) if "actions/checkout" in s.get("uses", "")),
            None,
        )

        assert checkout_index == 0, "Checkout should be the first step"

    @staticmethod
    def test_step_order_is_logical(bearer_workflow_content):
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

    @staticmethod
    def test_workflow_handles_schedule_trigger_independently(bearer_workflow_content):
        """Verify schedule trigger works independently of push/PR."""
        triggers = bearer_workflow_content["on"]
        # Schedule should be able to run independently
        assert "schedule" in triggers, "Schedule should be independent trigger"

    @staticmethod
    def test_exit_code_zero_prevents_false_failures(bearer_workflow_content):
        """Verify exit-code: 0 prevents Bearer findings from failing workflow."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )

        exit_code = bearer_step["with"]["exit-code"]
        assert exit_code == 0, (
            "Exit code 0 allows workflow to continue even with findings"
        )

    @staticmethod
    def test_all_required_with_parameters_present(bearer_workflow_content):
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

    @staticmethod
    def test_workflow_name_is_descriptive(bearer_workflow_content):
        """Verify workflow has a clear, descriptive name."""
        name = bearer_workflow_content["name"]
        assert len(name) > 0, "Workflow should have a non-empty name"
        assert name.isalnum() or " " in name, "Workflow name should be readable"

    @staticmethod
    def test_step_names_are_descriptive(bearer_workflow_content):
        """Verify steps have descriptive names where provided."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]

        for step in steps:
            if "name" in step:
                name = step["name"]
                assert len(name) > 0, "Step name should not be empty"
                assert len(name.split()) >= 1, "Step name should be descriptive"

    @staticmethod
    def test_bearer_action_version_is_documented(bearer_workflow_raw):
        """Verify Bearer action version/SHA is clear for future updates."""
        steps_section = bearer_workflow_raw[bearer_workflow_raw.find("steps:") :]
        bearer_section = steps_section[steps_section.find("bearer/bearer-action") :]

        # Should have the SHA visible for easy reference
        assert "828eeb928ce2f4a7ca5ed57fb8b59508cb8c79bc" in bearer_section, (
            "Bearer action commit SHA should be clearly visible"
        )


class TestBearerWorkflowCompliance:
    """Test compliance with GitHub Actions and security tool standards."""

    @staticmethod
    def test_sarif_format_for_security_tab(bearer_workflow_content):
        """Verify SARIF format is used for GitHub Security tab integration."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        bearer_step = next(
            (s for s in steps if "bearer/bearer-action" in s.get("uses", "")), None
        )

        assert bearer_step["with"]["format"] == "sarif", (
            "SARIF format required for GitHub Security tab"
        )

    @staticmethod
    def test_codeql_upload_for_security_integration(bearer_workflow_content):
        """Verify CodeQL action is used for proper Security tab integration."""
        steps = bearer_workflow_content["jobs"]["bearer"]["steps"]
        upload_step = next(
            (s for s in steps if "upload-sarif" in s.get("uses", "")), None
        )

        assert "codeql-action" in upload_step["uses"], (
            "CodeQL action required for Security tab integration"
        )

    @staticmethod
    def test_security_events_permission_for_upload(bearer_workflow_content):
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
        """
        Assert that a given permission in the bearer job equals the expected value.

        Parameters:
            permission (str): Permission key to verify (for example, "contents" or "security-events").
            value (str): Expected permission value (for example, "read" or "write").
        """
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
