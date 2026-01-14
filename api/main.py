"""
Comprehensive YAML schema validation tests for GitHub workflows.

Tests validate YAML structure, syntax, and GitHub Actions schema compliance
for all workflow files in .github/workflows/
"""

import warnings as GLOBAL_WARNINGS
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml


class TestWorkflowYAMLSyntax:
    """Test YAML syntax and structure validity."""

    @pytest.fixture
    def workflow_files(self):
        """Get all workflow YAML files."""
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))

    def test_all_workflows_are_valid_yaml(self, workflow_files):
        """All workflow files should be valid YAML."""
        assert len(workflow_files) > 0, "No workflow files found"

        for workflow_file in workflow_files:
            try:
                with open(workflow_file, "r") as f:
                    data = yaml.safe_load(f)

                assert data is not None, f"{workflow_file.name} is empty"
                assert isinstance(data, dict), (
                    f"{workflow_file.name} should be a dictionary"
                )
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file.name}: {e}")

    def test_workflows_have_no_tabs(self, workflow_files):
        """Workflow files should use spaces, not tabs."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                content = f.read()

            if "\t" in content:
                raise AssertionError(
                    f"{workflow_file.name} contains tabs "
                    f"(should use spaces for indentation)"
                )

    def test_workflows_use_consistent_indentation(self, workflow_files):
        """Workflow files should use consistent indentation (2 spaces)."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                if line.strip() and not line.strip().startswith("#"):
                    # Count leading spaces
                    leading_spaces = len(line) - len(line.lstrip(" "))
                    if leading_spaces > 0:
                        if leading_spaces % 2 != 0:
                            raise AssertionError(
                                f"{workflow_file.name}:{i} has odd indentation "
                                f"({leading_spaces} spaces)"
                            )

    def test_workflows_have_no_trailing_whitespace(self, workflow_files):
        """Workflow files should not have trailing whitespace."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                if line.rstrip("\n").endswith((" ", "\t")):
                    pytest.fail(f"{workflow_file.name}:{i} has trailing whitespace")


class TestWorkflowGitHubActionsSchema:
    """Test GitHub Actions schema compliance."""

    @pytest.fixture
    def workflow_data(self):
        """Load all workflow files as structured data."""
        workflow_dir = Path(".github/workflows")
        workflows = {}

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                workflows[workflow_file.name] = yaml.safe_load(f)

        return workflows

    def test_workflows_have_name(self, workflow_data):
        """All workflows should have a name field."""
        for filename, data in workflow_data.items():
            if "name" not in data:
                raise AssertionError(f"{filename} missing 'name' field")
            if not isinstance(data["name"], str):
                raise AssertionError(f"{filename} name should be string")
            if not len(data["name"]) > 0:
                raise AssertionError(f"{filename} name is empty")

    def test_workflows_have_trigger(self, workflow_data):
        """All workflows should have at least one trigger."""
        valid_triggers = {
            "on",
            "push",
            "pull_request",
            "workflow_dispatch",
            "schedule",
            "issues",
            "issue_comment",
            "pull_request_review",
            "pull_request_review_comment",
            "workflow_run",
            "repository_dispatch",
        }

        for filename, data in workflow_data.items():
            if "on" not in data:
                raise AssertionError(f"{filename} missing 'on' trigger")

            # 'on' can be string, list, or dict
            trigger = data["on"]
            if isinstance(trigger, str):
                if trigger not in valid_triggers:
                    raise AssertionError(f"{filename} has invalid trigger: {trigger}")
            elif isinstance(trigger, list):
                if not all(t in valid_triggers for t in trigger):
                    raise AssertionError(f"{filename} has invalid triggers in list")
            elif isinstance(trigger, dict):
                if not any(k in valid_triggers for k in trigger.keys()):
                    raise AssertionError(f"{filename} has no valid triggers in dict")

    def test_workflows_have_jobs(self, workflow_data):
        """All workflows should define at least one job."""
        for filename, data in workflow_data.items():
            if "jobs" not in data:
                raise AssertionError(f"{filename} missing 'jobs' section")
            if not isinstance(data["jobs"], dict):
                raise AssertionError(f"{filename} jobs should be dict")
            if not len(data["jobs"]) > 0:
                raise AssertionError(f"{filename} has no jobs defined")

    def test_jobs_have_runs_on(self, workflow_data):
        """All jobs should specify runs-on."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                if "runs-on" not in job_data:
                    raise AssertionError(
                        "{} job '{}' missing 'runs-on'".format(
                            filename,
                            job_name,
                        )
                    )

                runs_on = job_data["runs-on"]
                valid_runners = [
                    "ubuntu-latest",
                    "ubuntu-20.04",
                    "ubuntu-18.04",
                    "windows-latest",
                    "windows-2022",
                    "windows-2019",
                    "macos-latest",
                    "macos-12",
                    "macos-11",
                ]

                if isinstance(runs_on, str):
                    # Can be expression or literal
                    if not runs_on.startswith("${{"):
                        if not any(runner in runs_on for runner in valid_runners):
                            raise AssertionError(
                                "{} job '{}' has invalid runs-on: {}".format(
                                    filename,
                                    job_name,
                                    runs_on,
                                )
                            )

    def test_jobs_have_steps_or_uses(self, workflow_data):
        """Jobs should have either steps or uses (for reusable workflows)."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                has_steps = "steps" in job_data
                has_uses = "uses" in job_data

                if not (has_steps or has_uses):
                    raise AssertionError(
                        f"{filename} job '{job_name}' has neither 'steps' nor 'uses'"
                    )

                if has_steps:
                    if not isinstance(job_data["steps"], list):
                        raise AssertionError(
                            f"{filename} job '{job_name}' steps should be a list"
                        )
                    if not len(job_data["steps"]) > 0:
                        raise AssertionError(
                            f"{filename} job '{job_name}' has empty steps"
                        )


class TestWorkflowSecurity:
    """Security-focused tests for GitHub workflows."""

    @pytest.fixture
    def workflow_files(self):
        """Get all workflow files."""
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))

    def test_no_hardcoded_secrets(self, workflow_files):
        """Workflows should not contain hardcoded secrets."""
        dangerous_patterns = [
            "ghp_",
            "github_pat_",
            "gho_",
            "ghu_",
            "ghs_",
            "ghr_",  # GitHub tokens
            "AKIA",
            "ASIA",  # AWS keys
            "-----BEGIN",
            "-----BEGIN RSA PRIVATE KEY",  # Private keys
        ]

        import re

        secret_ref_re = re.compile(r"\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}")

        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                content = f.read()

            lines = content.splitlines()
            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                # Skip commented lines
                if stripped.startswith("#"):
                    continue
                for pattern in dangerous_patterns:
                    if pattern in line:
                        valid_refs = list(secret_ref_re.finditer(line))
                        if valid_refs:
                            # Mask valid secret reference spans, then check remaining text for dangerous patterns
                            masked = list(line)
                            for m in valid_refs:
                                for idx in range(m.start(), m.end()):
                                    masked[idx] = " "
                            remaining = "".join(masked)
                            if pattern in remaining:
                                raise AssertionError(
                                    f"{workflow_file.name}:{i} may contain hardcoded secret "
                                    f"outside secrets.* reference: {pattern}"
                                )
                        else:
                            pytest.fail(
                                f"{workflow_file.name}:{i} may contain hardcoded secret "
                                f"without secrets.* reference: {pattern}"
                            )

    def test_pull_request_safe_checkout(self, workflow_files):
        """PR workflows should checkout safely (not HEAD of PR)."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)

            # Check if triggered by pull_request
            triggers = data.get("on", {})
            if "pull_request" in triggers or (
                isinstance(triggers, list) and "pull_request" in triggers
            ):
                # Look for checkout actions
                jobs = data.get("jobs", {})
                for _, job_data in jobs.items():
                    steps = job_data.get("steps", [])

                    for step in steps:
                        if step.get("uses", "").startswith(
                                "actions/checkout"
                        ):
                            # Should specify ref or not checkout HEAD
                            # If no ref specified, it's okay (checks out merge commit)
                            # If ref specified, shouldn't be dangerous
                            with_data = step.get("with", {})
                            ref = with_data.get("ref", "")
                            if (
                                ref
                                and "head" in ref.lower()
                                and "sha" not in ref.lower()
                            ):
                                warnings.warn(
                                    f"{workflow_file.name} checks out PR HEAD "
                                    f"(potential security risk)"
                                )

    def test_restricted_permissions(self, workflow_files):
        """Workflows should use minimal required permissions."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)

            # Check top-level permissions
            permissions = data.get("permissions", {})

            # If permissions defined, shouldn't be 'write-all'
            if permissions:
                if isinstance(permissions, str):
                    if permissions == "write-all":
                        raise AssertionError(f"{workflow_file.name} uses write-all permissions (too broad)")
                elif isinstance(permissions, dict):
                    # Check individual permissions
                    for perm, level in permissions.items():
                        if level == "write":
                            # Write permissions should have justification in comments
                            warnings.warn(
                                f"{workflow_file.name} uses write permission for '{perm}' (too broad)",
                                UserWarning
                            )


class TestWorkflowBestPractices:
    """Test adherence to GitHub Actions best practices."""

    @pytest.fixture
    def workflow_data(self):
        """Load all workflow files."""
        workflow_dir = Path(".github/workflows")
        workflows = {}

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                workflows[workflow_file.name] = yaml.safe_load(f)

        return workflows

    def test_actions_use_specific_versions(self, workflow_data):
        """Actions should use specific versions (not latest/master)."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                steps = job_data.get("steps", [])

                for i, step in enumerate(steps):
                    uses = step.get("uses", "")
                    if uses:
                        # Should not use @main or @master
                        if "@main" in uses or "@master" in uses:
                            warnings.warn(
                                f"{filename} job '{job_name}' step {i} "
                                f"uses unstable version: {uses}"
                            )

    def test_steps_have_names(self, workflow_data):
        """Steps should have descriptive names."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                steps = job_data.get("steps", [])

                unnamed_steps = [
                    i for i, step in enumerate(steps) if "name" not in step
                ]

                # Allow a few unnamed steps, but not too many
                unnamed_ratio = len(unnamed_steps) / len(steps) if steps else 0
                if not unnamed_ratio < 0.5:
                    raise AssertionError(
                        f"{filename} job '{job_name}' has too many unnamed steps"
                    )

    def test_timeouts_defined(self, workflow_data):
        """Long-running jobs should have timeouts."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                steps = job_data.get("steps", [])

                # If job has many steps or installs dependencies, should have timeout
                if len(steps) > 5:
                    # Check for timeout-minutes
                    if "timeout-minutes" not in job_data:
                        warnings.warn(
                            f"{filename} job '{job_name}' has many steps "
                            f"but no timeout defined"
                        )


