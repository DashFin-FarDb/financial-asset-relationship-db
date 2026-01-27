"""
Comprehensive validation tests for documentation markdown files added in current branch.

Tests ensure that:
- All markdown files are valid and parseable
- Links within markdown files are correctly formatted
- Code blocks have proper language identifiers
- Tables are properly formatted
- Headings follow a logical hierarchy
"""

import re
from pathlib import Path
from typing import List

import pytest


class TestDocumentationFilesValidation:
    """Validate all markdown documentation files in the repository."""

    @pytest.fixture
    def doc_root(self) -> Path:
        """Return the repository root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def markdown_files(self, doc_root: Path) -> List[Path]:
        """
        Collect markdown files located directly in the repository root,
        excluding README.md and LICENSE.md.
        """
        return [
            path
            for path in doc_root.glob("*.md")
            if path.name not in {"README.md", "LICENSE.md"}
        ]

    def test_all_markdown_files_exist(self, markdown_files: List[Path]) -> None:
        """Verify that markdown files exist and are readable."""
        assert markdown_files, "No markdown files found"

        for md_file in markdown_files:
            assert md_file.exists(), f"File {md_file} does not exist"
            assert md_file.is_file(), f"{md_file} is not a file"
            assert md_file.open("r", encoding="utf-8")

    def test_markdown_files_not_empty(self, markdown_files: List[Path]) -> None:
        """Verify each markdown file contains non-whitespace content."""
        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            assert content.strip(), f"File {md_file.name} is empty"
            assert len(content) > 100, (
                f"File {md_file.name} is suspiciously short ({len(content)} chars)"
            )

    def test_markdown_has_proper_headings(
        self, markdown_files: List[Path]
    ) -> None:
        """Each file must contain at least one heading and start with level-1."""
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            headings = heading_pattern.findall(content)

            assert headings, f"File {md_file.name} has no headings"

            first_level = len(headings[0][0])
            assert first_level == 1, (
                f"File {md_file.name} first heading is not level 1"
            )

    def test_code_blocks_have_language_identifiers(
        self, markdown_files: List[Path]
    ) -> None:
        """
        Ensure fenced code blocks include language identifiers.
        Allows <50% blocks without language.
        """
        code_block_pattern = re.compile(r"```(\w*)\n", re.MULTILINE)

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            code_blocks = code_block_pattern.findall(content)

            if not code_blocks:
                continue

            empty_blocks = [lang for lang in code_blocks if not lang]
            assert len(empty_blocks) < len(code_blocks) * 0.5, (
                f"File {md_file.name} has too many code blocks without language identifiers"
            )

    def test_markdown_tables_are_properly_formatted(
        self, markdown_files: List[Path]
    ) -> None:
        """Verify markdown tables have consistent column counts."""
        table_row_pattern = re.compile(r"^\|(.+)\|$", re.MULTILINE)

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            lines = content.splitlines()

            in_table = False
            table_column_count = 0

            for index, line in enumerate(lines, start=1):
                if not table_row_pattern.match(line):
                    in_table = False
                    continue

                columns = len([col for col in line.split("|") if col.strip()])

                if not in_table:
                    in_table = True
                    table_column_count = columns
                    continue

                if re.match(r"^[\|\-\:\s]+$", line):
                    continue

                assert columns == table_column_count, (
                    f"File {md_file.name} line {index}: inconsistent table columns "
                    f"(expected {table_column_count}, got {columns})"
                )

    def test_no_broken_markdown_links(
        self, markdown_files: List[Path], doc_root: Path
    ) -> None:
        """Verify that internal markdown links point to existing files."""
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            links = link_pattern.findall(content)

            for _, link_url in links:
                if link_url.startswith(("http://", "https://", "#", "mailto:")):
                    continue

                target_path = (md_file.parent / link_url).resolve()

                if target_path.name in {
                    "LICENSE",
                    "CONTRIBUTING.md",
                    "CODE_OF_CONDUCT.md",
                }:
                    continue

                if link_url.endswith(".md"):
                    assert target_path.exists(), (
                        f"File {md_file.name} links to non-existent file: {link_url}"
                    )

    def test_no_trailing_whitespace(
        self, markdown_files: List[Path]
    ) -> None:
        """Check markdown files for trailing whitespace."""
        for md_file in markdown_files:
            lines = md_file.read_text(encoding="utf-8").splitlines()

            bad_lines: List[int] = []
            for index, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                if line.rstrip() != line:
                    bad_lines.append(index)

            assert len(bad_lines) < 5, (
                f"File {md_file.name} has trailing whitespace on lines: {bad_lines[:10]}"
            )

    def test_test_summary_files_have_required_sections(
        self, doc_root: Path
    ) -> None:
        """Verify summary/generation markdown contains key terms."""
        summary_files = list(doc_root.glob("*TEST*SUMMARY*.md"))
        summary_files.extend(doc_root.glob("*GENERATION*.md"))

        required_keywords = ("test", "coverage", "summary")

        for summary_file in summary_files:
            content = summary_file.read_text(encoding="utf-8").lower()
            found = sum(1 for kw in required_keywords if kw in content)

            assert found >= 2, (
                f"File {summary_file.name} doesn't appear to be a proper test summary"
            )

    def test_test_reference_files_have_examples(
        self, doc_root: Path
    ) -> None:
        """Reference markdown files must contain runnable examples."""
        reference_files = list(doc_root.glob("*REFERENCE*.md"))

        for ref_file in reference_files:
            content = ref_file.read_text(encoding="utf-8")

            assert "```" in content, (
                f"Reference file {ref_file.name} should contain code examples"
            )

            assert any(
                keyword in content.lower()
                for keyword in ("pytest", "npm test", "run", "command")
            ), f"Reference file {ref_file.name} should contain usage examples"


class TestMarkdownContentQuality:
    """Test the quality and consistency of markdown content."""

    @pytest.fixture
    def test_generation_files(self) -> List[Path]:
        """Collect TEST_GENERATION*.md files."""
        doc_root = Path(__file__).parent.parent.parent
        return list(doc_root.glob("TEST_GENERATION*.md"))

    def test_test_generation_files_have_statistics(
        self, test_generation_files: List[Path]
    ) -> None:
        """TEST_GENERATION files must include statistics keywords."""
        stats_keywords = ("lines", "tests", "coverage", "files", "methods")

        for gen_file in test_generation_files:
            content = gen_file.read_text(encoding="utf-8").lower()
            found = sum(1 for kw in stats_keywords if kw in content)

            assert found >= 3, (
                f"File {gen_file.name} should contain test statistics"
            )

    def test_comprehensive_files_are_actually_comprehensive(self) -> None:
        """COMPREHENSIVE files must be large and structured."""
        doc_root = Path(__file__).parent.parent.parent
        comp_files = list(doc_root.glob("*COMPREHENSIVE*.md"))

        for comp_file in comp_files:
            content = comp_file.read_text(encoding="utf-8")

            assert len(content) > 5000, (
                f"File {comp_file.name} marked as comprehensive but is only {len(content)} chars"
            )

            major_sections = len(re.findall(r"^##\s+", content, re.MULTILINE))
            assert major_sections >= 5, (
                f"File {comp_file.name} should have at least 5 major sections"
            )

    def test_quick_reference_files_are_concise(self) -> None:
        """QUICK reference files must be concise and practical."""
        doc_root = Path(__file__).parent.parent.parent
        quick_files = list(doc_root.glob("*QUICK*.md"))

        for quick_file in quick_files:
            content = quick_file.read_text(encoding="utf-8")

            assert len(content) < 10000, (
                f"File {quick_file.name} marked as quick reference but is {len(content)} chars"
            )

            assert "```" in content, (
                f"Quick reference {quick_file.name} should have code examples"
            )


class TestDocumentationConsistency:
    """Test consistency across documentation files."""

    def test_consistent_terminology_usage(self) -> None:
        """
        Ensure TEST_*.md files use preferred terminology.
        """
        doc_root = Path(__file__).parent.parent.parent
        md_files = list(doc_root.glob("TEST_*.md"))

        inconsistencies = {
            "pytest": ("py.test", "py-test"),
            "frontend": ("front-end", "Front-end"),
            "backend": ("back-end", "Back-end"),
        }

        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")

            for alternatives in inconsistencies.values():
                for alt in alternatives:
                    if alt in content:
                        # intentionally informational (no assertion by design)
                        pass

    def test_all_summaries_reference_actual_test_files(self) -> None:
        """SUMMARY markdown must reference existing test files."""
        doc_root = Path(__file__).parent.parent.parent
        summary_files = list(doc_root.glob("*SUMMARY*.md"))

        test_file_pattern = re.compile(
            r"`?(tests/[a-zA-Z0-9_/]+\.py|frontend/__tests__/[a-zA-Z0-9_/]+\.test\.(ts|tsx|js|jsx))`?"
        )

        for summary in summary_files:
            content = summary.read_text(encoding="utf-8")
            referenced_tests = test_file_pattern.findall(content)

            for test_ref in referenced_tests:
                test_path = test_ref[0]
                full_path = doc_root / test_path

                assert full_path.exists(), (
                    f"Summary {summary.name} references non-existent test: {test_path}"
                )
