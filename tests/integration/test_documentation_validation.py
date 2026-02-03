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
                # Toggle open/close state on a fence line
                open_block = not open_block
        assert open_block is False, (
            "Code blocks not properly closed or mismatched triple backticks detected"
        )
    """


class TestListFormatting:
    """Test suite for markdown list formatting validation."""

    @staticmethod
    def test_lists_properly_formatted(summary_lines: List[str]):
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

    @staticmethod
    def test_mentions_workflow_file(summary_content: str):
        """Test that document mentions the pr-agent.yml workflow."""
        assert (
            "pr-agent.yml" in summary_content.lower()
            or "pr-agent" in summary_content.lower()
        ), "Document should mention pr-agent workflow"

    @staticmethod
    def test_mentions_duplicate_keys_issue(summary_content: str):
        """Test that document mentions the duplicate keys issue that was fixed."""
        assert "duplicate" in summary_content.lower(), (
            "Document should mention duplicate keys issue"
        )

    @staticmethod
    def test_mentions_pytest(summary_content: str):
        """Test that document mentions pytest."""
        assert "pytest" in summary_content.lower(), (
            "Document should mention pytest as the testing framework"
        )

    @staticmethod
    def test_has_code_examples(summary_content: str):
        """
        Asserts the document contains at least one fenced code block (
        )
        """
        code_blocks = summary_content.count("```")
        assert code_blocks >= 2, (
            f"Expected at least one fenced code block, found {code_blocks}"
        )


class TestDocumentMaintainability:
    """Test suite for document maintainability."""

    @staticmethod
    def test_line_length_reasonable(summary_lines: List[str]):
        """
        Check that fewer than 10% of non-URL lines exceed 120 characters.

        Parameters:
            summary_lines (List[str]): Lines of the summary file to evaluate.

        Notes:
            Lines starting with a URL (after stripping leading whitespace) are excluded from the length check.
        """
        long_lines = [
            line
            for line in summary_lines
            if len(line) > 120 and not line.strip().startswith("http")
        ]
        # Allow some long lines but flag excessive ones
        assert len(long_lines) < len(summary_lines) * 0.1, (
            f"Too many long lines ({len(long_lines)}), consider breaking them up"
        )

    @staticmethod
    def test_has_clear_structure(summary_content: str):
        """
        Assert the markdown document has a clear hierarchical heading structure.

        Requires at least one level-1 heading (H1) and at least three level-2 headings (H2).
        """
        h1_count = len(re.findall(r"^# ", summary_content, re.MULTILINE))
        h2_count = len(re.findall(r"^## ", summary_content, re.MULTILINE))

        assert h1_count >= 1, "Should have at least one H1 heading"
        assert h2_count >= 3, "Should have at least 3 H2 headings for organization"

    @staticmethod
    def test_sections_have_content(summary_content: str):
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

    @staticmethod
    def test_internal_links_valid(summary_lines: List[str], summary_content: str):
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
        valid_anchors: Set[str] = {_to_gfm_anchor(header) for header in headers}
        internal_links = re.findall(r"\[([^\]]+)\]\(#([^)]+)\)", summary_content)

        # Check each internal link
        for _, anchor in internal_links:
            assert anchor in valid_anchors, (
                f"Internal link to #{anchor} references non-existent header"
            )


class TestSecurityAndBestPractices:
    """Test suite for security and best practices in documentation."""

    @staticmethod
    def test_no_hardcoded_secrets(summary_content: str):
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

    @staticmethod
    def test_uses_secure_examples(summary_content: str):
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

    @staticmethod
    def test_test_counts_are_realistic(summary_content: str):
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

    @staticmethod
    def test_file_references_are_consistent(summary_content: str):
        """Test suite for edge cases."""
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

    @staticmethod
    def test_handles_special_characters(summary_content: str):
        """
        Fail if the document contains the Unicode replacement character U+FFFD (�).

        This detects encoding or decoding issues that produced the replacement character in the summary content.
        """
        # Check for common encoding issues
        assert "�" not in summary_content, (
            "Document contains invalid characters. Document should not contain replacement characters (encoding issues)"
        )

    @staticmethod
    def test_utf8_encoding():
        """Test that file is properly UTF-8 encoded."""
        try:
            with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("File should be valid UTF-8")

    @staticmethod
    def test_consistent_line_endings():
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
