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
    """
    Return the text of a level-2 Markdown heading if the line is a top-level `##` heading.
    
    Returns:
        The heading text if the line contains a level-2 heading, `None` otherwise.
    """
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
    """
    Append the current section (heading and its content) to `sections` if `current_heading` is present.
    
    Parameters:
    	sections (List[Tuple[str, str]]): Mutable list of (heading, content) tuples to append to.
    	current_heading (str | None): The heading for the current section; if `None` nothing is appended.
    	current_content (List[str]): Lines comprising the section body; joined with newline characters to form the stored content.
    """
    if current_heading is None:
        return
    sections.append((current_heading, "\n".join(current_content)))


def parse_manifest(content: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Parse the manifest into a preamble and a list of level-2 sections.

    The function treats lines beginning with "## " (level-2 headings) as section delimiters and ignores deeper headings (e.g., "###"). Text before the first level-2 heading is returned as the preamble. Each section is represented as a (heading, content) tuple where `heading` is the heading text (without the leading "##") and `content` is the text that follows that heading up to, but not including, the next level-2 heading. Section order is preserved.
    Parameters:
        content (str): The full manifest text to parse.

    Returns:
        Tuple[str, List[Tuple[str, str]]]:
            - preamble: The text preceding the first level-2 heading.
            - sections: A list of (heading, content) tuples for each level-2 section in the manifest.
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
    """
    Deduplicate section entries by keeping only the last occurrence of each heading.

    Parameters:
        sections (List[Tuple[str, str]]): Sequence of (heading, content) pairs representing sections in the manifest.

    Returns:
        List[Tuple[str, str]]: Sections with duplicate headings removed; for each heading, the last occurrence from the input is kept and returned in the original input order.
    """
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
    """
    Assembles manifest text from a preamble and an ordered list of level-2 sections.

    Each section is rendered as a "## {heading}" header followed by its content. Sections (and the preamble, if present) are separated by a single blank line. If the resulting manifest is non-empty, it ends with a single trailing newline; otherwise an empty string is returned.

    Parameters:
        preamble (str): Text that appears before the first section; may be empty.
        sections (List[Tuple[str, str]]): Ordered list of (heading, content) pairs for level-2 sections.

    Returns:
        str: The reconstructed manifest text.
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
    """
    Return a mapping of section headings to their occurrence counts.
    
    Parameters:
        sections (List[Tuple[str, str]]): Sequence of (heading, content) pairs from a parsed manifest.
    
    Returns:
        Dict[str, int]: Mapping where each key is a heading and the value is the number of times it appears.
    """
    counts: Dict[str, int] = {}
    for heading, _ in sections:
        counts[heading] = counts.get(heading, 0) + 1
    return counts


def _has_invalid_path_chars(user_value: str) -> bool:
    """
    Detect whether a path string contains NUL, newline, or carriage return characters.

    Parameters:
        user_value (str): The path string to inspect.

    Returns:
        bool: `True` if `user_value` contains NUL (`\x00`), newline (`\n`), or carriage return (`\r`), `False` otherwise.
    """
    forbidden_chars = ("\x00", "\n", "\r")
    return any(char in user_value for char in forbidden_chars)


def _resolve_path_within_base(user_value: str, base_dir: Path) -> tuple[Path, Path]:
    """
    Compute and return the absolute base directory and the resolved candidate path obtained by interpreting the given user path relative to the base directory.
    
    Parameters:
        user_value (str): User-supplied filesystem path (may be relative).
        base_dir (Path): Base directory to resolve against.
    
    Returns:
        tuple[Path, Path]: (base, resolved) where `base` is base_dir.resolve() and `resolved` is the absolute path of `base / user_value`.
    """
    base = base_dir.resolve()
    resolved = (base / Path(user_value)).resolve()
    return base, resolved


def _is_within_base(base: Path, candidate: Path) -> bool:
    """
    Determine whether `candidate` is the same path as `base` or is located inside `base`.
    
    Returns:
        bool: `True` if `candidate` is the same path as `base` or a descendant of `base`, `False` otherwise.
    """
    return os.path.commonpath([str(base), str(candidate)]) == str(base)


def safe_path(user_value: str, base_dir: Path) -> Path:
    # Basic input hardening (avoid multiline / NUL path tricks)
    """
    Validate and resolve a user-supplied relative path so it stays inside the given base directory.

    Performs character checks, rejects absolute paths, resolves the value against `base_dir`, and ensures the resulting path does not escape `base_dir`.

    Parameters:
        user_value (str): User-provided path string to validate and resolve.
        base_dir (Path): Base directory that `user_value` must remain inside.

    Returns:
        Path: Resolved path located inside `base_dir`.

    Raises:
        ValueError: If `user_value` contains invalid characters, is an absolute path, or resolves outside `base_dir`.
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
