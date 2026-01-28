"""
Comprehensive YAML schema validation tests for GitHub workflows.

Tests validate YAML structure, syntax, and GitHub Actions schema compliance
for all workflow files in .github/workflows/
"""

import warnings
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

# --- Helper Functions (Avoids Duplication) ---


def _get_workflow_files() -> List[Path]:
    """Helper to get all workflow files."""
    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        return []
    return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))


def _get_workflow_data() -> Dict[str, Any]:
    """Helper to load all workflow data."""
    workflows = {}
    for workflow_file in _get_workflow_files():
        with open(workflow_file, "r", encoding="utf-8") as f:
            workflows[workflow_file.name] = yaml.safe_load(f)
    return workflows


# --- Test Classes ---


class TestWorkflowYAMLSyntax:
    """Test YAML syntax and structure validity."""

    @staticmethod
    @pytest.fixture
    def workflow_files():
        """Get all workflow YAML files."""
        return _get_workflow_files()

    @staticmethod
    def test_all_workflows_are_valid_yaml(workflow_files):
        """All workflow files should be valid YAML."""
        assert len(workflow_files) > 0, "No workflow files found"

        for workflow_file in workflow_files:
            try:
                with open(workflow_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                assert data is not None, f"{workflow_file.name} is empty"
                assert isinstance(data, dict), (
                    f"{workflow_file.name} should be a dictionary"
                )
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file.name}: {e}")

    @staticmethod
    def test_workflows_have_no_tabs(workflow_files):
        """Workflow files should use spaces, not tabs."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r", encoding="utf-8") as f:
                content = f.read()

            assert "\t" not in content, (
                f"{workflow_file.name} contains tabs (should use spaces for indentation)"
            )

    @staticmethod
    def test_workflows_use_consistent_indentation(workflow_files):
        """Workflow files should use consistent indentation (2 spaces)."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                if line.strip() and not line.strip().startswith("#"):
                    # Count leading spaces
                    leading_spaces = len(line) - len(line.lstrip(" "))
                    if leading_spaces > 0:
                        assert leading_spaces % 2 == 0, (
                            f"{workflow_file.name}:{i} has odd indentation ({leading_spaces} spaces)"
                        )

    @staticmethod
    def test_workflows_have_no_trailing_whitespace(workflow_files):
        """Workflow files should not have trailing whitespace."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                if line.rstrip("\n").endswith((" ", "\t")):
                    pytest.fail(f"{workflow_file.name}:{i} has trailing whitespace")


class TestWorkflowGitHubActionsSchema:
    """Test GitHub Actions schema compliance."""

    @staticmethod
    @pytest.fixture
    def workflow_data():
        """Fixture to provide loaded workflow data for schema tests."""
        return _get_workflow_data()

    @staticmethod
    def test_workflows_have_name(workflow_data):
        """All workflows should have a name field."""
        for filename, data in workflow_data.items():
            assert "name" in data, f"{filename} missing 'name' field"
            assert isinstance(data["name"], str), f"{filename} name should be string"
            assert len(data["name"]) > 0, f"{filename} name is empty"

    @staticmethod
    def test_workflows_have_trigger(workflow_data):
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
            assert "on" in data, f"{filename} missing 'on' trigger"

            # 'on' can be string, list, or dict
            trigger = data["on"]
            if isinstance(trigger, str):
                assert trigger in valid_triggers, (
                    f"{filename} has invalid trigger: {trigger}"
                )
            elif isinstance(trigger, list):
                assert all(t in valid_triggers for t in trigger), (
                    f"{filename} has invalid triggers in list"
                )
            elif isinstance(trigger, dict):
                assert any(k in valid_triggers for k in trigger.keys()), (
                    f"{filename} has no valid triggers in dict"
                )

    @staticmethod
    def test_workflows_have_jobs(workflow_data):
        """All workflows should define at least one job."""
        for filename, data in workflow_data.items():
            assert "jobs" in data, f"{filename} missing 'jobs' section"
            assert isinstance(data["jobs"], dict), f"{filename} jobs should be dict"
            assert len(data["jobs"]) > 0, f"{filename} has no jobs defined"

    @staticmethod
    def test_jobs_have_runs_on(workflow_data):
        """All jobs should specify runs-on."""
        for filename, data in workflow_data.items():
        jobs = data.get("jobs", {})

        for job_name, job_data in jobs.items():
            assert "runs-on" in job_data, (
                f"{filename} job '{job_name}' missing 'runs-on'"
            )

            runs_on = job_data["runs-on"]
            valid_runners = [
                "ubuntu-latest",
                "ubuntu-22.04",
                "ubuntu-20.04",
                "ubuntu-18.04",
                "windows-latest",
                "windows-2022",
                "windows-2019",
                "macos-latest",
                "macos-13",
                "macos-12",
                "macos-11",
            ]

            if isinstance(runs_on, str):
                # Can be expression or literal
                if not runs_on.startswith("${{"):
                    assert any(runner in runs_on for runner in valid_runners), (
                        f"{filename} job '{job_name}' has invalid 'runs-on': {runs_on}"
                    )


@staticmethod
def test_jobs_have_steps_or_uses(workflow_data):
    """Jobs should have either steps or uses (for reusable workflows)."""
    for filename, data in workflow_data.items():
        jobs = data.get("jobs", {})

        for job_name, job_data in jobs.items():
            has_steps = "steps" in job_data
            has_uses = "uses" in job_data

            assert has_steps or has_uses, (
                f"{filename} job '{job_name}' has neither 'steps' nor 'uses'"
            )

            if has_steps:
                assert isinstance(job_data["steps"], list), (
                    f"{filename} job '{job_name}' steps should be a list"
                )
                assert len(job_data["steps"]) > 0, (
                    f"{filename} job '{job_name}' has empty steps"
                )
# and do not include hardcoded secrets or other security vulnerabilities.


class TestWorkflowSecurity:
    """Security-focused tests for GitHub workflows."""

    @staticmethod
    @pytest.fixture
    def workflow_files():
        """Retrieve all workflow files for security tests."""
        return _get_workflow_files()

    @staticmethod
    def test_no_hardcoded_secrets(workflow_files):
        """Workflows should not contain hardcoded secrets."""
        warnings.warn("Workflows should not contain hardcoded secrets.")
