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


def test_no_trailing_whitespace(self, markdown_files: List[Path]) -> None:
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


def test_test_summary_files_have_required_sections(self, doc_root: Path) -> None:
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


def test_test_reference_files_have_examples(self, doc_root: Path) -> None:
    """Reference markdown files must contain runnable examples."""
    reference_files = list(doc_root.glob("*REFERENCE*.md"))

    for ref_file in reference_files:
        content = ref_file.read_text(encoding="utf-8")

        assert "```" in content, (
            f"File {ref_file.name} doesn't contain runnable code examples"
        )
