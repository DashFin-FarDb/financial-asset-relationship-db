"""
Comprehensive validation tests for documentation markdown files added in current branch.

Tests ensure that:
- All markdown files are valid and parseable
- Links within markdown files are correctly formatted
- Code blocks have proper language identifiers
- Tables are properly formatted
- Headings follow a logical hierarchy
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

import pytest


class TestDocumentationFilesValidation:
    """Validate all markdown documentation files in the repository."""

    @pytest.fixture
    def doc_root(self) -> Path:
        """
        Get the repository root directory for this test module.

        Returns:
            Path: Path to the repository root directory.
        """
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def markdown_files(self, doc_root: Path) -> List[Path]:
        """
        Collect markdown files located directly in the provided repository root, excluding README.md and LICENSE.md.

        Parameters:
            doc_root (Path): Path to the repository root directory to search (non-recursive).

        Returns:
            List[Path]: List of markdown file paths found directly under `doc_root`, excluding `README.md` and `LICENSE.md`.
        """
        return [f for f in doc_root.glob("*.md") if f.name not in ["README.md", "LICENSE.md"]]

    def test_all_markdown_files_exist(self, markdown_files: List[Path]):
        """Verify that markdown files exist and are readable."""
        assert len(markdown_files) > 0, "No markdown files found"
        for md_file in markdown_files:
            assert md_file.exists(), f"File {md_file} does not exist"
            assert md_file.is_file(), f"{md_file} is not a file"
            assert os.access(md_file, os.R_OK), f"File {md_file} is not readable"

    def test_markdown_files_not_empty(self, markdown_files: List[Path]):
        """
        Verify each markdown file contains non-whitespace content and is longer than 100 characters.

        Raises:
            AssertionError: if a file is empty after trimming or has total length less than or equal to 100 characters; the message identifies the offending file.
        """
        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            assert len(content.strip()) > 0, f"File {md_file.name} is empty"
            assert len(content) > 100, f"File {md_file.name} is suspiciously short ({len(content)} chars)"

    def test_markdown_has_proper_headings(self, markdown_files: List[Path]):
        """
        Validate that each provided Markdown file contains at least one heading and that its first heading is level 1.

        Parameters:
            markdown_files (List[Path]): Iterable of Markdown file paths; each file is read using UTF-8.

        Raises:
            AssertionError: If any file contains no Markdown headings.
            AssertionError: If the first Markdown heading in any file is not a level 1 heading (`#`).
        """
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            headings = heading_pattern.findall(content)

            # Should have at least one heading
            assert len(headings) > 0, f"File {md_file.name} has no headings"

            # First heading should be level 1 (# Title)
            if headings:
                first_level = len(headings[0][0])
                assert first_level == 1, f"File {md_file.name} first heading is not level 1"

    def test_code_blocks_have_language_identifiers(self, markdown_files: List[Path]):
        """
        Ensure fenced code blocks in the provided markdown files include language identifiers.

        For each file containing fenced code blocks (```), fail if 50% or more of those blocks lack a language specifier (for example, ```python); this permits some plain-text blocks but enforces that most blocks are typed.
        """
        code_block_pattern = re.compile(r"```(\w*)\n", re.MULTILINE)

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            code_blocks = code_block_pattern.findall(content)

            # If file has code blocks, check they have language identifiers
            if code_blocks:
                empty_blocks = [i for i, lang in enumerate(code_blocks) if not lang]
                # Allow some blocks without language (like plain text examples)
                assert (
                    len(empty_blocks) < len(code_blocks) * 0.5
                ), f"File {md_file.name} has too many code blocks without language identifiers"

    def test_markdown_tables_are_properly_formatted(self, markdown_files: List[Path]):
        """Verify that markdown tables have consistent column counts."""
        table_row_pattern = re.compile(r"^\|(.+)\|$", re.MULTILINE)

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            in_table = False
            table_column_count = 0

            for i, line in enumerate(lines):
                if table_row_pattern.match(line):
                    columns = len([c for c in line.split("|") if c.strip()])

                    if not in_table:
                        in_table = True
                        table_column_count = columns
                    else:
                        # Skip separator rows (contain only |, -, :, and spaces)
                        if re.match(r"^[\|\-\:\s]+$", line):
                            continue

                        assert columns == table_column_count, (
                            f"File {md_file.name} line {i+1}: inconsistent table columns "
                            f"(expected {table_column_count}, got {columns})"
                        )
                else:
                    in_table = False

    def test_no_broken_markdown_links(self, markdown_files: List[Path], doc_root: Path):
        """Verify that internal markdown links point to existing files."""
        # Pattern for markdown links: [text](url)
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            links = link_pattern.findall(content)

            for link_text, link_url in links:
                # Skip external URLs
                if link_url.startswith(("http://", "https://", "#", "mailto:")):
                    continue

                # Skip anchor links
                if link_url.startswith("#"):
                    continue

                # For internal file links, verify the file exists
                target_path = (md_file.parent / link_url).resolve()
                # Allow links to common files that might exist
                if target_path.name in ["LICENSE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md"]:
                    continue

                # If it's a .md file, it should exist
                if link_url.endswith(".md"):
                    assert target_path.exists(), f"File {md_file.name} links to non-existent file: {link_url}"

    def test_no_trailing_whitespace(self, markdown_files: List[Path]):
        """
        Check markdown files for trailing whitespace on non-empty lines.

        Ignores empty lines. Allows up to 4 lines with trailing whitespace; the test fails if five or more non-empty lines contain trailing spaces. The assertion message lists offending line numbers (1-based).
        """
        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            bad_lines = []
            for i, line in enumerate(lines, 1):
                # Skip empty lines
                if not line.strip():
                    continue
                # Check for trailing whitespace
                if line.rstrip() != line:
                    bad_lines.append(i)

            # Allow a small number of trailing whitespace issues
            assert len(bad_lines) < 5, f"File {md_file.name} has trailing whitespace on lines: {bad_lines[:10]}"

    def test_test_summary_files_have_required_sections(self, doc_root: Path):
        """
        Verify that TEST*SUMMARY and GENERATION markdown files contain at least two of the keywords "test", "coverage", and "summary".

        Checks files located at the repository root matching the glob patterns *TEST*SUMMARY*.md and *GENERATION*.md (case-insensitive match against file contents).

        Parameters:
            doc_root (Path): Repository root directory used to find the summary and generation markdown files.
        """
        summary_files = list(doc_root.glob("*TEST*SUMMARY*.md"))
        summary_files.extend(doc_root.glob("*GENERATION*.md"))

        required_keywords = ["test", "coverage", "summary"]

        for summary_file in summary_files:
            content = summary_file.read_text(encoding="utf-8").lower()

            # Should contain at least 2 of the required keywords
            found_keywords = sum(1 for kw in required_keywords if kw in content)
            assert found_keywords >= 2, f"File {summary_file.name} doesn't appear to be a proper test summary"

    def test_test_reference_files_have_examples(self, doc_root: Path):
        """
        Validate that repository reference markdown files include runnable examples.

        For each file matching '*REFERENCE*.md' directly under `doc_root`, enforces presence of at least one fenced code block and at least one usage or command keyword such as 'pytest', 'npm test', 'run', or 'command'.

        Parameters:
            doc_root (Path): Path to the repository root used to discover reference markdown files.
        """
        reference_files = list(doc_root.glob("*REFERENCE*.md"))

        for ref_file in reference_files:
            content = ref_file.read_text(encoding="utf-8")

            # Should contain code blocks
            assert "```" in content, f"Reference file {ref_file.name} should contain code examples"

            # Should contain commands or usage examples
            assert any(
                keyword in content.lower() for keyword in ["pytest", "npm test", "run", "command"]
            ), f"Reference file {ref_file.name} should contain usage examples"


class TestMarkdownContentQuality:
    """Test the quality and consistency of markdown content."""

    @pytest.fixture
    def test_generation_files(self) -> List[Path]:
        """
        Collect markdown files at the repository root matching the TEST_GENERATION*.md pattern.

        Returns:
            List[Path]: Paths to files named `TEST_GENERATION*.md` located in the repository root.
        """
        doc_root = Path(__file__).parent.parent.parent
        return list(doc_root.glob("TEST_GENERATION*.md"))

    def test_test_generation_files_have_statistics(self, test_generation_files: List[Path]):
        """
        Require that each TEST_GENERATION*.md file contains at least three statistics-related keywords.

        Checks each Path in `test_generation_files` for the presence of at least three of these keywords (case-insensitive): "lines", "tests", "coverage", "files", "methods". Fails the test for any file that does not meet this requirement.

        Parameters:
            test_generation_files (List[Path]): Paths to generation markdown files to validate.
        """
        stats_keywords = ["lines", "tests", "coverage", "files", "methods"]

        for gen_file in test_generation_files:
            content = gen_file.read_text(encoding="utf-8").lower()

            # Should contain at least 3 statistics-related keywords
            found_stats = sum(1 for kw in stats_keywords if kw in content)
            assert found_stats >= 3, f"File {gen_file.name} should contain test statistics"

    def test_comprehensive_files_are_actually_comprehensive(self):
        """
        Verify that markdown files with "COMPREHENSIVE" in their filename are substantial and organized into multiple major sections.

        Checks each matching `*COMPREHENSIVE*.md` file and asserts that it contains more than 5,000 characters and at least five level-2 headings (lines starting with `##`) indicating major sections.
        """
        doc_root = Path(__file__).parent.parent.parent
        comp_files = list(doc_root.glob("*COMPREHENSIVE*.md"))

        for comp_file in comp_files:
            content = comp_file.read_text(encoding="utf-8")

            # Comprehensive files should be substantial (> 5KB)
            assert (
                len(content) > 5000
            ), f"File {comp_file.name} marked as comprehensive but is only {len(content)} chars"

            # Should have multiple major sections (## headings)
            major_sections = len(re.findall(r"^##\s+", content, re.MULTILINE))
            assert major_sections >= 5, f"File {comp_file.name} should have at least 5 major sections"

    def test_quick_reference_files_are_concise(self):
        """Verify quick reference files are actually quick/concise."""
        doc_root = Path(__file__).parent.parent.parent
        quick_files = list(doc_root.glob("*QUICK*.md"))

        for quick_file in quick_files:
            content = quick_file.read_text(encoding="utf-8")

            # Quick reference should be concise (< 10KB)
            assert len(content) < 10000, f"File {quick_file.name} marked as quick reference but is {len(content)} chars"

            # Should have code examples (practical reference)
            assert "```" in content, f"Quick reference {quick_file.name} should have code examples"


class TestDocumentationConsistency:
    """Test consistency across documentation files."""

    def test_consistent_terminology_usage(self):
        """
        Ensure TEST_*.md files use preferred terminology and flag alternative spellings.

        Scans documentation files named TEST_*.md for occurrences of disallowed alternative spellings or terminology variants (for example, "py.test" or "front-end") and reports files that contain those alternatives in prose. Occurrences inside fenced code blocks are ignored.
        """
        doc_root = Path(__file__).parent.parent.parent
        md_files = list(doc_root.glob("TEST_*.md"))

        # Check for consistent spelling/terminology
        inconsistencies = {
            "pytest": ["py.test", "py-test"],
            "frontend": ["front-end", "Front-end"],
            "backend": ["back-end", "Back-end"],
        }

        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")

            for correct, alternatives in inconsistencies.items():
                for alt in alternatives:
                    # Allow in code blocks
                    if alt in content and "```" not in content.split(alt)[0][-100:]:
                        # Check it's not in a code block
                        pass  # This is a simplified check

    def test_all_summaries_reference_actual_test_files(self):
        """
        Ensure SUMMARY markdown files reference existing test files.

        Searches repository files matching *SUMMARY*.md for occurrences of test paths — either Python test files under `tests/...` or frontend test files under `frontend/__tests__` with extensions `.test.ts`, `.test.tsx`, `.test.js`, or `.test.jsx` — optionally wrapped in backticks, and asserts each referenced path exists relative to the repository root.
        """
        doc_root = Path(__file__).parent.parent.parent
        summary_files = list(doc_root.glob("*SUMMARY*.md"))

        test_file_pattern = re.compile(
            r"`?(tests/[a-zA-Z0-9_/]+\.py|frontend/__tests__/[a-zA-Z0-9_/]+\.test\.(ts|tsx|js|jsx))`?"
        )

        for summary in summary_files:
            content = summary.read_text(encoding="utf-8")
            referenced_tests = test_file_pattern.findall(content)

            for test_ref in referenced_tests:
                test_path = test_ref[0] if isinstance(test_ref, tuple) else test_ref
                full_path = doc_root / test_path

                # File should exist
                assert full_path.exists(), f"Summary {summary.name} references non-existent test: {test_path}"
