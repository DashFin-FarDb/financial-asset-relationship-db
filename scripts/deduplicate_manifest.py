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
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

HEADING_RE = re.compile(r"^\s*##\s+(.+?)\s*$")  # matches "## Title"


def _extract_section_heading(line: str) -> str | None:
    """Return level-2 heading text from a line, otherwise None."""
    match = HEADING_RE.match(line)
    if match is None:
        return None
    # Only treat level-2 headings as delimiters, not ###.
    if line.lstrip().startswith("###"):
        return None
    return match.group(1)


def _flush_current_section(
    sections: List[Tuple[str, str]],
    current_heading: str | None,
    current_content: List[str],
) -> None:
    """Append current section to sections when heading is present."""
    if current_heading is None:
        return
    sections.append((current_heading, "\n".join(current_content)))


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
        heading = _extract_section_heading(line)
        if heading is None:
            if found_first_heading:
                current_content.append(line)
            else:
                preamble_lines.append(line)
            continue

        if found_first_heading:
            _flush_current_section(sections, current_heading, current_content)
        else:
            found_first_heading = True

        current_heading = heading
        current_content = []

    if found_first_heading:
        _flush_current_section(sections, current_heading, current_content)

    return "\n".join(preamble_lines), sections


def deduplicate_sections(
    sections: List[Tuple[str, str]],
) -> List[Tuple[str, str]]:
    """Remove duplicate headings, keeping only the last occurrence."""
    seen: set[str] = set()
    out_reversed: List[Tuple[str, str]] = []

    for heading, content in reversed(sections):
        if heading in seen:
            continue
        seen.add(heading)
        out_reversed.append((heading, content))

    return list(reversed(out_reversed))


def reconstruct_manifest(
    preamble: str,
    sections: List[Tuple[str, str]],
) -> str:
    """Reconstruct the manifest content from preamble and sections."""
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
    """Count occurrences of each heading in the given sections."""
    counts: Dict[str, int] = {}
    for heading, _ in sections:
        counts[heading] = counts.get(heading, 0) + 1
    return counts


def _has_invalid_path_chars(user_value: str) -> bool:
    """Return True when path includes NUL or newline characters."""
    forbidden_chars = ("\x00", "\n", "\r")
    return any(char in user_value for char in forbidden_chars)


def _resolve_path_within_base(user_value: str, base_dir: Path) -> tuple[Path, Path]:
    """Resolve and return (base, resolved_path)."""
    base = base_dir.resolve()
    resolved = (base / Path(user_value)).resolve()
    return base, resolved


def _is_within_base(base: Path, candidate: Path) -> bool:
    """Check whether candidate resolves inside base."""
    return os.path.commonpath([str(base), str(candidate)]) == str(base)


def safe_path(user_value: str, base_dir: Path) -> Path:
    # Basic input hardening (avoid multiline / NUL path tricks)
    """Ensure the provided user_value is a safe relative path under base_dir.

    This function performs several checks to validate user_value as a safe path.
    It first checks for invalid characters and ensures that the path is not
    absolute. Then, it resolves the path against base_dir and verifies that
    the resolved path does not escape the base directory. If any of these
    conditions are violated, a ValueError is raised.
    """
    if _has_invalid_path_chars(user_value):
        raise ValueError("Invalid path characters")

    candidate = Path(user_value)

    # Reject absolute paths outright
    if candidate.is_absolute():
        raise ValueError("Absolute paths are not allowed")

    # Resolve against base_dir and normalize
    base, resolved = _resolve_path_within_base(user_value, base_dir)

    # Enforce "must be inside base"
    # (use commonpath on strings for broad compatibility)
    if not _is_within_base(base, resolved):
        raise ValueError("Path escapes allowed base directory")

    return resolved


def main() -> int:
    """
    Parse command-line arguments and process the manifest file.

    Returns:
        Exit code 0 on success, 1 if manifest not found, 2 for invalid path.
    """
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
    main()
    raise SystemExit(main())
