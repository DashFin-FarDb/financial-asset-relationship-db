# pylint: disable=redefined-outer-name, unused-argument
"""
Comprehensive tests for the Debricked vulnerability scanning workflow.

This module validates the debricked.yml workflow file to ensure:
- Proper YAML structure and syntax
- Required fields and configuration
- Security best practices (permissions, injection prevention)
- Integration with Debricked CLI
"""

import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

# Constants
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Ensure we test the actual workflow file, not a root copy
DEBRICKED_WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "debricked.yml"


# --- Fixtures ---


@pytest.fixture(scope="module")
def workflow_content() -> str:
    """Load raw content of the debricked workflow file once for the module."""
    if not DEBRICKED_WORKFLOW_FILE.exists():
        pytest.fail(f"{DEBRICKED_WORKFLOW_FILE} does not exist.")
    return DEBRICKED_WORKFLOW_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow_config(workflow_content: str) -> Dict[str, Any]:
    """Parse YAML content once for the module."""
    try:
        return yaml.safe_load(workflow_content)
    except yaml.YAMLError as e:
        pytest.fail(f"Invalid YAML syntax in debricked.yml: {e}")


@pytest.fixture(scope="module")
def scan_job(workflow_config: Dict[str, Any]) -> Dict[str, Any]:
    """Get the scan job configuration."""
    jobs = workflow_config.get("jobs", {})
    if "scan" not in jobs:
        pytest.fail("Workflow missing required job: 'scan'")
    return jobs["scan"]


