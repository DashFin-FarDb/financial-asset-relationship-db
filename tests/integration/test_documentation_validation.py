"""
Comprehensive validation tests for TEST_GENERATION_WORKFLOW_SUMMARY.md

This test suite validates the documentation file to ensure it is well-formed,
contains accurate information, and follows markdown best practices.
"""

import re
from pathlib import Path
from typing import List, Set

import pytest

SUMMARY_FILE = (
    Path(__file__).parent.parent.parent / "TEST_GENERATION_WORKFLOW_SUMMARY.md"
)


@pytest.fixture
def summary_content() -> str:
    """
    Read and return the contents of the TEST_GENERATION_WORKFLOW_SUMMARY.md file.

    If the summary file does not exist, the current test is skipped via pytest.skip.

    Returns:
        content (str): The full file contents decoded as UTF-8.
    """
    if not SUMMARY_FILE.exists():
        pytest.skip("TEST_GENERATION_WORKFLOW_SUMMARY.md not found")
    with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def summary_lines(summary_content: str) -> List[str]:
    """
    Split the markdown summary content into a list of lines.

    Parameters:
        summary_content (str): Full text content of the summary file.

    Returns:
        lines (List[str]): Lines produced by splitting the content on newline characters.
    """
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
        assert "## Overview" in summary_content, (
            "Document should have an Overview section"
        )

    def test_has_generated_files_section(self, summary_content: str):
        """Test that document describes generated files."""
        assert "## Generated Files" in summary_content, (
            "Document should list generated files"
        )

    def test_has_test_suite_structure_section(self, summary_content: str):
        """Test that document describes test suite structure."""
        assert "## Test Suite Structure" in summary_content, (
            "Document should describe test structure"
        )

    def test_has_running_tests_section(self, summary_content: str):
        """Test that document includes running instructions."""
        assert "## Running the Tests" in summary_content, (
            "Document should have running instructions"
        )

    def test_has_benefits_section(self, summary_content: str):
        """
        Assert the summary contains a "## Benefits" or "## Key Features" section.

        Parameters:
            summary_content (str): Full markdown content of the summary document.

        Raises:
            AssertionError: If neither '## Benefits' nor '## Key Features' headings are present.
        """
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
            assert re.match(r"^#{1,6} .+", line), (
                f"Heading '{line}' should have space after #"
            )

    def test_no_trailing_whitespace(self, summary_lines: List[str]):
        """
        Verify that no non-blank line in the provided lines ends with trailing whitespace.

        Fails the test if any non-blank line ends with one or more trailing whitespace characters; the assertion reports the count of offending lines.
        """
        lines_with_trailing = [
            (i + 1, line)
            for i, line in enumerate(summary_lines)
            if line.rstrip() != line and line.strip() != ""
        ]
        assert len(lines_with_trailing) == 0, (
            f"Found {len(lines_with_trailing)} lines with trailing whitespace"
        )

    def test_code_blocks_properly_closed(self, summary_lines: List[str]):
        """
        Ensure every fenced code block delimited by triple backticks in the summary has a matching closing fence.

        Parameters:
            summary_lines (List[str]): Lines of the Markdown summary to inspect.
        """
        open_block = False
        for i, line in enumerate(summary_lines, start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                # Toggle open/close state on a fence line
                open_block = not open_block
        assert open_block is False, (
            "Code blocks not properly closed or mismatched triple backticks detected"
        )

    def test_lists_properly_formatted(self, summary_lines: List[str]):
        """
        Validate that markdown bullet list items use indentation in multiples of two spaces.

        Parameters:
                summary_lines (List[str]): Lines of the markdown summary file.

        Raises:
                AssertionError: If any bullet list item ('-', '*', '+') has leading indentation that is not divisible by two.
        """
        list_lines = [line for line in summary_lines if re.match(r"^\s*[-*+] ", line)]
        if list_lines:
            # Check that indentation is consistent
            for line in list_lines:
                indent = len(line) - len(line.lstrip())
                assert indent % 2 == 0, (
                    f"List item '{line.strip()}' has odd indentation"
                )


class TestContentAccuracy:
    """Test suite for content accuracy validation."""

    def test_mentions_workflow_file(self, summary_content: str):
        """Test that document mentions the pr-agent.yml workflow."""
        assert (
            "pr-agent.yml" in summary_content.lower()
            or "pr-agent" in summary_content.lower()
        ), "Document should mention pr-agent workflow"

    def test_mentions_duplicate_keys_issue(self, summary_content: str):
        """Test that document mentions the duplicate keys issue that was fixed."""
        assert "duplicate" in summary_content.lower(), (
            "Document should mention duplicate keys issue"
        )

    def test_mentions_pytest(self, summary_content: str):
        """Test that document mentions pytest."""
        assert "pytest" in summary_content.lower(), (
            "Document should mention pytest as the testing framework"
        )

    def test_has_code_examples(self, summary_content: str):
        """
        Asserts the document contains at least one fenced code block (```).

        Checks that the summary includes at least one Markdown code fence indicating a code example.
        """
        assert "```" in summary_content, "Document should include code examples"

    def test_mentions_yaml(self, summary_content: str):
        """
        Assert the summary content mentions YAML (either "yaml" or "yml").

        Parameters:
            summary_content (str): Full text of the summary document to check.
        """
        assert "yaml" in summary_content.lower() or "yml" in summary_content.lower(), (
            "Document should mention YAML"
        )

    def test_mentions_test_classes(self, summary_content: str):
        """
        Check that the summary mentions at least one expected test class name.

        Parameters:
                summary_content (str): Full text of the TEST_GENERATION_WORKFLOW_SUMMARY.md to inspect. The test looks for mentions of specific test class names such as `TestWorkflowSyntax`, `TestWorkflowStructure`, or `TestPrAgentWorkflow`.
        """
        test_class_keywords = [
            "TestWorkflowSyntax",
            "TestWorkflowStructure",
            "TestPrAgentWorkflow",
        ]
        found_classes = [kw for kw in test_class_keywords if kw in summary_content]
        assert len(found_classes) > 0, "Document should mention specific test classes"

    def test_includes_file_paths(self, summary_content: str):
        """Test that document includes actual file paths."""
        assert (
            "tests/integration" in summary_content
            or "test_github_workflows" in summary_content
        ), "Document should include actual file paths"

    def test_mentions_requirements(self, summary_content: str):
        """Test that document mentions requirements or dependencies."""
        assert (
            "requirements" in summary_content.lower()
            or "pyyaml" in summary_content.lower()
        ), "Document should mention dependencies"


class TestCodeExamples:
    """Test suite for code example validation."""

    def test_pytest_commands_valid(self, summary_content: str):
        """
        Verify the markdown contains bash/shell code examples that run pytest and that each such example includes the 'pytest' command.

        Parameters:
            summary_content (str): Full markdown document text to scan for fenced code blocks and commands.

        Raises:
            AssertionError: If no pytest examples are found or if any extracted pytest example does not contain the 'pytest' command.
        """
        # Extract code blocks
        code_blocks = re.findall(
            r"```(?:bash|shell)?\n(.*?)```", summary_content, re.DOTALL
        )
        pytest_commands = [block for block in code_blocks if "pytest" in block]
        assert len(pytest_commands) > 0, (
            "Document should include pytest command examples"
        )

        for cmd in pytest_commands:
            # Basic validation
            assert "pytest" in cmd, "pytest command should contain 'pytest'"

    def test_file_paths_in_examples_exist(self, summary_content: str):
        """
        Ensure every referenced integration test file path in the document exists in the repository.

        Scans the provided document text for occurrences of paths matching the pattern `tests/integration/test_<name>.py` and resolves each against the repository root; the test fails with a consolidated message listing any referenced files that do not exist, including their resolved filesystem paths.

        Parameters:
                summary_content (str): The full text of the documentation file to scan for referenced test file paths.
        """
        # Look for test file references
        test_file_pattern = r"tests/integration/test_[^\s/]+\.py"
        mentioned_files = re.findall(test_file_pattern, summary_content)

        repo_root = Path(__file__).parent.parent.parent
        missing: List[str] = []

        for file_path in mentioned_files:
            full_path = repo_root / file_path
            if not full_path.exists():
                missing.append(f"{file_path} (resolved: {full_path})")

        # Fail only once with a consolidated, informative message if any are missing
        assert not missing, (
            "One or more referenced files in documentation were not found:\n"
            + "\n".join(f"- {m}" for m in missing)
            + "\nIf files were recently moved or renamed, update the documentation examples accordingly."
        )


class TestDocumentCompleteness:
    """Test suite for document completeness."""

    def test_has_summary_statistics(self, summary_content: str):
        """
        Check that the document contains numeric statistics mentioning tests or classes.

        Parameters:
            summary_content (str): Full markdown content of the summary document to inspect.
        """
        # Should mention numbers of tests, classes, etc.
        has_numbers = re.search(
            r"\d+\s+(tests?|class(?:es)?)", summary_content, re.IGNORECASE
        )
        assert has_numbers is not None, (
            "Document should include statistics about test coverage"
        )

    def test_describes_what_tests_prevent(self, summary_content: str):
        """Test that document explains what the tests prevent."""
        prevention_keywords = ["prevent", "catch", "detect", "ensure"]
        found = any(
            keyword in summary_content.lower() for keyword in prevention_keywords
        )
        assert found, "Document should describe what problems tests prevent"

    def test_has_integration_info(self, summary_content: str):
        """Test that document describes CI integration."""
        ci_keywords = ["ci", "continuous integration", "github actions", "workflow"]
        found = any(keyword in summary_content.lower() for keyword in ci_keywords)
        assert found, "Document should mention CI/workflow integration"

    def test_has_practical_examples(self, summary_content: str):
        """
        Asserts the document contains at least two fenced code block examples.

        Parameters:
            summary_content (str): Full markdown content of the summary document to inspect.
        """
        assert "```" in summary_content, "Document should have code examples"
        code_blocks = summary_content.count("```")
        assert code_blocks >= 4, "Document should have at least 2 code block examples"


class TestDocumentMaintainability:
    """Test suite for document maintainability."""

    def test_line_length_reasonable(self, summary_lines: List[str]):
        """
        Check that fewer than 10% of non-URL lines exceed 120 characters.

        Parameters:
            summary_lines (List[str]): Lines of the summary file to evaluate.

        Notes:
            Lines starting with a URL (after stripping leading whitespace) are excluded from the length check.
        """
        long_lines = [
            (i + 1, line)
            for i, line in enumerate(summary_lines)
            if len(line) > 120 and not line.strip().startswith("http")
        ]
        # Allow some long lines but flag excessive ones
        assert len(long_lines) < len(summary_lines) * 0.1, (
            f"Too many long lines ({len(long_lines)}), consider breaking them up"
        )

    def test_has_clear_structure(self, summary_content: str):
        """
        Assert the markdown document has a clear hierarchical heading structure.

        Requires at least one level-1 heading (H1) and at least three level-2 headings (H2).
        """
        h1_count = len(re.findall(r"^# ", summary_content, re.MULTILINE))
        h2_count = len(re.findall(r"^## ", summary_content, re.MULTILINE))

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
            assert len(content_lines) > 0, (
                f"Section '{section_name}' should have content"
            )


class TestLinkValidation:
    """Test suite for link validation."""

    def test_internal_links_valid(self, summary_lines: List[str], summary_content: str):
        """
        Validate that every internal GitHub-style link in the Markdown targets an existing header.

        Parses document headers into GitHub Flavored Markdown (GFM) anchors and verifies every internal link of the form [text](#anchor) references one of those anchors.

        Parameters:
            summary_lines (List[str]): File content split into lines; used to extract header texts.
            summary_content (str): Full file content as a single string; used to find internal link targets.
        """
        import unicodedata

        def _to_gfm_anchor(text: str) -> str:
            # Lowercase
            """
            Convert a header string into a GitHub Flavored Markdown (GFM) anchor.

            Parameters:
                text (str): Header text to convert into an internal GFM anchor.

            Returns:
                str: Anchor string suitable for internal GFM links: lowercase, diacritics removed, punctuation omitted, consecutive whitespace collapsed to single hyphens, consecutive hyphens collapsed, and with no leading or trailing hyphens.
            """
            s = text.strip().lower()
            # Normalize unicode to NFKD and remove diacritics
            s = unicodedata.normalize("NFKD", s)
            s = "".join(ch for ch in s if not unicodedata.combining(ch))
            # Remove punctuation/special chars except spaces and hyphens
            s = re.sub(r"[^\w\s-]", "", s)
            # Replace whitespace with single hyphen
            s = re.sub(r"\s+", "-", s)
            # Collapse multiple hyphens
            s = re.sub(r"-{2,}", "-", s)
            # Strip leading/trailing hyphens
            s = s.strip("-")
            return s

        # Extract headers and internal links from the document
        headers = [
            line.lstrip("#").strip() for line in summary_lines if line.startswith("#")
        ]
        valid_anchors: Set[str] = set(_to_gfm_anchor(header) for header in headers)
        internal_links = re.findall(r"\[([^\]]+)\]\(#([^)]+)\)", summary_content)

        # Check each internal link
        for text, anchor in internal_links:
            assert anchor in valid_anchors, (
                f"Internal link to #{anchor} references non-existent header"
            )


class TestSecurityAndBestPractices:
    """Test suite for security and best practices in documentation."""

    def test_no_hardcoded_secrets(self, summary_content: str):
        """
        Fail the test if the document contains common hardcoded GitHub token patterns.

        Parameters:
            summary_content (str): Full text of the summary document to scan.
        """
        secret_patterns = [
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub Personal Access Token
            r"gho_[a-zA-Z0-9]{36}",  # GitHub OAuth Token
            r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}",  # GitHub Fine-grained PAT
        ]

        for pattern in secret_patterns:
            matches = re.findall(pattern, summary_content)
            assert len(matches) == 0, (
                f"Document should not contain hardcoded secrets (found pattern: {pattern})"
            )

    def test_uses_secure_examples(self, summary_content: str):
        """
        Require secure examples when tokens are mentioned.

        If the summary content contains the word "token" (case-insensitive), the document must also reference GitHub secrets context (for example the word "secrets") or include the GitHub Actions expression syntax '${{'. This enforces that examples involving tokens show secure handling.

        Parameters:
            summary_content (str): Full text content of the TEST_GENERATION_WORKFLOW_SUMMARY.md file being validated.
        """
        # If the document mentions tokens, it should mention secrets context
        if "token" in summary_content.lower():
            assert "secrets" in summary_content.lower() or "${{" in summary_content, (
                "Document should reference GitHub secrets context when mentioning tokens"
            )


