"""
Comprehensive tests for the Debricked vulnerability scanning workflow.

This module validates the debricked.yml workflow file to ensure:
- Proper YAML structure and syntax
- Required fields and configuration
- Security best practices (permissions, injection prevention)
- Integration with Debricked actions
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
    """Get the vulnerabilities-scan job configuration."""
    jobs = workflow_config.get("jobs", {})
    if "vulnerabilities-scan" not in jobs:
        pytest.fail("Workflow missing required job: 'vulnerabilities-scan'")
    return jobs["vulnerabilities-scan"]


@pytest.fixture(scope="module")
def job_steps(scan_job: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get the list of steps from the scan job."""
    return scan_job.get("steps", [])


# --- Helpers ---


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
        assert "debricked" in name.lower(), "Workflow name should mention 'Debricked'"

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

    def test_triggers_on_push_to_main(self, workflow_config: Dict[str, Any]):
        """Test that workflow triggers on push to main branch."""
        triggers = workflow_config.get("on", {})
        assert "push" in triggers, "Workflow should trigger on 'push'"

        push_config = triggers.get("push", {})
        if isinstance(push_config, dict) and "branches" in push_config:
            assert "main" in push_config["branches"], "Workflow should trigger on push to 'main' branch"
        assert "push" in trigger_keys, "Workflow should trigger on 'push' to main branch"
        assert "workflow_dispatch" in trigger_keys, "Workflow should support 'workflow_dispatch' for manual testing"

    def test_job_permissions(self, scan_job: Dict[str, Any]):
        """Test that job has explicit permissions (Principle of Least Privilege)."""
        permissions = scan_job.get("permissions", {})
        assert permissions, "Job must have explicit permissions defined"
        assert permissions.get("contents") == "read", "Job requires 'contents: read'"
        assert permissions.get("security-events") == "write", "Job requires 'security-events: write'"


class TestStepsConfiguration:
    """Test specific steps in the workflow."""

    def test_checkout_step_version(self, job_steps: List[Dict[str, Any]]):
        """Test that checkout action exists and uses at least v4 (tag or SHA)."""
        checkout_steps = get_steps_by_action(job_steps, "actions/checkout")
        assert checkout_steps, "Job must include actions/checkout step"

        for step in checkout_steps:
            action = step["uses"]
            assert "@" in action, f"Checkout must specify version: {action}"
            version = action.split("@")[1]
            # Accept either SHA (40 chars) or v4 tag
            if len(version) != 40:
                assert "v4" in version, f"Checkout tag must be v4 or later (found {version})"

    def test_debricked_action_version(self, job_steps: List[Dict[str, Any]]):
        """Test that Debricked action exists and uses at least v4 (tag or SHA)."""
        debricked_steps = get_steps_by_action(job_steps, "debricked")
        assert debricked_steps, "Job must include Debricked action"

        for step in debricked_steps:
            action = step["uses"]
            assert "@" in action, f"Debricked action must specify version: {action}"
            version = action.split("@")[1]
            if len(version) != 40:
                assert "v4" in version, f"Debricked action tag must be v4 or later (found {version})"


class TestSecretHandling:
    """Test proper handling of secrets."""

    def test_debricked_token_configuration(self, job_steps: List[Dict[str, Any]]):
        """Test DEBRICKED_TOKEN injection via secrets."""
        debricked_steps = get_steps_by_action(job_steps, "debricked")
        assert debricked_steps, "Job must include Debricked action to configure DEBRICKED_TOKEN"
        for step in debricked_steps:
            env = step.get("env", {})
            assert "DEBRICKED_TOKEN" in env, "Debricked step must define DEBRICKED_TOKEN in env"

            token = env["DEBRICKED_TOKEN"]
            # Fix: Remove spaces from BOTH the token and the expected string for comparison
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
