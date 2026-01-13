"""
Comprehensive tests specifically for pr-agent.yml workflow.
Tests the duplicate key fix and PR Agent-specific functionality.
"""

import re
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


class TestPRAgentWorkflowDuplicateKeyRegression:
    """Regression tests for the duplicate Setup Python key fix."""

    @pytest.fixture
    def workflow_file(self) -> Path:
        """
        Get the path to the GitHub Actions workflow file for the PR agent.

        Returns:
            Path: Path to .github/workflows/pr-agent.yml
        """
        return Path(".github/workflows/pr-agent.yml")

    @pytest.fixture
    @staticmethod
    @staticmethod
    def workflow_content(workflow_file: Path) -> Dict[str, Any]:
        """
        Parse the GitHub Actions workflow YAML file into a Python mapping.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file.

        Returns:
            Dict[str, Any]: Parsed YAML content as a dictionary.
        """
        with open(workflow_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @pytest.fixture
    @staticmethod
    def workflow_raw(workflow_file: Path) -> str:
        """
        Get the raw text of the workflow file for text-based validation.

        Returns:
            The file contents decoded as UTF-8.
        """
        with open(workflow_file, "r", encoding="utf-8") as f:
            return f.read()

    def test_no_duplicate_step_name_setup_python(self, workflow_content: Dict[str, Any]):
        """Test that there's no duplicate 'Setup Python' step name."""
        for job_name, job_config in workflow_content.get("jobs", {}).items():
            steps = job_config.get("steps", [])
            setup_python_count = sum(1 for step in steps if step.get("name") == "Setup Python")

            assert (
                setup_python_count <= 1
            ), f"Job '{job_name}' has {setup_python_count} 'Setup Python' steps, expected at most 1"

    def test_no_duplicate_with_blocks_in_setup_python(self, workflow_raw: str):
        """Test that Setup Python step doesn't have duplicate 'with:' blocks."""
        # Split into lines and check for pattern of duplicate 'with:' after Setup Python
        lines = workflow_raw.split("\n")

        for i, line in enumerate(lines):
            if "name: Setup Python" in line:
                # Check next 10 lines for duplicate 'with:' keywords
                with_count = 0
                for j in range(i + 1, min(i + 11, len(lines))):
                    if re.match(r"^\s+with:\s*$", lines[j]):
                        with_count += 1
                    # Stop at next step
                    if re.match(r"^\s+- name:", lines[j]) and j != i:
                        break

                assert with_count <= 1, f"Setup Python step at line {i+1} has {with_count} 'with:' blocks, expected 1"

    def test_setup_python_single_python_version_definition(self, workflow_raw: str):
        """Test that python-version is defined only once per Setup Python step."""
        lines = workflow_raw.split("\n")

        for i, line in enumerate(lines):
            if "name: Setup Python" in line:
                # Count python-version definitions in next lines until next step
                version_count = 0
                for j in range(i + 1, min(i + 15, len(lines))):
                    if "python-version" in lines[j]:
                        version_count += 1
                    # Stop at next step
                    if re.match(r"^\s+- name:", lines[j]):
                        break

                assert (
                    version_count == 1
                ), f"Setup Python at line {i+1} has {version_count} python-version definitions, expected 1"


class TestPRAgentWorkflowStructureValidation:
    """Validate the overall structure of pr-agent.yml."""

    @pytest.fixture
    def workflow_content(self) -> Dict[str, Any]:
        """
        Load and parse the repository's pr-agent GitHub Actions workflow YAML.

        Returns:
            dict: The workflow content parsed from .github/workflows/pr-agent.yml as a mapping of YAML keys to Python objects.
        """
        with open(".github/workflows/pr-agent.yml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_has_pr_agent_trigger_job(self, workflow_content: Dict[str, Any]):
        """
        Verify the workflow defines a top-level job named "pr-agent-trigger".

        Parameters:
            workflow_content (Dict[str, Any]): Parsed YAML content of the workflow file.
        """
        assert "jobs" in workflow_content
        assert "pr-agent-trigger" in workflow_content["jobs"], "Workflow should have 'pr-agent-trigger' job"

    def test_has_auto_merge_check_job(self, workflow_content: Dict[str, Any]):
        """Test that workflow has the auto-merge-check job."""
        assert "auto-merge-check" in workflow_content.get("jobs", {}), "Workflow should have 'auto-merge-check' job"

    def test_has_dependency_update_job(self, workflow_content: Dict[str, Any]):
        """Test that workflow has the dependency-update job."""
        assert "dependency-update" in workflow_content.get("jobs", {}), "Workflow should have 'dependency-update' job"

    def test_trigger_on_pr_events(self, workflow_content: Dict[str, Any]):
        """Test that workflow triggers on appropriate PR events."""
        triggers = workflow_content.get("on", {})

        assert "pull_request" in triggers, "Workflow should trigger on pull_request events"

        if isinstance(triggers.get("pull_request"), dict):
            pr_types = triggers["pull_request"].get("types", [])
            expected_types = ["opened", "synchronize", "reopened"]
            for expected in expected_types:
                assert expected in pr_types, f"pull_request trigger should include '{expected}' type"

    def test_trigger_on_pr_review(self, workflow_content: Dict[str, Any]):
        """Test that workflow triggers on PR review events."""
        triggers = workflow_content.get("on", {})
        assert "pull_request_review" in triggers, "Workflow should trigger on pull_request_review events"

    def test_trigger_on_issue_comment(self, workflow_content: Dict[str, Any]):
        """
        Check that the workflow includes an `issue_comment` trigger (used for @copilot mentions).

        Parameters:
            workflow_content (Dict[str, Any]): Parsed workflow YAML as a dictionary.
        """
        triggers = workflow_content.get("on", {})
        assert "issue_comment" in triggers, "Workflow should trigger on issue_comment events for @copilot mentions"


class TestPRAgentWorkflowSetupSteps:
    """Test the setup steps in pr-agent workflow."""

    @pytest.fixture
    def pr_agent_job(self) -> Dict[str, Any]:
        """
        Return the configuration for the 'pr-agent-trigger' job from the workflow file.

        Returns:
            job (Dict[str, Any]): Mapping of the 'pr-agent-trigger' job as defined in .github/workflows/pr-agent.yml
        """
        with open(".github/workflows/pr-agent.yml", "r", encoding="utf-8") as f:
            workflow = yaml.safe_load(f)
        return workflow["jobs"]["pr-agent-trigger"]

    def test_checkout_step_exists(self, pr_agent_job: Dict[str, Any]):
        """
        Assert the job contains at least one checkout step that uses actions/checkout.

        Parameters:
            pr_agent_job (Dict[str, Any]): Parsed job dictionary from the workflow YAML; inspected for a `steps` list.
        """
        steps = pr_agent_job.get("steps", [])
        checkout_steps = [step for step in steps if step.get("uses", "").startswith("actions/checkout")]
        assert len(checkout_steps) >= 1, "Job should have checkout step"

    def test_setup_python_exists(self, pr_agent_job: Dict[str, Any]):
        """
        Assert the job contains exactly one step named "Setup Python".

        Parameters:
            pr_agent_job (Dict[str, Any]): Parsed job configuration from the workflow YAML; expected to include a 'steps' list.
        """
        steps = pr_agent_job.get("steps", [])
        python_steps = [step for step in steps if step.get("name") == "Setup Python"]
        assert len(python_steps) == 1, "Job should have exactly one Setup Python step"

    def test_setup_nodejs_exists(self, pr_agent_job: Dict[str, Any]):
        """Assert that the job includes at least one step named "Setup Node.js"."""
        steps = pr_agent_job.get("steps", [])
        node_steps = [step for step in steps if step.get("name") == "Setup Node.js"]
        assert len(node_steps) >= 1, "Job should have Setup Node.js step"

    def test_python_version_is_311(self, pr_agent_job: Dict[str, Any]):
        """Test that Python 3.11 is specified."""
        steps = pr_agent_job.get("steps", [])
        for step in steps:
            if step.get("name") == "Setup Python":
                version = step.get("with", {}).get("python-version")
                assert version == "3.11", f"Expected Python version '3.11', got '{version}'"

    def test_nodejs_version_is_18(self, pr_agent_job: Dict[str, Any]):
        """Test that Node.js 18 is specified."""
        steps = pr_agent_job.get("steps", [])
        for step in steps:
            if step.get("name") == "Setup Node.js":
                version = step.get("with", {}).get("node-version")
                assert version == "18", f"Expected Node.js version '18', got '{version}'"

    def test_setup_order_correct(self, pr_agent_job: Dict[str, Any]):
        """
        Ensure the pr-agent-trigger job's setup steps are ordered: checkout, Setup Python, then Setup Node.js.

        Parameters:
            pr_agent_job (Dict[str, Any]): Parsed job dictionary for the pr-agent-trigger job from the workflow YAML.
        """
        steps = pr_agent_job.get("steps", [])

        checkout_idx = None
        python_idx = None
        node_idx = None

        for i, step in enumerate(steps):
            if step.get("uses", "").startswith("actions/checkout"):
                checkout_idx = i
            elif step.get("name") == "Setup Python":
                python_idx = i
            elif step.get("name") == "Setup Node.js":
                node_idx = i

        if checkout_idx is not None and python_idx is not None:
            assert checkout_idx < python_idx, "Checkout should come before Setup Python"

        if python_idx is not None and node_idx is not None:
            assert python_idx < node_idx, "Setup Python should come before Setup Node.js"
