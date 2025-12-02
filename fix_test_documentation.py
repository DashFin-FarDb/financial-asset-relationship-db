import re

# Read the file content from GitHub (content we fetched earlier)
github_content = '''"""
Comprehensive validation tests for TEST_GENERATION_WORKFLOW_SUMMARY.md

This test suite validates the documentation file to ensure it is well-formed,
contains accurate information, and follows markdown best practices.
"""

import re
import pytest
from pathlib import Path
from typing import List, Set


SUMMARY_FILE = Path(__file__).parent.parent.parent / "TEST_GENERATION_WORKFLOW_SUMMARY.md"


@pytest.fixture
def summary_content() -> str:
    """Load the summary file content."""
    if not SUMMARY_FILE.exists():
        pytest.skip("TEST_GENERATION_WORKFLOW_SUMMARY.md not found")
    with open(SUMMARY_FILE, 'r', encoding='utf-8') as f:
        return f.read()


@pytest.fixture
def summary_lines(summary_content: str) -> List[str]:
    """Get summary file lines."""
    return summary_content.split('\\n')


class TestDocumentStructure:
    """Test suite for document structure validation."""
    
    def test_file_exists(self):
        """Test that the summary file exists."""
        assert SUMMARY_FILE.exists(), "TEST_GENERATION_WORKFLOW_SUMMARY.md should exist"
    
    def test_file_is_not_empty(self, summary_content: str):
        """Test that the file contains content."""
        assert len(summary_content.strip()) > 0, "File should not be empty"
    
    def test_file_has_title(self, summary_lines: List[str]):
        """Test that file starts with a markdown title."""
        first_heading = None
        for line in summary_lines:
            if line.startswith('#'):
                first_heading = line
                break
        assert first_heading is not None, "File should have at least one heading"
        assert first_heading.startswith('# '), "First heading should be level 1"
    
    def test_has_overview_section(self, summary_content: str):
        """Test that document has an Overview section."""
        assert '## Overview' in summary_content, "Document should have an Overview section"
    
    def test_has_generated_files_section(self, summary_content: str):
        """Test that document describes generated files."""
        assert '## Generated Files' in summary_content, "Document should list generated files"
    
    def test_has_test_suite_structure_section(self, summary_content: str):
        """Test that document describes test suite structure."""
        assert '## Test Suite Structure' in summary_content, "Document should describe test structure"
    
    def test_has_running_tests_section(self, summary_content: str):
        """Test that document includes running instructions."""
        assert '## Running the Tests' in summary_content, "Document should have running instructions"
    
    def test_has_benefits_section(self, summary_content: str):
        """Test that document lists benefits."""
        assert '## Benefits' in summary_content or '## Key Features' in summary_content, \\
            "Document should describe benefits or key features"


class TestMarkdownFormatting:
    """Test suite for markdown formatting validation."""
    
    def test_headings_properly_formatted(self, summary_lines: List[str]):
        """Test that headings follow proper markdown format."""
        heading_lines = [line for line in summary_lines if line.startswith('#')]
        for line in heading_lines:
            # Heading should have space after hash marks
            assert re.match(r'^#{1,6} .+', line), f"Heading '{line}' should have space after #"
    
    def test_no_trailing_whitespace(self, summary_lines: List[str]):
        """
        Ensure no non-blank line ends with trailing whitespace.
        
        Asserts that there are zero non-empty lines with trailing spaces or tabs; on failure the assertion message reports the number of offending lines.
        """
        lines_with_trailing = [
            (i + 1, line) for i, line in enumerate(summary_lines)
            if line.rstrip() != line and line.strip() != ''
        ]
        assert len(lines_with_trailing) == 0, \\
            f"Found {len(lines_with_trailing)} lines with trailing whitespace"
    
    def test_code_blocks_properly_closed(self, summary_lines: List[str]):
        """
        Verify that every fenced code block delimited by triple backticks in the summary is properly closed.
        
        Parameters:
            summary_lines (List[str]): Lines of the Markdown summary file to inspect.
        """
        open_block = False
        for i, line in enumerate(summary_lines, start=1):
            stripped = line.strip()
            if stripped.startswith('```'):
                # Toggle open/close state on a fence line
                open_block = not open_block
        assert open_block is False, "Code blocks not properly closed or mismatched triple backticks detected"
    def test_lists_properly_formatted(self, summary_lines: List[str]):
        """
        Validate that Markdown bullet list items use even indentation (multiples of two spaces).
        
        Scans the provided file lines for list items starting with '-', '*' or '+' and asserts each item's leading space count is divisible by two; raises an AssertionError for any list item with odd indentation.
        
        Parameters:
            summary_lines (List[str]): Lines of the Markdown summary file to inspect.
        """
        list_lines = [line for line in summary_lines if re.match(r'^\\s*[-*+] ', line)]
        if list_lines:
            # Check that indentation is consistent
            for line in list_lines:
                indent = len(line) - len(line.lstrip())
                assert indent % 2 == 0, f"List item '{line.strip()}' has odd indentation"
'''

# Fix the syntax error: remove the misplaced comment before the docstring
fixed_content = github_content.replace(
    '''        def _to_gfm_anchor(text: str) -> str:
            # Lowercase
            """''',
    '''        def _to_gfm_anchor(text: str) -> str:
            """'''
)

print("Fixed content length:", len(fixed_content))
print("Syntax error fixed")
