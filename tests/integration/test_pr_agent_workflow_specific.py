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


@staticmethod
@pytest.fixture
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


@staticmethod
@pytest.fixture
def workflow_raw(workflow_file: Path) -> str:
    """
    Get the raw text of the workflow file for text-based validation.

    Returns:
        The file contents decoded as UTF-8.
    """
    with open(workflow_file, "r", encoding="utf-8") as f:
        return f.read()


@staticmethod
def test_no_duplicate_step_name_setup_python(workflow_content: Dict[str, Any]):
    """Test that there's no duplicate 'Setup Python' step name."""
    for job_name, job_config in workflow_content.get("jobs", {}).items():
        steps = job_config.get("steps", [])
        setup_python_count = sum(
            1 for step in steps if step.get("name") == "Setup Python"
        )

        assert setup_python_count <= 1, (
            f"Job '{job_name}' has {setup_python_count} 'Setup Python' steps, expected at most 1"
        )


@staticmethod
def test_no_duplicate_with_blocks_in_setup_python(workflow_raw: str):
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

            assert with_count <= 1, (
                f"Setup Python step at line {i + 1} has {with_count} 'with:' blocks, expected 1"
            )


@staticmethod
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

            assert version_count == 1, (
                f"Setup Python at line {i + 1} has {version_count} python-version definitions, expected 1"
            )
