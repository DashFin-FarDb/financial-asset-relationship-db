"""
Comprehensive validation tests for TEST_GENERATION_WORKFLOW_SUMMARY.md

This test suite validates the documentation file to ensure it is well-formed,
contains accurate information, and follows markdown best practices.
"""

import re
from pathlib import Path
from typing import List, Set

import pytest

SUMMARY_FILE = Path(__file__).parent.parent.parent / "TEST_GENERATION_WORKFLOW_SUMMARY.md"


@pytest.fixture
def summary_content() -> str:
    """Load the summary file content."""
    if not SUMMARY_FILE.exists():
        pytest.skip("TEST_GENERATION_WORKFLOW_SUMMARY.md not found")
    with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def summary_lines(summary_content: str) -> List[str]:
    """Get summary file lines."""
    return summary_content.split("\n")


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
            if line.startswith("#"):
                first_heading = line
                break
        assert first_heading is not None, "File should have at least one heading"
        assert first_heading.startswith("# "), "First heading should be level 1"

    def test_has_overview_section(self, summary_content: str):
        """Test that document has an Overview section."""
        assert "## Overview" in summary_content, "Document should have an Overview section"

    def test_has_generated_files_section(self, summary_content: str):
        """Test that document describes generated files."""
        assert "## Generated Files" in summary_content, "Document should list generated files"

    def test_has_test_suite_structure_section(self, summary_content: str):
        """Test that document describes test suite structure."""
        assert "## Test Suite Structure" in summary_content, "Document should describe test structure"

    def test_has_running_tests_section(self, summary_content: str):
        """Test that document includes running instructions."""
        assert "## Running the Tests" in summary_content, "Document should have running instructions"

    def test_has_benefits_section(self, summary_content: str):
        """Test that document lists benefits."""
        assert (
            "## Benefits" in summary_content or "## Key Features" in summary_content
        ), "Document should describe benefits or key features"


class TestMarkdownFormatting:
    """Test suite for markdown formatting validation."""

    def test_headings_properly_formatted(self, summary_lines: List[str]):
        """Test that headings follow proper markdown format."""
        heading_lines = [line for line in summary_lines if line.startswith("#")]
        for line in heading_lines:
            # Heading should have space after hash marks
            assert re.match(r"^#{1,6} .+", line), f"Heading '{line}' should have space after #"

    def test_no_trailing_whitespace(self, summary_lines: List[str]):
        """Test that lines don't have trailing whitespace."""
        lines_with_trailing = [
            (i + 1, line) for i, line in enumerate(summary_lines) if line.rstrip() != line and line.strip() != ""
        ]
        assert len(lines_with_trailing) == 0, f"Found {len(lines_with_trailing)} lines with trailing whitespace"

    def test_code_blocks_properly_closed(self, summary_content: str):
        """Test that code blocks are properly opened and closed."""
        # Count triple backticks
        backtick_count = summary_content.count("```")
        assert (
            backtick_count % 2 == 0
        ), f"Code blocks not properly closed (found {backtick_count} triple backticks, should be even)"

    def test_lists_properly_formatted(self, summary_lines: List[str]):
        """Test that bullet lists use consistent markers."""
        list_lines = [line for line in summary_lines if re.match(r"^\s*[-*+] ", line)]
        if list_lines:
            # Check that indentation is consistent
            for line in list_lines:
                indent = len(line) - len(line.lstrip())
                assert indent % 2 == 0, f"List item '{line.strip()}' has odd indentation"


