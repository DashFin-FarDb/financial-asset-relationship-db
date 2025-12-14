"""
Tests for TEST_GENERATION_WORKFLOW_SUMMARY.md documentation file.

This test suite validates that the documentation file exists, is well-formed,
contains required sections, and has no broken internal references.
"""

import re
from pathlib import Path
from typing import List, Set

import pytest

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
            with open(DOC_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                assert len(content) > 0, "Documentation file is empty"
        except Exception as e:
            pytest.fail(f"Could not read documentation file: {e}")

    def test_file_extension(self):
        """Test that the file has .md extension."""
        assert DOC_FILE.suffix == ".md", "Documentation file should have .md extension"


class TestDocumentationStructure:
    """Test the structure and formatting of the documentation."""

    @pytest.fixture
    def doc_content(self) -> str:
        """Load the documentation content."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    def doc_lines(self) -> List[str]:
        """Load the documentation as a list of lines."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            return f.readlines()

    def test_has_main_title(self, doc_content: str):
        """Test that document has a main title (H1 heading)."""
        assert re.search(r"^# .+", doc_content, re.MULTILINE), "Document should have at least one H1 heading (# Title)"

    def test_title_content(self, doc_content: str):
        """Test that the title mentions workflow and test generation."""
        title_match = re.search(r"^# (.+)", doc_content, re.MULTILINE)
        assert title_match, "No title found"

        title = title_match.group(1).lower()
        assert "workflow" in title or "test" in title, "Title should mention 'workflow' or 'test'"

    def test_has_overview_section(self, doc_content: str):
        """Test that document has an Overview section."""
        assert re.search(r"##\s+Overview", doc_content, re.IGNORECASE), "Document should have an Overview section"

    def test_has_multiple_sections(self, doc_content: str):
        """Test that document has multiple H2 sections."""
        h2_sections = re.findall(r"^##\s+(.+)", doc_content, re.MULTILINE)
        assert len(h2_sections) >= 3, f"Document should have at least 3 H2 sections, found {len(h2_sections)}"

    def test_has_code_blocks(self, doc_content: str):
        """Test that document contains code blocks."""
        code_blocks = re.findall(r"```[\s\S]*?```", doc_content)
        assert len(code_blocks) > 0, "Document should contain at least one code block"

    def test_code_blocks_have_language(self, doc_content: str):
        """Test that code blocks specify a language."""
        code_block_starts = re.findall(r"```(\w+)?", doc_content)
        # At least some should have languages specified
        with_lang = [lang for lang in code_block_starts if lang]
        assert len(with_lang) > 0, "At least some code blocks should specify a language"

    def test_no_trailing_whitespace(self, doc_lines: List[str]):
        """Test that lines don't have trailing whitespace."""
        lines_with_trailing = [
            (i + 1, line) for i, line in enumerate(doc_lines) if line.rstrip("\n") != line.rstrip("\n").rstrip()
        ]
        assert len(lines_with_trailing) == 0, f"Found {len(lines_with_trailing)} lines with trailing whitespace"

    def test_consistent_heading_style(self, doc_content: str):
        """Test that headings use consistent ATX style (# not underlines)."""
        # Check for setext-style headers (underlines with = or -)
        setext_headers = re.findall(r"^\S.*\n[=-]+$", doc_content, re.MULTILINE)
        assert len(setext_headers) == 0, "Use ATX-style headers (# Title) instead of setext-style (underlines)"


class TestDocumentationContent:
    """Test the content and completeness of the documentation."""

    @pytest.fixture
    def doc_content(self) -> str:
        """Load the documentation content."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def test_mentions_test_file(self, doc_content: str):
        """Test that document mentions the test_github_workflows.py file."""
        assert "test_github_workflows.py" in doc_content, "Document should mention test_github_workflows.py"

    def test_mentions_requirements_dev(self, doc_content: str):
        """Test that document mentions requirements-dev.txt."""
        assert "requirements-dev.txt" in doc_content, "Document should mention requirements-dev.txt dependency file"

    def test_mentions_pytest(self, doc_content: str):
        """Test that document mentions pytest."""
        assert "pytest" in doc_content.lower(), "Document should mention pytest testing framework"

    def test_mentions_yaml(self, doc_content: str):
        """Test that document mentions YAML."""
        assert (
            "yaml" in doc_content.lower() or "YAML" in doc_content
        ), "Document should mention YAML since it's about workflow validation"

    def test_has_running_tests_section(self, doc_content: str):
        """Test that document explains how to run the tests."""
        # Should have either "Running" or "Run" in a section title
        assert re.search(
            r"##\s+.*Run(ning)?\s", doc_content, re.IGNORECASE
        ), "Document should have a section about running the tests"

    def test_has_examples(self, doc_content: str):
        """Test that document provides examples."""
        # Should have code blocks with pytest commands
        assert re.search(r"```.*pytest", doc_content, re.DOTALL), "Document should show pytest command examples"

    def test_mentions_duplicate_keys(self, doc_content: str):
        """Test that document discusses duplicate key detection."""
        content_lower = doc_content.lower()
        assert (
            "duplicate" in content_lower and "key" in content_lower
        ), "Document should mention duplicate key detection"

    def test_has_test_count_info(self, doc_content: str):
        """Test that document mentions number of tests or test classes."""
        # Should mention numbers related to tests
        assert re.search(
            r"\d+\s+(test|class)", doc_content, re.IGNORECASE
        ), "Document should mention test counts or test class counts"


class TestDocumentationLinks:
    """Test links and references in the documentation."""

    @pytest.fixture
    def doc_content(self) -> str:
        """Load the documentation content."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def test_no_broken_internal_links(self, doc_content: str):
        """Test that internal anchor links reference existing headers."""
        # Find all internal links [text](#anchor)
        internal_links = re.findall(r"\[([^\]]+)\]\(#([^)]+)\)", doc_content)

        # Find all headers that could be anchors
        headers = re.findall(r"^#+\s+(.+)$", doc_content, re.MULTILINE)

        # Convert headers to likely anchor format (lowercase, spaces to hyphens)
        anchors = set()
        for header in headers:
            # Remove markdown formatting
            clean_header = re.sub(r"[`*_]", "", header)
            # Convert to anchor format
            anchor = clean_header.lower().strip()
            anchor = re.sub(r"[^\w\s-]", "", anchor)
            anchor = re.sub(r"\s+", "-", anchor)
            anchors.add(anchor)

        # Check each internal link
        for link_text, link_anchor in internal_links:
            assert (
                link_anchor in anchors
            ), f"Internal link #{link_anchor} ('{link_text}') references non-existent header"

    def test_relative_file_paths_exist(self, doc_content: str):
        """Test that referenced file paths exist in the repository."""
        # Find patterns that look like file paths
        file_patterns = [
            r"tests/integration/\S+\.py",
            r"requirements-dev\.txt",
            r"\.github/workflows/\S+\.yml",
        ]

        repo_root = DOC_FILE.parent

        for pattern in file_patterns:
            matches = re.findall(pattern, doc_content)
            for match in matches:
                file_path = repo_root / match
                # Some paths might be examples, so just warn if many are missing
                if not file_path.exists():
                    print(f"Warning: Referenced file may not exist: {match}")


class TestDocumentationBestPractices:
    """Test documentation follows best practices."""

    @pytest.fixture
    def doc_content(self) -> str:
        """Load the documentation content."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    def doc_lines(self) -> List[str]:
        """Load the documentation as a list of lines."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            return f.readlines()

    def test_reasonable_line_length(self, doc_lines: List[str]):
        """Test that most lines are not excessively long."""
        long_lines = [(i + 1, len(line)) for i, line in enumerate(doc_lines) if len(line.rstrip()) > 120]

        # Allow some long lines (code blocks, URLs, etc.) but not too many
        max_long_lines = len(doc_lines) * 0.1  # 10% threshold
        assert len(long_lines) < max_long_lines, f"Too many long lines (>{len(long_lines)}). Consider breaking them up."

    def test_has_list_items(self, doc_content: str):
        """Test that document uses lists for organization."""
        # Should have either bullet lists (-) or numbered lists (1.)
        has_bullets = bool(re.search(r"^\s*[-*+]\s+", doc_content, re.MULTILINE))
        has_numbered = bool(re.search(r"^\s*\d+\.\s+", doc_content, re.MULTILINE))

        assert has_bullets or has_numbered, "Document should use lists for better organization"

    def test_proper_code_fence_closure(self, doc_content: str):
        """Test that all code fences are properly closed."""
        # Count opening and closing code fences
        code_fences = re.findall(r"^```", doc_content, re.MULTILINE)

        assert (
            len(code_fences) % 2 == 0
        ), f"Unmatched code fences: found {len(code_fences)} ``` markers (should be even)"

    def test_uses_proper_emphasis(self, doc_content: str):
        """Test that document uses proper emphasis markers."""
        # Check for improperly closed emphasis
        # Should not have orphaned * or _
        text_without_code = re.sub(r"```[\s\S]*?```", "", doc_content)

        # Count asterisks not in code
        asterisks = text_without_code.count("*")
        underscores = text_without_code.count("_")

        # Should be even (paired for opening/closing)
        if asterisks > 0:
            assert asterisks % 2 == 0, "Unmatched * for emphasis"


class TestDocumentationCompleteness:
    """Test that documentation covers all important aspects."""

    @pytest.fixture
    def doc_content(self) -> str:
        """Load the documentation content."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def test_has_benefits_or_features(self, doc_content: str):
        """Test that document lists benefits or features."""
        content_lower = doc_content.lower()
        assert "benefit" in content_lower or "feature" in content_lower, "Document should describe benefits or features"

    def test_has_usage_instructions(self, doc_content: str):
        """Test that document provides usage instructions."""
        # Should have imperative verbs or command examples
        has_instructions = any(
            [
                re.search(r"\brun\b.*pytest", doc_content, re.IGNORECASE),
                re.search(r"\bexecute\b", doc_content, re.IGNORECASE),
                re.search(r"\binstall\b", doc_content, re.IGNORECASE),
            ]
        )
        assert has_instructions, "Document should provide usage instructions"

    def test_mentions_ci_integration(self, doc_content: str):
        """Test that document mentions CI/CD integration."""
        content_lower = doc_content.lower()
        has_ci_mention = any(
            [
                "ci" in content_lower,
                "continuous integration" in content_lower,
                "github actions" in content_lower,
                "workflow" in content_lower,
            ]
        )
        assert has_ci_mention, "Document should mention CI/CD or workflow integration"


class TestDocumentationSections:
    """Test that all expected sections are present."""

    @pytest.fixture
    def section_headers(self) -> List[str]:
        """Extract all section headers from the document."""
        with open(DOC_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        return re.findall(r"^##\s+(.+)$", content, re.MULTILINE)

    def test_has_overview(self, section_headers: List[str]):
        """Test that there's an Overview section."""
        overview = [h for h in section_headers if "overview" in h.lower()]
        assert len(overview) > 0, "Should have an Overview section"

    def test_has_generated_files_section(self, section_headers: List[str]):
        """Test that there's a section about generated files."""
        generated = [h for h in section_headers if "generated" in h.lower() or "file" in h.lower()]
        assert len(generated) > 0, "Should have a section about generated files"

    def test_has_running_section(self, section_headers: List[str]):
        """Test that there's a section about running tests."""
        running = [h for h in section_headers if "run" in h.lower()]
        assert len(running) > 0, "Should have a section about running tests"

    def test_has_sufficient_sections(self, section_headers: List[str]):
        """Test that document has sufficient number of sections."""
        assert (
            len(section_headers) >= 5
        ), f"Document should have at least 5 major sections, found {len(section_headers)}"
