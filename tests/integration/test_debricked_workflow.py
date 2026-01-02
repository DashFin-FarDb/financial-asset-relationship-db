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
ROOT_DEBRICKED_FILE = REPO_ROOT / "debricked.yml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
WORKFLOW_DEBRICKED_FILE = WORKFLOWS_DIR / "debricked.yml"


# --- Fixtures ---


@pytest.fixture(scope="module")
def root_debricked_content() -> str:
    """Load raw content of root debricked.yml once for the module."""
    if not ROOT_DEBRICKED_FILE.exists():
        pytest.fail(f"{ROOT_DEBRICKED_FILE} does not exist.")
    return ROOT_DEBRICKED_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def debricked_config(root_debricked_content: str) -> Dict[str, Any]:
    """Parse YAML content once for the module."""
    try:
        return yaml.safe_load(root_debricked_content)
    except yaml.YAMLError as e:
        pytest.fail(f"Invalid YAML syntax in debricked.yml: {e}")


@pytest.fixture(scope="module")
def scan_job(debricked_config: Dict[str, Any]) -> Dict[str, Any]:
    """Get the vulnerabilities-scan job configuration."""
    jobs = debricked_config.get("jobs", {})
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

    def test_root_debricked_is_file(self):
        """Test that debricked.yml is a regular file."""
        assert ROOT_DEBRICKED_FILE.is_file(), "debricked.yml should be a regular file"

    def test_root_debricked_not_empty(self, root_debricked_content: str):
        """Test that the file is not empty."""
        assert len(root_debricked_content) > 0, "debricked.yml should not be empty"


class TestWorkflowStructure:
    """Test the structure and required fields."""

    def test_has_valid_name(self, debricked_config: Dict[str, Any]):
        """Test workflow name presence and description."""
        name = debricked_config.get("name", "")
        assert isinstance(name, str) and name, "Workflow must have a non-empty string name"
        assert "debricked" in name.lower(), "Workflow name should mention 'Debricked'"

    def test_triggers_events(self, debricked_config: Dict[str, Any]):
        """Test that workflow triggers on necessary events."""
        # Default to empty dict as 'on' is typically a mapping
        triggers = debricked_config.get("on", {})
        assert triggers, "Workflow triggers must not be empty"

        if isinstance(triggers, dict):
            assert "pull_request" in triggers, "Workflow should trigger on 'pull_request'"
            assert "workflow_dispatch" in triggers, "Workflow should support 'workflow_dispatch' for manual testing"
        elif isinstance(triggers, list):
            assert "pull_request" in triggers, "Workflow should trigger on 'pull_request'"
            assert "workflow_dispatch" in triggers, "Workflow should support 'workflow_dispatch' for manual testing"
        else:
            pytest.fail(f"Unexpected type for workflow 'on' triggers: {type(triggers)}")

    def test_job_runner(self, scan_job: Dict[str, Any]):
        """Test that job uses Ubuntu runner."""
        runner = scan_job.get("runs-on", "")
        assert "ubuntu" in runner.lower(), "Job should run on Ubuntu runner"

    def test_job_permissions(self, scan_job: Dict[str, Any]):
        """Test that job has explicit permissions (Principle of Least Privilege)."""
        permissions = scan_job.get("permissions", {})
        assert permissions, "Job must have explicit permissions defined"
        assert permissions.get("contents") == "read", "Job requires 'contents: read'"
        # Security scanning often needs to write security-events
        assert permissions.get("security-events") == "write", "Job requires 'security-events: write'"


class TestStepsConfiguration:
    """Test specific steps in the workflow."""

    def test_checkout_step_version(self, job_steps: List[Dict[str, Any]]):
        """Test that checkout action exists and uses at least v4."""
        checkout_steps = get_steps_by_action(job_steps, "actions/checkout")
        assert checkout_steps, "Job must include actions/checkout step"

        for step in checkout_steps:
            action = step["uses"]
            assert "@" in action, f"Checkout must specify version: {action}"
            # Check for v4 (tag or SHA) or later
            assert "v4" in action or len(action.split("@")[1]) == 40, "Checkout should use v4 or a full SHA"

    def test_debricked_action_version(self, job_steps: List[Dict[str, Any]]):
        """Test that Debricked action exists and uses at least v4."""
        debricked_steps = get_steps_by_action(job_steps, "debricked")
        assert debricked_steps, "Job must include Debricked action"

        for step in debricked_steps:
            action = step["uses"]
            assert "@" in action, f"Debricked action must specify version: {action}"
            assert "v4" in action or len(action.split("@")[1]) == 40, "Debricked action should use v4 or a full SHA"


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
            # Strict check for secrets context
            assert "${{ secrets.DEBRICKED_TOKEN }}" in token.replace(
                " ", ""
            ), "Token must use secrets context: ${{ secrets.DEBRICKED_TOKEN }}"

    def test_no_hardcoded_secrets(self, root_debricked_content: str):
        """Test for potential hardcoded secrets in the file content."""
        suspicious_patterns = ["ghp_", "dbr_"]
        for pattern in suspicious_patterns:
            assert pattern not in root_debricked_content, f"Found potential hardcoded secret pattern '{pattern}'"


class TestSecurityPatterns:
    """Test for specific security vulnerabilities."""

    def test_no_script_injection(self, root_debricked_content: str):
        """Check for unsafe interpolation in run scripts."""
        # Detects patterns like: run: echo ${{ github.event.issue.title }}
        # Unsafe context in scripts can lead to command injection
        unsafe_contexts = [
            r"github\.event\.issue\.title",
            r"github\.event\.issue\.body",
            r"github\.event\.pull_request\.title",
            r"github\.event\.pull_request\.body",
            r"github\.event\.comment\.body",
            r"github\.event\.review\.body",
        ]

        for ctx in unsafe_contexts:
            pattern = r"run:.*(\$\{\{\s*" + ctx + r".*\}\})"
            matches = re.findall(pattern, root_debricked_content, re.IGNORECASE)
            assert not matches, f"Potential script injection vulnerability found using context: {ctx}"

    def test_no_secret_logging(self, root_debricked_content: str):
        """Check for echoing secrets."""
        # Detects: echo ${{ secrets.TOKEN }}
        logging_pattern = r"(echo|print).*(\$\{\{\s*secrets\..*\}\})"
        matches = re.findall(logging_pattern, root_debricked_content, re.IGNORECASE)
        assert not matches, f"Potential secret logging found: {matches}"