class TestContentAccuracy:
    """Test suite for content accuracy validation."""

    def test_mentions_workflow_file(self, summary_content: str):
        """Test that document mentions the pr-agent.yml workflow."""
        assert (
            "pr-agent.yml" in summary_content.lower() or "pr-agent" in summary_content.lower()
        ), "Document should mention pr-agent workflow"

    def test_mentions_duplicate_keys_issue(self, summary_content: str):
        """Test that document mentions the duplicate keys issue that was fixed."""
        assert "duplicate" in summary_content.lower(), "Document should mention duplicate keys issue"

    def test_mentions_pytest(self, summary_content: str):
        """Test that document mentions pytest."""
        assert "pytest" in summary_content.lower(), "Document should mention pytest as the testing framework"

    def test_has_code_examples(self, summary_content: str):
        """Test that document includes code examples."""
        assert "```" in summary_content, "Document should include code examples"

    def test_mentions_yaml(self, summary_content: str):
        """Test that document mentions YAML."""
        assert "yaml" in summary_content.lower() or "yml" in summary_content.lower(), "Document should mention YAML"

    def test_mentions_test_classes(self, summary_content: str):
        """Test that document describes test classes."""
        test_class_keywords = ["TestWorkflowSyntax", "TestWorkflowStructure", "TestPrAgentWorkflow"]
        found_classes = [kw for kw in test_class_keywords if kw in summary_content]
        assert len(found_classes) > 0, "Document should mention specific test classes"

    def test_includes_file_paths(self, summary_content: str):
        """Test that document includes actual file paths."""
        assert (
            "tests/integration" in summary_content or "test_github_workflows" in summary_content
        ), "Document should include actual file paths"

    def test_mentions_requirements(self, summary_content: str):
        """Test that document mentions requirements or dependencies."""
        assert (
            "requirements" in summary_content.lower() or "pyyaml" in summary_content.lower()
        ), "Document should mention dependencies"


class TestCodeExamples:
    """Test suite for code example validation."""

    def test_pytest_commands_valid(self, summary_content: str):
        """Test that pytest commands are valid."""
        # Extract code blocks
        code_blocks = re.findall(r"```(?:bash|shell)?\n(.*?)```", summary_content, re.DOTALL)
        pytest_commands = [block for block in code_blocks if "pytest" in block]
        assert len(pytest_commands) > 0, "Document should include pytest command examples"

        for cmd in pytest_commands:
            # Basic validation
            assert "pytest" in cmd, "pytest command should contain 'pytest'"

    def test_file_paths_in_examples_exist(self, summary_content: str):
        """Test that referenced file paths in examples actually exist."""
        # Look for test file references
        test_file_pattern = r"tests/integration/test_\w+\.py"
        mentioned_files = re.findall(test_file_pattern, summary_content)

        repo_root = Path(__file__).parent.parent.parent
        for file_path in mentioned_files:
            full_path = repo_root / file_path
            assert full_path.exists(), f"Referenced file {file_path} should exist"


class TestDocumentCompleteness:
    """Test suite for document completeness."""

    def test_has_summary_statistics(self, summary_content: str):
        """Test that document includes statistics about tests."""
        # Should mention numbers of tests, classes, etc.
        has_numbers = re.search(r"\d+\s+(test|class)", summary_content, re.IGNORECASE)
        assert has_numbers is not None, "Document should include statistics about test coverage"

    def test_describes_what_tests_prevent(self, summary_content: str):
        """Test that document explains what the tests prevent."""
        prevention_keywords = ["prevent", "catch", "detect", "ensure"]
        found = any(keyword in summary_content.lower() for keyword in prevention_keywords)
        assert found, "Document should describe what problems tests prevent"

    def test_has_integration_info(self, summary_content: str):
        """Test that document describes CI integration."""
        ci_keywords = ["ci", "continuous integration", "github actions", "workflow"]
        found = any(keyword in summary_content.lower() for keyword in ci_keywords)
        assert found, "Document should mention CI/workflow integration"

    def test_has_practical_examples(self, summary_content: str):
        """Test that document has practical examples."""
        assert "```" in summary_content, "Document should have code examples"
        code_blocks = summary_content.count("```")
        assert code_blocks >= 4, "Document should have at least 2 code block examples"


class TestDocumentMaintainability:
    """Test suite for document maintainability."""

    def test_line_length_reasonable(self, summary_lines: List[str]):
        """Test that lines aren't excessively long."""
        long_lines = [
            (i + 1, line)
            for i, line in enumerate(summary_lines)
            if len(line) > 120 and not line.strip().startswith("http")
        ]
        # Allow some long lines but flag excessive ones
        assert (
            len(long_lines) < len(summary_lines) * 0.1
        ), f"Too many long lines ({len(long_lines)}), consider breaking them up"

    def test_has_clear_structure(self, summary_content: str):
        """Test that document has clear hierarchical structure."""
        h1_count = summary_content.count("\n# ")
        h2_count = summary_content.count("\n## ")

        assert h1_count >= 1, "Should have at least one H1 heading"
        assert h2_count >= 3, "Should have at least 3 H2 headings for organization"

    def test_sections_have_content(self, summary_content: str):
        """Test that major sections have substantial content."""
        sections = re.split(r"\n## ", summary_content)
        # Skip first section (before first H2)
        for section in sections[1:]:
            lines = section.split("\n")
            section_name = lines[0]
            content_lines = [l for l in lines[1:] if l.strip()]
            assert len(content_lines) > 0, f"Section '{section_name}' should have content"


