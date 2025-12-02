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


@pytest.fixture(scope='session')
def doc_content() -> str:
    """
    Load the documentation file into a single string for use by tests.
    
    Returns:
        content (str): The entire contents of the documentation file at DOC_FILE.
    """
    try:
        with open(DOC_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        pytest.fail(f"Documentation file not found: {DOC_FILE}")
    except Exception as e:
        pytest.fail(f"Could not read documentation file {DOC_FILE}: {e}")


@pytest.fixture(scope='session')
def doc_lines(doc_content: str) -> List[str]:
    """
    Return the documentation content as a list of lines preserving original line endings.
    
    Parameters:
        doc_content (str): The full documentation text to split.
    
    Returns:
        List[str]: The documentation split into lines with line ending characters preserved.
    
    Raises:
        pytest.fail: Fails the test session if `doc_content` is empty.
    """
    if not doc_content:
        pytest.fail("Loaded documentation content is empty.")
    return doc_content.splitlines(keepends=True)


@pytest.fixture(scope='session')
def section_headers(doc_lines: List[str]) -> List[str]:
    """
    Extracts Markdown section header lines from a list of document lines.
    
    Ignores lines inside fenced code blocks delimited by lines that start with "```".
    Returns header lines with surrounding whitespace removed (each line begins with one or more `#` characters).
    
    Parameters:
        doc_lines (List[str]): Lines of the Markdown document.
    
    Returns:
        List[str]: A list of header lines (stripped), e.g. "# Overview", "## Details".
    """
    headers = []
    in_code_block = False
    for line in doc_lines:
        stripped = line.lstrip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped.startswith('#'):
            headers.append(stripped.strip())
    return headers


from typing import List, Set

    def test_has_overview(self, section_headers: List[str]):
        """Test that there's an Overview section."""
        overview = [h for h in section_headers if 'overview' in h.lower()]
        assert len(overview) > 0, "Should have an Overview section"

    def test_has_generated_files_section(self, section_headers: List[str]):
        """Test that there's a section about generated files."""
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

