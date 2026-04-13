#!/usr/bin/env python3
"""
Validate systemManifest.md for duplicate section headings (MD024).

This script checks for duplicate level 2 headings (##) in the manifest file,
which violates the markdownlint MD024 rule (no-duplicate-heading).

Exit codes:
    0: No duplicates found
    1: Duplicates found or error occurred
"""

import sys
from pathlib import Path
from typing import Dict, List


def _collect_headings(lines: List[str]) -> Dict[str, List[int]]:
    """
    Collect level-2 Markdown headings and their 1-based line numbers.

    Parameters:
        lines (List[str]): Lines of a Markdown document in order; lines may include line endings.

    Returns:
        Dict[str, List[int]]: Mapping from each level-2 heading text (the text following '##') to a list of 1-based line numbers where that heading appears.
    """
    occurrences: Dict[str, List[int]] = {}

    for line_num, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            heading = stripped[3:].strip()
            occurrences.setdefault(heading, []).append(line_num)

    return occurrences


def _report_duplicates(
    duplicates: Dict[str, List[int]],
    manifest_path: Path,
) -> int:
    """
    Print a formatted MD024 violation report for duplicated level-2 headings to stderr.

    Parameters:
        duplicates (Dict[str, List[int]]): Mapping from duplicated heading text to the list of 1-based line numbers where each occurs.
        manifest_path (Path): Path to the manifest file being validated.

    Returns:
        int: 1 to indicate a duplicate-heading validation failure.
    """
    print(
        f"❌ MD024 violation: Duplicate headings found in {manifest_path}\n",
        file=sys.stderr,
    )
    print(
        f"Found {len(duplicates)} heading(s) with duplicates:\n",
        file=sys.stderr,
    )

    for heading, line_nums in sorted(duplicates.items()):
        print(
            f"  '{heading}' appears {len(line_nums)} times:",
            file=sys.stderr,
        )
        for line_num in line_nums:
            print(f"    - Line {line_num}", file=sys.stderr)
        print(file=sys.stderr)

    print(
        "Run 'python scripts/deduplicate_manifest.py' to fix these issues.",
        file=sys.stderr,
    )
    return 1


def check_duplicate_headings(manifest_path: Path) -> int:
    """
    Validate that the repository's systemManifest.md contains no duplicate level-2 headings.

    Checks that the provided path refers to the expected .elastic-copilot/memory/systemManifest.md within the repository, reads the file, and detects duplicate level-2 headings (lines beginning with "## " but not "### "). Reports duplicates to stderr when found.

    Parameters:
        manifest_path (Path): Path to the systemManifest.md file to validate.

    Returns:
        int: Exit code where `0` indicates no duplicate level-2 headings were found, and `1` indicates a validation failure, unexpected path, missing file, or that duplicates were detected.
    """
    if not manifest_path.exists():
        print(f"Error: {manifest_path} not found", file=sys.stderr)
        return 1

    # Read the manifest
    repo_root = Path(__file__).resolve().parents[1]
    expected_manifest_path = (repo_root / ".elastic-copilot/memory/systemManifest.md").resolve()
    manifest_path = manifest_path.resolve()

    # Ensure we only ever read the expected manifest file within the repo.
    if manifest_path != expected_manifest_path:
        print(
            (f"Error: Refusing to read unexpected manifest path: {manifest_path}"),
            file=sys.stderr,
        )
        return 1

    lines = manifest_path.read_text(encoding="utf-8").splitlines(keepends=True)

    heading_occurrences = _collect_headings(lines)
    duplicates = {heading: nums for heading, nums in heading_occurrences.items() if len(nums) > 1}

    if duplicates:
        return _report_duplicates(duplicates, manifest_path)

    print(f"✅ No duplicate headings found in {manifest_path}")
    print(f"   Total sections: {len(heading_occurrences)}")
    return 0


def main():
    """Main entry point for the validation script."""
    manifest_path = Path(".elastic-copilot/memory/systemManifest.md")
    exit_code = check_duplicate_headings(manifest_path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