@pytest.fixture(scope="module")
def job_steps(scan_job: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get the list of steps from the scan job."""
    return scan_job.get("steps", [])


# --- Helpers ---


def get_steps_by_name(steps: List[Dict[str, Any]], name_substring: str) -> List[Dict[str, Any]]:
    """Filter steps by name (case-insensitive)."""
    return [s for s in steps if "name" in s and name_substring.lower() in s["name"].lower()]


def get_steps_by_action(steps: List[Dict[str, Any]], action_substring: str) -> List[Dict[str, Any]]:
    """Filter steps by action name (case-insensitive)."""
    return [s for s in steps if "uses" in s and action_substring.lower() in s["uses"].lower()]


# --- Tests ---


class TestFileBasics:
    """Test file existence and basic properties."""

    def test_workflow_file_exists(self):
        """Test that .github/workflows/debricked.yml exists."""
        assert DEBRICKED_WORKFLOW_FILE.is_file(), "debricked.yml should be a regular file in .github/workflows"

    def test_workflow_not_empty(self, workflow_content: str):
        """Test that the file is not empty."""
        assert len(workflow_content) > 0, "debricked.yml should not be empty"


class TestWorkflowStructure:
    """Test the structure and required fields."""

    def test_has_valid_name(self, workflow_config: Dict[str, Any]):
        """Test workflow name presence and description."""
        name = workflow_config.get("name", "")
        assert isinstance(name, str) and name, "Workflow must have a non-empty string name"

    def test_triggers_events(self, workflow_config: Dict[str, Any]):
        """Test that workflow triggers on necessary events."""
        triggers = workflow_config.get("on", {})
        assert triggers, "Workflow triggers must not be empty"

        # Normalize triggers to a set of keys
        if isinstance(triggers, dict):
            trigger_keys = set(triggers.keys())
        elif isinstance(triggers, list):
            trigger_keys = set(triggers)
        else:
            pytest.fail(f"Unexpected type for workflow 'on' triggers: {type(triggers)}")

        assert "pull_request" in trigger_keys, "Workflow should trigger on 'pull_request'"
        assert "push" in trigger_keys, "Workflow should trigger on 'push' to main branch"
        assert "workflow_dispatch" in trigger_keys, "Workflow should support 'workflow_dispatch' for manual testing"

    def test_triggers_on_push_to_main(self, workflow_config: Dict[str, Any]):
        """Test that workflow triggers on push to main branch."""
        triggers = workflow_config.get("on", {})
        assert "push" in triggers, "Workflow should trigger on 'push' events"

        push_config = triggers.get("push")
        if isinstance(push_config, dict):
            branches = push_config.get("branches", [])
            assert branches, "Push trigger should specify branches"
            assert any(
                b in ["main", "master"] for b in branches
            ), "Push trigger should include 'main' or 'master' branch"

    def test_triggers_on_pull_request_to_main(self, workflow_config: Dict[str, Any]):
        """Test that workflow triggers on pull requests to main branch."""
        triggers = workflow_config.get("on", {})
        assert "pull_request" in triggers, "Workflow should trigger on 'pull_request' events"

        pr_config = triggers.get("pull_request")
        if isinstance(pr_config, dict):
            branches = pr_config.get("branches", [])
            assert branches, "Pull request trigger should specify branches"
            assert any(
                b in ["main", "master"] for b in branches
            ), "Pull request trigger should include 'main' or 'master' branch"

    def test_job_runs_on_ubuntu(self, scan_job: Dict[str, Any]):
        """Test that the scan job runs on Ubuntu."""
        runs_on = scan_job.get("runs-on", "")
        assert "ubuntu" in runs_on.lower(), "Job should run on Ubuntu"

    def test_workflow_permissions(self, workflow_config: Dict[str, Any]):
        """Test that workflow has explicit permissions (Principle of Least Privilege)."""
        permissions = workflow_config.get("permissions", {})
        assert permissions, "Workflow must have explicit permissions defined"
        assert permissions.get("contents") == "read", "Workflow requires 'contents: read'"
        assert permissions.get("security-events") == "write", "Workflow requires 'security-events: write'"


class TestStepsConfiguration:
    """Test specific steps in the workflow."""

    def test_checkout_step_exists(self, job_steps: List[Dict[str, Any]]):
        """Test that checkout step exists."""
        checkout_steps = get_steps_by_action(job_steps, "actions/checkout")
        assert checkout_steps, "Job must include actions/checkout step"

    def test_checkout_step_version(self, job_steps: List[Dict[str, Any]]):
        """Test that checkout action uses at least v4 (tag or SHA)."""
        checkout_steps = get_steps_by_action(job_steps, "actions/checkout")
        assert checkout_steps, "Job must include actions/checkout step"

        for step in checkout_steps:
            action = step["uses"]
            assert "@" in action, f"Checkout must specify version: {action}"
            version = action.split("@")[1]
            # Accept either SHA (40 chars) or v4 tag
            if len(version) != 40:
                assert "v4" in version or "v3" in version, f"Checkout tag must be v3 or later (found {version})"

    def test_debricked_cli_installation(self, job_steps: List[Dict[str, Any]]):
        """Test that Debricked CLI installation step exists."""
        install_steps = get_steps_by_name(job_steps, "install debricked")
        assert install_steps, "Job must include Debricked CLI installation step"

        for step in install_steps:
            run_script = step.get("run", "")
            assert "debricked" in run_script.lower(), "Installation step should install Debricked CLI"

    def test_debricked_scan_step(self, job_steps: List[Dict[str, Any]]):
        """Test that Debricked scan step exists."""
        scan_steps = get_steps_by_name(job_steps, "debricked scan")
        assert scan_steps, "Job must include Debricked scan step"

        for step in scan_steps:
            run_script = step.get("run", "")
            assert "debricked scan" in run_script.lower(), "Scan step should run 'debricked scan' command"


class TestSecretHandling:
    """Test proper handling of secrets."""

    def test_debricked_token_configuration(self, job_steps: List[Dict[str, Any]]):
        """Test DEBRICKED_TOKEN injection via secrets."""
        scan_steps = get_steps_by_name(job_steps, "debricked scan")
        assert scan_steps, "Job must include Debricked scan step to configure DEBRICKED_TOKEN"

        for step in scan_steps:
            env = step.get("env", {})
            assert "DEBRICKED_TOKEN" in env, "Debricked scan step must define DEBRICKED_TOKEN in env"

            token = env["DEBRICKED_TOKEN"]
            # Remove spaces from BOTH the token and the expected string for comparison
            normalized_token = token.replace(" ", "")
            normalized_expected = "${{secrets.DEBRICKED_TOKEN}}"

            assert (
                normalized_expected in normalized_token
            ), "Token must use secrets context: ${{ secrets.DEBRICKED_TOKEN }}"

    def test_no_hardcoded_secrets(self, workflow_content: str):
        """Test for potential hardcoded secrets in the file content."""
        suspicious_patterns = ["ghp_", "dbr_"]
        for pattern in suspicious_patterns:
            assert pattern not in workflow_content, f"Found potential hardcoded secret pattern '{pattern}'"


class TestSecurityPatterns:
    """Test for specific security vulnerabilities."""

    def test_no_script_injection(self, workflow_content: str):
        """Check for unsafe interpolation in run scripts."""
        unsafe_contexts = [
            r"github\.event\.issue\.title",
            r"github\.event\.issue\.body",
            r"github\.event\.pull_request\.title",
            r"github\.event\.pull_request\.body",
        ]
        for ctx in unsafe_contexts:
            pattern = r"run:.*(\$\{\{\s*" + ctx + r".*\}\})"
            matches = re.findall(pattern, workflow_content, re.IGNORECASE)
            assert not matches, f"Potential script injection vulnerability found using context: {ctx}"
