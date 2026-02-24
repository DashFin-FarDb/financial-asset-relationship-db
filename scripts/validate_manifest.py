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


def check_duplicate_headings(manifest_path: Path) -> int:
    """
    Check for duplicate level 2 headings in the manifest.

    Args:
        manifest_path: Path to the systemManifest.md file

    Returns:
        Exit code: 0 if no duplicates, 1 if duplicates found
    """
    if not manifest_path.exists():
        print(f"Error: {manifest_path} not found", file=sys.stderr)
        return 1

    # Read the manifest
    repo_root = Path(__file__).resolve().parents[1]
    expected_manifest_path = (
        repo_root / ".elastic-copilot/memory/systemManifest.md"
    ).resolve()
    manifest_path = manifest_path.resolve()

    # Ensure we only ever read the expected manifest file within the repo.
    if manifest_path != expected_manifest_path:
        print(
            f"Error: Refusing to read unexpected manifest path: {manifest_path}",
            file=sys.stderr,
        )
        return 1

    lines = manifest_path.read_text(encoding="utf-8").splitlines(keepends=True)
    # (already read with read_text above; remove this line)

    # Track headings and their line numbers
    heading_occurrences: Dict[str, List[int]] = {}

    for line_num, line in enumerate(lines, start=1):
        # Check for level 2 headings (## but not ###)
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            heading = stripped[3:].strip()
            if heading not in heading_occurrences:
                heading_occurrences[heading] = []
            heading_occurrences[heading].append(line_num)

    # Find duplicates
    duplicates = {
        h: lines for h, lines in heading_occurrences.items() if len(lines) > 1
    }

    if duplicates:
        print(
            "❌ MD024 violation: Duplicate headings found in systemManifest.md\n",
            file=sys.stderr,
        )
        print(f"Found {len(duplicates)} heading(s) with duplicates:\n", file=sys.stderr)

        for heading, line_nums in sorted(duplicates.items()):
            print(f"  '{heading}' appears {len(line_nums)} times:", file=sys.stderr)
            for line_num in line_nums:
                print(f"    - Line {line_num}", file=sys.stderr)
            print(file=sys.stderr)

        print(
            "Run 'python scripts/deduplicate_manifest.py' to fix these issues.",
            file=sys.stderr,
        )
        return 1
    else:
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
