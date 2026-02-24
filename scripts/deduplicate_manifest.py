#!/usr/bin/env python3
"""
Deduplicate sections in .elastic-copilot/memory/systemManifest.md.

This script removes duplicate section headings (## level 2 headings) from the
manifest file, keeping only the LAST occurrence of each section. This ensures
the manifest contains only the most recent version of each section.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def parse_manifest(content: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Parse the manifest content into preamble and sections.

    Args:
        content: The full content of the manifest file

    Returns:
        A tuple of (preamble, sections) where:
        - preamble is content before the first ## heading (e.g., "# System Manifest")
        - sections is a list of (heading, content) tuples, where heading is the section title
          (without the ## prefix) and content is everything between this heading
          and the next ## heading
    """
    lines = content.split("\n")

    preamble_lines: List[str] = []
    sections: List[Tuple[str, str]] = []
    current_heading: str | None = None
    current_content: List[str] = []
    found_first_heading = False

    for line in lines:
        # Check if this is a level 2 heading (## but not ###)
        if re.match(r"^## [^#]", line):
            if not found_first_heading:
                found_first_heading = True
            else:
                # Save previous section if exists
                sections.append((current_heading, "\n".join(current_content)))  # type: ignore[arg-type]
            # Start new section
            current_heading = line[3:].strip()  # Remove "## " prefix
            current_content = []
        else:
            if not found_first_heading:
                preamble_lines.append(line)
            else:
                current_content.append(line)

    # Add the last section if present
    if found_first_heading and current_heading is not None:
        sections.append((current_heading, "\n".join(current_content)))

    preamble = "\n".join(preamble_lines)
    return preamble, sections


def deduplicate_sections(sections: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Remove duplicate sections, keeping only the LAST occurrence of each.

    Args:
        sections: List of (heading, content) tuples

    Returns:
        Deduplicated list with only the last occurrence of each heading
    """
    # Use a dictionary to track the last occurrence of each heading
    section_dict: Dict[str, str] = {}
    section_order: List[str] = []

    for heading, content in sections:
        if heading not in section_dict:
            section_order.append(heading)
        section_dict[heading] = content

    # Reconstruct sections in the order of their last appearance
    deduplicated: List[Tuple[str, str]] = []
    for heading in section_order:
        deduplicated.append((heading, section_dict[heading]))

    return deduplicated


def reconstruct_manifest(sections: List[Tuple[str, str]]) -> str:
    """
    Reconstruct the manifest content from sections.

    Args:
        sections: List of (heading, content) tuples

    Returns:
        The reconstructed manifest content as a string
    """
    PREAMBLE_HEADING = "__PREAMBLE__"
    result = []

    for heading, content in sections:
        if heading == PREAMBLE_HEADING:
            # Emit preamble as-is (no "##" heading)
            if content:
                result.append(content)
            continue

        result.append(f"## {heading}")
        result.append(content)

    return "\n".join(result)


def main():
    """Main entry point for the deduplication script."""
    manifest_path = Path(".elastic-copilot/memory/systemManifest.md")

    if not manifest_path.exists():
        print(f"Error: {manifest_path} not found", file=sys.stderr)
        sys.exit(1)

    # Read the manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse into preamble and sections
    preamble, sections = parse_manifest(content)


def reconstruct_manifest(preamble: str, sections: List[Tuple[str, str]]) -> str:
    """
    Reconstruct the manifest content from a preamble and list of sections.

    Args:
        preamble: Content before the first ## heading.
        sections: List of (heading, content) tuples.

    Returns:
        The full manifest content as a single string.
    """
    parts: List[str] = []

    if preamble:
        parts.append(preamble.rstrip())

    for heading, content in sections:
        # Add a blank line before each section if there is already content
        if parts:
            parts.append("")
        parts.append(f"## {heading}")
        if content:
            parts.append(content.rstrip())

    return "\n".join(parts) + ("\n" if parts else "")

    print(f"Found {len(sections)} total sections")
    if preamble.strip():
        print(f"Preserved preamble content ({len(preamble.split(chr(10)))} lines)")

    # Count duplicates
    heading_counts: Dict[str, int] = {}
    for heading, _ in sections:
        heading_counts[heading] = heading_counts.get(heading, 0) + 1

    duplicates = {h: c for h, c in heading_counts.items() if c > 1}
    if duplicates:
        print(f"\nFound {len(duplicates)} section(s) with duplicates:")
        for heading, count in sorted(duplicates.items()):
            print(f"  - '{heading}': {count} occurrences")
    else:
        print("\nNo duplicates found!")
        return

    # Deduplicate
    deduplicated = deduplicate_sections(sections)

    print(f"\nAfter deduplication: {len(deduplicated)} sections")

    # Reconstruct manifest
    new_content = reconstruct_manifest(preamble, deduplicated)

    # Save backup
    backup_path = manifest_path.with_suffix(".md.backup")
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\nBackup saved to: {backup_path}")

    # Write deduplicated version
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Deduplicated manifest saved to: {manifest_path}")

    # Calculate size reduction
    old_lines = len(content.split("\n"))
    new_lines = len(new_content.split("\n"))
    reduction = old_lines - new_lines
    reduction_pct = (reduction / old_lines * 100) if old_lines > 0 else 0

    print(
        f"\nSize reduction: {old_lines} → {new_lines} lines ({reduction_pct:.1f}% reduction)"
    )


if __name__ == "__main__":
    main()
