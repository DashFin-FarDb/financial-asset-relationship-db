# pylint: disable=redefined-outer-name, unused-argument
"""
Comprehensive tests for the Debricked vulnerability scanning workflow.

This module validates the debricked.yml workflow file to ensure:
- Proper YAML structure and syntax
- Required fields and configuration
- Security best practices (permissions, injection prevention)
- Integration with Debricked actions
- Compliance with issue #492 requirements
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
        """Test that workflow triggers on necessary events (PR, push, manual dispatch)."""
        triggers = workflow_config.get("on", {})
        assert triggers, "Workflow triggers must not be empty"

        # Normalize triggers to a set of keys
        if isinstance(triggers, dict):
            trigger_keys = set(triggers.keys())
        elif isinstance(triggers, list):
            trigger_keys = set(triggers)
        else:
            pytest.fail(f"Unexpected type for workflow 'on' triggers: {type(triggers)}")

        # Requirement: Run on PRs to main
        assert "pull_request" in trigger_keys, "Workflow should trigger on 'pull_request'"

        # Requirement: Run on pushes to main
        assert "push" in trigger_keys, "Workflow should trigger on 'push'"

        # Requirement: Support manual dispatch for adhoc verification
        assert "workflow_dispatch" in trigger_keys, "Workflow should support 'workflow_dispatch' for manual testing"

    def test_triggers_target_main_branch(self, workflow_config: Dict[str, Any]):
        """Test that PR and push triggers target the main branch."""
        triggers = workflow_config.get("on", {})

        if isinstance(triggers, dict):
            # Check pull_request targets main
            if "pull_request" in triggers and isinstance(triggers["pull_request"], dict):
                pr_branches = triggers["pull_request"].get("branches", [])
                assert "main" in pr_branches, "pull_request should target 'main' branch"

            # Check push targets main
            if "push" in triggers and isinstance(triggers["push"], dict):
                push_branches = triggers["push"].get("branches", [])
                assert "main" in push_branches, "push should target 'main' branch"

    def test_job_permissions(self, scan_job: Dict[str, Any]):
        """Test that job has explicit permissions (Principle of Least Privilege)."""
        permissions = scan_job.get("permissions", {})
        assert permissions, "Job must have explicit permissions defined"
        assert permissions.get("contents") == "read", "Job requires 'contents: read'"
        assert permissions.get("security-events") == "write", "Job requires 'security-events: write'"

    def test_runs_on_ubuntu(self, scan_job: Dict[str, Any]):
        """Test that job runs on a supported Ubuntu runner."""
        runs_on = scan_job.get("runs-on", "")
        assert "ubuntu" in runs_on.lower(), "Job should run on Ubuntu runner"


class TestStepsConfiguration:
    """Test specific steps in the workflow."""

    @staticmethod
    def test_checkout_step_exists(job_steps: List[Dict[str, Any]]):
        """Test that checkout action exists."""
        checkout_steps = get_steps_by_action(job_steps, "actions/checkout")
        assert checkout_steps, "Job must include actions/checkout step"

    @staticmethod
    def test_checkout_step_version_pinned(job_steps: List[Dict[str, Any]]):
        """Test that checkout action uses pinned version (SHA or tag)."""
        checkout_steps = get_steps_by_action(job_steps, "actions/checkout")
        assert checkout_steps, "Job must include actions/checkout step"

        for step in checkout_steps:
            action = step["uses"]
            assert "@" in action, f"Checkout must specify version: {action}"
            version = action.split("@")[1]
            # Accept either SHA (40 chars) or v4+ tag
            if len(version) == 40:
                # SHA format - verify it's hexadecimal
                assert all(
                    c in "0123456789abcdef" for c in version.lower()
                ), f"Checkout version should be valid SHA: {version}"
            else:
                # Tag format - should be v4 or later
                assert "v4" in version or "v5" in version, f"Checkout tag must be v4 or later (found {version})"

    @staticmethod
    def test_debricked_action_exists(job_steps: List[Dict[str, Any]]):
        """Test that Debricked action exists."""
        debricked_steps = get_steps_by_action(job_steps, "debricked")
        assert debricked_steps, "Job must include Debricked action"

    @staticmethod
    def test_debricked_action_version_pinned(job_steps: List[Dict[str, Any]]):
        """Test that Debricked action uses pinned version (SHA or tag)."""
        debricked_steps = get_steps_by_action(job_steps, "debricked")
        assert debricked_steps, "Job must include Debricked action"

        for step in debricked_steps:
            action = step["uses"]
            assert "@" in action, f"Debricked action must specify version: {action}"
            version = action.split("@")[1]
            # Accept either SHA (40 chars) or v4+ tag
            if len(version) == 40:
                # SHA format - verify it's hexadecimal
                assert all(
                    c in "0123456789abcdef" for c in version.lower()
                ), f"Debricked version should be valid SHA: {version}"
            else:
                # Tag format - should be v4 or later
                assert version.startswith("v") and any(
                    char.isdigit() for char in version
                ), f"Debricked action tag must be a valid semantic version (found {version})"


class TestSecretHandling:
    """Test proper handling of secrets."""

    @staticmethod
    def test_debricked_token_configuration(job_steps: List[Dict[str, Any]]):
        """Test DEBRICKED_TOKEN injection via secrets."""
        debricked_steps = get_steps_by_action(job_steps, "debricked")
        assert debricked_steps, "Job must include Debricked action to configure DEBRICKED_TOKEN"

        for step in debricked_steps:
            env = step.get("env", {})
            assert "DEBRICKED_TOKEN" in env, "Debricked step must define DEBRICKED_TOKEN in env"

            token = env["DEBRICKED_TOKEN"]
            # Use strict pattern match to ensure exact secret reference format
            # Allows optional whitespace around 'secrets.DEBRICKED_TOKEN' but nothing else
            assert re.fullmatch(
                r"\$\{\{\s*secrets\.DEBRICKED_TOKEN\s*\}\}", token.strip()
            ), f"DEBRICKED_TOKEN must be exactly '${{ secrets.DEBRICKED_TOKEN }}', found '{token}'"

    @staticmethod
    def test_no_hardcoded_secrets(workflow_content: str):
        """Test for potential hardcoded secrets in the file content."""
        suspicious_patterns = [
            "ghp_",  # GitHub personal access token
            "gho_",  # GitHub OAuth token
            "ghu_",  # GitHub user token
            "ghs_",  # GitHub server token (except in comments)
            "ghr_",  # GitHub refresh token
            "dbr_",  # Debricked token prefix
        ]

        # Split content into lines to check context
        lines = workflow_content.split("\n")
        for i, line in enumerate(lines, 1):
            # Skip comment lines
            if line.strip().startswith("#"):
                continue

            for pattern in suspicious_patterns:
                if pattern in line:
                    pytest.fail(f"Found potential hardcoded secret pattern '{pattern}' at line {i}: {line.strip()}")


class TestSecurityPatterns:
    """Test for specific security vulnerabilities."""

    @staticmethod
    def test_no_script_injection(workflow_content: str):
        """Check for unsafe interpolation in run scripts."""
        unsafe_contexts = [
            r"github\\.event\\.issue\\.title",
            r"github\\.event\\.issue\\.body",
            r"github\\.event\\.pull_request\\.title",
            r"github\\.event\\.pull_request\\.body",
        ]
        for ctx in unsafe_contexts:
            pattern = r"run:.*(\$\{\{\s*" + ctx + r".*\}\})"
            matches = re.findall(pattern, workflow_content, re.IGNORECASE)
            assert not matches, f"Potential script injection vulnerability found using context: {ctx}"

    @staticmethod
    def test_no_secret_logging(workflow_content: str):
        """Test that secrets are not echoed or printed to logs."""
        secret_logging_patterns = [
            r"echo.*\$\{\{.*secrets\\.",
            r"print.*\$\{\{.*secrets\\.",
            r"console\\.log.*\$\{\{.*secrets\\.",
        ]

        for pattern in secret_logging_patterns:
            matches = re.findall(pattern, workflow_content, re.IGNORECASE)
            assert not matches, f"Potential secret logging detected with pattern: {pattern}"


class TestWorkflowDocumentation:
    """Test that workflow has proper documentation."""

    @staticmethod
    def test_has_comments(workflow_content: str):
        """Test that workflow file contains explanatory comments."""
        # Should have at least some comment lines
        comment_lines = [line for line in workflow_content.split("\n") if line.strip().startswith("#")]
        assert len(comment_lines) > 0, "Workflow should have explanatory comments"

    @staticmethod
    def test_documents_security_features(workflow_content: str):
        """Test that security features are documented."""
        content_lower = workflow_content.lower()

        # Should document key security aspects
        security_keywords = ["secret", "permission", "security"]
        found_keywords = [kw for kw in security_keywords if kw in content_lower]

        assert len(found_keywords) > 0, "Workflow should document security features in comments"


class TestVersionConsistency:
    """Test version consistency and supply-chain security."""

    @staticmethod
    def test_actions_use_consistent_versioning(job_steps: List[Dict[str, Any]]):
        """Test that all actions use consistent versioning approach."""
        for step in job_steps:
            if "uses" in step:
                action = step["uses"]
                assert "@" in action, f"Action must specify version: {action}"

                # Extract version
                version = action.split("@")[1]

                # Should be either SHA (40 hex chars) or semantic version tag
                is_sha = len(version) == 40 and all(c in "0123456789abcdef" for c in version.lower())
                is_semver = version.startswith("v") and any(char.isdigit() for char in version)

                assert is_sha or is_semver, f"Action version should be SHA or semantic version tag: {action}"

    @staticmethod
    def test_no_mutable_tags(job_steps: List[Dict[str, Any]]):
        """Test that actions don't use mutable tags like 'latest', 'main', 'master'."""
        mutable_tags = ["latest", "main", "master", "develop"]

        for step in job_steps:
            if "uses" in step:
                action = step["uses"]
                version = action.split("@")[1] if "@" in action else ""

                assert version.lower() not in mutable_tags, f"Action should not use mutable tag '{version}': {action}"


