"""Unit tests for validating summary documentation markdown files.

This module tests the summary documentation files created in this branch:
- ENHANCED_TEST_SUMMARY.md
- FINAL_TEST_SUMMARY.md
- TEST_DOCUMENTATION_SUMMARY.md

Tests ensure:
- Valid markdown structure
- Required sections are present
- Content accuracy and consistency
- No broken internal references
- Proper formatting and readability
"""

import re
from pathlib import Path

import pytest


class TestEnhancedTestSummary:
    """Test cases for ENHANCED_TEST_SUMMARY.md."""

    @pytest.fixture
    def summary_path(self):
        """
    @staticmethod
    @pytest.fixture
    def summary_path():
        """
        Provide the path to the enhanced test summary file.

        Returns:
            Path: Path to "ENHANCED_TEST_SUMMARY.md".
        """
        return Path("ENHANCED_TEST_SUMMARY.md")

    @pytest.fixture
    def summary_content(self, summary_path):
        """
        Load the text content of the summary file at the given path.

        Parameters:
                summary_path(Path): Path to the summary markdown file to read.

        Returns:
                str: The file content.

        Raises:
                AssertionError: If `summary_path` does not exist.
        """
        assert summary_path.exists(), "ENHANCED_TEST_SUMMARY.md not found"
        with open(summary_path, encoding="utf-8") as f:
            return f.read()

    def test_summary_file_exists(self, summary_path):
        """Test that ENHANCED_TEST_SUMMARY.md exists."""
        assert summary_path.exists()
        assert summary_path.is_file()

    def test_summary_not_empty(self, summary_content):
        """Test that summary file is not empty."""
        assert len(summary_content.strip()) > 0

    def test_summary_has_main_title(self, summary_content):
        """
        Verify the summary contains the main title "Enhanced Test Suite Summary".

        Parameters:
            summary_content(str): Full text content of the summary markdown file being tested.
        """
        assert "# Enhanced Test Suite Summary" in summary_content

    def test_summary_has_executive_summary(self, summary_content):
        """Test that summary has Executive Summary section."""
        assert "## Executive Summary" in summary_content

    def test_summary_has_statistics_table(self, summary_content):
        """Test that summary includes test statistics table."""
        assert "| Metric |" in summary_content
        assert "Test Classes" in summary_content
        assert "Test Functions" in summary_content

    def test_summary_mentions_new_test_classes(self, summary_content):
        """
        Verify the summary contains the expected new test class names.

        Checks that the summary content mentions TestDocumentationEdgeCases, TestDocumentationPerformance,
        TestDocumentationRobustness and TestDocumentationSchemaValidation.
        """
        assert "TestDocumentationEdgeCases" in summary_content
        assert "TestDocumentationPerformance" in summary_content
        assert "TestDocumentationRobustness" in summary_content
        assert "TestDocumentationSchemaValidation" in summary_content

    def test_summary_includes_test_counts(self, summary_content):
        """Test that summary includes specific test counts."""
        # Should mention 64 tests total
        assert "64" in summary_content

    def test_summary_valid_markdown_headings(self, summary_content):
        """
        Assert that every Markdown heading in the provided content has a space after the leading `  # ` characters.

        Parameters:
            summary_content(str): Full text of the summary Markdown file to validate.

        Raises:
            AssertionError: If any heading line does not have a space after its `  # ` markers; the error message includes the failing line number.
        """
        lines = summary_content.split("\n")
        for i, line in enumerate(lines, 1):
            if line.startswith("#"):
                # Headings should have space after #
                assert re.match(r"^#+\s", line), f"Line {i}: Heading missing space after #"

    def test_summary_no_broken_formatting(self, summary_content):
        """
        Verify the summary contains no malformed Markdown heading markers(for example, consecutive `  # ` characters without the required space).

        Parameters:
            summary_content(str): The full text content of the summary markdown file to validate.
        """
        # Check for common markdown issues
        assert "##" not in summary_content.replace("##", "# #")  # No triple hashes without space


class TestFinalTestSummary:
    """Test cases for FINAL_TEST_SUMMARY.md."""

    @staticmethod
    @pytest.fixture
    def summary_path():
        """
        Path to the final test summary markdown file.

        Returns:
            Path: Path object pointing to "FINAL_TEST_SUMMARY.md".
        """
        return Path("FINAL_TEST_SUMMARY.md")

    @pytest.fixture
    def summary_content(self, summary_path):
        """
        Read the UTF - 8 text content of the specified summary file.

        Parameters:
            summary_path(Path): Path to the summary markdown file.

        Returns:
            str: The file content as a Unicode string.
        """
        assert summary_path.exists(), "FINAL_TEST_SUMMARY.md not found"
        with open(summary_path, encoding="utf-8") as f:
            return f.read()

    def test_summary_file_exists(self, summary_path):
        """
        Verify the FINAL_TEST_SUMMARY.md file exists and is a regular file.
        """
        assert summary_path.exists()
        assert summary_path.is_file()

    def test_summary_not_empty(self, summary_content):
        """Test that summary file is not empty."""
        assert len(summary_content.strip()) > 0

    def test_summary_has_main_title(self, summary_content):
        """Test that summary has main title."""
        assert "# Comprehensive Test Generation Summary" in summary_content

    def test_summary_has_overview_section(self, summary_content):
        """Test that summary has Overview section."""
        assert "## Overview" in summary_content

    def test_summary_lists_changed_files(self, summary_content):
        """Test that summary lists the files changed."""
        assert "dependencyMatrix.md" in summary_content
        assert "systemManifest.md" in summary_content

    def test_summary_has_test_suite_section(self, summary_content):
        """Test that summary has Test Suite Created section."""
        assert "## Test Suite Created" in summary_content

    def test_summary_mentions_test_file_location(self, summary_content):
        """Test that summary mentions the test file location."""
        assert "test_documentation_validation.py" in summary_content

    def test_summary_has_test_statistics(self, summary_content):
        """Test that summary includes test statistics."""
        assert "Statistics:" in summary_content or "statistics" in summary_content.lower()
        # Should mention line count
        assert "lines" in summary_content.lower()

    def test_summary_describes_test_classes(self, summary_content):
        """
        Verify the summary includes the expected test class names.

        Asserts that the provided summary content mentions the test classes TestDependencyMatrix, TestSystemManifest and TestDocumentationConsistency.
        """
        assert "TestDependencyMatrix" in summary_content
        assert "TestSystemManifest" in summary_content
        assert "TestDocumentationConsistency" in summary_content

    def test_summary_includes_tables(self, summary_content):
        """Test that summary includes markdown tables."""
        # Should have at least one table
        assert "|" in summary_content
        # Table separator line
        assert re.search(r"\|[-\s|]+\|", summary_content)

    def test_summary_valid_markdown_structure(self, summary_content):
        """
        Validate that a Markdown document's top - level heading is H1 when headings are present.

        Parses the content for lines starting with '#' followed by a space and , if any headings are found, asserts the first heading's level is 1.

        Parameters:
            summary_content(str): The Markdown document content to check.
        """
        lines = summary_content.split("\n")
        # Check heading hierarchy
        heading_levels = []
        for line in lines:
            if line.startswith("#"):
                match = re.match(r"^(#+)\s", line)
                if match:
                    heading_levels.append(len(match.group(1)))

        # Should start with h1
        if heading_levels:
            assert heading_levels[0] == 1, "Document should start with h1"


class TestDocumentationSummary:
    """Test cases for TEST_DOCUMENTATION_SUMMARY.md."""

    @pytest.fixture
    def summary_path(self):
        """
"""
# Should have at least one code block
assert "
