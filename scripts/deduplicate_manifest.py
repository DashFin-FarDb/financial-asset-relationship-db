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


def safe_path(user_value: str, base_dir: Path) -> Path:
    # Basic input hardening (avoid multiline / NUL path tricks)
    if "\x00" in user_value or "\n" in user_value or "\r" in user_value:
        raise ValueError("Invalid path characters")

    p = Path(user_value)

    # Reject absolute paths outright
    if p.is_absolute():
        raise ValueError("Absolute paths are not allowed")

    # Resolve against base_dir and normalize
    base = base_dir.resolve()
    resolved = (base / p).resolve()

    # Enforce "must be inside base"
    # (use commonpath on strings for broad compatibility)
    if os.path.commonpath([str(base), str(resolved)]) != str(base):
        raise ValueError("Path escapes allowed base directory")

    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default=".elastic-copilot/memory/systemManifest.md",
        help="Path to the manifest file (relative to the repository root)",
    )
    args = parser.parse_args()

    repo_root = Path.cwd()  # or set explicitly if you know it

    try:
        manifest_path = safe_path(args.path, repo_root)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if not manifest_path.exists():
        print(f"Error: {manifest_path} not found", file=sys.stderr)
        return 1

    # ... proceed with read/parse/dedup/write ...
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
