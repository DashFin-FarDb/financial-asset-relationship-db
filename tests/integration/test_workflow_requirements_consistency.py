"""
Integration tests for workflow and requirements consistency.

This module tests that the GitHub workflows and requirements files
are consistent with each other, ensuring that:
- Workflows reference packages that exist in requirements
- Python versions are consistent
- Node versions are consistent
- Dependencies are properly specified

Tests cover recent simplifications:
- Removal of tiktoken from workflows and requirements
- Simplified PyYAML usage
- Consistent environment setup
"""

from pathlib import Path
from typing import Any, Dict, Set

import pytest
import yaml


class TestWorkflowRequirementsConsistency:
    """Test consistency between workflows and requirements files."""

    @pytest.fixture
    def requirements_dev(self) -> Set[str]:
        """Load package names from requirements-dev.txt."""
        req_path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        packages = set()

        try:
            with open(req_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pkg_name = line.split("==")[0].split(">=")[0].split("[")[0].strip().lower()
                        packages.add(pkg_name)
        except FileNotFoundError:
            pytest.fail(f"requirements-dev.txt not found at {req_path}")
        except Exception as e:
            pytest.fail(f"Failed to read or parse requirements-dev.txt at {req_path}: {e}")

        return packages

    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """Load PR agent workflow."""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "pr-agent.yml"
        try:
            with open(workflow_path, "r") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"Failed to parse workflow YAML at {workflow_path}: {e}")

    def test_pyyaml_in_requirements_for_workflows(self, requirements_dev: Set[str]):
        """Test that PyYAML is in requirements for workflow YAML processing."""
        yaml_packages = {"pyyaml", "yaml"}

        has_yaml = any(pkg in requirements_dev for pkg in yaml_packages)
        assert has_yaml, "PyYAML should be in requirements-dev.txt for workflow testing"

    def test_tiktoken_removed_from_requirements(self, requirements_dev: Set[str]):
        """Test that tiktoken has been removed as part of simplification."""
        assert (
            "tiktoken" not in requirements_dev
        ), "tiktoken should be removed from requirements as part of simplification"

    def test_pr_agent_workflow_doesnt_install_tiktoken(self, pr_agent_workflow: Dict[str, Any]):
        """Test that PR agent workflow no longer tries to install tiktoken."""
        workflow_str = str(pr_agent_workflow).lower()

        assert "tiktoken" not in workflow_str, "PR agent workflow should not reference tiktoken after simplification"

    def test_workflow_python_version_consistency(self, pr_agent_workflow: Dict[str, Any]):
        """Test that Python version in workflow is consistent."""
        jobs = pr_agent_workflow.get("jobs", {})
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            python_versions = []
            for step in steps:
                if "uses" in step and "setup-python" in step["uses"]:
                    if "with" in step and "python-version" in step["with"]:
                        python_versions.append(step["with"]["python-version"])

            # All Python versions in a job should match
            if len(python_versions) > 1:
                assert (
                    len(set(python_versions)) == 1
                ), f"Job '{job_name}' has inconsistent Python versions: {python_versions}"

    def test_workflow_installs_python_dependencies(self, pr_agent_workflow: Dict[str, Any]):
        """Test that workflow installs Python dependencies correctly.

        Allows exceptions for jobs that intentionally do not install dependencies.
        """
        # Jobs that set up Python but are allowed to skip dependency installation
        allowed_without_deps = {
            # add job ids here if they legitimately don't need deps
            # e.g., 'label_check', 'docs_lint'
        }

        for job_name, job_config in pr_agent_workflow.get("jobs", {}).items():
            steps = job_config.get("steps", [])

            has_python_setup = False
            has_dep_install = False

            for step in steps:
                if "uses" in step and "setup-python" in str(step.get("uses", "")):
                    has_python_setup = True

                run_cmd = str(step.get("run", "")).lower()
                if "pip install" in run_cmd or "python -m pip install" in run_cmd:
                    has_dep_install = True

            # If Python is setup, dependencies should be installed unless explicitly allowed
            if has_python_setup and job_name not in allowed_without_deps:
                assert has_dep_install, f"Job '{job_name}' sets up Python but doesn't install dependencies"


class TestSimplificationConsistency:
    """Test that simplifications are consistent across all files."""

    def test_no_context_chunker_script_references(self):
        """Test that references to deleted context_chunker.py are removed."""
        pr_agent_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "pr-agent.yml"

        with open(pr_agent_path, "r") as f:
            content = f.read()

        assert "context_chunker.py" not in content, "PR agent workflow should not reference deleted context_chunker.py"

    def test_simplified_greetings_messages(self):
        """Test that greetings workflow has simplified messages."""
        greetings_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "greetings.yml"

        with open(greetings_path, "r") as f:
            data = yaml.safe_load(f)

        jobs = data.get("jobs") or {}
        assert isinstance(jobs, dict) and jobs, "greetings.yml is missing 'jobs' section"

        greeting_job = jobs.get("greeting") or {}
        assert isinstance(greeting_job, dict) and greeting_job, "greetings.yml is missing 'jobs.greeting' section"

        steps = greeting_job.get("steps") or []
        assert isinstance(steps, list) and steps, "greetings.yml 'jobs.greeting.steps' is missing or empty"

        for step in steps:
            if "uses" in step and "first-interaction" in step.get("uses", ""):
                with_section = step.get("with") or {}
                assert (
                    isinstance(with_section, dict) and with_section
                ), "first-interaction step is missing 'with' section"

                issue_msg = with_section.get("issue-message")
                pr_msg = with_section.get("pr-message")

                assert (
                    isinstance(issue_msg, str) and issue_msg
                ), "first-interaction 'issue-message' is missing or not a string"
                assert isinstance(pr_msg, str) and pr_msg, "first-interaction 'pr-message' is missing or not a string"

                # Messages should be simplified (not multi-paragraph)
                assert len(issue_msg) < 200, "Issue message should be simplified"
                assert len(pr_msg) < 200, "PR message should be simplified"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
