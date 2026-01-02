"""
Comprehensive tests for the Debricked vulnerability scanning workflow.

This module validates the debricked.yml workflow file to ensure:
- Proper YAML structure and syntax
- Required fields and configuration
- Security best practices
- Integration with Debricked actions
"""

import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

# Constants
# Assuming the structure is: repo_root/debricked.yml and repo_root/.github/workflows/debricked.yml
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
        assert "scan" in name.lower(), "Workflow name should mention 'scan'"

    def test_triggers_on_pull_request(self, debricked_config: Dict[str, Any]):
        """Test that workflow triggers on pull requests."""
        triggers = debricked_config.get("on", [])
        assert triggers, "Workflow triggers must not be empty"
        assert "pull_request" in triggers, "Workflow should trigger on 'pull_request'"

    def test_job_runner(self, scan_job: Dict[str, Any]):
        """Test that job uses Ubuntu runner."""
        runner = scan_job.get("runs-on", "")
        assert "ubuntu" in runner.lower(), "Job should run on Ubuntu runner"


class TestStepsConfiguration:
    """Test specific steps in the workflow."""

    def test_checkout_step_v4(self, job_steps: List[Dict[str, Any]]):
        """Test that checkout action exists and uses v4."""
        checkout_steps = get_steps_by_action(job_steps, "actions/checkout")
        assert checkout_steps, "Job must include actions/checkout step"

        for step in checkout_steps:
            action = step["uses"]
            assert "@v4" in action, f"Checkout should use v4, found: {action}"

    def test_debricked_action_v4(self, job_steps: List[Dict[str, Any]]):
        """Test that Debricked action exists and uses v4."""
        debricked_steps = get_steps_by_action(job_steps, "debricked")
        assert debricked_steps, "Job must include Debricked action"

        for step in debricked_steps:
            action = step["uses"]
            assert "@v4" in action, f"Debricked action should use v4, found: {action}"


class TestSecretHandling:
    """Test proper handling of secrets."""

    def test_debricked_token_configuration(self, job_steps: List[Dict[str, Any]]):
        """Test DEBRICKED_TOKEN injection via secrets."""
        debricked_steps = get_steps_by_action(job_steps, "debricked")

        for step in debricked_steps:
            env = step.get("env", {})
            assert "DEBRICKED_TOKEN" in env, "Debricked step must define DEBRICKED_TOKEN in env"

            token = env["DEBRICKED_TOKEN"]
            # Flexible check for ${{ secrets.X }} or ${{secrets.X}}
            assert (
                "${{" in token and "secrets" in token.lower()
            ), "Token must use secrets context (e.g., ${{ secrets.DEBRICKED_TOKEN }})"

    def test_no_hardcoded_secrets(self, root_debricked_content: str):
        """Test for potential hardcoded secrets in the file content."""
        suspicious_patterns = ["ghp_", "dbr_"]
        for pattern in suspicious_patterns:
            assert pattern not in root_debricked_content, f"Found potential hardcoded secret pattern '{pattern}'"


class TestFormattingAndBestPractices:
    """Test linting and best practices."""

    def test_indentation_and_tabs(self, root_debricked_content: str):
        """Test for tabs and inconsistent indentation."""
        assert "\t" not in root_debricked_content, "Workflow should not use tabs"

    def test_reasonable_file_size(self):
        """Test that workflow file is reasonably sized."""
        assert ROOT_DEBRICKED_FILE.stat().st_size < 10240, "Workflow file is too large"

    def test_workflow_focus(self, debricked_config: Dict[str, Any]):
        """Test that workflow isn't overloaded with jobs."""
        jobs = debricked_config.get("jobs", {})
        assert len(jobs) <= 2, "Debricked workflow should be focused (max 2 jobs)"


class TestWorkflowComparison:
    """Compare root workflow with the installed workflow."""

    def test_workflows_sync(self):
        """Ensure root and workflow-dir files align on key versions."""
        if not WORKFLOW_DEBRICKED_FILE.exists():
            pytest.skip(f"{WORKFLOW_DEBRICKED_FILE} does not exist yet")

        # Load workflows file
        with open(WORKFLOW_DEBRICKED_FILE, "r") as f:
            wf_config = yaml.safe_load(f)

        # Simple check: Ensure the installed workflow also uses v4
        wf_steps = wf_config["jobs"]["vulnerabilities-scan"]["steps"]
        wf_debricked = get_steps_by_action(wf_steps, "debricked")

        for step in wf_debricked:
            assert "@v4" in step["uses"], "Installed workflow should uses Debricked v4"


class TestSecurityPatterns:
    """Test for specific security vulnerabilities."""

    def test_no_script_injection(self, root_debricked_content: str):
        """Check for unsafe interpolation in run scripts."""
        # Detects patterns like: run: echo ${{ github.event.issue.title }}
        unsafe_pattern = r"run:.*(\$\{\{\s*github\.event\..*\}\})"
        matches = re.findall(unsafe_pattern, root_debricked_content, re.IGNORECASE)
        assert not matches, f"Potential script injection vulnerability found: {matches}"

    def test_no_secret_logging(self, root_debricked_content: str):
        """Check for echoing secrets."""
        # Detects: echo ${{ secrets.TOKEN }}
        logging_pattern = r"(echo|print).*(\$\{\{\s*secrets\..*\}\})"
        matches = re.findall(logging_pattern, root_debricked_content, re.IGNORECASE)
        assert not matches, f"Potential secret logging found: {matches}"
