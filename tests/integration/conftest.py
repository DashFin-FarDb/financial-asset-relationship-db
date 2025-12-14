"""Shared fixtures for integration tests."""

from pathlib import Path
from typing import List, Tuple

import pytest

from tests.integration.test_requirements_dev import parse_requirements

REQUIREMENTS_DEV_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


@pytest.fixture
def parsed_requirements() -> List[Tuple[str, str]]:
    """Parse requirements-dev.txt and return list of (package, version) tuples."""
    return parse_requirements(REQUIREMENTS_DEV_FILE)