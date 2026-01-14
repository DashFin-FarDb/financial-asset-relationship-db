"""Shared fixtures for integration tests."""

from pathlib import Path
from typing import List, Tuple

import pytest
import yaml

REQUIREMENTS_DEV_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


def _parse_requirements_file(file_path: Path) -> List[Tuple[str, str]]:
    """Helper to parse requirements file into (package, version) tuples."""
    if not file_path.exists():
        return []

    requirements = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Simple parsing for package>=version or package==version
            # This covers standard pinned requirements
            parts = []
            if "==" in line:
                parts = line.split("==")
            elif ">=" in line:
                parts = line.split(">=")

            if len(parts) == 2:
                requirements.append((parts[0].strip(), parts[1].strip()))
            else:
                # Handle cases like just 'package' or complex specifiers if needed
                # For now, just add the raw line as package and 'any' as version
                requirements.append((line, "any"))

    return requirements


@pytest.fixture
def parsed_requirements() -> List[Tuple[str, str]]:
    """Parse requirements-dev.txt and return list of (package, version) tuples."""
    return _parse_requirements_file(REQUIREMENTS_DEV_FILE)


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
                with open(workflow_file, "r", encoding="utf-8") as f:
                    raw = f.read()
                    content = yaml.safe_load(raw)
                    if isinstance(content, dict):
                        workflows.append(
                            {
                                "path": workflow_file,
                                "content": content,
                                "raw": raw,
                            }
                        )
            except Exception:
                continue

    return workflows
