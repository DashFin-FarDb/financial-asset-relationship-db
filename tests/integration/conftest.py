"""Shared fixtures for integration tests."""

from pathlib import Path
from typing import List, Tuple

import pytest
import yaml

from tests.integration.test_requirements_dev import parse_requirements

REQUIREMENTS_DEV_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


@pytest.fixture
def parsed_requirements() -> List[Tuple[str, str]]:
    """Parse requirements-dev.txt and return list of (package, version) tuples."""
    return parse_requirements(REQUIREMENTS_DEV_FILE)


@pytest.fixture
def all_workflows() -> List[dict]:
    """
    Load and parse all GitHub Actions workflow YAML files from .github/workflows.

    Returns:
        List[dict]: A list of dictionaries containing 'path', 'content', and 'raw' keys.
    """
    workflow_dir = Path(__file__).parent.parent.parent / ".github" / "workflows"
    workflows = []
    if workflow_dir.exists():
        for workflow_file in workflow_dir.glob("*.y*ml"):
            try:
                with open(workflow_file, "r") as f:
                    raw = f.read()
                    content = yaml.safe_load(raw)
                    if isinstance(content, dict):
                        workflows.append({"path": workflow_file, "content": content, "raw": raw})
            except Exception:
                continue
    return workflows
