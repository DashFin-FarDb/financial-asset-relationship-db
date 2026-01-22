"""
Advanced security tests for GitHub workflows.

Focus areas:
1. Injection vulnerability prevention
2. Secret exposure prevention
3. Permissions and least privilege
4. Supply chain security
5. Workflow isolation and sandboxing
"""

import re
from typing import Any, Dict, List


class TestWorkflowInjectionPrevention:
    """Tests for preventing injection attacks in workflows."""

    @staticmethod
    def test_no_unquoted_github_context_in_run_commands(all_workflows):
        """
        Ensure GitHub context variables in 'run' steps are enclosed in quotes.
        """
        dangerous_patterns = [
            r"\${{\s*github\.event\.[\w.]+\s*}}",  # ${{ github.event.* }}
            r"\${{\s*github\.head_ref\s*}}",  # ${{ github.head_ref }}
            r"\${{\s*github\.base_ref\s*}}",  # ${{ github.base_ref }}
        ]

        for workflow in all_workflows:
            jobs = workflow["content"].get("jobs", {})
            for job_name, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step_idx, step in enumerate(steps):
                    if "run" in step:
                        run_command = step["run"]
                        # Check if unquoted context variables are used
                        for pattern in dangerous_patterns:
                            matches = re.findall(pattern, run_command)
                            for match in matches:
                                # Ensure the specific context variable occurrence is within quotes
                                quoted = re.search(
                                    r'(["\']).*?' + re.escape(match) + r".*?\1",
                                    run_command,
                                    flags=re.DOTALL,
                                )
                                assert quoted, (
                                    f"Unquoted context variable in {workflow['path']} "
                                    f"job '{job_name}' step {step_idx}: {match}"
                                )

    @staticmethod
    def test_no_eval_with_user_input(all_workflows):
        """Verify workflows don't use eval with user-controllable input."""
        dangerous_commands = ["eval", "exec", "source"]

        for workflow in all_workflows:
            jobs = workflow["content"].get("jobs", {})
            for job_name, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step_idx, step in enumerate(steps):
                    if "run" in step:
                        run_command = step["run"].lower()
                        for dangerous_cmd in dangerous_commands:
                            if dangerous_cmd in run_command:
                                # If found, ensure it's not with github context
                                assert "github.event" not in run_command, (
                                    f"Dangerous {dangerous_cmd} with user input in "
                                    f"{workflow['path']} job '{job_name}' step {step_idx}"
                                )


class TestWorkflowSecretHandling:
    """Tests for proper secret handling in workflows."""

    @staticmethod
    def test_secrets_not_echoed_in_logs(all_workflows):
        """
        Scan each workflow's raw YAML for secret references and assert they are not printed to logs.

        Searches for occurrences of secrets.<name> in each workflow's raw content and for each matching line asserts it is not used with echo, print, or printf (case-insensitive). The `all_workflows` parameter is an iterable of mappings with at least the keys `"raw"` (the workflow YAML as a string) and `"path"` (the workflow file path). Assertion failures include the workflow path and the offending line number.
        """
        for workflow in all_workflows:
            raw_content = workflow["raw"]

            # Find all references to secrets
            secret_refs = re.findall(r"secrets\.([A-Za-z0-9_\-]+)", raw_content)

            for secret_ref in secret_refs:
                lines = raw_content.split("\n")
                for line_no, line in enumerate(lines, 1):
                    if secret_ref in line:
                        # Should not be in echo, print, or printf
                        assert not re.search(
                            r"(echo|print|printf)\s+.*" + re.escape(secret_ref),
                            line,
                            re.IGNORECASE,
                        ), (
                            f"Secret {secret_ref} may be logged in {workflow['path']} line {line_no}"
                        )

    @staticmethod
    def test_secrets_not_in_artifact_uploads(all_workflows):
        """Verify secrets are not uploaded as artifacts."""
        for workflow in all_workflows:
            jobs = workflow["content"].get("jobs", {})
            for job_name, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step_idx, step in enumerate(steps):
                    if "actions/upload-artifact" in step.get("uses", ""):
                        step_str = str(step)
                        assert "secrets." not in step_str, (
                            f"Secret reference in artifact upload: {workflow['path']} "
                            f"job '{job_name}' step {step_idx}"
                        )


