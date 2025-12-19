"""
Tests for TEST_GENERATION_WORKFLOW_SUMMARY.md documentation file.

This test suite validates that the documentation file exists, is well-formed,
contains required sections, and has no broken internal references.
"""

import pytest
import re
from pathlib import Path
from typing import List, Set


# Path to the documentation file
DOC_FILE = Path(__file__).parent.parent.parent / "TEST_GENERATION_WORKFLOW_SUMMARY.md"


class TestDocumentationExists:
    """Test that the documentation file exists and is readable."""
    
    def test_file_exists(self):
        """Test that TEST_GENERATION_WORKFLOW_SUMMARY.md exists."""
        assert DOC_FILE.exists(), f"Documentation file {DOC_FILE} does not exist"
    
    def test_file_is_file(self):
        """Test that the path is a file, not a directory."""
        assert DOC_FILE.is_file(), f"{DOC_FILE} is not a file"
    
    def test_file_is_readable(self):
        """Test that the file can be read."""
        try:
            with open(DOC_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                assert len(content) > 0, "Documentation file is empty"
        except Exception as e:
            pytest.fail(f"Could not read documentation file: {e}")
    
    def test_file_extension(self):
        """Test that the file has .md extension."""
        assert DOC_FILE.suffix == ".md", "Documentation file should have .md extension"


class TestDocumentationStructure:
    """Test the structure and formatting of the documentation."""

    @pytest.fixture(scope='class')
    def doc_content(self) -> str:
        """
        Return the documentation file's full text.

        Returns:
            str: Full contents of DOC_FILE read using UTF-8 encoding.
        """
        try:
            with open(DOC_FILE, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            pytest.fail(f"Documentation file not found: {DOC_FILE}")
        return [line.strip() for line in doc_lines if line.lstrip().startswith('#')]

    def test_has_overview(self, section_headers: List[str]):
        """Test that there's an Overview section."""
        overview = [h for h in section_headers if 'overview' in h.lower()]
        assert len(overview) > 0, "Should have an Overview section"

    def test_has_generated_files_section(self, section_headers: List[str]):
        """
        Checks the documentation contains at least one header about generated files.
        
        Parameters:
            section_headers (List[str]): List of markdown header lines extracted from the document; matching is case-insensitive and looks for headers containing "generated" or "file".
        """
        generated = [h for h in section_headers 
                    if 'generated' in h.lower() or 'file' in h.lower()]
        assert len(generated) > 0, "Should have a section about generated files"

    def test_has_running_section(self, section_headers: List[str]):
        """Test that there's a section about running tests."""
        running = [h for h in section_headers if 'run' in h.lower()]
        assert len(running) > 0, "Should have a section about running tests"

    def test_has_sufficient_sections(self, section_headers: List[str]):
        """Test that document has sufficient number of sections."""
        assert len(section_headers) >= 5, \
            f"Document should have at least 5 major sections, found {len(section_headers)}"