class TestReferenceAccuracy:
    """Test suite for reference accuracy."""

    def test_test_counts_are_realistic(self, summary_content: str):
        """
        Ensure numeric mentions of tests in the summary are realistic.

        Scans the provided summary text for numbers immediately followed by the word "test" or "tests" and asserts each numeric value is greater than 0 and less than 1000.

        Parameters:
                summary_content (str): Full text content of the TEST_GENERATION_WORKFLOW_SUMMARY.md document to validate.
        """
        # Extract numbers mentioned with "test"
        test_counts = re.findall(r"(\d+)\s+tests?", summary_content, re.IGNORECASE)
        for count_str in test_counts:
            count = int(count_str)
            assert 0 < count < 1000, f"Test count {count} seems unrealistic"

    def test_file_references_are_consistent(self, summary_content: str):
        """
        Verify that references to "test_github_workflows.py" appear with consistent casing.

        Searches the document for occurrences of "test_github_workflows.py" (case-insensitive) and fails the test if more than two distinct casings are found, indicating inconsistent file-name references.

        Parameters:
            summary_content (str): Full text of the markdown document to inspect.
        """
        # Main test file should be referenced consistently
        test_file_mentions = re.findall(
            r"test_github_workflows\.py", summary_content, re.IGNORECASE
        )
        if test_file_mentions:
            # All mentions should use the same case
            unique_mentions = set(test_file_mentions)
            assert len(unique_mentions) <= 2, (
                "File name should be referenced consistently"
            )


