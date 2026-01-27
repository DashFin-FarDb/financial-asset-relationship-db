"""
Tests for TEST_GENERATION_WORKFLOW_SUMMARY.md documentation file.

This test suite validates that the documentation file exists, is well-formed,
contains required sections, and has no broken internal references.
"""

from pathlib import Path
from typing import List, Set

import pytest

# Path to the documentation file
DOC_FILE = Path(__file__).parent.parent.parent / "TEST_GENERATION_WORKFLOW_SUMMARY.md"


class TestDocumentationExists:
    """Test that the documentation file exists and is readable."""

    @staticmethod
    def test_file_exists():
        """Test that TEST_GENERATION_WORKFLOW_SUMMARY.md exists."""
        assert DOC_FILE.exists(), f"Documentation file {DOC_FILE} does not exist"

    @staticmethod
    def test_file_is_file():
        """Test that the path is a file, not a directory."""
        assert DOC_FILE.is_file(), f"{DOC_FILE} is not a file"

    @staticmethod
    def test_file_is_readable():
        """Test that the file can be read."""
        try:
            with open(DOC_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                assert len(content) > 0, "Documentation file is empty"
        except Exception as e:
            pytest.fail(f"Could not read documentation file: {e}")

    @staticmethod
    @staticmethod
    def test_file_extension():
        """Test that the file has .md extension."""
        assert DOC_FILE.suffix == ".md", "Documentation file should have .md extension"


class TestDocumentationStructure:
    """Test the structure and formatting of the documentation."""

    @pytest.fixture(scope="class")
    def doc_content(self) -> str:
        """
        Read and return the full text of the documentation file.

        Returns:
            str: The full contents of DOC_FILE decoded as UTF-8.

        Raises:
            Failed: Fails the test via pytest.fail if DOC_FILE does not exist.
        """
        try:
            with open(DOC_FILE, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            pytest.fail(f"Documentation file not found: {DOC_FILE}")

    def test_has_overview(self, section_headers: List[str]):
        """Test that there's an Overview section."""
        overview = [h for h in section_headers if "overview" in h.lower()]
        assert len(overview) > 0, "Should have an Overview section"

    def test_has_generated_files_section(self, section_headers: List[str]):
        """
        Ensure the document includes at least one markdown header referencing generated files.

        Parameters:
            section_headers (List[str]): List of markdown header lines to search; matching is case-insensitive and looks for headers containing the words "generated" or "file".
        """
        generated = [
            h
            for h in section_headers
            if "generated" in h.lower() or "file" in h.lower()
        ]
        assert len(generated) > 0, "Should have a section about generated files"

    def test_has_running_section(self, section_headers: List[str]):
        """
        Verify the documentation includes at least one header related to running tests.

        Searches the provided list of markdown header lines for any header containing the substring "run" (case-insensitive) and asserts that at least one match exists.

        Parameters:
            section_headers (List[str]): Markdown header lines extracted from the documentation file.
        """
        running = [h for h in section_headers if "run" in h.lower()]
        assert len(running) > 0, "Should have a section about running tests"

    def test_has_sufficient_sections(self, section_headers: List[str]):
        """
        Ensure the documentation contains at least five major markdown section headers.

        Parameters:
            section_headers (List[str]): Extracted markdown header lines from the document (for example, lines beginning with `#`).
        """
        assert len(section_headers) >= 5, (
            f"Document should have at least 5 major sections, found {len(section_headers)}"
        )