class TestWorkflowCrossPlatform:
    """Test cross-platform compatibility issues."""

    @pytest.fixture
    def workflow_data(self):
        """Load workflow data."""
        workflow_dir = Path(".github/workflows")
        workflows = {}

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                workflows[workflow_file.name] = yaml.safe_load(f)

        return workflows

    def test_shell_script_compatibility(self, workflow_data):
        """Shell scripts should be compatible with runner OS."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                runs_on = job_data.get("runs-on", "")
                steps = job_data.get("steps", [])

                is_windows = "windows" in str(runs_on).lower()

                for step in steps:
                    run_command = step.get("run", "")
                    shell = step.get(
                        "shell",
                        "bash" if not is_windows else "pwsh"
                    )

                    if run_command:
                        # Check for Unix-specific commands on Windows
                        if is_windows and shell in ["bash", "sh"]:
                            unix_commands = ["grep", "sed", "awk", "find"]
                            for cmd in unix_commands:
                                if cmd in run_command:
                                    warnings.warn(
                                        f"{filename} job '{job_name}' uses "
                                        f"Unix command '{cmd}' on Windows"
                                    )

    def test_path_separators(self, workflow_data):
        """File paths should use forward slashes for cross-platform compatibility."""
        for _, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for _, job_data in jobs.items():
                steps = job_data.get("steps", [])

                for step in steps:
                    run_command = step.get("run", "")

                    # Check for Windows-style paths (backslashes)
                    if (
                        "\\" in run_command
                        and "windows" not in str(job_data.get("runs-on", "")).lower()
                    ):
                        # Might be legitimate (escaped chars), so just warn
                        self.fail(f"Windows-style path (backslashes) found in run command: {run_command}")


class TestWorkflowMaintainability:
    """Test workflow maintainability and documentation."""

    @staticmethod
    def test_workflows_have_comments():
        """Workflows should have explanatory comments."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                content = f.read()

            lines = content.split("\n")
            comment_lines = [line for line in lines if line.strip().startswith("#")]
            code_lines = [
                line for line in lines if line.strip() and not line.strip().startswith("#")
            ]

            if len(code_lines) > 20:
                # Large workflows should have comments
                comment_ratio = len(comment_lines) / len(code_lines)
                if comment_ratio < 0.05:
                    raise AssertionError(
                        f"{workflow_file.name} is large but has few comments"
                    )

    @staticmethod
    def test_complex_expressions_explained():
        """Complex expressions should have explanatory comments."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                content = f.read()

            # Look for complex expressions
            import re

            complex_patterns = [
                r"\$\{\{.*\&\&.*\}\}",  # Multiple conditions
                r"\$\{\{.*\|\|.*\}\}",  # OR conditions
                r"\$\{\{.*\(.*\).*\\}\}",  # Grouping expressions
            ]

            for pattern in complex_patterns:
                for match_item in re.finditer(pattern, content):
                    context = match_item.group()

                    # Should have explanation
                    lines = context.split("\n")
                    if len(lines) < 2 or "#" not in lines[-2]:
                        line_num = content[: match_item.start()].count("\n") + 1
                        GLOBAL_WARNINGS.warn(
                            f"{workflow_file.name}: complex expression at line {line_num} "
                            f"lacks explanation: {match_item.group()}"
                        )
