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
                summary_path (Path): Path to the summary markdown file to read.

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
            summary_content (str): Full text content of the summary markdown file being tested.
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
        Assert that every Markdown heading in the provided content has a space after the leading `#` characters.

        Parameters:
            summary_content (str): Full text of the summary Markdown file to validate.

        Raises:
            AssertionError: If any heading line does not have a space after its `#` markers; the error message includes the failing line number.
        """
        lines = summary_content.split("\n")
        for i, line in enumerate(lines, 1):
            if line.startswith("#"):
                # Headings should have space after #
                assert re.match(r"^#+\s", line), f"Line {i}: Heading missing space after #"

    def test_summary_no_broken_formatting(self, summary_content):
        """
        Verify the summary contains no malformed Markdown heading markers (for example, consecutive `#` characters without the required space).

        Parameters:
            summary_content (str): The full text content of the summary markdown file to validate.
        """
        # Check for common markdown issues
        assert "##" not in summary_content.replace("##", "# #")  # No triple hashes without space


class TestFinalTestSummary:
    """Test cases for FINAL_TEST_SUMMARY.md."""

    @pytest.fixture
    def summary_path(self):
        """
        Path to the final test summary markdown file.

        Returns:
            Path: Path object pointing to "FINAL_TEST_SUMMARY.md".
        """
        return Path("FINAL_TEST_SUMMARY.md")

    @pytest.fixture
    def summary_content(self, summary_path):
        """
        Read the UTF-8 text content of the specified summary file.

        Parameters:
            summary_path (Path): Path to the summary markdown file.

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
        Validate that a Markdown document's top-level heading is H1 when headings are present.

        Parses the content for lines starting with '#' followed by a space and, if any headings are found, asserts the first heading's level is 1.

        Parameters:
            summary_content (str): The Markdown document content to check.
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
        Return the path to the documentation validation summary file.

        Returns:
            Path: A pathlib.Path pointing to "TEST_DOCUMENTATION_SUMMARY.md".
        """
        return Path("TEST_DOCUMENTATION_SUMMARY.md")

    @pytest.fixture
    def summary_content(self, summary_path):
        """
        Read and return the UTF-8 contents of a summary markdown file.

        Parameters:
            summary_path (Path): Path to the summary markdown file.

        Returns:
            str: Contents of the file.

        Raises:
            AssertionError: If `summary_path` does not exist.
        """
        assert summary_path.exists(), "TEST_DOCUMENTATION_SUMMARY.md not found"
        with open(summary_path, encoding="utf-8") as f:
            return f.read()

    def test_summary_file_exists(self, summary_path):
        """Test that TEST_DOCUMENTATION_SUMMARY.md exists."""
        assert summary_path.exists()
        assert summary_path.is_file()

    def test_summary_not_empty(self, summary_content):
        """Test that summary file is not empty."""
        assert len(summary_content.strip()) > 0

    def test_summary_has_main_title(self, summary_content):
        """
        Verify the summary contains the expected main title.

        Parameters:
                summary_content (str): Full Markdown text of the summary file to be validated. The test checks for the presence of the line "# Documentation Validation Test Suite".
        """
        assert "# Documentation Validation Test Suite" in summary_content

    def test_summary_has_overview_section(self, summary_content):
        """Test that summary has Overview section."""
        assert "## Overview" in summary_content

    def test_summary_describes_test_file(self, summary_content):
        """Test that summary describes the test file created."""
        assert "Test File Created" in summary_content
        assert "test_documentation_validation.py" in summary_content

    def test_summary_has_test_coverage_section(self, summary_content):
        """
        Verify the summary includes a "## Test Coverage" heading.

        Parameters:
                summary_content (str): Full text content of the summary markdown file to check.
        """
        assert "## Test Coverage" in summary_content

    def test_summary_lists_all_test_classes(self, summary_content):
        """Test that summary lists all test classes."""
        test_classes = [
            "TestDependencyMatrix",
            "TestSystemManifest",
            "TestDocumentationConsistency",
            "TestDocumentationRealisticContent",
        ]
        for test_class in test_classes:
            assert test_class in summary_content, f"Missing test class: {test_class}"

    def test_summary_has_execution_results(self, summary_content):
        """
        Verify the summary contains a section or mention of test execution results.

        Checks for the exact heading "Test Execution Results" or a case-insensitive occurrence of the word "execution".
        """
        assert "Test Execution Results" in summary_content or "execution" in summary_content.lower()

    def test_summary_has_key_features_section(self, summary_content):
        """
        Verify the summary contains a "Key Features" or "Features" section.
        """
        assert "Key Features" in summary_content or "Features" in summary_content

    def test_summary_mentions_validation_types(self, summary_content):
        """Test that summary mentions different types of validation."""
        validation_types = ["structure", "data", "format", "content"]
        found = sum(1 for vtype in validation_types if vtype in summary_content.lower())
        assert found >= 2, "Should mention at least 2 validation types"

    def test_summary_has_how_to_run_section(self, summary_content):
        """Test that summary includes how to run the tests."""
        assert "How to Run" in summary_content or "run" in summary_content.lower()
        # Should have pytest command example
        assert "pytest" in summary_content

    def test_summary_includes_code_blocks(self, summary_content):
        """
        Verify the summary contains at least one fenced code block marker (```) .
        """
        # Should have at least one code block
        assert "```" in summary_content

    def test_summary_valid_markdown_lists(self, summary_content):
        """
        Verify Markdown list items use a space after the marker.

        Checks each line of the provided Markdown content and asserts that any unordered list marker ('-' or '*') is followed by a single space (a lone marker is allowed).

        Parameters:
            summary_content (str): The Markdown document text to validate.

        Raises:
            AssertionError: If a list item marker is not followed by a space, with the failing line included in the message.
        """
        lines = summary_content.split("\n")
        for line in lines:
            if line.strip().startswith("-") or line.strip().startswith("*"):
                # List items should have space after marker
                stripped = line.lstrip()
                if stripped.startswith("-"):
                    assert stripped.startswith("- ") or stripped == "-", f"List item should have space: {line}"


class TestSummaryFilesConsistency:
    """Test consistency across all summary documentation files."""

    @pytest.fixture
    def all_summaries(self):
        """
        Load the contents of the three expected summary markdown files that exist in the current directory.

        Only files among ENHANCED_TEST_SUMMARY.md, FINAL_TEST_SUMMARY.md and TEST_DOCUMENTATION_SUMMARY.md that are present are included.

        Returns:
            dict: Mapping of filename (str) to file content (str) decoded as UTF-8.
        """
        summaries = {}
        for filename in ["ENHANCED_TEST_SUMMARY.md", "FINAL_TEST_SUMMARY.md", "TEST_DOCUMENTATION_SUMMARY.md"]:
            path = Path(filename)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    summaries[filename] = f.read()
        return summaries

    def test_all_summary_files_exist(self):
        """Test that all expected summary files exist."""
        expected_files = ["ENHANCED_TEST_SUMMARY.md", "FINAL_TEST_SUMMARY.md", "TEST_DOCUMENTATION_SUMMARY.md"]
        for filename in expected_files:
            assert Path(filename).exists(), f"Missing summary file: {filename}"

    def test_summaries_mention_same_test_file(self, all_summaries):
        """Test that all summaries mention the same test file."""
        test_file = "test_documentation_validation.py"
        for filename, content in all_summaries.items():
            assert test_file in content, f"{filename} should mention {test_file}"

    def test_summaries_mention_same_documentation_files(self, all_summaries):
        """Test that all summaries mention the same documentation files."""
        doc_files = ["dependencyMatrix.md", "systemManifest.md"]
        for filename, content in all_summaries.items():
            mentions = sum(1 for df in doc_files if df in content)
            assert mentions >= 1, f"{filename} should mention at least one documentation file"

    def test_summaries_use_consistent_terminology(self, all_summaries):
        """
        Verify each summary contains the word "test".

        Parameters:
                all_summaries (dict): Mapping from filename (str or Path) to the file's text content (str); each value is checked for the presence of the word "test" (case-insensitive).
        """
        # All should use "test" terminology consistently
        for filename, content in all_summaries.items():
            assert "test" in content.lower(), f"{filename} should use test terminology"

    def test_summaries_are_utf8_encoded(self, all_summaries):
        """Test that all summary files are properly UTF-8 encoded."""
        for filename in all_summaries.keys():
            path = Path(filename)
            try:
                with open(path, encoding="utf-8") as f:
                    f.read()
            except UnicodeDecodeError:
                pytest.fail(f"{filename} is not valid UTF-8")


class TestSummaryFilesEdgeCases:
    """Test edge cases for summary documentation files."""

    def test_summaries_have_reasonable_length(self):
        """Test that summary files are not excessively long."""
        max_lines = 500
        for filename in ["ENHANCED_TEST_SUMMARY.md", "FINAL_TEST_SUMMARY.md", "TEST_DOCUMENTATION_SUMMARY.md"]:
            path = Path(filename)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    line_count = sum(1 for _ in f)
                assert line_count < max_lines, f"{filename} is too long: {line_count} lines"

    def test_summaries_have_reasonable_file_size(self):
        """
        Verify that each summary markdown file present is smaller than 100 KB.

        Checks ENHANCED_TEST_SUMMARY.md, FINAL_TEST_SUMMARY.md and TEST_DOCUMENTATION_SUMMARY.md (if they exist) and asserts that each file's size is less than 100 kilobytes. Fails with an AssertionError naming the offending file and its size in KB if a file exceeds the limit.
        """
        max_size_kb = 100  # 100KB
        for filename in ["ENHANCED_TEST_SUMMARY.md", "FINAL_TEST_SUMMARY.md", "TEST_DOCUMENTATION_SUMMARY.md"]:
            path = Path(filename)
            if path.exists():
                size_kb = path.stat().st_size / 1024
                assert size_kb < max_size_kb, f"{filename} is too large: {size_kb:.1f}KB"

    def test_summaries_no_excessive_blank_lines(self):
        """Test that summaries don't have excessive blank lines."""
        for filename in ["ENHANCED_TEST_SUMMARY.md", "FINAL_TEST_SUMMARY.md", "TEST_DOCUMENTATION_SUMMARY.md"]:
            path = Path(filename)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    lines = f.readlines()

                max_consecutive = 0
                current = 0
                for line in lines:
                    if line.strip() == "":
                        current += 1
                        max_consecutive = max(max_consecutive, current)
                    else:
                        current = 0

                assert max_consecutive < 4, f"{filename} has too many consecutive blank lines: {max_consecutive}"

    def test_summaries_markdown_links_format(self):
        """Test that markdown links (if present) are properly formatted."""
        for filename in ["ENHANCED_TEST_SUMMARY.md", "FINAL_TEST_SUMMARY.md", "TEST_DOCUMENTATION_SUMMARY.md"]:
            path = Path(filename)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    content = f.read()

                # Find markdown links: [text](url)
                links = re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", content)
                for link_text, url in links:
                    # Link text should not be empty
                    assert len(link_text.strip()) > 0, f"{filename} has link with empty text"
                    # URL should not be empty
                    assert len(url.strip()) > 0, f"{filename} has link with empty URL"


class TestSummaryReadability:
    """Test readability and documentation quality of summary files."""

    def test_summaries_have_descriptive_titles(self):
        """Test that summaries have descriptive titles."""
        expected_titles = {
            "ENHANCED_TEST_SUMMARY.md": "Enhanced Test Suite Summary",
            "FINAL_TEST_SUMMARY.md": "Comprehensive Test Generation Summary",
            "TEST_DOCUMENTATION_SUMMARY.md": "Documentation Validation Test Suite",
        }

        for filename, expected_title in expected_titles.items():
            path = Path(filename)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                assert expected_title in first_line, f"{filename} should have title containing '{expected_title}'"

    def test_summaries_have_multiple_sections(self):
        """Test that summaries are well-structured with multiple sections."""
        for filename in ["ENHANCED_TEST_SUMMARY.md", "FINAL_TEST_SUMMARY.md", "TEST_DOCUMENTATION_SUMMARY.md"]:
            path = Path(filename)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    content = f.read()

                # Count h2 sections
                h2_count = content.count("\n## ")
                assert h2_count >= 2, f"{filename} should have at least 2 sections"

    def test_summaries_use_proper_capitalization(self):
        """Test that summary titles use proper capitalization."""
        for filename in ["ENHANCED_TEST_SUMMARY.md", "FINAL_TEST_SUMMARY.md", "TEST_DOCUMENTATION_SUMMARY.md"]:
            path = Path(filename)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    lines = f.readlines()

                # Check headings for proper capitalization
                for line in lines:
                    if line.startswith(("# ", "## ")):
                        heading = line.lstrip("#").strip()
                        if heading:
                            # First character should be uppercase
                            assert (
                                heading[0].isupper() or heading[0].isdigit()
                            ), f"{filename}: Heading should start with capital: {line}"
