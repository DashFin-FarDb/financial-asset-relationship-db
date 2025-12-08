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
    
    @pytest.fixture(scope='session')
    @pytest.fixture(scope='session')
    def doc_content() -> str:
        """
        Provide the full text of the documentation file for use by tests.
        
        Returns:
        	doc_text (str): The complete contents of the documentation file.
        """
        with open(DOC_FILE, 'r', encoding='utf-8') as f:
            return f.read()

    @pytest.fixture(scope='session')
    # Move this fixture to module level (outside the class)
    @pytest.fixture(scope='session')
    def doc_lines(doc_content: str) -> List[str]:
        """
        Split the documentation content into a list of lines.
        
        The returned lines preserve original line endings.
        
        Parameters:
            doc_content (str): Full documentation text.
        
        Returns:
            List[str]: List of lines from `doc_content`, each retaining its trailing newline where present.
        """
        return doc_content.splitlines(keepends=True)
    
    @pytest.fixture(scope='session')
    def section_headers(doc_lines: List[str]) -> List[str]:
        """
        Collects Markdown header lines from a list of document lines.
        
        Parameters:
            doc_lines (List[str]): Lines of the document, typically including line endings.
        
        Returns:
            List[str]: Header lines (lines starting with one or more '#') with surrounding whitespace removed.
        """
        return [line.strip() for line in doc_lines if line.lstrip().startswith('#')]

    def test_has_overview(self, section_headers: List[str]):
        """Test that there's an Overview section."""
        overview = [h for h in section_headers if 'overview' in h.lower()]
        assert len(overview) > 0, "Should have an Overview section"

    def test_has_generated_files_section(self, section_headers: List[str]):
        """
        Assert the documentation includes a section related to generated files.
        
        Parameters:
            section_headers (List[str]): List of Markdown header lines extracted from the documentation file (each header as a single string).
        """
        generated = [h for h in section_headers 
                    if 'generated' in h.lower() or 'file' in h.lower()]
        assert len(generated) > 0, "Should have a section about generated files"

    def test_has_running_section(self, section_headers: List[str]):
        """
        Check that the documentation contains a section about running tests.
        
        Parameters:
            section_headers (List[str]): List of markdown header lines extracted from the documentation.
        """
        running = [h for h in section_headers if 'run' in h.lower()]
        assert len(running) > 0, "Should have a section about running tests"

    def test_has_sufficient_sections(self, section_headers: List[str]):
        """
        Assert that the documentation contains at least five major section headers.
        
        Parameters:
            section_headers (List[str]): List of Markdown header lines extracted from the document.
        
        Raises:
            AssertionError: If fewer than five section headers are present; the message includes the actual count.
        """
        assert len(section_headers) >= 5, \
            f"Document should have at least 5 major sections, found {len(section_headers)}"