class TestWorkflowPermissionsHardening:
    """Tests for workflow permissions and least privilege."""

    @staticmethod
    def test_workflows_define_explicit_permissions(all_workflows):
        """
        Ensure each workflow explicitly defines a top-level `permissions` field.

        Checks each item in `all_workflows` (expected to be a sequence of mapping objects containing at least the keys `"path"` and `"content"`) and asserts that `"permissions"` exists in the workflow's `content`. Raises an AssertionError identifying the workflow path when a workflow is missing the field.

        Parameters:
            all_workflows (Iterable[Mapping]): Iterable of workflow records; each record must include `"path"` (str) and `"content"` (mapping of the workflow YAML).

        Raises:
            AssertionError: If any workflow's `content` does not contain a `"permissions"` key, with a message containing the workflow path.
        """
        for workflow in all_workflows:
            assert "permissions" in workflow["content"], (
                f"Workflow {workflow['path']} should define permissions"
            )

    @staticmethod
    def test_default_permissions_are_restrictive(all_workflows):
        """
        Ensure each workflow's default permissions adhere to least privilege.

        If the workflow's `permissions` is a string, it must be either "read-all" or "none".
        If `permissions` is a mapping, any entries with value "write" must be limited to
        the allowed set {"contents", "pull-requests", "issues", "checks"}.

        Raises:
            AssertionError: If a workflow has an overly permissive string value or if any
            unexpected write permissions are present; the assertion message includes the
            workflow path and the offending permission(s).
        """
        for workflow in all_workflows:
            permissions = workflow["content"].get("permissions", {})

            if isinstance(permissions, str):
                assert permissions in [
                    "read-all",
                    "none",
                ], (
                    f"Workflow {workflow['path']} has overly permissive default: {permissions}"
                )
            elif isinstance(permissions, dict):
                default_write_perms = [
                    k for k, v in permissions.items() if v == "write"
                ]
                allowed_write_perms = {"contents", "pull-requests", "issues", "checks"}
                unexpected_write = set(default_write_perms) - allowed_write_perms
                assert len(unexpected_write) == 0, (
                    f"Workflow {workflow['path']} has unexpected write permissions: {unexpected_write}"
                )

    @staticmethod
    def test_no_workflows_with_write_all_permission(all_workflows):
        """
        Ensure no workflow declares permissions as the string "write-all".

        Parameters:
            all_workflows (Iterable[dict]): An iterable of workflow records where each record is a dict
                containing at least "path" (str) and "content" (dict). The function asserts that for any
                workflow whose `content.permissions` is a string, it is not equal to "write-all".

        Raises:
            AssertionError: If any workflow has `content.permissions` set to "write-all". The assertion
            message includes the offending workflow's path.
        """
        for workflow in all_workflows:
            permissions = workflow["content"].get("permissions", {})
            if isinstance(permissions, str):
                assert permissions != "write-all", (
                    f"Workflow {workflow['path']} uses dangerous 'write-all'"
                )


class TestWorkflowSupplyChainSecurity:
    """Tests for supply chain security in workflows."""

    @staticmethod
    def test_third_party_actions_pinned_to_commit_sha(all_workflows):
        """Verify third-party actions are pinned to a full commit SHA."""
        for workflow in all_workflows:
            jobs = workflow["content"].get("jobs", {})
            for job_name, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step_idx, step in enumerate(steps):
                    action = step.get("uses", "")
                    if not action or action.startswith(("./", ".\\", "docker://")):
                        continue
                    if "@" in action:
                        version = action.split("@")[1]
                        assert re.match(r"^[a-f0-9]{40}$", version.lower()), (
                            f"Action {action} in {workflow['path']} job '{job_name}' "
                            f"step {step_idx} must be pinned to a SHA"
                        )

    @staticmethod
    def test_no_insecure_downloads(all_workflows):
        """Verify no insecure HTTP downloads in workflows."""
        for workflow in all_workflows:
            raw_content = workflow["raw"]
            insecure_downloads = re.findall(
                r"(curl|wget|download)\s+[^\s]*http://[^\s]+",
                raw_content,
                re.IGNORECASE,
            )
            assert len(insecure_downloads) == 0, (
                f"Insecure HTTP download found in {workflow['path']}: {insecure_downloads}"
            )