class TestLinkValidation:
    """Test suite for link validation."""

    def test_no_broken_internal_links(self, summary_content: str):
        """Test that internal markdown links reference valid headers."""
        # Find markdown links [text](#anchor)
        internal_links = re.findall(r"\[([^\]]+)\]\(#([^\)]+)\)", summary_content)

        # Find all headers
        headers = re.findall(r"^#{1,6}\s+(.+)$", summary_content, re.MULTILINE)
        # Convert headers to anchor format
        valid_anchors = set()
        for header in headers:
            anchor = header.lower().strip()
            anchor = re.sub(r"[^\w\s-]", "", anchor)
            anchor = re.sub(r"\s+", "-", anchor)
            valid_anchors.add(anchor)

        # Check each internal link
        for _, anchor in internal_links:
            assert anchor in valid_anchors, f"Internal link to #{anchor} references non-existent header"


class TestSecurityAndBestPractices:
    """Test suite for security and best practices in documentation."""

    def test_no_hardcoded_secrets(self, summary_content: str):
        """Test that document doesn't contain hardcoded secrets."""
        secret_patterns = [
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub Personal Access Token
            r"gho_[a-zA-Z0-9]{36}",  # GitHub OAuth Token
            r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}",  # GitHub Fine-grained PAT
        ]

        for pattern in secret_patterns:
            matches = re.findall(pattern, summary_content)
            assert len(matches) == 0, f"Document should not contain hardcoded secrets (found pattern: {pattern})"

    def test_uses_secure_examples(self, summary_content: str):
        """Test that examples follow security best practices."""
        # If the document mentions tokens, it should mention secrets context
        if "token" in summary_content.lower():
            assert (
                "secrets" in summary_content.lower() or "${{" in summary_content
            ), "Document should reference GitHub secrets context when mentioning tokens"


class TestReferenceAccuracy:
    """Test suite for reference accuracy."""

    def test_test_counts_are_realistic(self, summary_content: str):
        """Test that mentioned test counts seem realistic."""
        # Extract numbers mentioned with "test"
        test_counts = re.findall(r"(\d+)\s+tests?", summary_content, re.IGNORECASE)
        for count_str in test_counts:
            count = int(count_str)
            assert 0 < count < 1000, f"Test count {count} seems unrealistic"

    def test_file_references_are_consistent(self, summary_content: str):
        """Test that file references are consistent throughout."""
        # Main test file should be referenced consistently
        test_file_mentions = re.findall(r"test_github_workflows\.py", summary_content, re.IGNORECASE)
        if test_file_mentions:
            # All mentions should use the same case
            unique_mentions = set(test_file_mentions)
            assert len(unique_mentions) <= 2, "File name should be referenced consistently"


class TestEdgeCases:
    """Test suite for edge cases."""

    def test_handles_special_characters(self, summary_content: str):
        """Test that document handles special characters properly."""
        # Check for common encoding issues
        assert "�" not in summary_content, "Document should not contain replacement characters (encoding issues)"

    def test_utf8_encoding(self):
        """Test that file is properly UTF-8 encoded."""
        try:
            with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("File should be valid UTF-8")

    def test_consistent_line_endings(self):
        """Test that file uses consistent line endings."""
        with open(SUMMARY_FILE, "rb") as f:
            content = f.read()

        has_crlf = b"\r\n" in content
        has_lf_only = b"\n" in content and b"\r\n" not in content

        assert has_lf_only or has_crlf, "File should have consistent line endings"
        assert not (has_lf_only and has_crlf), "File should not mix line ending styles"
