#!/usr/bin/env python3
"""
Deduplicate sections in .elastic-copilot/memory/systemManifest.md.

This script removes duplicate section headings (## level 2 headings) from the
manifest file, keeping only the LAST occurrence of each section (including the
position of that last occurrence). This ensures the manifest contains only the
most recent version of each section.

Verbose mode behavior:
- Prints counts and duplicate summary
- Saves a backup file alongside the manifest
- Prints size reduction stats
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


HEADING_RE = re.compile(r"^\s*##\s+(.+?)\s*$")  # matches "## Title"


def parse_manifest(content: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Parse the manifest content into preamble and sections.

    Returns:
      (preamble, sections)
        - preamble: content before the first ## heading
        - sections: list of (heading, content) where content is the text between
          this heading and the next ## heading
    """
    lines = content.splitlines()

    preamble_lines: List[str] = []
    sections: List[Tuple[str, str]] = []

    current_heading: str | None = None
    current_content: List[str] = []
    found_first_heading = False

    for line in lines:
        m = HEADING_RE.match(line)
        # Treat only level-2 headings as section delimiters, not ###.
        if m and not line.lstrip().startswith("###"):
            if not found_first_heading:
                found_first_heading = True
            else:
                assert current_heading is not None
                sections.append((current_heading, "\n".join(current_content)))
            current_heading = m.group(1)
            current_content = []
        else:
            if not found_first_heading:
                preamble_lines.append(line)
            else:
                current_content.append(line)

    if found_first_heading and current_heading is not None:
        sections.append((current_heading, "\n".join(current_content)))

    return "\n".join(preamble_lines), sections


def deduplicate_sections(sections: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Remove duplicate headings, keeping only the LAST occurrence of each heading,
    and preserving the order of those last occurrences.
    """
    seen: set[str] = set()
    out_reversed: List[Tuple[str, str]] = []

    for heading, content in reversed(sections):
        if heading in seen:
            continue
        seen.add(heading)
        out_reversed.append((heading, content))

    return list(reversed(out_reversed))


def reconstruct_manifest(preamble: str, sections: List[Tuple[str, str]]) -> str:
    """
    Reconstruct the manifest content from preamble and sections.
    """
    parts: List[str] = []

    if preamble:
        parts.append(preamble.rstrip())

    for heading, content in sections:
        if parts:
            parts.append("")
        parts.append(f"## {heading}")
        if content:
            parts.append(content.rstrip())

    return "\n".join(parts) + ("\n" if parts else "")


def count_duplicates(sections: List[Tuple[str, str]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for heading, _ in sections:
        counts[heading] = counts.get(heading, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deduplicate ## sections in .elastic-copilot/memory/systemManifest.md"
    )
    parser.add_argument(
        "--path",
        default=".elastic-copilot/memory/systemManifest.md",
        help="Path to the manifest file",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not write a .backup file before overwriting the manifest",
    )
    args = parser.parse_args()

    manifest_path = Path(args.path)

    if not manifest_path.exists():
        print(f"Error: {manifest_path} not found", file=sys.stderr)
        return 1

    content = manifest_path.read_text(encoding="utf-8")

    preamble, sections = parse_manifest(content)
    total_sections = len(sections)

    print(f"Found {total_sections} total section(s).")
    if preamble.strip():
        pre_lines = len(preamble.splitlines())
        print(f"Preserved preamble content ({pre_lines} line(s)).")
    else:
        print("No preamble content found (file starts with a section heading).")

    heading_counts = count_duplicates(sections)
    duplicates = {h: c for h, c in heading_counts.items() if c > 1}

    if not duplicates:
        print("No duplicate section headings found. No changes made.")
        return 0

    print(f"Found {len(duplicates)} section heading(s) with duplicates:")
    for heading, count in sorted(duplicates.items(), key=lambda x: x[0].lower()):
        print(f"  - {heading!r}: {count} occurrence(s)")

    deduped_sections = deduplicate_sections(sections)
    print(f"After deduplication: {len(deduped_sections)} section(s).")

    new_content = reconstruct_manifest(preamble, deduped_sections)

    if new_content == content:
        print("Resulting content is identical. No changes made.")
        return 0

    if not args.no_backup:
        backup_path = manifest_path.with_suffix(manifest_path.suffix + ".backup")
        backup_path.write_text(content, encoding="utf-8")
        print(f"Backup saved to: {backup_path}")

    manifest_path.write_text(new_content, encoding="utf-8")
    print(f"Deduplicated manifest saved to: {manifest_path}")

    old_lines = len(content.splitlines())
    new_lines = len(new_content.splitlines())
    reduction = old_lines - new_lines
    reduction_pct = (reduction / old_lines * 100.0) if old_lines > 0 else 0.0
    print(f"Size reduction: {old_lines} → {new_lines} lines ({reduction_pct:.1f}% reduction).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