class TestComplianceWithIssue492:
    """Test compliance with specific requirements from issue #492."""

    @staticmethod
    def test_workflow_location():
        """Test that workflow is at the correct location."""
        expected_path = REPO_ROOT / ".github" / "workflows" / "debricked.yml"
        assert expected_path.exists(), "Workflow must be at .github/workflows/debricked.yml"

    @staticmethod
    def test_supports_all_required_triggers(workflow_config: Dict[str, Any]):
        """Test that workflow supports all required trigger events."""
        triggers = workflow_config.get("on", {})

        if isinstance(triggers, dict):
            trigger_keys = set(triggers.keys())
        elif isinstance(triggers, list):
            trigger_keys = set(triggers)
        else:
            trigger_keys = set()

        required_triggers = {"pull_request", "push", "workflow_dispatch"}
        missing_triggers = required_triggers - trigger_keys

        assert not missing_triggers, f"Workflow missing required triggers: {missing_triggers}"

    @staticmethod
    def test_uses_github_secrets(job_steps: List[Dict[str, Any]]):
        """Test that workflow uses GitHub Actions secrets for authentication."""
        debricked_steps = get_steps_by_action(job_steps, "debricked")

        for step in debricked_steps:
            env = step.get("env", {})
            if "DEBRICKED_TOKEN" in env:
                token_value = env["DEBRICKED_TOKEN"]
                assert "secrets.DEBRICKED_TOKEN" in token_value, "Must use GitHub Actions secrets for DEBRICKED_TOKEN"

    @staticmethod
    def test_minimal_permissions(scan_job: Dict[str, Any]):
        """Test that workflow uses minimal required permissions."""
        permissions = scan_job.get("permissions", {})

        # Should have exactly the required permissions, no more
        required_permissions = {"contents", "security-events"}
        granted_permissions = set(permissions.keys())

        # All required permissions should be present
        assert required_permissions.issubset(
            granted_permissions
        ), f"Missing required permissions: {required_permissions - granted_permissions}"

        # No write permissions except security-events
        for perm, value in permissions.items():
            if perm != "security-events" and value == "write":
                pytest.fail(f"Unnecessary write permission granted: {perm}")

    @staticmethod
    def test_ubuntu_runner(scan_job: Dict[str, Any]):
        """Test that workflow uses a supported Ubuntu runner."""
        runs_on = scan_job.get("runs-on", "")
        assert "ubuntu" in runs_on.lower(), "Workflow must use a supported Ubuntu runner"
