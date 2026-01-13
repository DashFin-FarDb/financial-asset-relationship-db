"""
Tests for TEST_GENERATION_WORKFLOW_SUMMARY.md documentation file.

This test suite validates that the documentation file exists, is well-formed,
contains required sections, and has no broken internal references.
"""

import re
from pathlib import Path
from typing import List, Set

import pytest

# Path to the documentation file
DOC_FILE = Path(__file__).parent.parent.parent / "TEST_GENERATION_WORKFLOW_SUMMARY.md"


class TestDocumentationSections:
    """Test that all expected sections are present."""

    @pytest.fixture
    @staticmethod
    def section_headers() -> List[str]:
        """Extract all section headers from the document."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        return re.findall(r"^##\s+(.+)$", content, re.MULTILINE)

    def test_has_overview(self, section_headers: List[str]):
        """Test that there's an Overview section."""
        overview = [h for h in section_headers if "overview" in h.lower()]
        assert len(overview) > 0, "Should have an Overview section"

    def test_has_generated_files_section(self, section_headers: List[str]):
        """Test that there's a section about generated files."""
        generated = [h for h in section_headers if "generated" in h.lower() or "file" in h.lower()]
        assert len(generated) > 0, "Should have a section about generated files"

    def test_has_running_section(self, section_headers: List[str]):
        """Test that there's a section about running tests."""
        running = [h for h in section_headers if "run" in h.lower()]
        assert len(running) > 0, "Should have a section about running tests"

    def test_has_sufficient_sections(self, section_headers: List[str]):
        """Test that document has sufficient number of sections."""
        assert len(section_headers) >= 5, "Document should have at least 5 major sections, found {}".format(
            len(section_headers)
        )