class TestEdgeCases:
    """Test suite for edge cases."""

    def test_handles_special_characters(self, summary_content: str):
        """
        Fail if the document contains the Unicode replacement character U+FFFD (�).

        This detects encoding or decoding issues that produced the replacement character in the summary content.
        """
        # Check for common encoding issues
        assert "�" not in summary_content, (
            "Document should not contain replacement characters (encoding issues)"
        )

    def test_utf8_encoding(self):
        """Test that file is properly UTF-8 encoded."""
        try:
            with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("File should be valid UTF-8")

    def test_consistent_line_endings(self):
        """
        Ensure the summary file uses a single line-ending style.

        Skips the check if the file is empty. Considers line-terminated lines with LF, CRLF, or CR endings and requires exactly one style among those lines; the file must use either LF or CRLF.
        """
        with open(SUMMARY_FILE, "rb") as f:
            content = f.read()

        # Split preserving line endings and detect per-line endings
        lines = content.splitlines(True)
        if not lines:
            pytest.skip(
                "File appears to be empty; skipping line ending consistency check"
            )

        endings = set()
        for line in lines:
            if line.endswith(b"\r\n"):
                endings.add("CRLF")
            elif line.endswith(b"\n"):
                endings.add("LF")
            elif line.endswith(b"\r"):
                # Rare classic Mac line ending; treat distinctly
                endings.add("CR")
            else:
                # Last line may not have a newline; ignore for consistency purposes
                pass

        # Require exactly one style among present line-terminated lines
        assert len(endings) == 1, (
            "File should use a single line ending style throughout"
        )
        # Additionally ensure the file uses recognized line endings
        assert endings.pop() in {"LF", "CRLF"}, (
            "File should use LF or CRLF line endings"
        )
