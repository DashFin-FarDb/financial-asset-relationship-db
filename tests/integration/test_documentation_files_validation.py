"""
Comprehensive validation tests for documentation markdown files.

Tests ensure that:
- All markdown files are readable and (optionally) parseable
- Links within markdown files are reasonably well formatted
- Code blocks have language identifiers where expected
- Tables have consistent column counts per table
- Headings follow a logical hierarchy (no large jumps)
"""

from pathlib import Path
from typing import List, Tuple

import pytest


class TestDocumentationFilesValidation:
    """Validation suite for documentation markdown files.

    Ensures that markdown files are parseable, links are correctly
    formatted, code blocks have proper language identifiers, tables are
    formatted consistently, and heading hierarchy is followed.
    """

    @staticmethod
    def _markdown_files() -> List[Path]:
        """
        Collect markdown files from the docs directory and top-level project root.

        Searches docs/ recursively for files ending with `.md` (if docs/ exists) and also includes top-level `*.md` files in the repository root. Duplicate paths are removed while preserving the discovery order.

        Returns:
            List[Path]: Ordered list of unique Path objects pointing to markdown files to validate.
        """
        docs_dir = Path("docs")
        files: List[Path] = []

        if docs_dir.exists():
            files.extend(docs_dir.rglob("*.md"))

        # Top-level markdown files such as README.md, CONTRIBUTING.md
        files.extend(Path(".").glob("*.md"))

        # De-duplicate while preserving order
        seen = set()
        unique_files: List[Path] = []
        for f in files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)

        return unique_files

    @pytest.fixture(scope="class")
    def markdown_files(self) -> List[Path]:
        """
        Provide the list of Markdown file paths used by the test class, skipping the entire test suite if none are found.

        Returns:
            List[Path]: Collected Markdown file paths. If no Markdown files are discovered, the fixture will call pytest.skip and not return.
        """
        files = self._markdown_files()
        if not files:
            pytest.skip("No markdown documentation files found.")
        return files

    def test_markdown_files_are_readable_and_non_empty(
        self,
        markdown_files: List[Path],
    ) -> None:
        """
        Verify that each Markdown file can be read with UTF-8 encoding and contains non-whitespace content.

        Reads every Path in `markdown_files`, records files that raise I/O errors and files whose content is empty after stripping whitespace, and fails the test with a consolidated list of problematic files and reasons if any issues are found.
        """
        unreadable: List[Tuple[Path, str]] = []
        empty: List[Path] = []

        for md_file in markdown_files:
            try:
                content = md_file.read_text(encoding="utf-8")
            except OSError as exc:
                unreadable.append((md_file, str(exc)))
                continue

            if not content.strip():
                empty.append(md_file)

        errors: List[str] = []
        for path, msg in unreadable:
            errors.append(f"{path}: unreadable ({msg})")
        for path in empty:
            errors.append(f"{path}: file is empty")

        assert not errors, "Markdown file issues:\n" + "\n".join(errors)

    def test_markdown_is_parseable_if_markdown_installed(
        self,
        markdown_files: List[Path],
    ) -> None:
        """
        Verify that each Markdown file can be parsed by the installed `markdown` package.

        Skips the test if the `markdown` package is not available. Attempts to parse the UTF-8 content of each provided file and fails the test with an aggregated message if any file raises a parsing exception.

        Parameters:
            markdown_files (List[Path]): Paths to Markdown files to validate.
        """
        try:
            import markdown  # type: ignore[import-not-found]
        except ImportError:
            pytest.skip(
                "markdown package not installed; skipping parseability checks.",
            )

        parse_errors: List[Tuple[Path, str]] = []

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            try:
                markdown.markdown(content)
            except Exception as exc:  # noqa: BLE001
                parse_errors.append((md_file, str(exc)))

        assert not parse_errors, "Markdown parse errors:\n" + "\n".join(f"{path}: {err}" for path, err in parse_errors)

    def test_links_are_well_formed(
        self,
        markdown_files: List[Path],
    ) -> None:
        """
        Validate that inline Markdown links use the basic [text](url) form and have no obvious formatting issues.

        Checks each provided Markdown file for inline links and flags:
        - empty link text,
        - empty link URL,
        - URLs containing space characters.

        Parameters:
            markdown_files (List[Path]): Paths of Markdown files to scan.

        Raises:
            AssertionError: If any malformed links are found; the assertion message lists each file and issue.
        """
        import re

        bad_links: List[Tuple[Path, str]] = []

        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            for match in link_pattern.finditer(content):
                text, url = match.groups()
                if not text.strip():
                    bad_links.append((md_file, f"Empty link text: {match.group(0)}"))
                if not url.strip():
                    bad_links.append((md_file, f"Empty link URL: {match.group(0)}"))
                if " " in url.strip():
                    bad_links.append(
                        (md_file, f"URL contains spaces: {match.group(0)}"),
                    )

        assert not bad_links, "Malformed markdown links:\n" + "\n".join(f"{path}: {msg}" for path, msg in bad_links)

    def test_code_blocks_have_language_identifiers_where_expected(
        self,
        markdown_files: List[Path],
    ) -> None:
        """Triple-backtick code fences should usually specify a language."""
        fence_issues: List[Tuple[Path, str]] = []

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            lines = content.splitlines()

            in_fence = False
            for idx, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("```"):
                    if not in_fence and stripped == "```":
                        fence_issues.append(
                            (
                                md_file,
                                f"Line {idx + 1}: code fence has no language identifier",
                            ),
                        )
                    in_fence = not in_fence
                    continue

        assert not fence_issues, "Code block language issues:\n" + "\n".join(
            f"{path}: {msg}" for path, msg in fence_issues
        )

    def test_tables_have_consistent_column_counts(
        self,
        markdown_files: List[Path],
    ) -> None:
        """
        Validate that every Markdown table has the same number of columns on each row within that table.

        Scans the provided Markdown files for contiguous table blocks (lines containing '|') and asserts that all rows in a table have an identical column count. On failure, reports the file path and line number for each mismatched row.
        """
        table_errors: List[Tuple[Path, str]] = []

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            lines = content.splitlines()

            in_table = False
            expected_cols = 0

            for idx, line in enumerate(lines):
                if "|" not in line:
                    # End of a table block
                    in_table = False
                    expected_cols = 0
                    continue

                # Count columns: ignore leading/trailing pipe empties
                cols = [c for c in line.split("|")]
                col_count = len(cols)

                if not in_table:
                    in_table = True
                    expected_cols = col_count
                else:
                    if col_count != expected_cols:
                        table_errors.append(
                            (
                                md_file,
                                (f"Line {idx + 1}: expected {expected_cols} " f"columns, found {col_count}"),
                            ),
                        )

        assert not table_errors, "Markdown table formatting issues:\n" + "\n".join(
            f"{path}: {msg}" for path, msg in table_errors
        )

    def test_heading_hierarchy_is_logical(
        self,
        markdown_files: List[Path],
    ) -> None:
        """
        Ensure Markdown heading levels do not increase by more than one level at a time.

        When a heading level jumps by more than one from the previous heading, record the file and line and fail the test with a summary of offending locations.
        """
        import re

        heading_pattern = re.compile(r"^(#{1,6})\s+.+$")
        hierarchy_errors: List[Tuple[Path, str]] = []

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            last_level = None

            for idx, line in enumerate(lines):
                match = heading_pattern.match(line)
                if not match:
                    continue

                level = len(match.group(1))
                if last_level is None:
                    last_level = level
                    continue

                # Allow same level, or increase by 1, or decrease arbitrarily.
                if level > last_level + 1:
                    hierarchy_errors.append(
                        (
                            md_file,
                            (f"Line {idx + 1}: heading level jumps from " f"H{last_level} to H{level}"),
                        ),
                    )
                last_level = level

        assert not hierarchy_errors, "Markdown heading hierarchy issues:\n" + "\n".join(
            f"{path}: {msg}" for path, msg in hierarchy_errors
        )
